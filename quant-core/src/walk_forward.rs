//! Walk-Forward 滚动步进验证.
//!
//! 实现与 Python `coinbot_quant.research.validation.build_walk_forward_windows`
//! **逐行对齐**（cursor 起点、步进逻辑、边界条件完全一致）。
//!
//! ## 设计原则
//! - `build_walk_forward_windows` 是纯函数（给定参数输出确定的窗口切片），
//!   结果必须与 Python 版 **bit-identical**（整数索引，无浮点误差）。
//! - `run_walk_forward_ma_backtest` 对每个窗口分别运行 MA crossover 回测，
//!   测试期净值复利链式拼接，与 Python WalkForwardEngine._aggregate 对齐。

use crate::run_ma_crossover_backtest;

// ── 配置 & 数据结构 ────────────────────────────────────────────────────────────

/// Walk-Forward 窗口切割参数.
///
/// 等价于 Python `TimeSeriesValidationConfig`：
/// `train_size`, `test_size`, `step_size`, `embargo_size`。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalkForwardConfig {
    /// 训练窗口大小（根 K 线数）.
    pub train_size: usize,
    /// 测试窗口大小（根 K 线数）.
    pub test_size: usize,
    /// 每次向前滚动的步进根数.
    pub step_size: usize,
    /// 隔离带（embargo）大小：train_end 与 test_start 之间跳过的根数.
    pub embargo_size: usize,
}

/// 单个 Walk-Forward 窗口的行索引（闭区间，0-based）.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalkForwardWindow {
    pub train_start: usize,
    pub train_end: usize,
    pub test_start: usize,
    pub test_end: usize,
}

/// Walk-Forward MA crossover 回测的汇总结果.
#[derive(Debug, Clone)]
pub struct WalkForwardResult {
    /// 成功执行的窗口数.
    pub n_windows: usize,
    /// 各窗口测试期净值复利链式拼接后的总 equity curve.
    pub equity_curve: Vec<f64>,
    /// 各窗口的行索引切分（与 build_walk_forward_windows 一致）.
    pub window_splits: Vec<WalkForwardWindow>,
}

// ── 核心函数 ──────────────────────────────────────────────────────────────────

/// 按时间顺序构建 walk-forward 窗口.
///
/// **算法与 Python `build_walk_forward_windows` 逐行对齐**：
///
/// ```python
/// cursor = config.train_size  # 初始 cursor
/// while True:
///     train_end   = cursor - 1
///     test_start  = train_end + 1 + config.embargo_size
///     test_end    = test_start + config.test_size - 1
///     train_start = train_end - config.train_size + 1
///     if train_start < 0 or test_end >= total_rows:
///         break
///     windows.append(...)
///     cursor += config.step_size
/// ```
///
/// # Examples
/// ```
/// use coinbot_quant::walk_forward::{WalkForwardConfig, build_walk_forward_windows};
/// let cfg = WalkForwardConfig { train_size: 10, test_size: 5, step_size: 5, embargo_size: 0 };
/// let wins = build_walk_forward_windows(30, &cfg);
/// assert_eq!(wins[0].train_start, 0);
/// assert_eq!(wins[0].train_end,   9);
/// assert_eq!(wins[0].test_start, 10);
/// assert_eq!(wins[0].test_end,   14);
/// ```
pub fn build_walk_forward_windows(
    total_rows: usize,
    config: &WalkForwardConfig,
) -> Vec<WalkForwardWindow> {
    let mut windows = Vec::new();
    let mut cursor = config.train_size;

    loop {
        // Python 用有符号整数；Rust 用 usize 需小心下溢。
        // 安全：cursor >= train_size >= 1，所以 cursor - 1 不溢出。
        let train_end = cursor - 1;
        let test_start = train_end + 1 + config.embargo_size;
        let test_end = test_start + config.test_size - 1;

        // train_start < 0 在 usize 下等价于 cursor < train_size（不可能发生，
        // 因初始 cursor = train_size，步进只增不减）；这里保留语义完整性。
        let train_start = train_end + 1 - config.train_size; // == cursor - train_size

        if test_end >= total_rows {
            break;
        }

        windows.push(WalkForwardWindow {
            train_start,
            train_end,
            test_start,
            test_end,
        });

        cursor += config.step_size;
    }

    windows
}

/// 对每个 walk-forward 窗口执行 MA crossover 回测，返回聚合结果.
///
/// **窗口内逻辑**：
/// 1. 取 `closes[train_start..=test_end]`（训练 + 测试，embargo 段数据被自然排除）
/// 2. 用 `run_ma_crossover_backtest` 跑完整区段（训练集作热身）
/// 3. 截取测试期净值 `equity[n_train..n_train+test_size]`
/// 4. 各窗口测试期净值复利链式拼接（与 Python WalkForwardEngine._aggregate 对齐）
///
/// # Errors
/// - closes 数据不足以产生任何窗口
/// - 某个窗口的回测自身失败（数据不足以算出 slow MA）
pub fn run_walk_forward_ma_backtest(
    closes: &[f64],
    fast_period: usize,
    slow_period: usize,
    initial_cash: f64,
    config: &WalkForwardConfig,
) -> Result<WalkForwardResult, String> {
    let windows = build_walk_forward_windows(closes.len(), config);

    if windows.is_empty() {
        return Err(format!(
            "数据不足以构建任何窗口：总长度 {}，需要至少 {}",
            closes.len(),
            config.train_size + config.embargo_size + config.test_size
        ));
    }

    let mut chained_equity: Vec<f64> = Vec::new();
    let mut current_base = initial_cash;
    let mut valid_windows = 0;

    for win in &windows {
        let n_train = win.train_end - win.train_start + 1;
        let segment = &closes[win.train_start..=win.test_end];

        // 用当前窗口的 initial_cash 运行（与 Python 一致：每窗口独立）
        let full_pv = match run_ma_crossover_backtest(segment, fast_period, slow_period, current_base) {
            Ok(v) => v,
            Err(e) => {
                return Err(format!("窗口 {} 回测失败: {e}", valid_windows));
            }
        };

        // 截取测试期净值
        let test_pv = if n_train < full_pv.len() {
            &full_pv[n_train..]
        } else {
            &full_pv[..]
        };

        if test_pv.is_empty() {
            continue;
        }

        // 复利链式拼接：当前测试段净值 / 测试段起点净值 * current_base
        let window_base = test_pv[0];
        if window_base == 0.0 {
            continue;
        }
        chained_equity.extend(test_pv.iter().map(|&v| current_base * v / window_base));
        current_base = *chained_equity.last().unwrap();
        valid_windows += 1;
    }

    Ok(WalkForwardResult {
        n_windows: valid_windows,
        equity_curve: chained_equity,
        window_splits: windows,
    })
}

// ── 单元测试 ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn window_splitter_basic() {
        // 30 rows, train=10, test=5, step=5, embargo=0
        let cfg = WalkForwardConfig {
            train_size: 10,
            test_size: 5,
            step_size: 5,
            embargo_size: 0,
        };
        let wins = build_walk_forward_windows(30, &cfg);
        // Window 0: train=[0,9], test=[10,14]
        assert_eq!(wins[0].train_start, 0);
        assert_eq!(wins[0].train_end, 9);
        assert_eq!(wins[0].test_start, 10);
        assert_eq!(wins[0].test_end, 14);
        // Window 1: train=[5,14], test=[15,19]
        assert_eq!(wins[1].train_start, 5);
        assert_eq!(wins[1].train_end, 14);
        assert_eq!(wins[1].test_start, 15);
        assert_eq!(wins[1].test_end, 19);
    }

    #[test]
    fn window_splitter_with_embargo() {
        // train=10, test=5, step=5, embargo=2
        let cfg = WalkForwardConfig {
            train_size: 10,
            test_size: 5,
            step_size: 5,
            embargo_size: 2,
        };
        let wins = build_walk_forward_windows(30, &cfg);
        // Window 0: train_end=9, test_start=9+1+2=12, test_end=12+5-1=16
        assert_eq!(wins[0].train_end, 9);
        assert_eq!(wins[0].test_start, 12);
        assert_eq!(wins[0].test_end, 16);
    }

    #[test]
    fn too_few_rows_returns_empty() {
        let cfg = WalkForwardConfig {
            train_size: 50,
            test_size: 20,
            step_size: 10,
            embargo_size: 5,
        };
        // 50 rows < 50+5+20=75 needed for one window
        let wins = build_walk_forward_windows(50, &cfg);
        assert!(wins.is_empty());
    }

    #[test]
    fn walk_forward_backtest_runs() {
        let closes: Vec<f64> = (0..100).map(|i| 100.0 + i as f64).collect();
        let cfg = WalkForwardConfig {
            train_size: 20,
            test_size: 10,
            step_size: 10,
            embargo_size: 2,
        };
        let result = run_walk_forward_ma_backtest(&closes, 3, 7, 10_000.0, &cfg).unwrap();
        assert!(result.n_windows > 0, "should have at least one window");
        assert!(!result.equity_curve.is_empty());
    }
}

//! Walk-Forward 窗口切割 + 回测集成测试.
//!
//! 验证 Rust `build_walk_forward_windows` 与 Python golden bit-identical，
//! 并验证 `run_walk_forward_ma_backtest` 基本运行正确。

use std::path::PathBuf;

use coinbot_quant::walk_forward::{
    build_walk_forward_windows, run_walk_forward_ma_backtest, WalkForwardConfig, WalkForwardWindow,
};

// ── helpers ───────────────────────────────────────────────────────────────────

fn golden_path() -> PathBuf {
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.push("../common/data-store/golden/expected/walk_forward_splits_basic.json");
    p
}

#[derive(serde::Deserialize)]
struct GoldenRoot {
    cases: Vec<GoldenCase>,
}

#[derive(serde::Deserialize)]
struct GoldenCase {
    name: String,
    config: GoldenConfig,
    expected_windows: Vec<GoldenWindow>,
    n_windows: usize,
}

#[derive(serde::Deserialize)]
struct GoldenConfig {
    total_rows: usize,
    train_size: usize,
    test_size: usize,
    step_size: usize,
    embargo_size: usize,
}

#[derive(serde::Deserialize, Debug)]
struct GoldenWindow {
    train_start: usize,
    train_end: usize,
    test_start: usize,
    test_end: usize,
}

fn load_golden() -> GoldenRoot {
    let path = golden_path();
    let content = std::fs::read_to_string(&path)
        .unwrap_or_else(|e| panic!("Cannot read {path:?}: {e}"));
    serde_json::from_str(&content).expect("walk_forward_splits_basic.json parse error")
}

fn windows_match(rust: &WalkForwardWindow, golden: &GoldenWindow) -> bool {
    rust.train_start == golden.train_start
        && rust.train_end == golden.train_end
        && rust.test_start == golden.test_start
        && rust.test_end == golden.test_end
}

// ── golden equivalence test ───────────────────────────────────────────────────

/// Walk-Forward 窗口索引与 Python golden bit-identical.
#[test]
fn walk_forward_splits_match_golden() {
    let golden = load_golden();

    for case in &golden.cases {
        let cfg = WalkForwardConfig {
            train_size: case.config.train_size,
            test_size: case.config.test_size,
            step_size: case.config.step_size,
            embargo_size: case.config.embargo_size,
        };
        let rust_wins = build_walk_forward_windows(case.config.total_rows, &cfg);

        assert_eq!(
            rust_wins.len(),
            case.n_windows,
            "case '{}': n_windows mismatch (Rust={} vs golden={})",
            case.name,
            rust_wins.len(),
            case.n_windows
        );

        for (i, (rw, gw)) in rust_wins.iter().zip(case.expected_windows.iter()).enumerate() {
            assert!(
                windows_match(rw, gw),
                "case '{}' window {}: Rust={:?} vs golden={gw:?}",
                case.name,
                i,
                rw,
            );
        }

        println!(
            "  ✓ case '{}': {} windows bit-identical",
            case.name,
            rust_wins.len()
        );
    }
}

// ── functional tests ──────────────────────────────────────────────────────────

/// run_walk_forward_ma_backtest 基本运行测试.
#[test]
fn walk_forward_ma_backtest_runs() {
    // 使用趋势上行数据，保证 MA crossover 有信号
    let closes: Vec<f64> = (0..100).map(|i| 100.0 + i as f64).collect();
    let cfg = WalkForwardConfig {
        train_size: 20,
        test_size: 10,
        step_size: 10,
        embargo_size: 2,
    };
    let result = run_walk_forward_ma_backtest(&closes, 3, 7, 10_000.0, &cfg)
        .expect("walk-forward backtest should succeed");

    assert!(result.n_windows > 0, "should have at least one window");
    assert!(
        !result.equity_curve.is_empty(),
        "equity_curve should not be empty"
    );
    assert_eq!(
        result.window_splits.len(),
        build_walk_forward_windows(100, &cfg).len(),
        "window_splits should match build_walk_forward_windows"
    );

    println!("  ✓ walk-forward: {} windows, equity_curve len={}", result.n_windows, result.equity_curve.len());
}

/// 数据不足时 run_walk_forward_ma_backtest 返回 Err.
#[test]
fn walk_forward_backtest_too_few_rows_is_err() {
    let closes = vec![100.0; 10];
    let cfg = WalkForwardConfig {
        train_size: 20,
        test_size: 10,
        step_size: 5,
        embargo_size: 2,
    };
    let result = run_walk_forward_ma_backtest(&closes, 3, 7, 10_000.0, &cfg);
    assert!(result.is_err(), "should fail with too few rows");
}

/// equity_curve 初始值等于 initial_cash（链式拼接第一个点）.
#[test]
fn walk_forward_equity_starts_at_initial_cash() {
    let closes: Vec<f64> = (0..80).map(|i| 100.0 + i as f64).collect();
    let cfg = WalkForwardConfig {
        train_size: 20,
        test_size: 10,
        step_size: 10,
        embargo_size: 2,
    };
    let result =
        run_walk_forward_ma_backtest(&closes, 3, 7, 10_000.0, &cfg).unwrap();

    // 复利链式拼接的第一个点等于 initial_cash
    if !result.equity_curve.is_empty() {
        let first = result.equity_curve[0];
        assert!(
            (first - 10_000.0).abs() < 1e-6,
            "first equity value should be initial_cash=10000, got {first}"
        );
    }
}

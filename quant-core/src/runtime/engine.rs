//! Rhai 策略引擎封装.
//!
//! ## 用法
//! ```no_run
//! use coinbot_quant::runtime::{RhaiEngine, Signal};
//!
//! let engine = RhaiEngine::new();
//! let strategy = engine.compile_file("strategies/ma_crossover.rhai")?;
//! let signal = engine.call_signal(&strategy, 105.0, 100.0)?;
//! assert_eq!(signal, Signal::Long);
//! # Ok::<(), String>(())
//! ```

use std::path::Path;

use rhai::{Dynamic, Engine, AST};

use crate::indicators::{ema_rhai, sma_rhai};
use crate::ml_runner::MlRunner;

/// 策略信号（最简化 MVP；Phase C.x 扩 strength/reason 等）.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Signal {
    Long,
    Flat,
    Hold,
}

impl Signal {
    fn from_rhai_string(s: &str) -> Result<Self, String> {
        match s {
            "long" => Ok(Signal::Long),
            "flat" => Ok(Signal::Flat),
            "hold" => Ok(Signal::Hold),
            other => Err(format!("Rhai 策略返回未知 signal: {other}")),
        }
    }
}

/// 编译后的 Rhai 策略.
pub struct CompiledStrategy {
    ast: AST,
    name: String,
}

impl CompiledStrategy {
    pub fn name(&self) -> &str {
        &self.name
    }

    /// 暴露内部 rhai::AST（测试/高级用途）.
    pub fn ast(&self) -> &rhai::AST {
        &self.ast
    }
}

/// 将 Rhai Dynamic 值转为 f64；整数自动提升，其他类型返回 NaN.
fn dynamic_to_float(d: &Dynamic) -> f64 {
    if let Ok(f) = d.as_float() {
        f
    } else if let Ok(i) = d.as_int() {
        i as f64
    } else {
        f64::NAN
    }
}

/// Rhai 引擎封装，承载共享配置 + 注册的内置函数.
pub struct RhaiEngine {
    engine: Engine,
}

impl RhaiEngine {
    /// 创建默认配置的引擎，并注册内置指标函数.
    ///
    /// 注册的 Rhai 函数：
    /// - `sma(closes: Array, period: int) -> Array` — 简单移动平均，warmup 期为 NaN
    /// - `ema(closes: Array, period: int) -> Array` — 指数移动平均，warmup 期为 NaN
    pub fn new() -> Self {
        let mut engine = Engine::new();
        engine.set_max_expr_depths(64, 32);
        engine.set_max_call_levels(32);

        // ── 注册 sma ──────────────────────────────────────────────────────────
        engine.register_fn(
            "sma",
            |closes: rhai::Array, period: i64| -> rhai::Array {
                let v: Vec<f64> = closes.iter().map(dynamic_to_float).collect();
                sma_rhai(v, period)
                    .into_iter()
                    .map(Dynamic::from_float)
                    .collect()
            },
        );

        // ── 注册 ema ──────────────────────────────────────────────────────────
        engine.register_fn(
            "ema",
            |closes: rhai::Array, period: i64| -> rhai::Array {
                let v: Vec<f64> = closes.iter().map(dynamic_to_float).collect();
                ema_rhai(v, period)
                    .into_iter()
                    .map(Dynamic::from_float)
                    .collect()
            },
        );

        // ── 注册 ml_predict_from_dir ─────────────────────────────────────────
        // MVP：每次调用时加载模型（无缓存）；C.x 版本可改为全局 Arc<Mutex<HashMap>> 缓存。
        engine.register_fn(
            "ml_predict_from_dir",
            |model_dir: String, features: rhai::Array| -> rhai::Dynamic {
                let feat: Vec<f64> = features.iter().map(dynamic_to_float).collect();
                match MlRunner::load(std::path::Path::new(&model_dir)) {
                    Ok(runner) => match runner.predict(&feat) {
                        Ok(outputs) => {
                            let arr: rhai::Array =
                                outputs.into_iter().map(Dynamic::from_float).collect();
                            Dynamic::from(arr)
                        }
                        Err(e) => Dynamic::from(format!("ERROR:{e}")),
                    },
                    Err(e) => Dynamic::from(format!("ERROR:{e}")),
                }
            },
        );

        Self { engine }
    }

    /// 从文件编译策略.
    pub fn compile_file<P: AsRef<Path>>(&self, path: P) -> Result<CompiledStrategy, String> {
        let path = path.as_ref();
        let name = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unnamed")
            .to_string();

        let ast = self
            .engine
            .compile_file(path.to_path_buf())
            .map_err(|e| format!("Rhai compile error in {path:?}: {e}"))?;

        Ok(CompiledStrategy { ast, name })
    }

    /// 从字符串编译策略（test/inline 用途）.
    pub fn compile_str(&self, source: &str, name: &str) -> Result<CompiledStrategy, String> {
        let ast = self
            .engine
            .compile(source)
            .map_err(|e| format!("Rhai compile error in {name}: {e}"))?;
        Ok(CompiledStrategy {
            ast,
            name: name.to_string(),
        })
    }

    /// 暴露内部 rhai::Engine（测试/高级用途）.
    pub fn engine(&self) -> &rhai::Engine {
        &self.engine
    }

    /// 调 Rhai 策略的 `signal(fast, slow)` 函数，返回 Signal 枚举.
    pub fn call_signal(
        &self,
        strategy: &CompiledStrategy,
        fast: f64,
        slow: f64,
    ) -> Result<Signal, String> {
        let result: String = self
            .engine
            .call_fn(&mut rhai::Scope::new(), &strategy.ast, "signal", (fast, slow))
            .map_err(|e| format!("Rhai call_fn signal in {} failed: {e}", strategy.name))?;
        Signal::from_rhai_string(&result)
    }
}

impl Default for RhaiEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE_SCRIPT: &str = r#"
        fn signal(fast, slow) {
            if fast > slow { return "long"; }
            if fast < slow { return "flat"; }
            return "hold";
        }
    "#;

    #[test]
    fn rhai_engine_compiles_and_calls_signal() {
        let engine = RhaiEngine::new();
        let strategy = engine.compile_str(SAMPLE_SCRIPT, "test").unwrap();

        assert_eq!(engine.call_signal(&strategy, 105.0, 100.0).unwrap(), Signal::Long);
        assert_eq!(engine.call_signal(&strategy, 95.0, 100.0).unwrap(), Signal::Flat);
        assert_eq!(engine.call_signal(&strategy, 100.0, 100.0).unwrap(), Signal::Hold);
    }

    #[test]
    fn unknown_signal_returns_error() {
        let bad_script = r#"
            fn signal(fast, slow) {
                return "buy_aggressive";  // not a valid signal
            }
        "#;
        let engine = RhaiEngine::new();
        let strategy = engine.compile_str(bad_script, "bad").unwrap();
        let err = engine.call_signal(&strategy, 1.0, 0.0).unwrap_err();
        assert!(err.contains("buy_aggressive"));
    }
}

//! Strategy runtime: Rhai DSL engine + native trait registry.
//!
//! Phase C.1 起：Rhai 引擎接入。用户可在 `strategies/*.rhai` 写策略；
//! Rust 端预计算 indicators，Rhai 端做 long/flat/hold 决策。
//!
//! 后续 C.x 扩：
//! - 在 Rhai 中暴露 sma/ema 等内置 indicator 函数
//! - 富 Signal 形态（含 strength、reason）
//! - native Strategy trait registry（性能敏感场景）

pub mod engine;

pub use engine::{CompiledStrategy, RhaiEngine, Signal};

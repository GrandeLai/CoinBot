//! POST /api/walk-forward — Walk-Forward CV 端点.

use axum::{http::StatusCode, Json};

use super::ApiError;
use serde::{Deserialize, Serialize};

use crate::walk_forward::{
    run_walk_forward_ma_backtest, WalkForwardConfig, WalkForwardWindow,
};

#[derive(Deserialize)]
pub struct WalkForwardRequest {
    pub closes: Vec<f64>,
    pub fast_period: usize,
    pub slow_period: usize,
    pub initial_cash: f64,
    pub train_size: usize,
    pub test_size: usize,
    #[serde(default = "default_step")]
    pub step_size: usize,
    #[serde(default)]
    pub embargo_size: usize,
}

fn default_step() -> usize {
    1
}

#[derive(Serialize)]
pub struct WalkForwardResponse {
    pub n_windows: usize,
    pub equity_curve: Vec<f64>,
    pub window_splits: Vec<WalkForwardWindowDto>,
}

#[derive(Serialize)]
pub struct WalkForwardWindowDto {
    pub train_start: usize,
    pub train_end: usize,
    pub test_start: usize,
    pub test_end: usize,
}

impl From<WalkForwardWindow> for WalkForwardWindowDto {
    fn from(w: WalkForwardWindow) -> Self {
        WalkForwardWindowDto {
            train_start: w.train_start,
            train_end: w.train_end,
            test_start: w.test_start,
            test_end: w.test_end,
        }
    }
}

pub async fn run_walk_forward(
    Json(req): Json<WalkForwardRequest>,
) -> Result<Json<WalkForwardResponse>, ApiError> {
    let config = WalkForwardConfig {
        train_size: req.train_size,
        test_size: req.test_size,
        step_size: req.step_size,
        embargo_size: req.embargo_size,
    };

    let result = run_walk_forward_ma_backtest(
        &req.closes,
        req.fast_period,
        req.slow_period,
        req.initial_cash,
        &config,
    )
    .map_err(|e| ApiError(StatusCode::BAD_REQUEST, e))?;

    Ok(Json(WalkForwardResponse {
        n_windows: result.n_windows,
        equity_curve: result.equity_curve,
        window_splits: result.window_splits.into_iter().map(Into::into).collect(),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::to_bytes, http::Request};
    use tower::ServiceExt;

    #[tokio::test]
    async fn walk_forward_returns_windows() {
        let router = axum::Router::new()
            .route("/api/walk-forward", axum::routing::post(run_walk_forward));

        let closes: Vec<f64> = (0..50).map(|i| 100.0 + i as f64 * 0.5).collect();
        let body = serde_json::json!({
            "closes": closes,
            "fast_period": 3,
            "slow_period": 7,
            "initial_cash": 10000.0,
            "train_size": 20,
            "test_size": 10,
            "step_size": 5,
        });

        let response = router
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/api/walk-forward")
                    .header("Content-Type", "application/json")
                    .body(axum::body::Body::from(serde_json::to_string(&body).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
        let json: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
        assert!(json["n_windows"].as_u64().unwrap() > 0);
        assert!(json["equity_curve"].is_array());
        assert!(json["window_splits"].is_array());
    }
}

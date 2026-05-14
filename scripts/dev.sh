#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting CoinBot Python API on http://127.0.0.1:8001"
(cd "$ROOT_DIR/backend" && uv run uvicorn coinbot_api.main:app --reload --host 127.0.0.1 --port 8001) &
API_PID=$!

echo "Starting CoinBot quant-core on http://127.0.0.1:8002"
(cd "$ROOT_DIR/quant-core" && COINBOT_QUANT_PORT=8002 cargo run --bin coinbot-quant-server) &
QUANT_PID=$!

echo "Starting CoinBot frontend on http://127.0.0.1:5173"
(cd "$ROOT_DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

trap 'kill "$API_PID" "$QUANT_PID" "$FRONTEND_PID" 2>/dev/null || true' INT TERM EXIT
wait

# Phase 0 Report: Project Inventory And Governance

## Scope

Phase 0 established governance for the 2026-05-09 crypto trading assistant refactor and inventoried the current monorepo before implementation.

## Current Project Inventory

- `backend`: existing FastAPI API package at `backend/src/coinbot_api`, including crypto market/trading API routes, derivatives analytics, advisor, whale monitoring, token unlocks, broker/security modules, and tests.
- `common/python`: shared settings, data models, storage, and OKX fetcher.
- `quant-core`: Rust axum/tokio/rhai quant service for backtest, walk-forward, optimization, indicators, reports, and ONNX surfaces.
- `frontend`: React/Vite/Tailwind crypto workbench UI.
- `docs`: design document and refactor plan area.

## Retain / Defer / Avoid

- Retain: crypto-only backend, common config/data helpers, Rust quant-core, frontend crypto surfaces, OKX credential environment contract.
- Add: isolated `backend/src/trading_assistant` package for agent-friendly CLI and local mock-first trading workflow.
- Defer: real CCXT/Binance/OKX/Bybit adapters and live execution until a separate sandbox validation phase.
- Avoid: deleting uncertain legacy modules, reintroducing stocks/equities, committing secrets, bypassing risk logic.

## External Project Research Summary

- Hummingbot: connector/strategy separation and standardized exchange connectors inspired the exchange interface/factory split.
- Freqtrade: config-driven CLI, dry-run wallet/backtesting, fee-inclusive backtesting informed the CLI/config/backtest shape.
- CCXT: unified public/private exchange abstraction is the right future adapter base, but not pulled into the offline core in this phase.
- Jesse: simple strategy developer experience, self-hosted workflow, paper/live split, and backtest metrics influenced the local-first CLI and deterministic tests.
- NautilusTrader: backtest/sandbox/live parity and strong domain model inspired separating opportunity/risk/execution models.
- TradingAgents: analyst/trader/risk role separation informed keeping risk independent from execution and avoiding LLM decision logic inside the executor.

Sources consulted:

- Hummingbot docs/connectors: https://hummingbot.org/docs/ and https://hummingbot.org/connectors/
- Freqtrade backtesting docs: https://docs.freqtrade.io/en/stable/backtesting/
- CCXT manual: https://github.com/ccxt/ccxt/wiki/manual
- Jesse docs/site: https://docs.jesse.trade/ and https://jesse.trade/
- NautilusTrader docs: https://nautilustrader.io/docs/latest/concepts/overview
- TradingAgents site/GitHub: https://tradingagents-ai.github.io/ and https://github.com/TauricResearch/TradingAgents

## Governance Files

- Updated `AGENTS.md`.
- Created `CLAUDE.md`.
- Created `docs/plan/2026-05-09-refactor/`.
- Copied spec to `docs/plan/2026-05-09-refactor/00-refactor-spec.md`.
- Created task checklist, acceptance checklist, and traceability matrix in the refactor directory.

## Verification

- `find docs/plan/2026-05-09-refactor -maxdepth 1 -type f` succeeded and showed refactor docs under the required directory.

## Status

Done.

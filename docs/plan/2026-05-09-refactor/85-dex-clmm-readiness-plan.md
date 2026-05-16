# DEX/CLMM Readiness Gate Plan

## Goal

Handle the deferred CLMM/DEX liquidity-provision item from the open-source profit-logic research without pretending CoinBot can safely provide DEX liquidity today. The immediate deliverable is a read-only readiness gate that exposes missing prerequisites and keeps execution unsupported.

## Design

Add `DexLpReadinessService` under `trading_assistant.strategies`. The service reads only `settings.dex_lp` and local filesystem evidence. It does not import wallet clients, DEX SDKs, RPC clients, or exchange adapters.

The report includes:

- `read_only=true`
- `orders_sent=false`
- `live_orders_sent=false`
- `execution_supported=false`
- prerequisite rows for DEX LP enablement, gateway URL, testnet network, wallet policy, gas model, MEV protection, testnet evidence, execution adapter, and live-order support
- reason codes for missing or deliberately unsupported prerequisites

## Tasks

- [x] Write RED unit tests for default deferred behavior and configured testnet readiness without execution support.
- [x] Write RED CLI integration and help tests for `strategy dex-lp-readiness`.
- [x] Add `DexLpConfig` with safe defaults and `COINBOT_` wallet env-name validation.
- [x] Implement `DexLpReadinessService` and JSON-safe dataclasses.
- [x] Wire `TradingAssistantApp.strategy_dex_lp_readiness`.
- [x] Wire `crypto-assistant strategy dex-lp-readiness --json`.
- [x] Update config examples, README, DESIGN, acceptance checklist, and traceability matrix.
- [x] Run focused tests, affected regression tests, ruff, mypy, and CLI smoke.
- [ ] Commit as `feat: add dex lp readiness gate`.

## Acceptance

- Default config reports `status=Deferred`, `testnet_ready=false`, and missing prerequisite reason codes.
- Fully configured testnet prerequisites can report `testnet_ready=true`, but still `execution_supported=false`.
- No wallet secrets are read.
- No DEX/RPC network calls are made.
- No orders or LP transactions are sent.

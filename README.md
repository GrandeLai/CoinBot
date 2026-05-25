# CoinBot

默认文档语言：中文。英文版本见：[README.en.md](README.en.md)。

CoinBot 是从 QuantPilot 拆出的本地优先、仅面向加密货币的量化交易与研究 monorepo。它聚焦安全的加密行情数据、OKX Demo/Live 隔离、套利与方向性策略验证、PnL 归因，以及适合本地 Agent 调用的 `crypto-assistant` CLI。

CoinBot 不是开箱即用的盈利机器。默认路径是 mock exchange、dry-run 和 paper trading；所有可能下单的路径都必须先经过安全门禁、可观测检查和风险批准，才可能触达 OKX Demo Trading 或实盘。

## 仓库内容

| 路径 | 用途 |
| --- | --- |
| `backend` | Python 3.12 FastAPI 服务，包含 crypto API、OKX 交易面、衍生品分析、研究、巨鲸流、解锁数据和 `crypto-assistant` CLI。 |
| `backend/src/trading_assistant` | 安全优先的本地交易助手包，包含配置、交易所接口、行情、套利、策略运行、验证、报告和 CLI handler。 |
| `common/python` | 共享 Python 配置、加密行情模型、DuckDB 存储和 OKX 数据抓取工具。 |
| `quant-core` | Rust axum 服务，提供回测、优化、walk-forward 验证、指标和 Rhai 策略运行时。 |
| `frontend` | React + Vite + Tailwind UI，用于 crypto assistant、OKX 交易视图、研究和 quant workbench 面板。 |
| `configs` | 本地 mock/paper、100 USDC paper validation、OKX Demo Trading 和 OKX live 隔离配置模板。 |
| `docs` | 设计文档、重构计划、阶段报告、迁移任务和验收记录。 |

## 安全模型

本仓库只支持加密货币。不要加入股票、ETF、A 股、港股、Futu 或 Longbridge 相关能力。

默认交易配置必须保持：

```yaml
trading:
  live_trading: false
  dry_run: true
  require_confirm_before_order: true
```

真实订单必须满足所有门禁：启用 live trading、关闭 dry-run、启用非 mock 交易所、从环境变量加载凭证、通过风险批准，并在需要时通过 agent/order 权限。自主实盘交易还必须满足 `agent_trading.enabled=true`、`agent_trading.allow_live_orders=true`、策略和交易所 allowlist、`COINBOT_AGENT_OPERATOR_ID`、审计日志、下单上限、执行质量批准，并且 `COINBOT_AGENT_LIVE_KILL_SWITCH` 未启用。

OKX Demo Trading 和 OKX live 使用不同配置和本地密钥文件：

| 模式 | 配置 | 本地密钥文件 | 说明 |
| --- | --- | --- | --- |
| 本地 paper/mock | `configs/config.example.yaml` | 不需要 | 开发和 Agent 默认安全配置。 |
| 100 USDC paper validation | `configs/100usdc.paper.example.yaml` | 不需要 | 小资金本地验证证据路径。 |
| OKX Demo Trading | `configs/okx.demo.example.yaml` | `.env.okx.demo` | 仅在 demo 门禁通过后允许极小 demo 订单。 |
| OKX live | `configs/okx.live.example.yaml` | `.env.okx.live` | 默认仍被 live 和 agent 门禁阻断。 |

不要提交 `.env`、`.env.okx.demo`、`.env.okx.live`、API key、secret、passphrase、token 或包含明文敏感信息的日志。

## 快速开始

分别在三个终端启动服务：

```bash
cd backend
uv run uvicorn coinbot_api.main:app --reload --host 127.0.0.1 --port 8001
```

```bash
cd quant-core
cargo run --bin coinbot-quant-server
```

```bash
cd frontend
npm install
npm run dev
```

本地地址：

| 服务 | URL |
| --- | --- |
| Frontend | `http://127.0.0.1:5173` |
| Python API | `http://127.0.0.1:8001` |
| Rust quant-core | `http://127.0.0.1:8002` |

## 第一次安全 CLI 运行

从 mock/paper 配置开始。以下命令不会发送真实订单：

```bash
cd backend
uv run crypto-assistant --help
uv run crypto-assistant config validate --config ../configs/config.example.yaml --json
uv run crypto-assistant status --json
uv run crypto-assistant exchange ping --config ../configs/config.example.yaml --exchange mock --json
uv run crypto-assistant market ticker --config ../configs/config.example.yaml --exchange mock --symbol BTC/USDT --json
```

如果 Codex 或沙盒环境不能写默认 uv cache，可以给命令加上 `UV_CACHE_DIR=.uv-cache`。

## 100 USDC Paper 验证

在任何 OKX demo 步骤前，可以先做小资金、本地-only 验证：

```bash
cd backend
uv run crypto-assistant strategy validate-local \
  --config ../configs/100usdc.paper.example.yaml \
  --strategy all \
  --cycles 1 \
  --symbol BTC/USDT \
  --json
```

再从生成的 journal 查看 paper PnL 和归因：

```bash
uv run crypto-assistant strategy validation-report \
  --config ../configs/100usdc.paper.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json

uv run crypto-assistant strategy pnl-attribution \
  --config ../configs/100usdc.paper.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json
```

paper/mock 结果是系统证据，不是市场盈利承诺。它验证策略选择、风险门禁、journal、PnL 聚合、回撤跟踪和归因链路。

## 策略工作流

策略平台分为 read-only discovery、paper validation、OKX demo sampling 和 promotion evidence。

### 只读发现

```bash
cd backend
uv run crypto-assistant strategy list --json
uv run crypto-assistant strategy catalog --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy scan --config ../configs/config.example.yaml --strategy all --symbol BTC/USDT --json
uv run crypto-assistant strategy score --config ../configs/config.example.yaml --strategy all --json
uv run crypto-assistant strategy advisory-rank --config ../configs/config.example.yaml --strategy all --execution-mode paper --window 24h --json
uv run crypto-assistant strategy dex-lp-readiness --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy portfolio-status --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy opportunity-report --config ../configs/config.example.yaml --window 24h --json
uv run crypto-assistant strategy universe --config ../configs/config.example.yaml --exchange mock --json
uv run crypto-assistant strategy regime-report --config ../configs/config.example.yaml --exchange mock --symbol BTC/USDT --json
```

三角套利路由扩展：

```bash
uv run crypto-assistant strategy discover-routes \
  --config ../configs/okx.demo.example.yaml \
  --exchange okx \
  --quote USDT \
  --json

uv run crypto-assistant strategy scan \
  --config ../configs/okx.demo.example.yaml \
  --strategy triangular-multi-route \
  --exchange okx \
  --route-mode discovered \
  --json
```

### Paper 运行

```bash
uv run crypto-assistant strategy run \
  --config ../configs/config.example.yaml \
  --strategy all \
  --max-cycles 1 \
  --interval-seconds 0 \
  --execution-mode paper \
  --json

uv run crypto-assistant strategy guard-status \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --json
```

## Autopilot 运行时

`crypto-assistant autopilot` 是脱离 Codex automation 的 paper/demo 循环，可以由 shell、cron、launchd、systemd 或其他进程管理器启动。

Paper 模式不会发送交易所订单：

```bash
cd backend
UV_CACHE_DIR=.uv-cache uv run crypto-assistant autopilot run \
  --config ../configs/config.example.yaml \
  --mode paper \
  --strategy all \
  --cycles 0 \
  --interval-seconds 60 \
  --json
```

OKX Demo 模式复用现有 demo-window 门禁，只可能发送极小 OKX Demo Trading 订单：

```bash
UV_CACHE_DIR=.uv-cache uv run crypto-assistant autopilot run \
  --config ../configs/okx.demo.example.yaml \
  --mode demo \
  --strategy triangular-multi-route \
  --cycles 0 \
  --interval-seconds 300 \
  --demo-cycles-per-window 3 \
  --target-exchange okx \
  --json
```

状态和报告是只读的：

```bash
uv run crypto-assistant autopilot status --config ../configs/config.example.yaml --json
uv run crypto-assistant autopilot report --config ../configs/config.example.yaml --mode paper --json
```

Autopilot 不会调用 `agent execute-live` 或任何 live broker。如果 paper/demo payload 报告 `live_orders_sent=true`，autopilot 会停止并持久化 `stopped_reason=live_order_detected`。

## 滚动证据

```bash
uv run crypto-assistant strategy validation-report \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json

uv run crypto-assistant strategy operator-brief \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json

uv run crypto-assistant strategy pnl-attribution \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --strategy all \
  --limit 50 \
  --json

uv run crypto-assistant strategy hedged-maker-report \
  --config ../configs/config.example.yaml \
  --limit 50 \
  --json

uv run crypto-assistant strategy diversification-report \
  --config ../configs/config.example.yaml \
  --strategy all \
  --execution-mode paper \
  --max-family-share-pct 60 \
  --min-queue-quality-score 80 \
  --json

uv run crypto-assistant strategy directional-sleeve-status \
  --config ../configs/config.example.yaml \
  --execution-mode paper \
  --limit 50 \
  --json
```

所有滚动证据命令都是只读命令，应该报告 `orders_sent=false` 和 `live_orders_sent=false`。

| 命令 | 用途 |
| --- | --- |
| `validation-report` | 聚合执行质量、PnL、回撤、原因计数、残余库存和 receipt/tolerance 失败。 |
| `advisory-rank` | 基于 scorecard、滚动验证、机会密度和 runtime guard 的确定性排名，不调用外部模型、不修改配置。 |
| `diversification-report` | 策略家族集中度、validation PnL、建议验证预算上限，以及带确定性质量分的 family-balanced `validation_queue`。 |
| `directional-sleeve-status` | long-only 方向性策略 promotion stage、仓位上限、guard cooldown 和永久 `directional_live_supported=false` 边界。 |
| `operator-brief` | 下一次 demo 或 promotion 前的 no-order operator checkpoint。 |
| `pnl-attribution` | 区分策略现金流 PnL 和账户权益变化，避免把无关库存当作策略表现。 |
| `hedged-maker-report` | Paper-only maker quote 生命周期、队列/部分成交质量、adverse selection 样本、模拟 hedge 滑点和当前 quote 状态。 |

`diversification-report --min-queue-quality-score` 只过滤 queue，不会隐藏 family diagnostics。`hedged-maker-demo` 是单独的 OKX Demo opportunity-file manager，不属于通用 `strategy run --strategy hedged-maker --execution-mode demo` 路径。

## 策略家族

| 家族 | 策略 | 典型模式 |
| --- | --- | --- |
| 跨交易所套利 | `cross-exchange` | 先 mock/paper；live adapter 覆盖有限。 |
| 三角套利 | `triangular-multi-route`，兼容别名 `triangular` | 只读发现、paper，再在门禁通过后做 OKX demo sampling。 |
| Carry and basis | `funding-carry-hedged`、`spot-perp-carry`、`futures-perp-basis` | 离线诊断和 paper，直到经济性覆盖手续费、滑点、持有成本和 basis hedge cost。 |
| Range grid | `range-grid` | Paper-only 区间网格机会估计；不支持 OKX Demo 和 live 订单。 |
| Smart DCA basket | `smart-dca-basket`，兼容别名 `smart-dca` | Paper-only BTC/ETH/SOL 回撤分层定投和 basket 权重诊断。 |
| Hedged maker / XEMM | `hedged-maker` | Paper 被动报价规划和 taker hedge preview；approved opportunity file 有显式 OKX Demo manager；不支持 live maker 订单。 |
| 方向性现货 | `trend-breakout`、`mean-reversion-spot`、`volatility-squeeze-breakout`、`momentum-rotation`、`orderbook-imbalance-scalp` | 先 paper；部分策略支持极小 long-only OKX demo 托管仓位。方向性 live trading 不支持。 |
| DEX/CLMM LP | `dex-lp-readiness` | 未来 DEX 流动性 provision 的 readiness gate；未实现 wallet、gateway、LP、demo 或 live execution。 |

Carry/basis 调优是只读的：

```bash
uv run crypto-assistant strategy carry-basis-optimize \
  --config ../configs/config.example.yaml \
  --symbol BTC/USDT \
  --json
```

对比同一 carry/basis 候选在目标交易所上的只读表现：

```bash
uv run crypto-assistant strategy carry-basis-optimize \
  --config ../configs/okx.demo.example.yaml \
  --symbol BTC/USDT \
  --target-exchange okx \
  --json
```

多 symbol sweep 并排序最接近解锁的候选：

```bash
uv run crypto-assistant strategy carry-basis-optimize \
  --config ../configs/okx.demo.example.yaml \
  --symbols BTC/USDT,ETH/USDT,SOL/USDT \
  --target-exchange okx \
  --min-quality-score 80 \
  --max-symbols 6 \
  --request-budget-seconds 60 \
  --per-symbol-timeout-seconds 15 \
  --json
```

OKX sweep 建议从小 symbol 集开始，因为每个 symbol 都会读取 spot/perp/funding/futures 公共端点诊断。使用 `--max-symbols`、`--request-budget-seconds` 和 `--per-symbol-timeout-seconds` 控制 bounded observer run；这些控制是只读的，不会绕过 demo preflight。

## OKX Demo Trading 路径

准备本地 demo 凭证：

```bash
cp .env.okx.demo.example .env.okx.demo
```

编辑 `.env.okx.demo` 填入 OKX Demo Trading 凭证，并保持 demo 与 live 凭证分离。

先运行 no-order 检查：

```bash
cd backend
uv run crypto-assistant exchange sandbox-check \
  --config ../configs/okx.demo.example.yaml \
  --exchange okx \
  --symbol BTC/USDT \
  --json

uv run crypto-assistant strategy market-compare \
  --config ../configs/okx.demo.example.yaml \
  --strategy all \
  --symbol BTC/USDT \
  --target-exchange okx \
  --json

uv run crypto-assistant strategy operator-brief \
  --config ../configs/okx.demo.example.yaml \
  --execution-mode demo \
  --strategy all \
  --limit 50 \
  --json
```

只有 no-order 检查通过后，才使用有界 OKX Demo Trading window。以下命令可能发送极小 OKX Demo Trading 订单，但不会发送 live 订单：

```bash
uv run crypto-assistant strategy demo-window \
  --config ../configs/okx.demo.example.yaml \
  --strategy triangular-multi-route \
  --cycles 3 \
  --symbol BTC/USDT \
  --json

uv run crypto-assistant strategy demo-sampling \
  --config ../configs/okx.demo.example.yaml \
  --strategy triangular-multi-route \
  --windows 3 \
  --cycles-per-window 3 \
  --interval-seconds 0 \
  --symbol BTC/USDT \
  --json
```

Hedged-maker sandbox parity 使用显式 opportunity-file manager，不走通用 demo runtime：

```bash
uv run crypto-assistant strategy hedged-maker-demo-candidate \
  --config ../configs/okx.demo.example.yaml \
  --symbol BTC/USDT \
  --target-exchange okx \
  --json

uv run crypto-assistant strategy hedged-maker-demo \
  --config ../configs/okx.demo.example.yaml \
  --opportunity-file hedged-maker-okx-opportunity.json \
  --json
```

Promotion 仍然只是 evidence-only，除非 operator 显式修改 live gate：

```bash
uv run crypto-assistant strategy promotion-status \
  --config ../configs/okx.demo.example.yaml \
  --strategy all \
  --json
```

`strategy validate-demo --allow-account-mode-switch` 仅用于 OKX Demo Trading swap/futures 验证。它只能在 provider demo-mode verification 和 open-risk 检查通过后切换 demo account mode，绝不能用于 live trading。

## CLI 命令地图

| 区域 | 命令 |
| --- | --- |
| 配置/状态 | `status`, `config validate` |
| 交易所/行情/账户 | `exchange list`, `exchange ping`, `exchange sandbox-check`, `market ticker`, `market orderbook`, `market candles`, `account balance` |
| 套利 | `arbitrage scan`, `arbitrage execute` |
| 策略发现 | `strategy list`, `strategy catalog`, `strategy scan`, `strategy discover-routes`, `strategy opportunity-report`, `strategy universe`, `strategy regime-report`, `strategy score`, `strategy advisory-rank`, `strategy dex-lp-readiness`, `strategy market-compare`, `strategy portfolio-status` |
| 策略运行 | `strategy run`, `strategy review`, `strategy guard-status`, `strategy retrospective`, `strategy evolve`, `strategy candidate-backtest`, `strategy revival-window` |
| Detached autopilot | `autopilot run`, `autopilot status`, `autopilot report` |
| 验证/证据 | `strategy validate-local`, `strategy validate-demo`, `strategy validate-demo-window`, `strategy demo-window`, `strategy demo-sampling`, `strategy promotion-status`, `strategy validation-report`, `strategy operator-brief`, `strategy diversification-report`, `strategy directional-sleeve-status`, `strategy pnl-attribution`, `strategy hedged-maker-report`, `strategy hedged-maker-demo-candidate`, `strategy hedged-maker-demo`, `strategy carry-basis-optimize`, `strategy exit-optimize`, `strategy position-report` |
| Agent live gate | `agent live-readiness`, `agent execute-live`, `agent operation-catalog` |
| 回测/报告/工作流 | `backtest run`, `backtest walk-forward`, `backtest bias-check`, `report generate`, `workflow run` |

每个机器可读 CLI 命令都应支持 `--json`，每个 CLI 命令都应支持 `--help`。

## 环境变量

只使用 `COINBOT_` 前缀：

```bash
COINBOT_TRADING_LIVE_TRADING=false
COINBOT_TRADING_DRY_RUN=true
COINBOT_REQUIRE_CONFIRM_BEFORE_ORDER=true
COINBOT_AGENT_TRADING_ENABLED=false
COINBOT_AGENT_ALLOW_DEMO_ORDERS=false
COINBOT_AGENT_ALLOW_LIVE_ORDERS=false
COINBOT_AGENT_OPERATOR_ID=
COINBOT_AGENT_LIVE_KILL_SWITCH=false
COINBOT_OKX_API_KEY=
COINBOT_OKX_API_SECRET=
COINBOT_OKX_PASSPHRASE=
COINBOT_OKX_DEMO=true
```

没有 OKX 凭证时，mock exchange、paper validation、本地扫描以及许多公共市场/分析端点仍可使用。私有 OKX 账户读取和 OKX Demo Trading 需要本地凭证。

## 仓库卫生

不要把本地运行产物提交到 git：

- 密钥文件：`.env`、`.env.*`、`.env.okx.demo`、`.env.okx.live`；只有已提交的 `*.example` 模板是安全的。
- 运行证据：`logs/`、`backend/logs/`、JSONL journal、本地 state 文件、生成的 opportunity payload 和临时 SQLite/DuckDB 数据库。
- 工具输出：Python cache、uv cache、Node build output、Rust `target/`、coverage report 和编辑器元数据。

应提交锁文件 `uv.lock`、`frontend/package-lock.json`、`Cargo.lock`，以及 `docs/plan/2026-05-09-refactor/` 下经过整理的重构 state JSON。

## 验证

变更后运行相关检查：

```bash
cd backend
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -v
```

```bash
cd quant-core
cargo test
```

```bash
cd frontend
npm install
npm run build
```

CLI smoke check：

```bash
cd backend
uv run crypto-assistant --help
uv run crypto-assistant strategy --help
uv run crypto-assistant config validate --config ../configs/config.example.yaml --json
uv run crypto-assistant strategy catalog --config ../configs/config.example.yaml --json
```

## 文档入口

优先阅读：

- [docs/DESIGN.md](docs/DESIGN.md)：当前架构和公共接口。
- [docs/plan/2026-05-09-refactor/00-refactor-spec.md](docs/plan/2026-05-09-refactor/00-refactor-spec.md)：crypto trading assistant 重构目标。
- [docs/plan/2026-05-09-refactor/](docs/plan/2026-05-09-refactor/)：活动 phase report、traceability、acceptance notes 和 final reports。

重构计划和验收材料必须放在 `docs/plan/2026-05-09-refactor/` 下。历史迁移任务记录位于 `docs/tasks/**` 和 `docs/acceptance/**`。

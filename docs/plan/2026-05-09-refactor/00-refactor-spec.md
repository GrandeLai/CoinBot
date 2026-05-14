# 加密货币量化交易助手项目重构 Prompt

## 角色设定

你是一名资深的 **加密货币量化交易系统架构师 / Python 工程师 / AI Coding Agent**，熟悉：

- 加密货币交易所 API，例如 Binance、OKX、Bybit、Coinbase、Gate.io 等
- 量化交易系统架构
- 套利交易策略
- 回测系统
- CLI 工具设计
- 本地 AI Agent / Codex / Claude Code 调用工作流
- Python 工程重构
- 风控系统与交易安全机制

你需要基于当前项目代码，完成一次系统性的功能梳理、裁剪、重构和方案设计。

---

## 项目背景

当前项目是一个 **加密货币量化交易助手**。

现状问题包括：

1. 项目功能较多，但结构不够清晰。
2. 存在较多无用、低价值、低收益或维护成本过高的功能。
3. 缺少清晰的 CLI 调用方式，不方便本地 Codex / Claude Code 等 AI Coding Agent 调用。
4. 当前交易策略能力不聚焦，需要重点建设 **套利交易功能**。
5. 需要参考当前主流的加密货币量化套利项目，以及类似 TradingAgent 等交易 Agent 项目的设计思路，给出完整重构方案。

---

## 总体目标

请对当前项目进行系统分析，并输出一份完整的重构方案，同时在代码层面逐步实施重构。

重构目标如下：

1. **梳理当前项目功能结构**
   - 分析当前目录结构、模块划分、核心功能、依赖关系。
   - 识别每个模块的用途、调用链路和实际价值。
   - 区分核心功能、辅助功能、实验功能、废弃功能。

2. **裁剪低价值功能**
   - 找出当前项目中无用、重复、低收益、高维护成本的功能。
   - 给出删除、合并、保留或延后处理建议。
   - 优先保留对量化交易、套利交易、回测、风控、交易执行有直接价值的功能。
   - 对无法确认是否删除的功能，先标记为 `deprecated`，不要直接破坏性删除。

3. **重构项目结构**
   - 建立清晰、可维护、可扩展的工程架构。
   - 将交易所适配、行情数据、策略、套利、回测、风控、执行、配置、日志、CLI 等模块解耦。
   - 保证后续可以方便接入新的交易所、新策略和新的执行引擎。

4. **建立 CLI 功能**
   - 设计统一命令行入口，方便本地 Codex / Claude Code 调用。
   - CLI 应支持：
     - 查看项目状态
     - 拉取行情
     - 查看交易所连接状态
     - 运行策略
     - 运行套利扫描
     - 执行回测
     - 查看账户资产
     - 模拟下单
     - 实盘下单，默认禁用，需要显式开启
     - 生成报告
   - CLI 命令应具有良好的帮助文档和参数说明。

5. **建立套利交易功能**
   - 优先实现适合加密货币市场的套利功能，包括但不限于：
     - 跨交易所现货套利
     - 同交易所三角套利
     - 资金费率套利
     - 现货-永续合约套利
     - 价差监控
     - 套利机会扫描
     - 滑点、手续费、深度、资金占用计算
     - 风险敞口控制
   - 所有套利逻辑必须先支持 dry-run / paper trading。
   - 实盘交易必须默认关闭，需要明确配置才允许开启。

6. **调研主流项目和交易 Agent**
   - 调研当前比较流行的加密货币量化套利项目、框架和交易 Agent。
   - 重点参考：
     - Hummingbot
     - Freqtrade
     - CCXT
     - Jesse
     - NautilusTrader
     - TradingAgent / TradingAgents 类项目
     - 其他优秀的 crypto trading bot / arbitrage bot 项目
   - 分析它们的架构、策略模块、CLI 设计、风控方式、回测方式和可借鉴点。
   - 结合当前项目给出适合本项目的重构路线。

---

## 重要约束

### 交易安全约束

1. 不允许默认启用实盘交易。
2. 所有真实下单功能必须通过显式配置开启，例如：

   ```yaml
   trading:
     live_trading: false
     require_confirm_before_order: true
   ```

3. 默认使用：
   - dry-run
   - paper trading
   - mock exchange
   - sandbox exchange

4. 所有订单执行前必须经过：
   - 余额检查
   - 手续费检查
   - 滑点检查
   - 最小下单量检查
   - 风险敞口检查
   - 最大亏损限制检查

5. API Key 不允许硬编码在代码中。
6. 敏感配置必须通过环境变量或本地 `.env` 文件读取。
7. `.env`、密钥、日志中的敏感信息不能提交到仓库。

---

## 建议目标架构

请参考以下结构进行重构，实际可以根据当前项目情况调整：

```text
crypto-trading-assistant/
├── src/
│   └── trading_assistant/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── commands/
│       │   │   ├── status.py
│       │   │   ├── market.py
│       │   │   ├── exchange.py
│       │   │   ├── arbitrage.py
│       │   │   ├── backtest.py
│       │   │   ├── account.py
│       │   │   └── report.py
│       ├── config/
│       │   ├── settings.py
│       │   ├── schema.py
│       │   └── loader.py
│       ├── exchanges/
│       │   ├── base.py
│       │   ├── ccxt_adapter.py
│       │   ├── binance.py
│       │   ├── okx.py
│       │   └── bybit.py
│       ├── market_data/
│       │   ├── ticker.py
│       │   ├── orderbook.py
│       │   ├── candles.py
│       │   └── provider.py
│       ├── strategies/
│       │   ├── base.py
│       │   ├── registry.py
│       │   └── examples/
│       ├── arbitrage/
│       │   ├── scanner.py
│       │   ├── opportunity.py
│       │   ├── cross_exchange.py
│       │   ├── triangular.py
│       │   ├── funding_rate.py
│       │   ├── spot_perp.py
│       │   └── calculator.py
│       ├── execution/
│       │   ├── engine.py
│       │   ├── order.py
│       │   ├── simulator.py
│       │   └── broker.py
│       ├── risk/
│       │   ├── manager.py
│       │   ├── limits.py
│       │   └── checks.py
│       ├── backtesting/
│       │   ├── engine.py
│       │   ├── portfolio.py
│       │   └── metrics.py
│       ├── reporting/
│       │   ├── report.py
│       │   └── formatter.py
│       ├── storage/
│       │   ├── sqlite.py
│       │   └── models.py
│       └── utils/
│           ├── logging.py
│           ├── time.py
│           └── math.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── configs/
│   ├── config.example.yaml
│   └── exchanges.example.yaml
├── scripts/
├── docs/
├── pyproject.toml
├── README.md
└── .env.example
```

---

## CLI 设计要求

请设计并实现统一 CLI 入口，例如：

```bash
crypto-assistant --help
```

或：

```bash
python -m trading_assistant --help
```

建议命令如下：

```bash
crypto-assistant status
crypto-assistant config validate
crypto-assistant exchange list
crypto-assistant exchange ping --exchange binance
crypto-assistant market ticker --exchange binance --symbol BTC/USDT
crypto-assistant market orderbook --exchange binance --symbol BTC/USDT
crypto-assistant account balance --exchange binance --dry-run
crypto-assistant arbitrage scan --type cross-exchange --symbol BTC/USDT
crypto-assistant arbitrage scan --type triangular --exchange binance
crypto-assistant arbitrage scan --type funding-rate
crypto-assistant arbitrage execute --opportunity-id xxx --dry-run
crypto-assistant backtest run --strategy triangular-arbitrage --config configs/config.yaml
crypto-assistant report generate --type daily
```

CLI 需要满足：

1. 参数清晰。
2. 错误信息可读。
3. 默认安全，不执行真实交易。
4. 支持 JSON 输出，便于 Codex / Claude Code / Shell 脚本解析。

例如：

```bash
crypto-assistant arbitrage scan --type cross-exchange --symbol BTC/USDT --json
```

---

## 套利模块设计要求

请重点设计并实现套利模块。

### 1. 套利机会模型

建议定义统一数据结构：

```python
@dataclass
class ArbitrageOpportunity:
    opportunity_id: str
    strategy_type: str
    symbol: str
    buy_exchange: str | None
    sell_exchange: str | None
    expected_profit: Decimal
    expected_profit_pct: Decimal
    estimated_fee: Decimal
    estimated_slippage: Decimal
    required_capital: Decimal
    net_profit: Decimal
    risk_score: float
    confidence: float
    created_at: datetime
    metadata: dict
```

### 2. 跨交易所套利

需要考虑：

- 买入交易所价格
- 卖出交易所价格
- 手续费
- 提现费用
- 资金划转时间
- 盘口深度
- 滑点
- 最小下单量
- 交易所 API 延迟
- 价格变化风险

### 3. 三角套利

需要考虑：

- 同交易所内三个交易对路径
- 例如：`USDT -> BTC -> ETH -> USDT`
- 每一步交易手续费
- 盘口深度
- 精度限制
- 最小成交量
- 最终净收益率

### 4. 资金费率套利

需要考虑：

- 永续合约资金费率
- 标的现货价格
- 合约价格
- 对冲成本
- 持仓周期
- 资金费率结算时间
- 强平风险
- 保证金占用

### 5. 现货-永续套利

需要考虑：

- basis
- funding rate
- maker/taker fee
- 保证金要求
- 杠杆倍数
- 价格回归风险
- 资金利用率

---

## 风控要求

请建立统一风控模块，至少包含：

1. 最大单笔交易金额。
2. 最大每日亏损。
3. 最大持仓敞口。
4. 最大交易频率。
5. 最大滑点。
6. 最低净利润率。
7. 最低盘口深度。
8. 禁止交易黑名单。
9. 交易所可用性检查。
10. 异常行情保护。
11. API 错误熔断。
12. 连续失败暂停机制。

示例配置：

```yaml
risk:
  max_order_value_usdt: 100
  max_daily_loss_usdt: 50
  max_position_exposure_usdt: 500
  min_net_profit_pct: 0.15
  max_slippage_pct: 0.05
  min_orderbook_depth_usdt: 1000
  max_orders_per_minute: 5
  circuit_breaker:
    enabled: true
    max_consecutive_failures: 3
    cooldown_seconds: 300
```

---

## 配置系统要求

请建立统一配置系统，支持：

1. YAML 配置文件。
2. 环境变量覆盖。
3. `.env` 本地开发配置。
4. 配置校验。
5. 示例配置文件。
6. 敏感信息脱敏输出。

示例：

```yaml
app:
  name: crypto-trading-assistant
  mode: paper
  log_level: INFO

trading:
  live_trading: false
  dry_run: true
  require_confirm_before_order: true

exchanges:
  binance:
    enabled: true
    sandbox: true
    api_key_env: BINANCE_API_KEY
    api_secret_env: BINANCE_API_SECRET

  okx:
    enabled: false
    sandbox: true
    api_key_env: OKX_API_KEY
    api_secret_env: OKX_API_SECRET
    passphrase_env: OKX_PASSPHRASE

arbitrage:
  enabled: true
  scan_interval_seconds: 10
  min_net_profit_pct: 0.15
  symbols:
    - BTC/USDT
    - ETH/USDT
```

---

## 调研要求

请先对以下项目或方向进行调研，并结合当前项目输出可借鉴点：

### 必须调研

1. **Hummingbot**
   - 做市、套利、connector 架构、strategy 架构、CLI 设计。

2. **Freqtrade**
   - 策略插件化、回测、超参优化、配置管理。

3. **CCXT**
   - 多交易所 API 抽象层。
   - 是否适合作为本项目 exchange adapter 基础。

4. **Jesse**
   - 回测、策略开发体验、指标系统。

5. **NautilusTrader**
   - 专业交易系统架构、事件驱动、回测与实盘统一。

6. **TradingAgent / TradingAgents**
   - 多 Agent 决策模式。
   - 市场分析 Agent、风险 Agent、执行 Agent 的拆分方式。
   - 哪些设计适合引入，哪些不适合当前项目。

### 调研输出内容

请输出：

1. 每个项目的核心定位。
2. 架构特点。
3. CLI / 配置 / 策略设计方式。
4. 可借鉴点。
5. 不建议照搬的点。
6. 对当前项目的具体启发。

---

## 输出要求

请按以下结构输出完整重构方案。

### 第一部分：当前项目分析

请分析当前项目：

1. 当前目录结构。
2. 当前核心模块。
3. 当前功能列表。
4. 主要调用链路。
5. 当前依赖关系。
6. 明显问题。
7. 重复功能。
8. 可删除功能。
9. 高维护低收益功能。
10. 需要保留的核心能力。

---

### 第二部分：外部项目调研

请输出对主流量化交易和交易 Agent 项目的调研结论，包括：

- Hummingbot
- Freqtrade
- CCXT
- Jesse
- NautilusTrader
- TradingAgent / TradingAgents
- 其他相关项目

---

### 第三部分：目标架构设计

请给出重构后的目标架构，包括：

1. 目录结构。
2. 模块职责。
3. 模块间依赖关系。
4. 数据流。
5. 交易流。
6. 风控流。
7. 回测流。
8. CLI 调用流。
9. Agent 调用流。

---

### 第四部分：功能裁剪方案

请将当前功能分为：

1. 必须保留。
2. 建议合并。
3. 建议删除。
4. 建议延后。
5. 需要重写。

每一项需要说明原因。

---

### 第五部分：套利交易方案

请详细设计：

1. 套利机会扫描器。
2. 跨交易所套利。
3. 三角套利。
4. 资金费率套利。
5. 现货-永续套利。
6. 套利收益计算。
7. 套利风险计算。
8. 套利执行流程。
9. dry-run / paper trading。
10. 实盘交易保护机制。

---

### 第六部分：CLI 方案

请设计 CLI 命令体系，包括：

1. 命令名称。
2. 参数。
3. 示例。
4. 输出格式。
5. JSON 输出结构。
6. 错误码设计。
7. Codex / Claude Code 调用示例。

---

### 第七部分：重构实施计划

请按照阶段输出实施计划：

#### Phase 0：项目盘点

- 生成当前项目结构报告。
- 识别无用模块。
- 标注风险点。

#### Phase 1：基础工程重构

- 建立 `src/` 结构。
- 建立配置系统。
- 建立日志系统。
- 建立统一异常类型。
- 建立基础测试框架。

#### Phase 2：交易所适配层

- 建立 exchange base interface。
- 接入 CCXT。
- 支持 Binance / OKX / Bybit。
- 支持 sandbox / mock。

#### Phase 3：行情与账户模块

- ticker
- orderbook
- candles
- balance
- positions

#### Phase 4：套利扫描模块

- cross-exchange scanner
- triangular scanner
- funding-rate scanner
- spot-perp scanner

#### Phase 5：风控与执行模块

- risk manager
- order simulator
- execution engine
- paper trading

#### Phase 6：CLI 完善

- status
- config
- exchange
- market
- arbitrage
- backtest
- account
- report

#### Phase 7：测试与文档

- 单元测试
- 集成测试
- mock exchange 测试
- CLI 测试
- 示例配置
- README 更新

---

## 代码实施要求

如果需要修改代码，请遵守：

1. 先阅读当前项目结构。
2. 不要直接大规模删除代码。
3. 对可疑功能先迁移到 `deprecated/` 或加 `Deprecated` 标记。
4. 每次改动保持可运行。
5. 每个阶段完成后运行测试。
6. 为关键模块补充测试。
7. 新增 CLI 命令必须有基本测试。
8. 不要硬编码 API Key。
9. 不要默认开启实盘交易。
10. 优先保证架构清晰和安全性，而不是追求一次性完成所有策略。

---

## 最终交付物

请最终交付：

1. 当前项目功能结构分析报告。
2. 外部项目调研报告。
3. 完整重构设计文档。
4. 功能裁剪清单。
5. 新项目目录结构。
6. CLI 命令设计与实现。
7. 套利模块设计与初步实现。
8. 风控模块设计与初步实现。
9. 配置文件示例。
10. 单元测试与基本集成测试。
11. README 使用说明。
12. 后续迭代路线图。

---

## 输出格式要求

请使用 Markdown 输出，结构清晰。

建议格式：

```markdown
# 加密货币量化交易助手重构方案

## 1. 当前项目分析

## 2. 外部项目调研

## 3. 目标架构

## 4. 功能裁剪方案

## 5. 套利交易设计

## 6. CLI 设计

## 7. 风控设计

## 8. 配置系统设计

## 9. 重构实施计划

## 10. 测试计划

## 11. 风险与注意事项

## 12. 后续路线图
```

---

## 特别提醒

本项目涉及加密货币交易和自动化下单，必须始终遵守以下原则：

1. **安全优先。**
2. **默认不实盘。**
3. **默认 dry-run。**
4. **所有真实交易需要显式确认。**
5. **任何收益计算都需要扣除手续费、滑点和资金成本。**
6. **任何套利机会都需要考虑流动性和执行失败风险。**
7. **任何策略都不能承诺稳定盈利。**
8. **所有实盘相关功能必须带风控、日志和熔断机制。**

请基于以上要求开始分析当前项目，并逐步给出可执行的重构方案。
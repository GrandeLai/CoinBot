/**
 * CoinBot navigation registry.
 */
export type AssistantTab =
  | "overview"
  | "trade"
  | "opportunities"
  | "rebalance"
  | "risk"
  | "derivs"
  | "research"
  | "whale"
  | "unlocks"
  | "backtest"
  | "optimize"
  | "walkforward"
  | "review";

export const ASSISTANT_TABS = [
  { key: "overview", label: "资产总览" },
  { key: "trade", label: "OKX 交易" },
  { key: "opportunities", label: "机会池" },
  { key: "rebalance", label: "调仓建议" },
  { key: "risk", label: "风险雷达" },
  { key: "derivs", label: "衍生品" },
  { key: "research", label: "研究" },
  { key: "whale", label: "巨鲸" },
  { key: "unlocks", label: "解锁" },
  { key: "backtest", label: "回测" },
  { key: "optimize", label: "优化" },
  { key: "walkforward", label: "验证" },
  { key: "review", label: "复盘与问答" },
] as const;

/**
 * CoinBot API client for advisor, crypto research, derivatives analytics,
 * token unlocks, whale flow, and local market data.
 */

const BASE = "/api";

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!response.ok) {
    let message = text || `HTTP ${response.status}`;
    try {
      const body = JSON.parse(text) as { detail?: string };
      message = body.detail ?? message;
    } catch {
      // Keep raw text when the response is not JSON.
    }
    throw new Error(message);
  }
  return (text ? JSON.parse(text) : null) as T;
}

async function getJson<T>(path: string): Promise<T> {
  return readJson<T>(await fetch(`${BASE}${path}`));
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  return readJson<T>(
    await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export interface OhlcBar {
  symbol: string;
  timeframe: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  turnover?: number | null;
}

export interface OhlcvResponse {
  symbol: string;
  timeframe: string;
  count: number;
  bars: OhlcBar[];
}

export type IndicatorSeries = Record<string, (number | null)[]>;

export interface AdvisorOverviewPayload {
  net_worth: number;
  cash_ratio: number;
  positions: Array<Record<string, unknown>>;
  generated_at: string;
}

export interface AdvisorEvidence {
  source: string;
  summary: string;
  observed_at?: string;
}

export interface AdvisorCard {
  type: string;
  subject: string;
  recommendation: string;
  confidence: number;
  evidence: AdvisorEvidence[];
  risk_notes: string[];
  freshness?: string;
}

export interface CryptoResearchWindowMetric {
  train_start: number;
  train_end: number;
  test_start: number;
  test_end: number;
  accuracy: number;
  strategy_return: number;
}

export interface CryptoResearchSummary {
  symbol: string;
  base_timeframe: string;
  higher_timeframes: string[];
  rows: number;
  dataset_version: string;
  feature_count: number;
  feature_columns: string[];
  validation_windows: number;
  window_metrics: CryptoResearchWindowMetric[];
  mean_accuracy: number;
  mean_strategy_return: number;
  latest_class_signal: number;
  latest_class_probabilities: Record<string, number>;
  feature_importance: Record<string, number>;
  reversal_probability: number;
  reversal_signal: string;
  reversal_evidence: string[];
  market_regime: string;
  recommended_strategy_ids: string[];
  recommended_timeframes: string[];
  parameter_search_ready: boolean;
  funding_percentile?: number;
  generated_at?: string;
}

export interface CryptoResearchOptimizationSummary {
  symbol: string;
  strategy_id: string;
  base_timeframe: string;
  higher_timeframes: string[];
  best_params: Record<string, number>;
  window_count: number;
  mean_accuracy: number;
  mean_strategy_return: number;
  max_drawdown: number;
  window_metrics: CryptoResearchWindowMetric[];
  regime?: string;
  method?: string;
  generated_at?: string;
}

export type AdvisorCryptoResearchSummary = CryptoResearchSummary;
export type AdvisorCryptoOptimizationSummary = CryptoResearchOptimizationSummary;

function normalizeResearchSummary(raw: Partial<CryptoResearchSummary>): CryptoResearchSummary {
  const marketRegime = raw.market_regime ?? "ranging";
  return {
    symbol: raw.symbol ?? "BTC-USDT",
    base_timeframe: raw.base_timeframe ?? "15m",
    higher_timeframes: raw.higher_timeframes ?? ["1h", "4h", "1d"],
    rows: raw.rows ?? 0,
    dataset_version: raw.dataset_version ?? raw.generated_at ?? "regime-latest",
    feature_count: raw.feature_count ?? 0,
    feature_columns: raw.feature_columns ?? [],
    validation_windows: raw.validation_windows ?? 0,
    window_metrics: raw.window_metrics ?? [],
    mean_accuracy: raw.mean_accuracy ?? 0,
    mean_strategy_return: raw.mean_strategy_return ?? 0,
    latest_class_signal: raw.latest_class_signal ?? 0,
    latest_class_probabilities: raw.latest_class_probabilities ?? { "-1": 0, "0": 1, "1": 0 },
    feature_importance: raw.feature_importance ?? {},
    reversal_probability: raw.reversal_probability ?? 0,
    reversal_signal: raw.reversal_signal ?? "none",
    reversal_evidence: raw.reversal_evidence ?? [],
    market_regime: marketRegime,
    recommended_strategy_ids: raw.recommended_strategy_ids ?? ["vwap_ema_trend"],
    recommended_timeframes: raw.recommended_timeframes ?? ["15m", "1h"],
    parameter_search_ready: raw.parameter_search_ready ?? true,
    funding_percentile: raw.funding_percentile,
    generated_at: raw.generated_at,
  };
}

function normalizeOptimization(
  raw: Partial<CryptoResearchOptimizationSummary>,
  symbol: string,
): CryptoResearchOptimizationSummary {
  return {
    symbol: raw.symbol ?? symbol,
    strategy_id: raw.strategy_id ?? "vwap_ema_trend",
    base_timeframe: raw.base_timeframe ?? "15m",
    higher_timeframes: raw.higher_timeframes ?? ["1h", "4h", "1d"],
    best_params: raw.best_params ?? {},
    window_count: raw.window_count ?? raw.window_metrics?.length ?? 0,
    mean_accuracy: raw.mean_accuracy ?? 0,
    mean_strategy_return: raw.mean_strategy_return ?? 0,
    max_drawdown: raw.max_drawdown ?? 0,
    window_metrics: raw.window_metrics ?? [],
    regime: raw.regime,
    method: raw.method,
    generated_at: raw.generated_at,
  };
}

export async function fetchBars(
  symbol: string,
  timeframe: string,
  limit = 300,
): Promise<OhlcBar[]> {
  const data = await getJson<OhlcvResponse>(
    `/data/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`,
  );
  return data.bars;
}

export async function triggerFetch(
  symbol: string,
  timeframe: string,
  start: string,
): Promise<void> {
  await postJson<{ status: string }>("/data/fetch", { symbol, timeframe, start, source: "okx" });
}

export function fetchOverview<T = AdvisorOverviewPayload>(): Promise<T> {
  return getJson<T>("/advisor/overview");
}

export function fetchCryptoOpportunities<T = { items: AdvisorCard[] }>(
  symbol = "BTC-USDT",
): Promise<T> {
  return getJson<T>(`/advisor/crypto/opportunities?symbol=${encodeURIComponent(symbol)}`);
}

export function fetchCryptoRisks<T = { items: AdvisorCard[] }>(
  symbol = "BTC-USDT",
): Promise<T> {
  return getJson<T>(`/advisor/crypto/risks?symbol=${encodeURIComponent(symbol)}`);
}

export async function fetchCryptoResearchLatest<T = CryptoResearchSummary>(
  symbol = "BTC-USDT",
): Promise<T> {
  const data = await getJson<Partial<CryptoResearchSummary>>(
    `/crypto/research/latest?symbol=${encodeURIComponent(symbol)}&base_timeframe=15m`,
  );
  return normalizeResearchSummary(data) as T;
}

export function fetchCryptoResearchLatestSummary(
  symbol = "BTC-USDT",
): Promise<CryptoResearchSummary> {
  return fetchCryptoResearchLatest<CryptoResearchSummary>(symbol);
}

export function fetchCryptoResearchSummary(
  symbol = "BTC-USDT",
): Promise<CryptoResearchSummary> {
  return fetchCryptoResearchLatestSummary(symbol);
}

export async function fetchCryptoResearchOptimization<T = CryptoResearchOptimizationSummary>(
  symbol = "BTC-USDT",
): Promise<T> {
  const data = await postJson<Partial<CryptoResearchOptimizationSummary>>(
    "/crypto/research/optimize",
    { symbol, base_timeframe: "15m", strategy_id: "vwap_ema_trend" },
  );
  return normalizeOptimization(data, symbol) as T;
}

export async function fetchCryptoResearchLatestOptimization<T = CryptoResearchOptimizationSummary>(
  symbol = "BTC-USDT",
  strategyId = "vwap_ema_trend",
): Promise<T> {
  const data = await getJson<Partial<CryptoResearchOptimizationSummary>>(
    `/crypto/research/optimize/latest?symbol=${encodeURIComponent(symbol)}&base_timeframe=15m&strategy_id=${encodeURIComponent(strategyId)}`,
  );
  return normalizeOptimization(data, symbol) as T;
}

export interface FundingRateLite {
  exchange: "binance" | "okx";
  symbol: string;
  raw_symbol: string;
  funding_rate: number;
  next_funding_time: string | null;
  timestamp: string;
}

export interface OpenInterestLite {
  exchange: "binance" | "okx";
  symbol: string;
  raw_symbol: string;
  open_interest: number;
  open_interest_value: number | null;
  timestamp: string;
}

export interface CryptoDerivsSnapshot {
  asset: string;
  timestamp: string;
  funding: { binance: FundingRateLite | null; okx: FundingRateLite | null };
  open_interest: { binance: OpenInterestLite | null; okx: OpenInterestLite | null };
  errors: Record<string, string>;
}

export interface FundingStats {
  mean: number;
  std: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface FundingExtremeSignal {
  z_score: number;
  percentile: number;
  signal: "contrarian_short" | "contrarian_long" | "neutral";
}

export interface FundingStatsResult {
  stats: FundingStats;
  n_samples: number;
  signal: FundingExtremeSignal | null;
}

export interface ETFFlowExtremeSignal {
  z_score: number;
  percentile: number;
  signal: "large_inflow" | "large_outflow" | "neutral";
}

export interface ETFFlowStatsResult {
  stats: FundingStats & { n_samples: number };
  signal: ETFFlowExtremeSignal | null;
}

export function fetchCryptoDerivsSnapshot(asset = "BTC"): Promise<CryptoDerivsSnapshot> {
  return postJson<CryptoDerivsSnapshot>("/crypto-derivs/snapshot", { asset });
}

export function fetchFundingStats(
  history: number[],
  current: number | null = null,
  zThreshold = 2.0,
): Promise<FundingStatsResult> {
  return postJson<FundingStatsResult>("/crypto-derivs/funding-stats", {
    history,
    current,
    z_threshold: zThreshold,
  });
}

export function fetchETFFlowStats(
  history: number[],
  current: number | null = null,
  zThreshold = 2.0,
): Promise<ETFFlowStatsResult> {
  return postJson<ETFFlowStatsResult>("/crypto-derivs/etf-flow-stats", {
    history,
    current,
    z_threshold: zThreshold,
  });
}

export interface WhaleTransferData {
  tx_hash: string;
  from_address: string;
  to_address: string;
  value_eth: number;
  value_usd: number | null;
  timestamp: string;
  exchange_name: string;
  direction: "inflow" | "outflow";
}

export interface CEXInflowData {
  symbol: string;
  hours: number;
  min_eth: number;
  inflow_eth: number;
  outflow_eth: number;
  net_flow_eth: number;
  inflow_usd: number | null;
  pressure_score: number;
  signal: "heavy_inflow" | "elevated_inflow" | "neutral" | "accumulation" | "heavy_accumulation";
  transfer_count: number;
  recent_transfers: WhaleTransferData[];
  as_of_date: string;
  api_key_missing: boolean;
}

export function fetchCEXInflow(hours = 24, minEth = 100): Promise<CEXInflowData> {
  return getJson<CEXInflowData>(
    `/crypto-whale/eth-inflow?hours=${hours}&min_eth=${minEth}`,
  );
}

export function fetchWhaleTransfers(
  hours = 24,
  minEth = 100,
  limit = 20,
): Promise<WhaleTransferData[]> {
  return getJson<WhaleTransferData[]>(
    `/crypto-whale/recent-transfers?hours=${hours}&min_eth=${minEth}&limit=${limit}`,
  );
}

export interface TokenUnlockEventData {
  protocol: string;
  symbol: string;
  unlock_date: string;
  days_until_unlock: number;
  unlock_tokens: number;
  unlock_usd: number | null;
  unlock_pct_circulating: number;
  category: string;
  sell_pressure_score: number;
  signal: "high_risk" | "moderate_risk" | "low_risk" | "post_unlock_rebound";
}

export interface TokenUnlockCalendarData {
  as_of_date: string;
  events: TokenUnlockEventData[];
  total_events: number;
  high_risk_count: number;
}

export function fetchTokenUnlocks(days = 30): Promise<TokenUnlockCalendarData> {
  return getJson<TokenUnlockCalendarData>(`/token-unlocks/upcoming?days=${days}`);
}

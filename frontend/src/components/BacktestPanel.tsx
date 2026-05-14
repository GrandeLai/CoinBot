/**
 * 回测面板 — MA crossover 策略历史回测（接 Rust coinbot-quant）.
 * 流程: 配置参数 → 拉 OKX K 线 → POST /api/backtest/run（Rust）→ 展示绩效
 */
import { useRef, useState } from "react";
import type { ElementType } from "react";
import {
  findInstrument,
  instrumentsForProduct,
  type DataSource,
  type SupportedInstrument,
} from "../shared/markets";
import {
  History,
  Play,
  BarChart3,
  TrendingUp,
  TrendingDown,
  ShieldAlert,
  Percent,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import EquityCurveChart from "@/components/EquityCurveChart";

// ── 数据类型 ──────────────────────────────────────────────────────────────────

interface BacktestMetrics {
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  volatility: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  win_trades: number;
  loss_trades: number;
  avg_win: number;
  avg_loss: number;
  initial_cash: number;
  final_value: number;
  start_date?: string | null;
  end_date?: string | null;
  trading_days: number;
}

export interface BacktestResult {
  symbol: string;
  fast_period: number;
  slow_period: number;
  bars_processed: number;
  equity_curve: number[];
  metrics: BacktestMetrics;
}

// ── 样式 token ────────────────────────────────────────────────────────────────

const INPUT_CLS =
  "w-full h-9 bg-[#161b22] border border-[#30363d] rounded-lg px-3 text-sm text-white outline-none focus:border-blue-500/50 transition-colors placeholder-[#8b949e]/50";

const TIMEFRAMES = ["1d", "1w", "1h", "4h"];
const QUICK_INSTRUMENTS = instrumentsForProduct("coinbot");

// ── 辅助组件 ─────────────────────────────────────────────────────────────────

function MetricTile({
  label,
  value,
  sub,
  color = "text-white",
  icon: Icon,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
  icon?: ElementType;
}) {
  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#8b949e] mb-3">
        {Icon && <Icon className="w-3 h-3" />}
        {label}
      </div>
      <div className={cn("text-2xl font-bold tracking-tight", color)}>{value}</div>
      {sub && <div className="text-[10px] text-[#8b949e] mt-1">{sub}</div>}
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────────────────────

interface BacktestPanelProps {
  onResult?: (result: BacktestResult) => void;
}

export default function BacktestPanel({ onResult }: BacktestPanelProps = {}) {
  // ── 配置状态
  const [symbol, setSymbol] = useState("BTC-USDT");
  const [timeframe, setTimeframe] = useState("1d");
  const [limit, setLimit] = useState(300);
  const [fastPeriod, setFastPeriod] = useState(10);
  const [slowPeriod, setSlowPeriod] = useState(30);
  const [initialCash, setInitialCash] = useState(1_000_000);

  // ── 运行状态
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<"idle" | "fetchingBars" | "running" | "done" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const selectedInstrument = findInstrument(symbol);

  const resolveSource = (instrument: SupportedInstrument | undefined): DataSource =>
    instrument?.default_source ?? "auto";

  const defaultStartDate = () => {
    const start = new Date();
    start.setFullYear(start.getFullYear() - 2);
    return start.toISOString().slice(0, 10);
  };

  const fetchBars = async () => {
    const barsRes = await fetch(
      `/api/data/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`,
      { signal: abortRef.current?.signal },
    );
    if (!barsRes.ok) throw new Error(`获取 K 线失败: ${await barsRes.text()}`);
    return (await barsRes.json()) as {
      bars: Array<{ close: number; time?: string | null; timestamp?: string | null }>;
    };
  };

  const ensureBars = async () => {
    const minimumBars = Math.max(2, slowPeriod + 1);
    let barsJson = await fetchBars();
    if (barsJson.bars?.length >= minimumBars) return barsJson;

    const fetchRes = await fetch("/api/data/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol,
        timeframe,
        start: defaultStartDate(),
        source: resolveSource(selectedInstrument),
      }),
      signal: abortRef.current?.signal,
    });
    if (!fetchRes.ok) throw new Error(`触发数据拉取失败: ${await fetchRes.text()}`);

    for (let attempt = 0; attempt < 8; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 800));
      barsJson = await fetchBars();
      if (barsJson.bars?.length >= minimumBars) return barsJson;
    }

    return barsJson;
  };

  // ── 执行回测
  const runBacktest = async () => {
    setRunning(true);
    setStatus("fetchingBars");
    setErrorMsg("");
    setResult(null);
    abortRef.current = new AbortController();

    try {
      // Step 1: 获取 OKX K 线数据；缺数据时触发数据拉取。
      const barsJson = await ensureBars();
      if (!barsJson.bars || barsJson.bars.length < Math.max(2, slowPeriod + 1)) {
        throw new Error("K 线数据不足，请检查 OKX 数据源或缩短慢线周期");
      }

      setStatus("running");

      // Step 2: 提交回测请求（Rust coinbot-quant proxy）
      const req = {
        symbol,
        bars: barsJson.bars.map((b) => ({ close: b.close, time: b.time ?? b.timestamp ?? null })),
        fast_period: fastPeriod,
        slow_period: slowPeriod,
        initial_cash: initialCash,
      };

      const runRes = await fetch("/api/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: abortRef.current.signal,
      });

      if (!runRes.ok) throw new Error(`回测失败: ${await runRes.text()}`);

      const data = (await runRes.json()) as BacktestResult;
      setResult(data);
      setStatus("done");
      onResult?.(data);
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setStatus("error");
    } finally {
      setRunning(false);
    }
  };

  // ── 格式化
  const pct = (v: number) => `${(v * 100).toFixed(2)}%`;
  const money = (v: number) =>
    v >= 1_000_000
      ? `$${(v / 1_000_000).toFixed(2)}M`
      : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  return (
    <div
      className="relative flex bg-[#0d1117] rounded-xl overflow-hidden border border-[#30363d]"
      style={{ height: "calc(100vh - 120px)" }}
    >
      {/* ── 左侧配置栏 */}
      <aside className="w-72 shrink-0 border-r border-[#30363d] bg-[#0d1117] flex flex-col">
        <div className="px-6 pt-8 pb-6 border-b border-[#30363d]">
          <div className="flex items-center gap-2 text-[10px] font-bold text-[#8b949e] uppercase tracking-[0.2em] mb-2">
            <History className="w-3 h-3" />
            MA Crossover
          </div>
          <h1 className="text-2xl font-bold text-white">回测引擎</h1>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* 标的 */}
          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">标的代码</label>
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} className={INPUT_CLS} placeholder="BTC-USDT" />
            {selectedInstrument && (
              <div className="text-[10px] text-[#8b949e] leading-relaxed">
                {selectedInstrument.name} · {selectedInstrument.exchange} · {selectedInstrument.asset_type}
              </div>
            )}
            <div className="grid grid-cols-3 gap-1 pt-1">
              {QUICK_INSTRUMENTS.slice(0, 9).map((instrument) => (
                <button
                  key={instrument.symbol}
                  type="button"
                  onClick={() => setSymbol(instrument.symbol)}
                  className={cn(
                    "h-7 rounded-md border text-[10px] font-mono font-bold transition-all",
                    symbol === instrument.symbol
                      ? "border-blue-500 bg-blue-600 text-white"
                      : "border-[#30363d] bg-[#161b22] text-[#8b949e] hover:text-white",
                  )}
                  title={`${instrument.name} · ${instrument.exchange}`}
                >
                  {instrument.symbol}
                </button>
              ))}
            </div>
          </div>

          {/* 时间周期 */}
          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">K 线周期</label>
            <div className="grid grid-cols-4 gap-1">
              {TIMEFRAMES.map((tf) => (
                <button key={tf} onClick={() => setTimeframe(tf)}
                  className={cn("h-8 rounded-md text-xs font-mono font-bold transition-all",
                    timeframe === tf ? "bg-blue-600 text-white" : "bg-[#161b22] text-[#8b949e] hover:text-white border border-[#30363d]")}>
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* K 线数量 */}
          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">
              K 线数量 <span className="text-blue-400 font-mono normal-case">{limit}</span>
            </label>
            <input type="range" min={50} max={1000} step={50} value={limit}
              onChange={(e) => setLimit(Number(e.target.value))} className="w-full accent-blue-500" />
            <div className="flex justify-between text-[9px] text-[#434651]">
              <span>50</span><span>500</span><span>1000</span>
            </div>
          </div>

          {/* MA 参数 */}
          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">快线周期 (Fast MA)</label>
            <input type="number" value={fastPeriod}
              onChange={(e) => setFastPeriod(Math.max(1, Number(e.target.value)))}
              className={INPUT_CLS} min={1} max={200} />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">慢线周期 (Slow MA)</label>
            <input type="number" value={slowPeriod}
              onChange={(e) => setSlowPeriod(Math.max(1, Number(e.target.value)))}
              className={INPUT_CLS} min={1} max={500} />
          </div>

          {/* 初始资金 */}
          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">初始资金 ($)</label>
            <input type="number" value={initialCash}
              onChange={(e) => setInitialCash(Number(e.target.value))}
              className={INPUT_CLS} step={100000} min={10000} />
          </div>
        </div>

        {/* 运行按钮 */}
        <div className="p-6 border-t border-[#30363d] space-y-3">
          <button
            onClick={() => void runBacktest()}
            disabled={running}
            className="w-full h-10 bg-white text-black font-bold rounded-lg hover:bg-[#e1e4e8] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm"
          >
            {running ? (
              <><RefreshCw className="w-4 h-4 animate-spin" />
                {status === "fetchingBars" ? "拉取 K 线…" : "运行中…"}</>
            ) : (
              <><Play className="w-4 h-4 fill-current" />运行回测</>
            )}
          </button>
          {running && (
            <button onClick={() => abortRef.current?.abort()}
              className="w-full h-8 text-xs text-[#8b949e] hover:text-white border border-[#30363d] rounded-lg transition-colors">
              取消
            </button>
          )}
        </div>
      </aside>

      {/* ── 右侧结果区 */}
      <main className="flex-1 overflow-y-auto p-8">
        {status === "idle" && (
          <div className="h-full flex flex-col items-center justify-center text-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-[#161b22] border border-[#30363d] flex items-center justify-center">
              <BarChart3 className="w-8 h-8 text-[#8b949e]" />
            </div>
            <div>
              <p className="text-white font-semibold text-lg">配置并运行 MA Crossover 回测</p>
              <p className="text-[#8b949e] text-sm mt-1">支持美股、ETF、港股、A 股与 OKX 加密标的</p>
            </div>
            <p className="text-[10px] text-[#434651] font-mono">缺少 K 线时会通过 OKX 数据层自动拉取</p>
          </div>
        )}

        {(status === "fetchingBars" || status === "running") && (
          <div className="h-full flex flex-col items-center justify-center gap-6">
            <RefreshCw className="w-10 h-10 text-blue-400 animate-spin" />
            <div className="text-center">
              <p className="text-white font-semibold">
                {status === "fetchingBars" ? "正在获取历史 K 线数据…" : "回测运行中…"}
              </p>
              <p className="text-[#8b949e] text-sm mt-1">{symbol} · {timeframe} · {limit} 根 K 线</p>
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="h-full flex flex-col items-center justify-center gap-4">
            <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center">
              <ShieldAlert className="w-7 h-7 text-red-400" />
            </div>
            <div className="text-center max-w-md">
              <p className="text-red-400 font-semibold mb-2">回测失败</p>
              <p className="text-[#8b949e] text-sm leading-relaxed">{errorMsg}</p>
            </div>
            <button onClick={() => setStatus("idle")} className="text-xs text-[#8b949e] hover:text-white underline">返回配置</button>
          </div>
        )}

        {status === "done" && result && (
          <div className="space-y-8">
            <div className="flex items-end justify-between">
              <div>
                <div className="flex items-center gap-2 text-[10px] font-bold text-[#8b949e] uppercase tracking-[0.2em] mb-1">
                  <History className="w-3 h-3" />回测结果
                </div>
                <h2 className="text-3xl font-bold text-white">
                  MA({result.fast_period},{result.slow_period}) · {result.symbol}
                </h2>
                <p className="text-[#8b949e] text-sm mt-0.5">
                  {result.bars_processed} 根 K 线 · {result.metrics.trading_days} 交易日
                </p>
              </div>
              <button onClick={() => setStatus("idle")}
                className="text-xs text-[#8b949e] hover:text-white border border-[#30363d] rounded-lg px-3 py-2 transition-colors">
                重新配置
              </button>
            </div>

            {/* 权益曲线 */}
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
              <div className="px-6 py-3 border-b border-[#30363d]">
                <h3 className="text-[10px] font-bold text-[#8b949e] uppercase tracking-wider">权益曲线</h3>
              </div>
              <div className="px-4 py-3">
                <EquityCurveChart
                  data={result.equity_curve}
                  initialCash={result.metrics.initial_cash}
                />
              </div>
            </div>

            {/* 核心指标 */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <MetricTile label="总收益率" value={pct(result.metrics.total_return)} sub="策略期间总回报"
                color={result.metrics.total_return >= 0 ? "text-green-400" : "text-red-400"}
                icon={result.metrics.total_return >= 0 ? TrendingUp : TrendingDown} />
              <MetricTile label="年化收益率" value={pct(result.metrics.annual_return)} sub="等效年化"
                color={result.metrics.annual_return >= 0 ? "text-green-400" : "text-red-400"} icon={Percent} />
              <MetricTile label="最大回撤" value={pct(result.metrics.max_drawdown)} sub="最大峰谷跌幅"
                color="text-red-400" icon={ShieldAlert} />
              <MetricTile label="夏普比率" value={result.metrics.sharpe_ratio.toFixed(3)} sub="风险调整后收益"
                color={result.metrics.sharpe_ratio >= 1 ? "text-green-400" : result.metrics.sharpe_ratio >= 0 ? "text-yellow-400" : "text-red-400"}
                icon={BarChart3} />
              <MetricTile label="胜率" value={pct(result.metrics.win_rate)}
                sub={`${result.metrics.win_trades}W / ${result.metrics.loss_trades}L`}
                color={result.metrics.win_rate >= 0.5 ? "text-green-400" : "text-orange-400"} />
              <MetricTile label="交易次数" value={String(result.metrics.total_trades)} sub="期间完整交易" />
            </div>

            {/* 详细指标 */}
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-[#30363d]">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">详细绩效指标</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-[#30363d]">
                <div className="divide-y divide-[#30363d]">
                  {[
                    ["Sortino 比率", result.metrics.sortino_ratio >= 9990 ? "∞" : result.metrics.sortino_ratio.toFixed(3)],
                    ["Calmar 比率", result.metrics.calmar_ratio.toFixed(3)],
                    ["年化波动率", pct(result.metrics.volatility)],
                    ["盈利因子", result.metrics.profit_factor >= 9990 ? "∞" : result.metrics.profit_factor.toFixed(3)],
                    ["平均盈利", money(result.metrics.avg_win)],
                    ["平均亏损", money(result.metrics.avg_loss)],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between items-center px-6 py-3">
                      <span className="text-xs text-[#8b949e]">{k}</span>
                      <span className="text-xs font-mono text-white">{v}</span>
                    </div>
                  ))}
                </div>
                <div className="divide-y divide-[#30363d]">
                  {[
                    ["初始资金", money(result.metrics.initial_cash)],
                    ["最终净值", money(result.metrics.final_value)],
                    ["净利润", money(result.metrics.final_value - result.metrics.initial_cash)],
                    ["交易天数", `${result.metrics.trading_days} 天`],
                    ["起始日期", result.metrics.start_date?.split("T")[0] ?? "—"],
                    ["结束日期", result.metrics.end_date?.split("T")[0] ?? "—"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between items-center px-6 py-3">
                      <span className="text-xs text-[#8b949e]">{k}</span>
                      <span className="text-xs font-mono text-white">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

/**
 * 参数优化面板 — MA crossover 网格搜索（接 POST /api/optimize）.
 */
import { useState } from "react";
import { Settings2, Play, RefreshCw, ShieldAlert, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

// ── 数据类型 ──────────────────────────────────────────────────────────────────

interface OptimizeResult {
  fast_period: number;
  slow_period: number;
  sharpe_ratio: number;
  total_return: number;
  max_drawdown: number;
}

interface OptimizeResponse {
  total_combinations: number;
  results: OptimizeResult[];
}

// ── 样式 token ────────────────────────────────────────────────────────────────

const INPUT_CLS =
  "w-full h-9 bg-[#161b22] border border-[#30363d] rounded-lg px-3 text-sm text-white outline-none focus:border-blue-500/50 transition-colors placeholder-[#8b949e]/50";

// ── 工具函数 ──────────────────────────────────────────────────────────────────

function parseInts(s: string): number[] {
  return s
    .split(",")
    .map((v) => parseInt(v.trim(), 10))
    .filter((v) => !isNaN(v) && v > 0);
}

// ── 主组件 ────────────────────────────────────────────────────────────────────

export default function OptimizationPanel() {
  // ── 配置状态
  const [symbol, setSymbol] = useState("BTC-USDT");
  const [timeframe, setTimeframe] = useState("1d");
  const [limit, setLimit] = useState(300);
  const [fastPeriodsStr, setFastPeriodsStr] = useState("5, 10, 15, 20");
  const [slowPeriodsStr, setSlowPeriodsStr] = useState("30, 50, 100");
  const [initialCash, setInitialCash] = useState(1_000_000);
  const [topN, setTopN] = useState(10);

  // ── 运行状态
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<"idle" | "fetchingBars" | "running" | "done" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [response, setResponse] = useState<OptimizeResponse | null>(null);

  const runOptimize = async () => {
    setRunning(true);
    setStatus("fetchingBars");
    setErrorMsg("");
    setResponse(null);

    try {
      // Step 1: 拉 K 线
      const barsRes = await fetch(
        `/api/data/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`,
      );
      if (!barsRes.ok) throw new Error(`获取 K 线失败: ${await barsRes.text()}`);

      const barsJson = (await barsRes.json()) as { bars: Array<{ close: number }> };
      if (!barsJson.bars || barsJson.bars.length < 2) {
        throw new Error("K 线数据不足，请先拉取历史数据");
      }
      const closes = barsJson.bars.map((b) => b.close);

      setStatus("running");

      // Step 2: 网格搜索
      const req = {
        closes,
        initial_cash: initialCash,
        fast_periods: parseInts(fastPeriodsStr),
        slow_periods: parseInts(slowPeriodsStr),
        top_n: topN,
      };

      const optRes = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!optRes.ok) throw new Error(`优化失败: ${await optRes.text()}`);

      const data = (await optRes.json()) as OptimizeResponse;
      setResponse(data);
      setStatus("done");
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setStatus("error");
    } finally {
      setRunning(false);
    }
  };

  const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

  return (
    <div
      className="relative flex bg-[#0d1117] rounded-xl overflow-hidden border border-[#30363d]"
      style={{ height: "calc(100vh - 120px)" }}
    >
      {/* 左侧配置 */}
      <aside className="w-72 shrink-0 border-r border-[#30363d] bg-[#0d1117] flex flex-col">
        <div className="px-6 pt-8 pb-6 border-b border-[#30363d]">
          <div className="flex items-center gap-2 text-[10px] font-bold text-[#8b949e] uppercase tracking-[0.2em] mb-2">
            <Settings2 className="w-3 h-3" />
            参数优化
          </div>
          <h1 className="text-2xl font-bold text-white">网格搜索</h1>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">标的代码</label>
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} className={INPUT_CLS} placeholder="BTC-USDT" />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">K 线周期</label>
            <input value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className={INPUT_CLS} placeholder="1d" />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">
              K 线数量 <span className="text-blue-400 font-mono">{limit}</span>
            </label>
            <input type="range" min={50} max={1000} step={50} value={limit}
              onChange={(e) => setLimit(Number(e.target.value))} className="w-full accent-blue-500" />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">快线周期列表（逗号分隔）</label>
            <input value={fastPeriodsStr} onChange={(e) => setFastPeriodsStr(e.target.value)} className={INPUT_CLS} placeholder="5, 10, 15, 20" />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">慢线周期列表（逗号分隔）</label>
            <input value={slowPeriodsStr} onChange={(e) => setSlowPeriodsStr(e.target.value)} className={INPUT_CLS} placeholder="30, 50, 100" />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">初始资金 ($)</label>
            <input type="number" value={initialCash} onChange={(e) => setInitialCash(Number(e.target.value))} className={INPUT_CLS} step={100000} min={10000} />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-[#8b949e] tracking-wider block">Top N 结果</label>
            <input type="number" value={topN} onChange={(e) => setTopN(Number(e.target.value))} className={INPUT_CLS} min={1} max={100} />
          </div>
        </div>

        <div className="p-6 border-t border-[#30363d]">
          <button onClick={() => void runOptimize()} disabled={running}
            className="w-full h-10 bg-white text-black font-bold rounded-lg hover:bg-[#e1e4e8] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm">
            {running ? <><RefreshCw className="w-4 h-4 animate-spin" />{status === "fetchingBars" ? "拉取 K 线…" : "搜索中…"}</>
              : <><Play className="w-4 h-4 fill-current" />开始优化</>}
          </button>
        </div>
      </aside>

      {/* 右侧结果 */}
      <main className="flex-1 overflow-y-auto p-8">
        {status === "idle" && (
          <div className="h-full flex flex-col items-center justify-center text-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-[#161b22] border border-[#30363d] flex items-center justify-center">
              <Settings2 className="w-8 h-8 text-[#8b949e]" />
            </div>
            <div>
              <p className="text-white font-semibold text-lg">MA Crossover 参数网格搜索</p>
              <p className="text-[#8b949e] text-sm mt-1">设置快线/慢线周期列表，按 Sharpe 排序找最优参数</p>
            </div>
          </div>
        )}

        {(status === "fetchingBars" || status === "running") && (
          <div className="h-full flex flex-col items-center justify-center gap-6">
            <RefreshCw className="w-10 h-10 text-blue-400 animate-spin" />
            <p className="text-white font-semibold">
              {status === "fetchingBars" ? "正在获取 K 线…" : "网格搜索中…"}
            </p>
          </div>
        )}

        {status === "error" && (
          <div className="h-full flex flex-col items-center justify-center gap-4">
            <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center">
              <ShieldAlert className="w-7 h-7 text-red-400" />
            </div>
            <div className="text-center max-w-md">
              <p className="text-red-400 font-semibold mb-2">优化失败</p>
              <p className="text-[#8b949e] text-sm">{errorMsg}</p>
            </div>
            <button onClick={() => setStatus("idle")} className="text-xs text-[#8b949e] hover:text-white underline">返回配置</button>
          </div>
        )}

        {status === "done" && response && (
          <div className="space-y-6">
            <div>
              <div className="flex items-center gap-2 text-[10px] font-bold text-[#8b949e] uppercase tracking-[0.2em] mb-1">
                <TrendingUp className="w-3 h-3" />优化结果
              </div>
              <h2 className="text-3xl font-bold text-white">{symbol} · MA Crossover</h2>
              <p className="text-[#8b949e] text-sm mt-0.5">
                共 {response.total_combinations} 组合，按 Sharpe 降序，展示 Top {response.results.length}
              </p>
            </div>

            <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#30363d]">
                    {["排名", "快线", "慢线", "Sharpe", "总收益率", "最大回撤"].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-[10px] font-bold text-[#8b949e] uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {response.results.map((r, i) => (
                    <tr key={i} className={cn("border-b border-[#30363d] last:border-0", i === 0 && "bg-blue-950/30")}>
                      <td className="px-4 py-3 text-[#8b949e] font-mono text-xs">#{i + 1}</td>
                      <td className="px-4 py-3 text-white font-mono text-xs">{r.fast_period}</td>
                      <td className="px-4 py-3 text-white font-mono text-xs">{r.slow_period}</td>
                      <td className={cn("px-4 py-3 font-mono text-xs font-bold",
                        r.sharpe_ratio >= 1 ? "text-green-400" : r.sharpe_ratio >= 0 ? "text-yellow-400" : "text-red-400")}>
                        {r.sharpe_ratio.toFixed(3)}
                      </td>
                      <td className={cn("px-4 py-3 font-mono text-xs",
                        r.total_return >= 0 ? "text-green-400" : "text-red-400")}>
                        {pct(r.total_return)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-orange-400">{pct(r.max_drawdown)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

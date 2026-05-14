import { Scale, Target } from "lucide-react";
import { useEffect, useState } from "react";

import {
  fetchCryptoOpportunities,
  fetchCryptoResearchLatest,
  fetchCryptoResearchLatestOptimization,
  fetchCryptoResearchOptimization,
  fetchCryptoRisks,
  type AdvisorCard,
  type AdvisorCryptoOptimizationSummary,
  type AdvisorCryptoResearchSummary,
} from "../api/client";
import { cn } from "../lib/utils";
import { EmptyState, ErrorOrEmptyState, LoadingState } from "./ui/StateMessages";

function ToneBadge({ type }: { type: string }) {
  const isRisk = /risk|hazard|warning/i.test(type);
  return (
    <span
      className={cn(
        "px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase",
        isRisk
          ? "bg-red-500/20 text-red-400 border-red-500/40"
          : "bg-green-500/20 text-green-400 border-green-500/40",
      )}
    >
      {isRisk ? "降险" : "进取"}
    </span>
  );
}

/**
 * Minimal rebalance suggestion view composed from advisor cards.
 */
export function RebalanceSuggestions() {
  const [suggestions, setSuggestions] = useState<AdvisorCard[]>([]);
  const [research, setResearch] = useState<Record<string, AdvisorCryptoResearchSummary>>({});
  const [optimizations, setOptimizations] = useState<
    Record<string, AdvisorCryptoOptimizationSummary>
  >({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [
          btcOpportunities,
          btcRisks,
          ethOpportunities,
          ethRisks,
          btcResearch,
          ethResearch,
          btcOptimization,
          ethOptimization,
        ] = await Promise.all([
          fetchCryptoOpportunities<{ items: AdvisorCard[] }>("BTC-USDT"),
          fetchCryptoRisks<{ items: AdvisorCard[] }>("BTC-USDT"),
          fetchCryptoOpportunities<{ items: AdvisorCard[] }>("ETH-USDT"),
          fetchCryptoRisks<{ items: AdvisorCard[] }>("ETH-USDT"),
          fetchCryptoResearchLatest<AdvisorCryptoResearchSummary>("BTC-USDT"),
          fetchCryptoResearchLatest<AdvisorCryptoResearchSummary>("ETH-USDT"),
          fetchCryptoResearchLatestOptimization<AdvisorCryptoOptimizationSummary>(
            "BTC-USDT",
            "vwap_ema_trend",
          ).catch(() =>
            fetchCryptoResearchOptimization<AdvisorCryptoOptimizationSummary>("BTC-USDT"),
          ),
          fetchCryptoResearchLatestOptimization<AdvisorCryptoOptimizationSummary>(
            "ETH-USDT",
            "vwap_ema_trend",
          ).catch(() =>
            fetchCryptoResearchOptimization<AdvisorCryptoOptimizationSummary>("ETH-USDT"),
          ),
        ]);
        setSuggestions([
          ...btcOpportunities.items,
          ...btcRisks.items,
          ...ethOpportunities.items,
          ...ethRisks.items,
        ]);
        setResearch({
          "BTC-USDT": btcResearch,
          "ETH-USDT": ethResearch,
        });
        setOptimizations({
          "BTC-USDT": btcOptimization,
          "ETH-USDT": ethOptimization,
        });
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <section aria-labelledby="rebalance-suggestions-title" className="space-y-4">
      <div>
        <h2
          id="rebalance-suggestions-title"
          className="text-white text-lg font-bold flex items-center gap-2"
        >
          <Scale size={18} className="text-[#00C087]" />
          调仓建议
        </h2>
        <p className="text-[#8E9299] text-sm mt-1">
          基于 BTC / ETH 研究结果生成最小可执行的观察/降风险建议。
        </p>
      </div>

      {loading && <LoadingState />}
      {!loading && error && <ErrorOrEmptyState error={error} />}
      {!loading && !error && suggestions.length === 0 && (
        <EmptyState message="当前没有调仓建议。" />
      )}

      {!loading && !error && suggestions.length > 0 && (
        <ul className="space-y-3 list-none p-0">
          {suggestions.map((item, index) => (
            <li
              key={`${item.type}-${item.subject}-${index}`}
              className="bg-[#151619] border border-[#2A2D35] rounded-xl p-4 hover:border-[#00C087]/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <Target size={14} className="text-[#00C087]" />
                  <span className="text-white font-bold">{item.subject}</span>
                </div>
                <ToneBadge type={item.type} />
              </div>
              <div className="text-white text-sm mt-2">
                {item.recommendation}
                <span className="text-[#8E9299] ml-2 text-xs">
                  ({(item.confidence * 100).toFixed(1)}%)
                </span>
              </div>
              {item.evidence[0]?.summary && (
                <div className="text-[#8E9299] text-xs mt-2">📌 {item.evidence[0].summary}</div>
              )}
              {item.risk_notes[0] && (
                <div className="text-yellow-400/80 text-xs mt-1">⚠ {item.risk_notes[0]}</div>
              )}
              <div className="text-[#8E9299] text-xs mt-2 flex flex-wrap gap-x-4 gap-y-1">
                <span>
                  状态:{" "}
                  <span className="text-white">{research[item.subject]?.market_regime ?? "—"}</span>
                </span>
                <span>
                  推荐策略:{" "}
                  <span className="text-white">
                    {research[item.subject]?.recommended_strategy_ids.join(" / ") ?? "—"}
                  </span>
                </span>
                <span>
                  推荐周期:{" "}
                  <span className="text-white">
                    {research[item.subject]?.recommended_timeframes.join(" / ") ?? "—"}
                  </span>
                </span>
              </div>
              {optimizations[item.subject] && (
                <div className="text-[#8E9299] text-xs mt-1 font-mono">
                  最优参数:{" "}
                  <span className="text-[#00C087]">
                    {Object.entries(optimizations[item.subject].best_params)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(", ")}
                  </span>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

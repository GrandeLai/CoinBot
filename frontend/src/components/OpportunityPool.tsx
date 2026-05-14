import { ListTree, Target, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

import {
  fetchCryptoOpportunities,
  fetchCryptoResearchLatest,
  fetchCryptoResearchLatestOptimization,
  fetchCryptoResearchOptimization,
  type AdvisorCard,
  type AdvisorCryptoOptimizationSummary,
  type AdvisorCryptoResearchSummary,
} from "../api/client";
import { cn } from "../lib/utils";
import { EmptyState, ErrorOrEmptyState, LoadingState } from "./ui/StateMessages";

function ConfidenceBadge({ value }: { value: number }) {
  const pct = value * 100;
  const tone =
    pct >= 70
      ? "bg-green-500/20 text-green-400 border-green-500/40"
      : pct >= 50
      ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/40"
      : "bg-gray-500/20 text-gray-300 border-gray-500/40";
  return (
    <span className={cn("px-2 py-0.5 rounded-full border text-[10px] font-bold", tone)}>
      {pct.toFixed(0)}%
    </span>
  );
}

/**
 * Crypto opportunity pool view backed by advisor cards.
 */
export function OpportunityPool() {
  const [items, setItems] = useState<AdvisorCard[]>([]);
  const [research, setResearch] = useState<Record<string, AdvisorCryptoResearchSummary>>({});
  const [optimizations, setOptimizations] = useState<
    Record<string, AdvisorCryptoOptimizationSummary>
  >({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [btc, eth, btcResearch, ethResearch] = await Promise.all([
          fetchCryptoOpportunities<{ items: AdvisorCard[] }>("BTC-USDT"),
          fetchCryptoOpportunities<{ items: AdvisorCard[] }>("ETH-USDT"),
          fetchCryptoResearchLatest<AdvisorCryptoResearchSummary>("BTC-USDT"),
          fetchCryptoResearchLatest<AdvisorCryptoResearchSummary>("ETH-USDT"),
        ]);
        setItems(
          [...btc.items, ...eth.items].sort(
            (left, right) => right.confidence - left.confidence,
          ),
        );
        setResearch({
          "BTC-USDT": btcResearch,
          "ETH-USDT": ethResearch,
        });
        const optimizationEntries = await Promise.all(
          ["BTC-USDT", "ETH-USDT"].map(async (symbol) => {
            try {
              return [
                symbol,
                await fetchCryptoResearchLatestOptimization<AdvisorCryptoOptimizationSummary>(
                  symbol,
                  "vwap_ema_trend",
                ),
              ] as const;
            } catch {
              try {
                return [
                  symbol,
                  await fetchCryptoResearchOptimization<AdvisorCryptoOptimizationSummary>(symbol),
                ] as const;
              } catch {
                return [symbol, null] as const;
              }
            }
          }),
        );
        setOptimizations(
          Object.fromEntries(
            optimizationEntries.filter(
              (entry): entry is readonly [string, AdvisorCryptoOptimizationSummary] =>
                entry[1] !== null,
            ),
          ),
        );
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <section aria-labelledby="opportunity-pool-title" className="space-y-4">
      <div>
        <h2
          id="opportunity-pool-title"
          className="text-white text-lg font-bold flex items-center gap-2"
        >
          <ListTree size={18} className="text-[#00C087]" />
          机会池
        </h2>
        <p className="text-[#8E9299] text-sm mt-1">
          集中浏览 BTC / ETH 的多周期机会卡片，按置信度倒序。
        </p>
      </div>

      {loading && <LoadingState />}
      {!loading && error && <ErrorOrEmptyState error={error} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState message="当前没有可见的机会信号。" />
      )}

      {!loading && !error && items.length > 0 && (
        <ul className="space-y-3 list-none p-0">
          {items.map((item) => (
            <li
              key={`${item.type}-${item.subject}`}
              className="bg-[#151619] border border-[#2A2D35] rounded-xl p-4 hover:border-[#00C087]/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <Target size={14} className="text-[#00C087]" />
                  <span className="text-white font-bold">{item.subject}</span>
                  <span className="text-[#8E9299] text-xs font-mono uppercase">
                    {item.type}
                  </span>
                </div>
                <ConfidenceBadge value={item.confidence} />
              </div>
              <div className="text-white text-sm mt-2">{item.recommendation}</div>
              {item.evidence[0]?.summary && (
                <div className="text-[#8E9299] text-xs mt-2">
                  📌 {item.evidence[0].summary}
                </div>
              )}
              <div className="text-[#8E9299] text-xs mt-2 flex flex-wrap gap-x-4 gap-y-1">
                <span>
                  状态: <span className="text-white">{research[item.subject]?.market_regime ?? "—"}</span>
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
              {item.risk_notes[0] && (
                <div className="text-yellow-400/80 text-xs mt-2 flex items-start gap-1">
                  <TrendingUp size={11} className="mt-0.5 shrink-0" />
                  <span>{item.risk_notes[0]}</span>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

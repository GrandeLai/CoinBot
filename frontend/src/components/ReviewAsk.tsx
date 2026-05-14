import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import {
  fetchCryptoOpportunities,
  fetchCryptoResearchLatest,
  fetchCryptoResearchLatestOptimization,
  fetchCryptoResearchOptimization,
  fetchCryptoRisks,
  fetchOverview,
  type AdvisorCard,
  type AdvisorCryptoOptimizationSummary,
  type AdvisorCryptoResearchSummary,
  type AdvisorOverviewPayload,
} from "../api/client";
import {
  ErrorOrEmptyState,
  KPICard,
  LoadingState,
} from "./ui/StateMessages";

/**
 * Minimal review view backed by current overview and advisor card summaries.
 */
export function ReviewAsk() {
  const [overview, setOverview] = useState<AdvisorOverviewPayload | null>(null);
  const [opportunities, setOpportunities] = useState<AdvisorCard[]>([]);
  const [risks, setRisks] = useState<AdvisorCard[]>([]);
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
          overviewData,
          btcOpportunities,
          btcRisks,
          ethOpportunities,
          ethRisks,
          btcResearch,
          ethResearch,
          btcOptimization,
          ethOptimization,
        ] = await Promise.all([
          fetchOverview<AdvisorOverviewPayload>(),
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
        setOverview(overviewData);
        setOpportunities([...btcOpportunities.items, ...ethOpportunities.items]);
        setRisks([...btcRisks.items, ...ethRisks.items]);
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
    <section aria-labelledby="review-ask-title" className="space-y-4">
      <div>
        <h2
          id="review-ask-title"
          className="text-white text-lg font-bold flex items-center gap-2"
        >
          <Sparkles size={18} className="text-[#00C087]" />
          复盘与问答
        </h2>
        <p className="text-[#8E9299] text-sm mt-1">
          基于当前概览与研究结果，形成最小复盘摘要。
        </p>
      </div>

      {loading && <LoadingState />}
      {!loading && error && <ErrorOrEmptyState error={error} />}

      {!loading && !error && overview && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KPICard
              title="净资产"
              value={overview.net_worth.toLocaleString("en-US", {
                maximumFractionDigits: 2,
              })}
              subValue="USD"
            />
            <KPICard
              title="现金占比"
              value={`${(overview.cash_ratio * 100).toFixed(1)}%`}
            />
            <KPICard title="高优先机会" value={String(opportunities.length)} />
            <KPICard title="高优先风险" value={String(risks.length)} />
          </div>

          <div className="bg-[#151619] border border-[#2A2D35] rounded-xl p-4 space-y-2 text-sm">
            <div className="text-[#8E9299] text-[11px] font-bold uppercase tracking-wider mb-1">
              复盘摘要
            </div>
            <div>
              <span className="text-[#8E9299]">高优先机会：</span>
              <span className="text-white">{opportunities[0]?.subject ?? "—"}</span>
            </div>
            <div>
              <span className="text-[#8E9299]">高优先风险：</span>
              <span className="text-white">{risks[0]?.subject ?? "—"}</span>
            </div>
            <div>
              <span className="text-[#8E9299]">BTC：</span>
              <span className="text-white">
                {research["BTC-USDT"]?.market_regime ?? "—"} ·{" "}
                {research["BTC-USDT"]?.recommended_strategy_ids.join(" / ") ?? "—"}
              </span>
            </div>
            <div>
              <span className="text-[#8E9299]">ETH：</span>
              <span className="text-white">
                {research["ETH-USDT"]?.market_regime ?? "—"} ·{" "}
                {research["ETH-USDT"]?.recommended_strategy_ids.join(" / ") ?? "—"}
              </span>
            </div>
            {optimizations["BTC-USDT"] && (
              <div className="font-mono text-xs">
                <span className="text-[#8E9299]">BTC 最优参数：</span>
                <span className="text-[#00C087]">
                  {Object.entries(optimizations["BTC-USDT"].best_params)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(", ")}
                </span>
              </div>
            )}
            <div className="pt-2 border-t border-[#2A2D35] mt-2">
              <span className="text-[#8E9299]">当前复盘结论：</span>
              <span className="text-white">
                {risks.length > 0
                  ? `优先关注 ${risks[0].subject} 的风险信号（${risks[0].recommendation}）。`
                  : "暂无高优先风险。"}
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

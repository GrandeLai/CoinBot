import { Briefcase, Coins, TrendingUp, Wallet } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchOverview, type AdvisorOverviewPayload } from "../api/client";
import { ErrorOrEmptyState, KPICard, LoadingState } from "./ui/StateMessages";

/**
 * Advisor overview backed by the shared backend snapshot.
 */
export function PortfolioOverview() {
  const [overview, setOverview] = useState<AdvisorOverviewPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setOverview(await fetchOverview<AdvisorOverviewPayload>());
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <section aria-labelledby="portfolio-overview-title" className="space-y-4">
      <div>
        <h2
          id="portfolio-overview-title"
          className="text-white text-lg font-bold flex items-center gap-2"
        >
          <Briefcase size={18} className="text-[#00C087]" />
          资产总览
        </h2>
        <p className="text-[#8E9299] text-sm mt-1">
          查看共享后端输出的净值、现金占比和当前持仓快照。
        </p>
      </div>

      {loading && <LoadingState />}
      {!loading && error && <ErrorOrEmptyState error={error} />}

      {overview && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
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
              subValue={overview.cash_ratio >= 0.5 ? "防守偏高" : overview.cash_ratio >= 0.2 ? "均衡" : "进攻偏高"}
            />
            <KPICard
              title="持仓数量"
              value={String(overview.positions.length)}
              subValue="标的"
            />
            <KPICard
              title="资产姿态"
              value={
                overview.cash_ratio >= 0.5
                  ? "防守"
                  : overview.cash_ratio >= 0.2
                  ? "均衡"
                  : "进攻"
              }
              subValue={overview.generated_at}
            />
          </div>

          {overview.positions.length > 0 && (
            <div className="bg-[#151619] border border-[#2A2D35] rounded-xl overflow-hidden">
              <div className="px-4 py-2 bg-[#1C1E22] text-[#8E9299] text-[11px] font-bold uppercase flex items-center gap-2">
                <Coins size={12} />
                当前持仓
              </div>
              <div className="divide-y divide-[#2A2D35]">
                {overview.positions.map((pos, i) => {
                  const symbol = String(pos.symbol ?? pos.ticker ?? `position_${i}`);
                  const value = pos.value ?? pos.market_value ?? pos.notional;
                  return (
                    <div
                      key={`${symbol}-${i}`}
                      className="px-4 py-2.5 flex items-center justify-between text-sm"
                    >
                      <span className="text-white font-mono">{symbol}</span>
                      <span className="text-[#8E9299] font-mono text-xs">
                        {value !== undefined && value !== null
                          ? Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 })
                          : JSON.stringify(pos)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 text-[#8E9299] text-xs">
            <TrendingUp size={12} />
            <span>
              <Wallet size={12} className="inline mr-1" />
              数据来自 advisor overview 快照（非实时）
            </span>
          </div>
        </div>
      )}
    </section>
  );
}

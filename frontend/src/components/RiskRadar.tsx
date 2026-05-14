import { ShieldAlert, AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchCryptoRisks, type AdvisorCard } from "../api/client";
import { cn } from "../lib/utils";
import { EmptyState, ErrorOrEmptyState, LoadingState } from "./ui/StateMessages";

function RiskBadge({ value }: { value: number }) {
  const pct = value * 100;
  const tone =
    pct >= 70
      ? "bg-red-500/20 text-red-400 border-red-500/40"
      : pct >= 40
      ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/40"
      : "bg-gray-500/20 text-gray-300 border-gray-500/40";
  return (
    <span className={cn("px-2 py-0.5 rounded-full border text-[10px] font-bold", tone)}>
      {pct.toFixed(0)}%
    </span>
  );
}

/**
 * Crypto risk radar view backed by advisor risk cards.
 */
export function RiskRadar() {
  const [items, setItems] = useState<AdvisorCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [btc, eth] = await Promise.all([
          fetchCryptoRisks<{ items: AdvisorCard[] }>("BTC-USDT"),
          fetchCryptoRisks<{ items: AdvisorCard[] }>("ETH-USDT"),
        ]);
        setItems([...btc.items, ...eth.items]);
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <section aria-labelledby="risk-radar-title" className="space-y-4">
      <div>
        <h2
          id="risk-radar-title"
          className="text-white text-lg font-bold flex items-center gap-2"
        >
          <ShieldAlert size={18} className="text-[#00C087]" />
          风险雷达
        </h2>
        <p className="text-[#8E9299] text-sm mt-1">
          聚合 BTC / ETH 的多周期趋势衰竭、反转概率与持仓分歧风险。
        </p>
      </div>

      {loading && <LoadingState />}
      {!loading && error && <ErrorOrEmptyState error={error} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState message="当前没有捕捉到高优先级风险。" />
      )}

      {!loading && !error && items.length > 0 && (
        <ul className="space-y-3 list-none p-0">
          {items.map((item, index) => (
            <li
              key={`${item.type}-${item.subject}-${index}`}
              className="bg-[#151619] border border-[#2A2D35] rounded-xl p-4 hover:border-red-500/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={14} className="text-red-400" />
                  <span className="text-white font-bold">{item.subject}</span>
                  <span className="text-[#8E9299] text-xs font-mono uppercase">
                    {item.type}
                  </span>
                </div>
                <RiskBadge value={item.confidence} />
              </div>
              <div className="text-white text-sm mt-2">{item.recommendation}</div>
              {item.evidence[0]?.summary && (
                <div className="text-[#8E9299] text-xs mt-2">📌 {item.evidence[0].summary}</div>
              )}
              {item.risk_notes[0] && (
                <div className="text-yellow-400/80 text-xs mt-1">⚠ {item.risk_notes[0]}</div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

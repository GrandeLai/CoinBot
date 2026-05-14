import { useEffect, useState } from "react";

import {
  fetchCryptoResearchLatestOptimization,
  fetchCryptoResearchLatestSummary,
  fetchCryptoResearchOptimization,
  fetchCryptoResearchSummary,
  type CryptoResearchOptimizationSummary,
  type CryptoResearchSummary,
} from "../api/client";
import { buildCryptoResearchViewModel } from "./cryptoResearchViewModel";

export default function CryptoResearchPanel() {
  const [summaries, setSummaries] = useState<CryptoResearchSummary[]>([]);
  const [optimizations, setOptimizations] = useState<Record<string, CryptoResearchOptimizationSummary>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const result = await Promise.all(
          ["BTC-USDT", "ETH-USDT"].map(async (symbol) => {
            try {
              return await fetchCryptoResearchLatestSummary(symbol);
            } catch {
              return fetchCryptoResearchSummary(symbol);
            }
          })
        );
        setSummaries(result);
        const optimizationEntries = await Promise.all(
          ["BTC-USDT", "ETH-USDT"].map(async (symbol) => {
            try {
              return [symbol, await fetchCryptoResearchLatestOptimization(symbol, "vwap_ema_trend")] as const;
            } catch {
              try {
                return [symbol, await fetchCryptoResearchOptimization(symbol)] as const;
              } catch {
                return [symbol, null] as const;
              }
            }
          })
        );
        setOptimizations(
          Object.fromEntries(
            optimizationEntries.filter((entry): entry is readonly [string, CryptoResearchOptimizationSummary] => entry[1] !== null)
          )
        );
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <section className="rounded-xl border border-[#30363d] bg-[#0d1117] p-5 space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white">加密 ML 验证摘要</h2>
        <p className="text-sm text-[#8b949e]">BTC / ETH 多周期研究、walk-forward 与反转识别结果。</p>
      </div>
      {loading ? <div className="text-sm text-[#8b949e]">加载中…</div> : null}
      {error ? <div className="text-sm text-red-400">{error}</div> : null}
      {!loading && !error ? (
        <div className="grid gap-4 md:grid-cols-2">
          {summaries.map((summary) => {
            const view = buildCryptoResearchViewModel(summary);
            const optimization = optimizations[summary.symbol];
            return (
            <div key={summary.symbol} className="rounded-lg border border-[#2a2e39] bg-[#161b22] p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-white">{summary.symbol}</span>
                <span className="text-xs text-[#8b949e]">{summary.validation_windows} 窗口</span>
              </div>
              <div className="text-sm text-[#c9d1d9]">特征数：{summary.feature_count}</div>
              <div className="text-xs text-[#8b949e]">样本数：{summary.rows} · 均值准确率 {(summary.mean_accuracy * 100).toFixed(1)}%</div>
              <div className="text-xs text-[#8b949e]">均值策略收益：{(summary.mean_strategy_return * 100).toFixed(2)}%</div>
              <div className="text-xs text-[#8b949e]">
                最新类别概率：空 {((summary.latest_class_probabilities["-1"] ?? 0) * 100).toFixed(1)}% / 横 {((
                  summary.latest_class_probabilities["0"] ?? 0
                ) * 100).toFixed(1)}% / 多 {((summary.latest_class_probabilities["1"] ?? 0) * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-[#8b949e]">当前方向解释：{view.directionLabel}</div>
              <div className="text-xs text-[#8b949e]">市场状态：{summary.market_regime}</div>
              <div className="text-xs text-[#8b949e]">推荐策略：{summary.recommended_strategy_ids.join(" / ")}</div>
              <div className="text-xs text-[#8b949e]">推荐周期：{summary.recommended_timeframes.join(" / ")}</div>
              <div className="text-xs text-[#8b949e]">反转概率：{(summary.reversal_probability * 100).toFixed(1)}% · 信号 {summary.reversal_signal}</div>
              <div className="text-xs text-[#8b949e]">关键证据：{summary.reversal_evidence.join(" / ") || "—"}</div>
              <div className="pt-2 border-t border-[#2a2e39]">
                <div className="text-xs font-medium text-white mb-2">Top 因子重要性</div>
                <ul className="space-y-1 text-xs text-[#8b949e]">
                  {view.topFactors.map((item) => (
                      <li key={item.name} className="flex items-center justify-between gap-2">
                        <span className="truncate">{item.name}</span>
                        <span className="font-mono text-white">{item.valuePct}</span>
                      </li>
                    ))}
                </ul>
              </div>
              <div className="pt-2 border-t border-[#2a2e39]">
                <div className="text-xs font-medium text-white mb-2">窗口表现</div>
                <ul className="space-y-1 text-xs text-[#8b949e]">
                  {view.windowRows.map((row) => (
                    <li key={`${summary.symbol}-${row.label}`} className="flex items-center justify-between gap-2">
                      <span>{row.label}</span>
                      <span className="font-mono">
                        准确率 {row.accuracyPct} / 收益 {row.returnPct}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              {optimization ? (
                <div className="pt-2 border-t border-[#2a2e39]">
                  <div className="text-xs font-medium text-white mb-2">参数优化摘要</div>
                  <div className="text-xs text-[#8b949e]">策略：{optimization.strategy_id}</div>
                  <div className="text-xs text-[#8b949e]">窗口数：{optimization.window_count}</div>
                  <div className="text-xs text-[#8b949e]">均值收益：{(optimization.mean_strategy_return * 100).toFixed(2)}%</div>
                  <div className="text-xs text-[#8b949e]">最大回撤：{(optimization.max_drawdown * 100).toFixed(2)}%</div>
                  <div className="text-xs text-[#8b949e]">
                    最优参数：{Object.entries(optimization.best_params)
                      .map(([key, value]) => `${key}=${value}`)
                      .join(", ")}
                  </div>
                </div>
              ) : null}
            </div>
          );
          })}
        </div>
      ) : null}
    </section>
  );
}

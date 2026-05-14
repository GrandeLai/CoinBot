import { useEffect, useMemo, useState } from "react";
import { Activity, RefreshCw, Send, WalletCards } from "lucide-react";

import {
  getCryptoAccount,
  getCryptoOpenOrders,
  getCryptoPairs,
  getCryptoStatus,
  getCryptoTicker,
  getFuturesTickers,
  getOptionsChain,
  getOptionsExpiries,
  getOptionsUnderlyings,
  submitCryptoOrder,
  type CryptoAccountOverview,
  type CryptoOrder,
  type CryptoPair,
  type CryptoStatus,
  type CryptoTicker,
  type OptionTicker,
  type SwapTicker,
} from "../api/crypto";
import { cn } from "../lib/utils";

const INPUT =
  "h-9 w-full rounded-md border border-[#2A2D35] bg-[#151619] px-3 text-sm text-white outline-none focus:border-[#00C087]/70";

function fmt(v: number): string {
  return v >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 2 }) : v.toFixed(4);
}

function StatusPill({ status }: { status: CryptoStatus | null }) {
  const configured = status?.configured ?? false;
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase",
        configured
          ? "border-[#00C087]/40 bg-[#00C087]/10 text-[#00C087]"
          : "border-yellow-500/40 bg-yellow-500/10 text-yellow-300",
      )}
    >
      {configured ? (status?.testnet ? "OKX Demo" : "OKX Live") : "API Key Missing"}
    </span>
  );
}

export default function TradingPanel() {
  const [status, setStatus] = useState<CryptoStatus | null>(null);
  const [pairs, setPairs] = useState<CryptoPair[]>([]);
  const [tickers, setTickers] = useState<CryptoTicker[]>([]);
  const [account, setAccount] = useState<CryptoAccountOverview | null>(null);
  const [orders, setOrders] = useState<CryptoOrder[]>([]);
  const [swaps, setSwaps] = useState<SwapTicker[]>([]);
  const [underlyings, setUnderlyings] = useState<string[]>([]);
  const [expiries, setExpiries] = useState<string[]>([]);
  const [chain, setChain] = useState<OptionTicker[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("BTC-USDT");
  const [optionUnderlying, setOptionUnderlying] = useState("BTC-USD");
  const [optionExpiry, setOptionExpiry] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<"market" | "limit">("market");
  const [quantity, setQuantity] = useState("0.001");
  const [price, setPrice] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const tickerBySymbol = useMemo(
    () => Object.fromEntries(tickers.map((ticker) => [ticker.symbol, ticker])),
    [tickers],
  );

  async function load() {
    setLoading(true);
    setMessage(null);
    try {
      const statusResult = await getCryptoStatus();
      setStatus(statusResult);
      const pairResult = await getCryptoPairs(true);
      setPairs(pairResult);
      const symbols = pairResult.map((pair) => pair.symbol).slice(0, 8);
      setTickers(symbols.length > 0 ? await getCryptoTicker(symbols) : []);
      setSwaps(await getFuturesTickers().catch(() => []));
      const optionUnderlyings = await getOptionsUnderlyings().catch(() => ["BTC-USD", "ETH-USD"]);
      setUnderlyings(optionUnderlyings);
      const accountResult = statusResult.configured ? await getCryptoAccount().catch(() => null) : null;
      setAccount(accountResult);
      const orderResult = statusResult.configured ? await getCryptoOpenOrders().catch(() => []) : [];
      setOrders(orderResult);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    void (async () => {
      const dates = await getOptionsExpiries(optionUnderlying).catch(() => []);
      setExpiries(dates);
      setOptionExpiry((current) => current || dates[0] || "");
    })();
  }, [optionUnderlying]);

  useEffect(() => {
    if (!optionExpiry) return;
    void getOptionsChain(optionUnderlying, optionExpiry)
      .then(setChain)
      .catch(() => setChain([]));
  }, [optionUnderlying, optionExpiry]);

  async function submitSpotOrder() {
    setSubmitting(true);
    setMessage(null);
    try {
      const parsedQty = Number(quantity);
      if (!Number.isFinite(parsedQty) || parsedQty <= 0) {
        throw new Error("请输入有效数量");
      }
      const parsedPrice = Number(price);
      await submitCryptoOrder({
        symbol: selectedSymbol,
        side,
        order_type: orderType,
        quantity: parsedQty,
        ...(orderType === "limit" ? { price: parsedPrice } : {}),
      });
      setMessage("现货订单已提交");
      setOrders(await getCryptoOpenOrders().catch(() => []));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-bold text-white">
            <Activity size={18} className="text-[#00C087]" />
            OKX 交易
          </h2>
          <div className="mt-1 flex items-center gap-2 text-xs text-[#8E9299]">
            <StatusPill status={status} />
            <span>{status?.base_url ?? "https://www.okx.com"}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="inline-flex items-center gap-2 rounded-md border border-[#2A2D35] bg-[#151619] px-3 py-2 text-sm text-[#8E9299] hover:text-white"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          刷新
        </button>
      </div>

      {message && (
        <div className="rounded-md border border-[#2A2D35] bg-[#151619] px-3 py-2 text-sm text-[#facc15]">
          {message}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            {tickers.slice(0, 6).map((ticker) => (
              <button
                key={ticker.symbol}
                type="button"
                onClick={() => setSelectedSymbol(ticker.symbol)}
                className={cn(
                  "rounded-lg border bg-[#151619] p-3 text-left transition-colors",
                  selectedSymbol === ticker.symbol ? "border-[#00C087]/70" : "border-[#2A2D35]",
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">{ticker.display}</span>
                  <span className={ticker.change_pct >= 0 ? "text-[#00C087]" : "text-red-400"}>
                    {ticker.change_pct >= 0 ? "+" : ""}
                    {ticker.change_pct.toFixed(2)}%
                  </span>
                </div>
                <div className="mt-2 font-mono text-xl text-white">${fmt(ticker.price)}</div>
                <div className="mt-1 text-xs text-[#8E9299]">24h vol ${fmt(ticker.volume_usdt)}</div>
              </button>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-lg border border-[#2A2D35] bg-[#151619] p-4">
              <h3 className="mb-3 text-sm font-bold text-white">永续合约</h3>
              <div className="space-y-2">
                {swaps.slice(0, 6).map((swap) => (
                  <div key={swap.inst_id} className="flex items-center justify-between text-sm">
                    <span className="font-mono text-white">{swap.inst_id}</span>
                    <span className="text-[#8E9299]">
                      funding {(swap.funding_rate * 100).toFixed(4)}%
                    </span>
                    <span className={swap.change_pct >= 0 ? "text-[#00C087]" : "text-red-400"}>
                      {swap.change_pct.toFixed(2)}%
                    </span>
                  </div>
                ))}
                {swaps.length === 0 && <div className="text-sm text-[#8E9299]">暂无合约行情</div>}
              </div>
            </div>

            <div className="rounded-lg border border-[#2A2D35] bg-[#151619] p-4">
              <h3 className="mb-3 text-sm font-bold text-white">期权链</h3>
              <div className="mb-3 grid grid-cols-2 gap-2">
                <select value={optionUnderlying} onChange={(e) => setOptionUnderlying(e.target.value)} className={INPUT}>
                  {underlyings.map((underlying) => (
                    <option key={underlying} value={underlying}>
                      {underlying}
                    </option>
                  ))}
                </select>
                <select value={optionExpiry} onChange={(e) => setOptionExpiry(e.target.value)} className={INPUT}>
                  {expiries.map((expiry) => (
                    <option key={expiry} value={expiry}>
                      {expiry}
                    </option>
                  ))}
                </select>
              </div>
              <div className="max-h-56 space-y-2 overflow-auto">
                {chain.slice(0, 12).map((option) => (
                  <div key={option.inst_id} className="grid grid-cols-4 gap-2 text-xs">
                    <span className="font-mono text-white">{option.strike_px}</span>
                    <span className={option.opt_type === "C" ? "text-[#00C087]" : "text-red-400"}>
                      {option.opt_type}
                    </span>
                    <span className="text-[#8E9299]">bid {fmt(option.bid_px)}</span>
                    <span className="text-[#8E9299]">ask {fmt(option.ask_px)}</span>
                  </div>
                ))}
                {chain.length === 0 && <div className="text-sm text-[#8E9299]">暂无期权链数据</div>}
              </div>
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="rounded-lg border border-[#2A2D35] bg-[#151619] p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-white">
              <Send size={14} className="text-[#00C087]" />
              现货下单
            </h3>
            <div className="space-y-3">
              <select value={selectedSymbol} onChange={(e) => setSelectedSymbol(e.target.value)} className={INPUT}>
                {pairs.map((pair) => (
                  <option key={pair.symbol} value={pair.symbol}>
                    {pair.display}
                  </option>
                ))}
              </select>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSide("buy")}
                  className={cn("rounded-md border px-3 py-2 text-sm", side === "buy" ? "border-[#00C087] text-[#00C087]" : "border-[#2A2D35] text-[#8E9299]")}
                >
                  买入
                </button>
                <button
                  type="button"
                  onClick={() => setSide("sell")}
                  className={cn("rounded-md border px-3 py-2 text-sm", side === "sell" ? "border-red-400 text-red-400" : "border-[#2A2D35] text-[#8E9299]")}
                >
                  卖出
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setOrderType("market")}
                  className={cn("rounded-md border px-3 py-2 text-sm", orderType === "market" ? "border-white text-white" : "border-[#2A2D35] text-[#8E9299]")}
                >
                  市价
                </button>
                <button
                  type="button"
                  onClick={() => setOrderType("limit")}
                  className={cn("rounded-md border px-3 py-2 text-sm", orderType === "limit" ? "border-white text-white" : "border-[#2A2D35] text-[#8E9299]")}
                >
                  限价
                </button>
              </div>
              <input value={quantity} onChange={(e) => setQuantity(e.target.value)} className={INPUT} type="number" min="0" step="0.0001" />
              {orderType === "limit" && (
                <input value={price} onChange={(e) => setPrice(e.target.value)} className={INPUT} type="number" min="0" step="0.01" />
              )}
              <button
                type="button"
                disabled={submitting || !status?.configured}
                onClick={() => void submitSpotOrder()}
                className="w-full rounded-md bg-[#00C087] px-3 py-2 text-sm font-bold text-black disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "提交中…" : "提交订单"}
              </button>
              {tickerBySymbol[selectedSymbol] && (
                <div className="text-xs text-[#8E9299]">
                  最新价 <span className="font-mono text-white">${fmt(tickerBySymbol[selectedSymbol].price)}</span>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-[#2A2D35] bg-[#151619] p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-white">
              <WalletCards size={14} className="text-[#00C087]" />
              账户
            </h3>
            <div className="text-sm text-[#8E9299]">
              总值 <span className="font-mono text-white">{account?.total_usdt_value.toFixed(2) ?? "—"} USDT</span>
            </div>
            <div className="mt-3 space-y-2">
              {(account?.balances ?? []).slice(0, 6).map((balance) => (
                <div key={balance.asset} className="flex justify-between text-xs">
                  <span className="font-mono text-white">{balance.asset}</span>
                  <span className="font-mono text-[#8E9299]">{balance.total}</span>
                </div>
              ))}
              {orders.slice(0, 4).map((order) => (
                <div key={order.order_id} className="flex justify-between text-xs">
                  <span className="font-mono text-white">{order.symbol}</span>
                  <span className="text-[#8E9299]">{order.status}</span>
                </div>
              ))}
              {!account && orders.length === 0 && (
                <div className="text-xs text-[#8E9299]">
                  {status?.configured ? "暂无账户数据" : "配置 OKX Key 后显示账户与订单"}
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

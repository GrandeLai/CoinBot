import assert from "node:assert/strict";
import test from "node:test";

import {
  fetchCryptoOpportunities,
  fetchCryptoResearchLatest,
  fetchCryptoResearchLatestOptimization,
  fetchCryptoResearchOptimization,
  fetchCryptoRisks,
} from "./client.ts";

test("fetchCryptoOpportunities calls the crypto opportunity advisor endpoint", async () => {
  let capturedUrl = "";
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    capturedUrl = String(input);
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  }) as typeof fetch;

  try {
    const result = await fetchCryptoOpportunities<{ items: [] }>("BTC-USDT");
    assert.equal(capturedUrl, "/api/advisor/crypto/opportunities?symbol=BTC-USDT");
    assert.deepEqual(result, { items: [] });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchCryptoRisks calls the crypto risk advisor endpoint", async () => {
  let capturedUrl = "";
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    capturedUrl = String(input);
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  }) as typeof fetch;

  try {
    const result = await fetchCryptoRisks<{ items: [] }>("BTC-USDT");
    assert.equal(capturedUrl, "/api/advisor/crypto/risks?symbol=BTC-USDT");
    assert.deepEqual(result, { items: [] });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchCryptoResearchLatest calls the cached research summary endpoint", async () => {
  let capturedUrl = "";
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    capturedUrl = String(input);
    return new Response(
      JSON.stringify({
        symbol: "BTC-USDT",
        base_timeframe: "15m",
        market_regime: "ranging",
        recommended_strategy_ids: ["vwap_ema_trend"],
        recommended_timeframes: ["15m", "1h"],
        parameter_search_ready: true,
      }),
      { status: 200 },
    );
  }) as typeof fetch;

  try {
    const result = await fetchCryptoResearchLatest<{ market_regime: string }>("BTC-USDT");
    assert.equal(capturedUrl, "/api/crypto/research/latest?symbol=BTC-USDT&base_timeframe=15m");
    assert.equal(result.market_regime, "ranging");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchCryptoResearchOptimization calls the optimization endpoint", async () => {
  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    capturedUrl = String(input);
    capturedInit = init;
    return new Response(
      JSON.stringify({
        symbol: "BTC-USDT",
        strategy_id: "vwap_ema_trend",
        best_params: { fast_period: 5 },
      }),
      { status: 200 },
    );
  }) as typeof fetch;

  try {
    const result = await fetchCryptoResearchOptimization<{ strategy_id: string }>("BTC-USDT");
    assert.equal(capturedUrl, "/api/crypto/research/optimize");
    assert.equal(capturedInit?.method, "POST");
    assert.ok(String(capturedInit?.body).includes('"strategy_id":"vwap_ema_trend"'));
    assert.equal(result.strategy_id, "vwap_ema_trend");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchCryptoResearchLatestOptimization calls the cached optimization endpoint", async () => {
  let capturedUrl = "";
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    capturedUrl = String(input);
    return new Response(
      JSON.stringify({
        symbol: "BTC-USDT",
        strategy_id: "vwap_ema_trend",
        best_params: { fast_period: 5 },
      }),
      { status: 200 },
    );
  }) as typeof fetch;

  try {
    const result = await fetchCryptoResearchLatestOptimization<{ strategy_id: string }>("BTC-USDT", "vwap_ema_trend");
    assert.equal(
      capturedUrl,
      "/api/crypto/research/optimize/latest?symbol=BTC-USDT&base_timeframe=15m&strategy_id=vwap_ema_trend",
    );
    assert.equal(result.strategy_id, "vwap_ema_trend");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

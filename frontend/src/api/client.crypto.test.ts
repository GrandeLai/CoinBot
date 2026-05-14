import assert from "node:assert/strict";
import test from "node:test";

import {
  fetchCryptoResearchLatestOptimization,
  fetchCryptoResearchLatestSummary,
  fetchCryptoResearchOptimization,
  fetchCryptoResearchSummary,
} from "./client.ts";

test("fetchCryptoResearchSummary reads the latest endpoint", async () => {
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
    const result = await fetchCryptoResearchSummary("BTC-USDT");
    assert.equal(capturedUrl, "/api/crypto/research/latest?symbol=BTC-USDT&base_timeframe=15m");
    assert.equal(result.symbol, "BTC-USDT");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchCryptoResearchLatestSummary normalizes compact backend payload", async () => {
  let capturedUrl = "";
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    capturedUrl = String(input);
    return new Response(
      JSON.stringify({
        symbol: "BTC-USDT",
        base_timeframe: "15m",
        market_regime: "bull_trending",
        recommended_strategy_ids: ["vwap_ema_trend"],
        recommended_timeframes: ["15m", "1h"],
        parameter_search_ready: true,
      }),
      { status: 200 },
    );
  }) as typeof fetch;

  try {
    const result = await fetchCryptoResearchLatestSummary("BTC-USDT");
    assert.equal(capturedUrl, "/api/crypto/research/latest?symbol=BTC-USDT&base_timeframe=15m");
    assert.equal(result.dataset_version, "regime-latest");
    assert.equal(result.market_regime, "bull_trending");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchCryptoResearchOptimization posts the expected optimization payload", async () => {
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
    const result = await fetchCryptoResearchOptimization("BTC-USDT");
    assert.equal(capturedUrl, "/api/crypto/research/optimize");
    assert.equal(capturedInit?.method, "POST");
    assert.ok(String(capturedInit?.body).includes('"symbol":"BTC-USDT"'));
    assert.ok(String(capturedInit?.body).includes('"strategy_id":"vwap_ema_trend"'));
    assert.equal(result.strategy_id, "vwap_ema_trend");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchCryptoResearchLatestOptimization reads the cached optimization endpoint", async () => {
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
    const result = await fetchCryptoResearchLatestOptimization("BTC-USDT", "vwap_ema_trend");
    assert.equal(
      capturedUrl,
      "/api/crypto/research/optimize/latest?symbol=BTC-USDT&base_timeframe=15m&strategy_id=vwap_ema_trend",
    );
    assert.equal(result.strategy_id, "vwap_ema_trend");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

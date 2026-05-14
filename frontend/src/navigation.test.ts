import test from "node:test";
import assert from "node:assert/strict";

import { ASSISTANT_TABS } from "./navigation.ts";

test("navigation labels stay aligned with CoinBot modules", () => {
  assert.deepEqual(
    ASSISTANT_TABS.map((tab) => tab.label),
    [
      "资产总览",
      "OKX 交易",
      "机会池",
      "调仓建议",
      "风险雷达",
      "衍生品",
      "研究",
      "巨鲸",
      "解锁",
      "回测",
      "优化",
      "验证",
      "复盘与问答",
    ],
  );
});

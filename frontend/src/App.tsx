import {
  Activity,
  BarChart3,
  Briefcase,
  GitBranch,
  LockKeyhole,
  ListTree,
  Search,
  Scale,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  WalletCards,
  Waves,
} from "lucide-react";
import type { ComponentType } from "react";

import BacktestPanel from "./components/BacktestPanel";
import CryptoDerivsPanel from "./components/CryptoDerivsPanel";
import CryptoResearchPanel from "./components/CryptoResearchPanel";
import { OpportunityPool } from "./components/OpportunityPool";
import OptimizationPanel from "./components/OptimizationPanel";
import { PortfolioOverview } from "./components/PortfolioOverview";
import { RebalanceSuggestions } from "./components/RebalanceSuggestions";
import { ReviewAsk } from "./components/ReviewAsk";
import { RiskRadar } from "./components/RiskRadar";
import TokenUnlockPanel from "./components/TokenUnlockPanel";
import TradingPanel from "./components/TradingPanel";
import WalkForwardPanel from "./components/WalkForwardPanel";
import WhaleMonitorPanel from "./components/WhaleMonitorPanel";
import type { AssistantTab } from "./navigation";
import { ASSISTANT_TABS } from "./navigation";
import { cn } from "./lib/utils";
import { instrumentsForProduct } from "./shared/markets";
import { useAdvisorStore } from "./store/advisorStore";

const TAB_ICONS: Record<AssistantTab, ComponentType<{ size?: number }>> = {
  overview: Briefcase,
  trade: WalletCards,
  opportunities: ListTree,
  rebalance: Scale,
  risk: ShieldAlert,
  derivs: Activity,
  research: Search,
  whale: Waves,
  unlocks: LockKeyhole,
  backtest: BarChart3,
  optimize: TrendingUp,
  walkforward: GitBranch,
  review: Sparkles,
};

const SUPPORTED_MARKETS = instrumentsForProduct("coinbot");

function renderView(tab: AssistantTab) {
  switch (tab) {
    case "overview":
      return <PortfolioOverview />;
    case "trade":
      return <TradingPanel />;
    case "opportunities":
      return <OpportunityPool />;
    case "rebalance":
      return <RebalanceSuggestions />;
    case "risk":
      return <RiskRadar />;
    case "derivs":
      return <CryptoDerivsPanel />;
    case "research":
      return <CryptoResearchPanel />;
    case "whale":
      return <WhaleMonitorPanel />;
    case "unlocks":
      return <TokenUnlockPanel />;
    case "backtest":
      return <BacktestPanel />;
    case "optimize":
      return <OptimizationPanel />;
    case "walkforward":
      return <WalkForwardPanel />;
    case "review":
      return <ReviewAsk />;
    default: {
      const exhaustiveCheck: never = tab;
      return exhaustiveCheck;
    }
  }
}

/**
 * CoinBot shell — crypto advisor, OKX trading, and quant research in one UI.
 */
export default function App() {
  const activeTab = useAdvisorStore((state) => state.activeTab);
  const setActiveTab = useAdvisorStore((state) => state.setActiveTab);

  return (
    <main className="min-h-screen bg-[#0E1014] text-white">
      <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
        <header className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#00C087]/10 border border-[#00C087]/30 rounded-lg">
              <Sparkles size={20} className="text-[#00C087]" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">CoinBot</h1>
              <p className="text-[#8E9299] text-sm mt-0.5">
                Crypto advisor · OKX · quant research
              </p>
            </div>
          </div>
        </header>

        <section
          aria-label="Supported crypto markets"
          className="flex flex-wrap items-center gap-2 border border-[#2A2D35] bg-[#151619] rounded-xl px-4 py-3"
        >
          <span className="text-[10px] uppercase tracking-wider font-bold text-[#8E9299]">
            Universe
          </span>
          {SUPPORTED_MARKETS.map((instrument) => (
            <span
              key={instrument.symbol}
              className="px-2 py-1 rounded-md border border-[#2A2D35] bg-[#0E1014] text-[11px] text-white font-mono"
              title={`${instrument.name} · ${instrument.exchange}`}
            >
              {instrument.symbol}
            </span>
          ))}
        </section>

        <nav aria-label="CoinBot views">
          <ul className="flex flex-wrap gap-2 list-none p-0 m-0">
            {ASSISTANT_TABS.map((tab) => {
              const Icon = TAB_ICONS[tab.key];
              const isActive = tab.key === activeTab;
              return (
                <li key={tab.key}>
                  <button
                    type="button"
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => setActiveTab(tab.key)}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 text-sm rounded-lg border transition-colors",
                      isActive
                        ? "bg-[#00C087] border-[#00C087] text-black font-bold"
                        : "bg-[#151619] border-[#2A2D35] text-[#8E9299] hover:text-white hover:border-[#00C087]/50",
                    )}
                  >
                    <Icon size={14} />
                    {tab.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="bg-[#0E1014] border border-[#2A2D35] rounded-xl p-6 min-h-[280px]">
          {renderView(activeTab)}
        </div>
      </div>
    </main>
  );
}

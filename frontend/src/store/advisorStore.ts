import { create } from "zustand";

import type { AssistantTab } from "../navigation";

type AdvisorState = {
  activeTab: AssistantTab;
  setActiveTab: (tab: AssistantTab) => void;
};

/**
 * Minimal assistant shell state for the active decision view.
 */
export const useAdvisorStore = create<AdvisorState>((set) => ({
  activeTab: "overview",
  setActiveTab: (tab) => set({ activeTab: tab }),
}));

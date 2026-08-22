import { create } from "zustand";

interface UiState {
  contextPanelOpen: boolean;
  toggleContextPanel: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  contextPanelOpen: true,
  toggleContextPanel: () => set((state) => ({ contextPanelOpen: !state.contextPanelOpen }))
}));


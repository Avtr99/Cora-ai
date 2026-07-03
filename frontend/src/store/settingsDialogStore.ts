import { create } from 'zustand';

type SettingsTab = 'llm' | 'embeddings' | 'search';

interface SettingsDialogState {
  open: boolean;
  tab: SettingsTab;
  openSettings: (tab?: SettingsTab) => void;
  closeSettings: () => void;
  setTab: (tab: SettingsTab) => void;
}

export const useSettingsDialogStore = create<SettingsDialogState>((set) => ({
  open: false,
  tab: 'llm',
  openSettings: (tab = 'llm') => set({ open: true, tab }),
  closeSettings: () => set({ open: false }),
  setTab: (tab) => set({ tab }),
}));

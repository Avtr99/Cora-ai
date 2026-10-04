import { create } from 'zustand';

export type AuthStatus = 'unknown' | 'open' | 'required' | 'authenticated';

interface AuthState {
  status: AuthStatus;
  setStatus: (status: AuthStatus) => void;
  markRequired: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  status: 'unknown',
  setStatus: (status) => set({ status }),
  markRequired: () => set({ status: 'required' }),
}));

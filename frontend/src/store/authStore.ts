import { create } from 'zustand';
import type { SessionStatus, SessionUser } from '@/services/authApi';

export type AuthStatus = 'unknown' | 'open' | 'required' | 'authenticated';

interface AuthState {
  status: AuthStatus;
  /** The signed-in account, or null in open mode / before login. */
  user: SessionUser | null;
  /** True when protection is on but nobody has claimed the owner account yet. */
  ownerClaimRequired: boolean;
  setStatus: (status: AuthStatus) => void;
  /** Store the whole session status returned by `getSession` or a login. */
  applySession: (session: SessionStatus) => void;
  markRequired: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  status: 'unknown',
  user: null,
  ownerClaimRequired: false,
  setStatus: (status) => set({ status }),
  applySession: (session) =>
    set({
      status: !session.required
        ? 'open'
        : session.authenticated
          ? 'authenticated'
          : 'required',
      user: session.user,
      ownerClaimRequired: session.owner_claim_required,
    }),
  markRequired: () => set({ status: 'required', user: null, ownerClaimRequired: false }),
}));

/** True once the visitor can administer the instance: open mode (protection
 * off) acts as the owner, and the only authenticated account is the owner.
 * False while signed out or before the session status resolves. */
export const useIsOwner = (): boolean =>
  useAuthStore((s) => s.status === 'open' || s.user?.role === 'owner');

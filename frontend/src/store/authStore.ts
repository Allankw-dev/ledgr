import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AuthUser } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:4000';

interface AuthState {
  token: string | null;
  // Long-lived, single-use, rotated on every refresh. Lets the short-lived
  // access token above be swapped silently (see api/client.ts).
  refreshToken: string | null;
  user: AuthUser | null;
  setSession: (token: string, user: AuthUser, refreshToken?: string | null) => void;
  // Used by the API client after a silent refresh — keeps the same user.
  setTokens: (token: string, refreshToken: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      setSession: (token, user, refreshToken = null) => set({ token, user, refreshToken }),
      setTokens: (token, refreshToken) => set({ token, refreshToken }),
      logout: () => {
        const { refreshToken } = get();
        set({ token: null, refreshToken: null, user: null });
        // Tell the server to kill this sign-in's refresh tokens. Fire-and-forget:
        // signing out locally must never wait on (or fail because of) the network.
        // Plain fetch, not apiClient — the client imports this store.
        if (refreshToken) {
          fetch(`${API_BASE_URL}/api/auth/logout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
            keepalive: true,
          }).catch(() => {});
        }
      },
    }),
    { name: 'ledgr-auth' } // localStorage key — tokens only, never a password
  )
);

// Two tabs share one localStorage entry. When another tab refreshes (rotating
// the refresh token) or signs out, pick that up here — otherwise this tab
// would later present an already-rotated refresh token.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === 'ledgr-auth') void useAuthStore.persist.rehydrate();
  });
}

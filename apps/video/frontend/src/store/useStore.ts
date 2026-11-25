/**
 * Bazzy Video — Zustand global store
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api, WalletInfo, Title } from "@/lib/api";

interface AuthState {
  token: string | null;
  userId: string | null;
  role: string | null;
  displayName: string | null;
  isAuthenticated: boolean;
  login: (token: string, userId: string, role: string) => void;
  logout: () => void;
}

interface WalletState {
  wallet: WalletInfo | null;
  fetchWallet: () => Promise<void>;
}

interface PlayerState {
  currentTitle: Title | null;
  isPlaying: boolean;
  sessionId: string | null;
  setCurrentTitle: (title: Title | null) => void;
  setIsPlaying: (v: boolean) => void;
}

interface BazzyStore extends AuthState, WalletState, PlayerState {
  hydrated: boolean;   // true once the saved session has loaded from localStorage
  setHydrated: (v: boolean) => void;
}

export const useStore = create<BazzyStore>()(
  persist(
    (set, get) => ({
      hydrated: false,
      setHydrated: (v) => set({ hydrated: v }),

      // Auth
      token: null, userId: null, role: null, displayName: null,
      isAuthenticated: false,

      login: (token, userId, role) => {
        localStorage.setItem("bv_token", token);
        set({ token, userId, role, isAuthenticated: true });
      },
      logout: () => {
        localStorage.removeItem("bv_token");
        set({ token: null, userId: null, role: null, isAuthenticated: false, wallet: null });
      },

      // Wallet
      wallet: null,
      fetchWallet: async () => {
        if (!get().isAuthenticated) return;
        try {
          const w = await api.wallet.get();
          set({ wallet: w });
        } catch {}
      },

      // Player
      currentTitle: null, isPlaying: false, sessionId: null,
      setCurrentTitle: (title) => {
        const sessionId = title ? crypto.randomUUID() : null;
        set({ currentTitle: title, sessionId, isPlaying: !!title });
      },
      setIsPlaying: (v) => set({ isPlaying: v }),
    }),
    {
      name: "bazzy-video-store",
      partialize: (s) => ({ token: s.token, userId: s.userId, role: s.role, isAuthenticated: s.isAuthenticated }),
      onRehydrateStorage: () => (state) => state?.setHydrated(true),
    }
  )
);

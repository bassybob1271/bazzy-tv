/**
 * Bazzy Video — API client
 */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("bv_token") : null;
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail ?? "API error");
  }
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const api = {
  auth: {
    register: (data: { email: string; password: string; display_name: string; is_filmmaker?: boolean; bio?: string }) =>
      request<{ access_token: string; user_id: string; role: string }>("/auth/register", {
        method: "POST", body: JSON.stringify(data),
      }),
    login: (email: string, password: string) => {
      const form = new URLSearchParams({ username: email, password });
      return request<{ access_token: string; user_id: string; role: string }>("/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form.toString(),
      });
    },
    /** Which social sign-in buttons are configured on the server. */
    providers: () => request<{ google: boolean; apple: boolean }>("/auth/providers"),
    /** Full URL that starts Google/Apple sign-in; `next` is where to land afterwards. */
    socialStartUrl: (provider: "google" | "apple", next = "/") =>
      `${BASE}/auth/oauth/${provider}/start?next=${encodeURIComponent(next)}`,
  },

  // ── Sign in with Bazzy TV (apps like BazzyBox) ──────────────────────────
  oauth: {
    client: (clientId: string, redirectUri: string) =>
      request<{ client_id: string; name: string; trusted: boolean }>(
        `/oauth/clients/${encodeURIComponent(clientId)}?redirect_uri=${encodeURIComponent(redirectUri)}`
      ),
    authorize: (body: { client_id: string; redirect_uri: string; state: string; code_challenge: string; code_challenge_method: string; scope: string }) =>
      request<{ redirect: string }>("/oauth/authorize", { method: "POST", body: JSON.stringify(body) }),
  },

  // ── Titles ────────────────────────────────────────────────────────────────
  titles: {
    homeRails: () => request<HomeRails>("/titles/home-rails"),
    discover: (params: DiscoverParams) =>
      request<Title[]>(`/titles/discover?${new URLSearchParams(params as any)}`),
    get: (slug: string) => request<Title>(`/titles/${slug}`),
    /** Alias so watch/[slug]/page.tsx can call api.titles.detail(slug) */
    detail: (slug: string) => request<Title>(`/titles/${slug}`),
    becauseYouWatched: (id: string) => request<Title[]>(`/titles/${id}/because-you-watched`),
    rent: (id: string) => request<{ status: string }>(`/titles/${id}/rent`, { method: "POST" }),
    buy: (id: string) => request<{ status: string }>(`/titles/${id}/buy`, { method: "POST" }),
    streamPing: (id: string, sessionId: string) =>
      request<{ credits_remaining: number }>(`/titles/${id}/stream-ping?session_id=${sessionId}`, { method: "POST" }),
    vote: (id: string, stars: number) =>
      request<{ voted: number }>(`/titles/${id}/vote?stars=${stars}`, { method: "POST" }),
    addWatchlist: (id: string) =>
      request<{ added: boolean }>(`/titles/${id}/watchlist`, { method: "POST" }),
    /** Alias used in watch/[slug]/page.tsx */
    watchlist: (id: string) =>
      request<{ added: boolean }>(`/titles/${id}/watchlist`, { method: "POST" }),
  },

  // ── Wallet ────────────────────────────────────────────────────────────────
  wallet: {
    get: () => request<WalletInfo>("/wallet/"),
    tiers: () => request<Record<string, CreditTier>>("/wallet/tiers"),
    checkout: (tier: string) => request<{ checkout_url: string }>("/wallet/checkout", {
      method: "POST", body: JSON.stringify({ tier }),
    }),
    transactions: (limit = 50) => request<Transaction[]>(`/wallet/transactions?limit=${limit}`),
  },

  // ── Filmmaker ─────────────────────────────────────────────────────────────
  filmmaker: {
    dashboard: () => request<FilmmakerDashboard>("/filmmaker/dashboard"),
    analytics: (titleId: string) => request<TitleAnalytics>(`/filmmaker/analytics/${titleId}`),
    requestPayout: () => request<PayoutResult>("/filmmaker/request-payout", { method: "POST" }),
    payoutHistory: () => request<Payout[]>("/filmmaker/payout-history"),
    connectStripe: (code: string) =>
      request<{ stripe_connected: boolean }>(`/filmmaker/connect-stripe?code=${code}`, { method: "POST" }),
  },

  // ── Admin ─────────────────────────────────────────────────────────────────
  admin: {
    queue: (status = "review") => request<Title[]>(`/admin/content/queue?status=${status}`),
    approve: (id: string, score = 0) =>
      request(`/admin/content/${id}/approve?editorial_score=${score}`, { method: "POST" }),
    reject: (id: string, reason: string) =>
      request(`/admin/content/${id}/reject?reason=${encodeURIComponent(reason)}`, { method: "POST" }),
    setEditorialScore: (id: string, score: number) =>
      request(`/admin/content/${id}/editorial-score?score=${score}`, { method: "POST" }),
    metrics: () => request<PlatformMetrics>("/admin/metrics"),
    ledger: () => request<Transaction[]>("/admin/ledger"),
    grantCredits: (userId: string, credits: number, reason: string) =>
      request(`/admin/users/${userId}/grant-credits?credits=${credits}&reason=${encodeURIComponent(reason)}`, {
        method: "POST",
      }),
  },
};

// ── Types ─────────────────────────────────────────────────────────────────────
export interface Title {
  id: string; title: string; slug: string; synopsis?: string;
  category: string; year?: number; runtime_minutes?: number;
  poster_url?: string; backdrop_url?: string; trailer_url?: string;
  /** Backend field name */
  hls_manifest_url?: string;
  /** Alias used by VideoPlayer — same value */
  hls_master_url?: string;
  rent_credits: number; buy_credits: number; is_free: boolean;
  view_count: number; completion_rate: number; fan_vote_score: number; status: string;
  has_access?: boolean;
}
export interface HomeRails { hero: Title[]; trending: Title[]; new_arrivals: Title[];
  documentary: Title[]; romance: Title[]; crime: Title[]; horror: Title[];
  new_releases: Title[]; fan_picks: Title[]; comedy: Title[]; }
export interface DiscoverParams { mood?: string; category?: string; min_runtime?: number; max_runtime?: number; limit?: number; }
export interface WalletInfo { credit_balance: number; lifetime_credits: number; usd_equivalent: number; }
export interface CreditTier { usd: number; credits: number; bonus: number; }
export interface Transaction { id: string; transaction_type: string; credits_delta: number; usd_equivalent?: number; description?: string; created_at: string; }
export interface FilmmakerDashboard { filmmaker_id: string; display_name: string; stripe_connected: boolean; kyc_verified: boolean; total_earned_credits: number; total_paid_out_usd: number; unsettled_credits: number; unsettled_usd: number; payout_ready: boolean; titles: any[]; }
export interface TitleAnalytics { title_id: string; title_name: string; view_count: number; completion_rate: number; fan_vote_score: number; revenue_velocity_7d: number; total_earned_credits: number; total_earned_usd: number; }
export interface PayoutResult { payout_id: string; amount_usd: number; stripe_transfer_id: string; }
export interface Payout { id: string; amount_usd: number; status: string; created_at: string; paid_at?: string; }
export interface PlatformMetrics { total_users: number; live_titles: number; total_transactions: number; total_credits_sold: number; total_filmmaker_paid_usd: number; }

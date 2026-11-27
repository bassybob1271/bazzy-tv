/**
 * Bazzy Live — API client
 */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/** Bazzy TV: one account and one wallet across films, Bazzy Live and BazzyBox. */
export const BAZZY_TV_URL = (process.env.NEXT_PUBLIC_BAZZY_TV_URL || "http://localhost:3000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("bl_token") : null;
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
    /** Which "Continue with…" buttons to show. One Bazzy account: same sign-in as Bazzy TV. */
    providers: () => request<{ google: boolean; apple: boolean }>("/auth/providers"),
    /** Google/Apple sign-in runs on Bazzy TV (the address registered with them) and comes back here. */
    socialStartUrl: (provider: "google" | "apple", next = "/") =>
      `${BAZZY_TV_URL}/api/v1/auth/oauth/${provider}/start?${new URLSearchParams({ next, site: "live" })}`,
  },

  // ── Titles ────────────────────────────────────────────────────────────────
  titles: {
    homeRails: () => request<HomeRails>("/live/home-rails"),
    discover: (params: DiscoverParams) =>
      request<Title[]>(`/titles/discover?${new URLSearchParams(params as any)}`),
    get: (slug: string) => request<Title>(`/titles/${slug}`),
    /** Alias so watch/[slug]/page.tsx can call api.titles.detail(slug) */
    detail: (slug: string) => request<Title>(`/titles/${slug}`),
    /** Signed-in viewer's access to a title (free / rented / bought) */
    access: (id: string) =>
      request<{ has_access: boolean; access_type: "free" | "rent" | "buy" | null; expires_at: string | null }>(`/titles/${id}/access`),
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

  // ── Live ──────────────────────────────────────────────────────────────────
  live: {
    /** Where to watch (ticket holders): live HLS + pass, or the replay */
    playback: (id: string) => request<Playback>(`/live/${id}/playback`),
    mine: () => request<MyLivestream[]>("/live/mine"),
    /** Join a show that's on air (100 credits; no charge if you already have a ticket) */
    join: (id: string) =>
      request<{ status: string; charged: boolean; credits: number }>(`/live/${id}/join`, { method: "POST" }),
    schedule: (data: NewLivestream) =>
      request<{ title_id: string; slug: string; status: string; ingest: IngestInfo }>("/live/", {
        method: "POST", body: JSON.stringify(data),
      }),
    rotateKey: (id: string) => request<{ ingest: IngestInfo }>(`/live/${id}/rotate-key`, { method: "POST" }),
    end: (id: string) => request<{ live_state: string }>(`/live/${id}/end`, { method: "POST" }),
    /** Streaming.xml for ATEM Software Control (needs the auth header, so fetched as a blob) */
    atemXml: async (id: string) => {
      const token = localStorage.getItem("bl_token");
      const res = await fetch(`${BASE}/live/${id}/atem-streaming.xml`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Couldn't download the ATEM file");
      return res.blob();
    },
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
  /** Livestream */
  performer_name?: string | null; venue?: string | null;
  starts_at?: string | null; ended_at?: string | null;
  live_state?: "scheduled" | "on_air" | "ended" | null;
  /** Public, silent 4:3 preview — only while on air */
  preview_hls_url?: string | null;
  /** Price to join while on air (100) */
  join_credits?: number;
}
export interface HomeRails { upcoming: Title[]; previous: Title[];
  concerts: Title[]; album_releases: Title[]; listening: Title[];
  screenings: Title[]; sound_baths: Title[]; }
export interface Playback { live_state: "scheduled" | "on_air" | "ended"; hls_url: string | null; token: string | null; starts_at?: string; }
export interface IngestInfo { server_url: string; stream_key: string; playback_id: string; }
export interface MyLivestream { id: string; slug: string; title: string; status: string;
  live_state: "scheduled" | "on_air" | "ended"; starts_at: string | null;
  performer_name: string | null; venue: string | null; rent_credits: number; view_count: number;
  ingest: IngestInfo | null; }
export interface NewLivestream { title: string; synopsis?: string; category: string;
  performer_name?: string; venue?: string; starts_at: string; rent_credits?: number;
  is_free?: boolean; poster_url?: string; }
export interface DiscoverParams { mood?: string; category?: string; min_runtime?: number; max_runtime?: number; limit?: number; }
export interface WalletInfo { credit_balance: number; lifetime_credits: number; usd_equivalent: number; }
export interface CreditTier { usd: number; credits: number; bonus: number; }
export interface Transaction { id: string; transaction_type: string; credits_delta: number; usd_equivalent?: number; description?: string; created_at: string; }
export interface FilmmakerDashboard { filmmaker_id: string; display_name: string; stripe_connected: boolean; kyc_verified: boolean; total_earned_credits: number; total_paid_out_usd: number; unsettled_credits: number; unsettled_usd: number; payout_ready: boolean; titles: any[]; }
export interface TitleAnalytics { title_id: string; title_name: string; view_count: number; completion_rate: number; fan_vote_score: number; revenue_velocity_7d: number; total_earned_credits: number; total_earned_usd: number; }
export interface PayoutResult { payout_id: string; amount_usd: number; stripe_transfer_id: string; }
export interface Payout { id: string; amount_usd: number; status: string; created_at: string; paid_at?: string; }
export interface PlatformMetrics { total_users: number; live_titles: number; total_transactions: number; total_credits_sold: number; total_filmmaker_paid_usd: number; }

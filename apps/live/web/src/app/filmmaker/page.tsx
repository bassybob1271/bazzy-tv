"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, FilmmakerDashboard, Payout } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { LivestreamManager } from "@/components/artist/LivestreamManager";

function StatCard({ label, value, sub, color = "#4F8EF7" }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="p-6 rounded-xl bg-[#12151E] border border-white/8">
      <p className="text-xs text-[#5A607A] uppercase tracking-wider mb-2">{label}</p>
      <p className="text-3xl font-black font-mono" style={{ color }}>{value}</p>
      {sub && <p className="text-xs text-[#5A607A] mt-1">{sub}</p>}
    </div>
  );
}

export default function FilmmakerPage() {
  const router = useRouter();
  const { hydrated, isAuthenticated, role } = useStore();
  const [dash, setDash] = useState<FilmmakerDashboard | null>(null);
  const [newArtist, setNewArtist] = useState(false);
  const [loading, setLoading] = useState(true);
  const [requestingPayout, setRequestingPayout] = useState(false);
  const [connectingStripe, setConnectingStripe] = useState(false);
  const [payouts, setPayouts] = useState<Payout[]>([]);

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated) { router.push("/auth/login"); return; }
    // Any member can be an artist on Live: the API creates their creator profile with their first show.
    async function load() {
      try {
        // Returning from Stripe Connect OAuth with ?code=
        const code = new URLSearchParams(window.location.search).get("code");
        if (code) {
          await api.filmmaker.connectStripe(code).catch((e) => alert(e.message ?? "Stripe connect failed"));
          window.history.replaceState(null, "", "/filmmaker");
        }
        const [d, p] = await Promise.all([api.filmmaker.dashboard(), api.filmmaker.payoutHistory()]);
        setDash(d);
        setPayouts(p);
      } catch {
        setNewArtist(true); // no shows or earnings yet: offer the scheduler
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [hydrated, isAuthenticated, role]);

  async function handlePayout() {
    setRequestingPayout(true);
    try {
      const r = await api.filmmaker.requestPayout();
      alert(`Payout of $${r.amount_usd.toFixed(2)} initiated. Transfer ${r.stripe_transfer_id}`);
      const [d, p] = await Promise.all([api.filmmaker.dashboard(), api.filmmaker.payoutHistory()]);
      setDash(d);
      setPayouts(p);
    } catch (e: any) {
      alert(e.message ?? "Payout failed");
    } finally {
      setRequestingPayout(false);
    }
  }

  async function handleStripeConnect() {
    setConnectingStripe(true);
    try {
      const clientId = process.env.NEXT_PUBLIC_STRIPE_CONNECT_CLIENT_ID;
      if (!clientId) throw new Error("Stripe Connect isn't configured (NEXT_PUBLIC_STRIPE_CONNECT_CLIENT_ID).");
      const redirect = `${window.location.origin}/filmmaker`;
      window.location.href =
        `https://connect.stripe.com/oauth/authorize?response_type=code&scope=read_write` +
        `&client_id=${clientId}&redirect_uri=${encodeURIComponent(redirect)}`;
    } catch (e: any) {
      alert(e.message ?? "Stripe connect failed");
      setConnectingStripe(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-5xl animate-pulse">◈</div>
      </div>
    );
  }

  if (!dash) {
    if (!newArtist) return null;
    return (
      <main className="max-w-5xl mx-auto px-5 py-10">
        <h1 className="text-3xl font-bold">Put on your first show</h1>
        <p className="text-[#A0A8C0] mt-2 mb-8 max-w-2xl">
          Schedule it, get your ATEM settings, and sell 200-credit tickets from the same Bazzy wallet fans use for films.
          Every ticket pays you 80% after fees, or split it with the venue, producers and crew on Bazzy TV&apos;s Splits page.
        </p>
        <LivestreamManager />
      </main>
    );
  }

  const payoutReady = dash.payout_ready;
  const liveCount = dash.titles.filter((t: any) => t.status === "live").length;
  const totalViews = dash.titles.reduce((n: number, t: any) => n + (t.view_count ?? 0), 0);

  return (
    <div className="max-w-5xl mx-auto px-6 py-12 fade-up">
      <div className="flex items-start justify-between mb-10">
        <div>
          <h1 className="text-3xl font-black mb-1">Artist Dashboard</h1>
          <p className="text-[#A0A8C0]">Your livestreams, ATEM setup, earnings and payouts. 80% of every ticket is yours.</p>
        </div>
        {!dash.stripe_connected && (
          <button
            onClick={handleStripeConnect}
            disabled={connectingStripe}
            className="px-5 py-2.5 bg-[#9B72CF] text-white font-bold rounded-full text-sm hover:bg-[#B086E5] transition-colors"
          >
            {connectingStripe ? "Connecting…" : "Connect Stripe"}
          </button>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
        <StatCard label="Total Earned" value={`◈ ${dash.total_earned_credits.toLocaleString()}`} sub={`$${dash.total_paid_out_usd.toFixed(2)} paid out`} color="#3DCC7E" />
        <StatCard label="Pending Payout" value={`$${dash.unsettled_usd.toFixed(2)}`} sub="Min $25 to withdraw" color={payoutReady ? "#F5C842" : "#5A607A"} />
        <StatCard label="Livestreams" value={String(dash.titles.length)} sub={`${liveCount} listed`} />
        <StatCard label="Total Views" value={totalViews.toLocaleString()} sub="All time" color="#4F8EF7" />
      </div>

      {/* Payout action */}
      <div className="mb-10 p-6 rounded-xl bg-[#1A1D2E] border border-[#F5C842]/20">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="font-bold mb-1">Request Payout</h2>
            <p className="text-sm text-[#A0A8C0]">
              {payoutReady
                ? `You have $${dash.unsettled_usd.toFixed(2)} ready to withdraw.`
                : `Earn $25 to request a payout. You have $${dash.unsettled_usd.toFixed(2)} so far.`}
            </p>
          </div>
          <button
            onClick={handlePayout}
            disabled={!payoutReady || !dash.stripe_connected || requestingPayout}
            className={`flex-shrink-0 px-6 py-2.5 rounded-full font-bold text-sm transition-all
              ${payoutReady && dash.stripe_connected ? "bg-[#F5C842] text-black hover:bg-[#FFDA50]" : "bg-white/10 text-[#5A607A] cursor-not-allowed"}`}
          >
            {requestingPayout ? "Processing…" : "Withdraw →"}
          </button>
        </div>
        {!dash.stripe_connected && (
          <p className="text-xs text-[#E05252] mt-3">⚠ Connect Stripe to receive payouts.</p>
        )}
      </div>

      {/* Livestreams + ATEM setup */}
      <LivestreamManager />

      {/* Payout history */}
      {payouts.length > 0 && (
        <section className="mt-10">
          <h2 className="text-xl font-bold mb-5">Payout History</h2>
          <div className="rounded-xl border border-white/8 overflow-hidden">
            {payouts.map((p, i) => (
              <div key={p.id} className={`flex items-center justify-between px-5 py-4 ${i > 0 ? "border-t border-white/5" : ""}`}>
                <div>
                  <p className="text-sm font-medium text-white capitalize">{p.status}</p>
                  <p className="text-xs text-[#5A607A]">{new Date(p.created_at).toLocaleString()}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono font-bold text-[#3DCC7E] text-sm">${p.amount_usd.toFixed(2)}</p>
                  {p.paid_at && <p className="text-xs text-[#5A607A]">Paid {new Date(p.paid_at).toLocaleDateString()}</p>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, PlatformMetrics } from "@/lib/api";
import { useStore } from "@/store/useStore";

type Tab = "queue" | "metrics" | "ledger";

export default function AdminPage() {
  const router = useRouter();
  const { hydrated, isAuthenticated, role } = useStore();
  const [tab, setTab] = useState<Tab>("queue");
  const [queue, setQueue] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [ledger, setLedger] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState<string | null>(null);

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated || role !== "admin") { router.push("/"); return; }
    loadAll();
  }, [hydrated, isAuthenticated, role]);

  async function loadAll() {
    setLoading(true);
    try {
      const [q, m, l] = await Promise.all([
        api.admin.queue(),
        api.admin.metrics(),
        api.admin.ledger(),
      ]);
      setQueue(q);
      setMetrics(m);
      setLedger(l);
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(id: string, score: number) {
    setScoring(id);
    try {
      await api.admin.approve(id, score);
      await loadAll();
    } finally {
      setScoring(null);
    }
  }

  async function handleReject(id: string, reason: string) {
    await api.admin.reject(id, reason);
    await loadAll();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-5xl animate-pulse">◈</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-12 fade-up">
      <div className="flex items-center gap-3 mb-8">
        <span className="text-2xl">🛡️</span>
        <h1 className="text-3xl font-black">Admin Panel</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-8 border-b border-white/8 pb-0">
        {(["queue", "metrics", "ledger"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-3 text-sm font-semibold capitalize transition-all border-b-2 -mb-px
              ${tab === t ? "border-[#4F8EF7] text-white" : "border-transparent text-[#5A607A] hover:text-[#A0A8C0]"}`}
          >
            {t === "queue" ? `Queue (${queue.length})` : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Content Queue */}
      {tab === "queue" && (
        <div>
          <h2 className="text-lg font-bold mb-5">Ingest Review Queue</h2>
          {queue.length === 0 ? (
            <div className="text-center py-16 text-[#5A607A]">
              <p className="text-4xl mb-3">✅</p>
              <p>Queue is empty. All good!</p>
            </div>
          ) : (
            <div className="space-y-4">
              {queue.map((item) => (
                <div key={item.id} className="p-5 rounded-xl bg-[#12151E] border border-white/8">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h3 className="font-bold text-white mb-1">{item.title}</h3>
                      <p className="text-sm text-[#A0A8C0] mb-1">{item.synopsis}</p>
                      <div className="flex gap-3 text-xs text-[#5A607A]">
                        <span>{item.category}</span>
                        {item.runtime_minutes && <span>{item.runtime_minutes} min</span>}
                        <span>By: {item.filmmaker_name ?? "Unknown"}</span>
                      </div>
                    </div>
                    {item.poster_url && (
                      <img src={item.poster_url} alt="" className="w-16 h-24 rounded object-cover flex-shrink-0" />
                    )}
                  </div>

                  {/* Approve / reject */}
                  <div className="flex items-center gap-3 mt-4">
                    <select
                      id={`score-${item.id}`}
                      className="bg-[#1A1D2E] border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white"
                      defaultValue="0.7"
                    >
                      {[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0].map((s) => (
                        <option key={s} value={s}>Editorial score: {s}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => {
                        const sel = document.getElementById(`score-${item.id}`) as HTMLSelectElement;
                        handleApprove(item.id, parseFloat(sel.value));
                      }}
                      disabled={scoring === item.id}
                      className="px-4 py-1.5 bg-[#3DCC7E] text-black font-bold rounded-lg text-sm hover:bg-[#50DFA0] transition-colors"
                    >
                      {scoring === item.id ? "…" : "Approve"}
                    </button>
                    <button
                      onClick={() => handleReject(item.id, "Does not meet content guidelines")}
                      className="px-4 py-1.5 bg-[#E05252]/20 text-[#E05252] font-bold rounded-lg text-sm hover:bg-[#E05252]/30 transition-colors"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Platform Metrics */}
      {tab === "metrics" && metrics && (
        <div>
          <h2 className="text-lg font-bold mb-5">Platform Overview</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
            {[
              { label: "Total Users", value: metrics.total_users.toLocaleString(), color: "#4F8EF7" },
              { label: "Live Titles", value: metrics.live_titles.toLocaleString(), color: "#3DCC7E" },
              { label: "Transactions", value: metrics.total_transactions.toLocaleString(), color: "#F5C842" },
              { label: "Total Credits Sold", value: `◈ ${metrics.total_credits_sold.toLocaleString()}`, color: "#9B72CF" },
              { label: "Paid to Filmmakers", value: `$${metrics.total_filmmaker_paid_usd.toLocaleString()}`, color: "#E8629A" },
            ].map((m) => (
              <div key={m.label} className="p-5 rounded-xl bg-[#12151E] border border-white/8">
                <p className="text-xs text-[#5A607A] uppercase tracking-wider mb-2">{m.label}</p>
                <p className="text-2xl font-black font-mono" style={{ color: m.color }}>{m.value}</p>
              </div>
            ))}
          </div>

          {/* Payout waterfall reminder */}
          <div className="p-6 rounded-xl bg-[#1A1D2E] border border-white/8 text-sm text-[#A0A8C0]">
            <h3 className="font-bold text-white mb-3">Payout Waterfall</h3>
            <div className="space-y-2">
              <div className="flex justify-between"><span>Payment processing</span><span className="text-[#E05252]">-3%</span></div>
              <div className="flex justify-between"><span>CDN / delivery</span><span className="text-[#E05252]">-7%</span></div>
              <div className="flex justify-between font-semibold text-white"><span>→ Filmmaker</span><span className="text-[#3DCC7E]">80%</span></div>
              <div className="flex justify-between"><span>Platform ops</span><span className="text-[#4F8EF7]">10%</span></div>
              <div className="flex justify-between"><span>Reserve pool</span><span className="text-[#F5C842]">10%</span></div>
            </div>
          </div>
        </div>
      )}

      {/* Ledger */}
      {tab === "ledger" && (
        <div>
          <h2 className="text-lg font-bold mb-5">Credit Transaction Ledger</h2>
          {ledger.length === 0 ? (
            <p className="text-[#5A607A]">No transactions yet.</p>
          ) : (
            <div className="rounded-xl border border-white/8 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/8 text-[#5A607A] text-left">
                    <th className="px-5 py-3 font-medium">User</th>
                    <th className="px-5 py-3 font-medium">Type</th>
                    <th className="px-5 py-3 font-medium">Title</th>
                    <th className="px-5 py-3 font-medium text-right">Credits</th>
                    <th className="px-5 py-3 font-medium text-right">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.map((tx, i) => (
                    <tr key={tx.id} className={`hover:bg-white/2 ${i > 0 ? "border-t border-white/5" : ""}`}>
                      <td className="px-5 py-3 text-[#A0A8C0]">{tx.user_email ?? tx.user_id}</td>
                      <td className="px-5 py-3">
                        <span className="text-xs px-2 py-0.5 rounded bg-white/8 text-[#A0A8C0] font-mono">
                          {tx.transaction_type}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-[#A0A8C0]">{tx.title ?? "—"}</td>
                      <td className={`px-5 py-3 text-right font-mono font-bold ${tx.amount > 0 ? "text-[#3DCC7E]" : "text-[#E05252]"}`}>
                        {tx.amount > 0 ? "+" : ""}◈ {tx.amount}
                      </td>
                      <td className="px-5 py-3 text-right text-[#5A607A] text-xs">
                        {new Date(tx.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

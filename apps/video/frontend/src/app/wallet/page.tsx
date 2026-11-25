"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type TierView = { id: string; label: string; usd: number; base_credits: number; bonus_credits: number };
import { useStore } from "@/store/useStore";

export default function WalletPage() {
  const router = useRouter();
  const { hydrated, isAuthenticated, wallet, fetchWallet } = useStore();
  const [tiers, setTiers] = useState<TierView[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<string | null>(null);

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated) { router.push("/auth/login"); return; }
    async function load() {
      try {
        const [t, tx] = await Promise.all([api.wallet.tiers(), api.wallet.transactions()]);
        setTiers(Object.entries(t).map(([id, v]) => ({
          id, label: id.charAt(0).toUpperCase() + id.slice(1), usd: v.usd,
          base_credits: v.credits - v.bonus, bonus_credits: v.bonus,
        })));
        setTransactions(tx);
        await fetchWallet();
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [hydrated, isAuthenticated]);

  async function handleCheckout(tierId: string) {
    setPurchasing(tierId);
    try {
      const { checkout_url } = await api.wallet.checkout(tierId);
      window.location.href = checkout_url;
    } catch (e: any) {
      alert(e.message ?? "Checkout failed");
      setPurchasing(null);
    }
  }

  const tierColors: Record<string, string> = {
    starter: "#4F8EF7",
    plus: "#3DCC7E",
    pro: "#F5C842",
    cinephile: "#9B72CF",
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-5xl animate-pulse">◈</div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-12 fade-up">
      <h1 className="text-3xl font-black mb-2">Wallet</h1>
      <p className="text-[#A0A8C0] mb-10">Credits power your Bazzy Video experience. 1 cr streams ~1 min of content.</p>

      {/* Balance card */}
      {wallet && (
        <div className="mb-10 p-8 rounded-2xl bg-gradient-to-br from-[#1A1D2E] to-[#12151E] border border-white/8">
          <p className="text-sm text-[#5A607A] mb-2 uppercase tracking-wider">Current Balance</p>
          <div className="flex items-baseline gap-3">
            <span className="text-6xl font-black font-mono" style={{ color: wallet.credit_balance < 100 ? "#E05252" : "#3DCC7E" }}>
              ◈ {wallet.credit_balance.toLocaleString()}
            </span>
            <span className="text-[#5A607A]">credits</span>
          </div>
          <p className="text-sm text-[#5A607A] mt-2">
            ≈ ${(wallet.credit_balance / 100).toFixed(2)} value · {Math.floor(wallet.credit_balance / 1)} minutes of streaming
          </p>
        </div>
      )}

      {/* Credit tiers */}
      <section className="mb-12">
        <h2 className="text-xl font-bold mb-6">Add Credits</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {tiers.map((tier) => {
            const color = tierColors[tier.id] ?? "#4F8EF7";
            const hasBonus = tier.bonus_credits > 0;
            return (
              <div
                key={tier.id}
                className="relative rounded-2xl border p-6 flex flex-col gap-4 hover:border-opacity-60 transition-all"
                style={{ borderColor: `${color}30`, background: `${color}08` }}
              >
                {hasBonus && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-xs font-bold px-3 py-1 rounded-full text-black"
                    style={{ background: color }}>
                    +{tier.bonus_credits.toLocaleString()} BONUS
                  </span>
                )}
                <div>
                  <p className="text-sm font-bold uppercase tracking-wider mb-1" style={{ color }}>
                    {tier.label}
                  </p>
                  <p className="text-3xl font-black font-mono" style={{ color }}>
                    ◈ {tier.base_credits.toLocaleString()}
                  </p>
                  {hasBonus && (
                    <p className="text-xs text-[#5A607A]">+ {tier.bonus_credits.toLocaleString()} bonus = {(tier.base_credits + tier.bonus_credits).toLocaleString()} total</p>
                  )}
                </div>
                <button
                  onClick={() => handleCheckout(tier.id)}
                  disabled={purchasing === tier.id}
                  className="mt-auto w-full py-2.5 rounded-xl font-bold text-sm transition-all"
                  style={{ background: color, color: "#000" }}
                >
                  {purchasing === tier.id ? "Redirecting…" : `$${tier.usd.toFixed(2)}`}
                </button>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-[#5A607A] mt-4">
          Payments processed securely by Stripe. Credits are non-refundable once used.
        </p>
      </section>

      {/* Transaction history */}
      <section>
        <h2 className="text-xl font-bold mb-6">Transaction History</h2>
        {transactions.length === 0 ? (
          <p className="text-[#5A607A]">No transactions yet.</p>
        ) : (
          <div className="rounded-xl border border-white/8 overflow-hidden">
            {transactions.map((tx, i) => (
              <div key={tx.id} className={`flex items-center justify-between px-5 py-4 ${i > 0 ? "border-t border-white/5" : ""}`}>
                <div>
                  <p className="text-sm font-medium text-white">{tx.description ?? tx.transaction_type}</p>
                  <p className="text-xs text-[#5A607A]">{new Date(tx.created_at).toLocaleString()}</p>
                </div>
                <span className={`font-mono font-bold text-sm ${tx.amount > 0 ? "text-[#3DCC7E]" : "text-[#E05252]"}`}>
                  {tx.amount > 0 ? "+" : ""}◈ {tx.amount.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

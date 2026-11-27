"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, WalletInfo, CreditTier } from "@/lib/api";
import { useStore } from "@/store/useStore";

export default function WalletPage() {
  const router = useRouter();
  const { isAuthenticated, wallet, fetchWallet } = useStore();
  const [tiers, setTiers] = useState<CreditTier[]>([]);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) { router.push("/auth/login"); return; }
    async function load() {
      try {
        const [t, tx] = await Promise.all([api.wallet.tiers(), api.wallet.transactions()]);
        setTiers(t as any);
        setTransactions(tx);
        await fetchWallet();
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [isAuthenticated]);

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
      <p className="text-[#A0A8C0] mb-10">Credits power Bazzy Live: a livestream ticket is 200 cr and includes 30 days of replay.</p>

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
            ≈ ${(wallet.credit_balance / 100).toFixed(2)} value · {wallet.credit_balance} minutes of streaming
          </p>
        </div>
      )}

      {/* Credit tiers */}
      <section className="mb-12">
        <h2 className="text-xl font-bold mb-6">Add Credits</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {(tiers as any[]).map((tier: any) => {
            const color = tierColors[tier.id] ?? "#4F8EF7";
            const hasBonus = (tier.bonus_credits ?? tier.bonus ?? 0) > 0;
            const baseCredits = tier.base_credits ?? tier.credits ?? 0;
            const bonusCredits = tier.bonus_credits ?? tier.bonus ?? 0;
            return (
              <div
                key={tier.id}
                className="relative rounded-2xl border p-6 flex flex-col gap-4 hover:border-opacity-60 transition-all"
                style={{ borderColor: `${color}30`, background: `${color}08` }}
              >
                {hasBonus && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-xs font-bold px-3 py-1 rounded-full text-black"
                    style={{ background: color }}>
                    +{bonusCredits.toLocaleString()} BONUS
                  </span>
                )}
                <div>
                  <p className="text-sm font-bold uppercase tracking-wider mb-1" style={{ color }}>
                    {tier.label ?? tier.id}
                  </p>
                  <p className="text-3xl font-black font-mono" style={{ color }}>
                    ◈ {baseCredits.toLocaleString()}
                  </p>
                  {hasBonus && (
                    <p className="text-xs text-[#5A607A]">+ {bonusCredits.toLocaleString()} bonus = {(baseCredits + bonusCredits).toLocaleString()} total</p>
                  )}
                </div>
                <button
                  onClick={() => handleCheckout(tier.id)}
                  disabled={purchasing === tier.id}
                  className="mt-auto w-full py-2.5 rounded-xl font-bold text-sm transition-all"
                  style={{ background: color, color: "#000" }}
                >
                  {purchasing === tier.id ? "Redirecting…" : `$${(tier.usd ?? 0).toFixed(2)}`}
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
                <span className={`font-mono font-bold text-sm ${tx.credits_delta > 0 ? "text-[#3DCC7E]" : "text-[#E05252]"}`}>
                  {tx.credits_delta > 0 ? "+" : ""}◈ {(tx.credits_delta ?? 0).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";

function Reset() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const { login } = useStore();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(token ? "" : "This link is missing its code. Open the newest reset email from Bazzy TV.");
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 10) return setError("Use at least 10 characters. A few words work well, like “bayou brass night”.");
    if (password !== again) return setError("The two passwords don't match.");
    setBusy(true);
    try {
      const r = await api.auth.resetPassword(token, password);
      login(r.access_token, r.user_id, r.role);
      setDone(true);
      setTimeout(() => router.push("/"), 1500);
    } catch (e: any) {
      setError(e.message ?? "Couldn't set the new password. Ask for a new link.");
    } finally {
      setBusy(false);
    }
  }

  const input = "w-full bg-[#0A0C14] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-[#4F8EF7] transition-colors";
  return (
    <main className="min-h-screen flex items-center justify-center px-4 bg-[#0A0C14]">
      <div className="w-full max-w-md">
        <Link href="/" className="flex items-center justify-center gap-2 mb-10">
          <span className="text-3xl font-black text-white">BAZZY<span className="text-[#4F8EF7]">TV</span></span>
        </Link>
        <div className="bg-[#12151E] border border-white/8 rounded-2xl p-8">
          {done ? (
            <>
              <h1 className="text-2xl font-black mb-2">Password changed</h1>
              <p className="text-[#A0A8C0] text-sm">You&apos;re signed in. Use the new password on Bazzy TV, Bazzy Live and BazzyBox.</p>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-black mb-2">Set a new password</h1>
              <p className="text-[#A0A8C0] text-sm mb-6">One password for Bazzy TV, Bazzy Live and BazzyBox.</p>
              {error && <div className="mb-5 p-3 rounded-lg bg-[#E05252]/15 border border-[#E05252]/30 text-[#E05252] text-sm">{error}</div>}
              <form onSubmit={submit} className="space-y-4">
                <input type="password" required autoFocus autoComplete="new-password" placeholder="New password (10+ characters)" value={password} onChange={(e) => setPassword(e.target.value)} className={input} />
                <input type="password" required autoComplete="new-password" placeholder="Same password again" value={again} onChange={(e) => setAgain(e.target.value)} className={input} />
                <button disabled={busy || !token} className="w-full py-3 rounded-xl bg-[#4F8EF7] text-white font-semibold disabled:opacity-60">{busy ? "Saving…" : "Save new password"}</button>
              </form>
              <Link href="/auth/forgot" className="mt-6 inline-block text-sm text-[#A0A8C0] hover:text-white">Send me a new link</Link>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

export default function ResetPage() {
  return <Suspense><Reset /></Suspense>;
}

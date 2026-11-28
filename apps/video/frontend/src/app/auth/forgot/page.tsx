"use client";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function Forgot() {
  const [email, setEmail] = useState(useSearchParams().get("email") ?? "");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    try {
      await api.auth.forgotPassword(email.trim());
      setState("sent");
    } catch {
      setState("error");
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4 bg-[#0A0C14]">
      <div className="w-full max-w-md">
        <Link href="/" className="flex items-center justify-center gap-2 mb-10">
          <span className="text-3xl font-black text-white">BAZZY<span className="text-[#4F8EF7]">TV</span></span>
        </Link>
        <div className="bg-[#12151E] border border-white/8 rounded-2xl p-8">
          {state === "sent" ? (
            <>
              <h1 className="text-2xl font-black mb-2">Check your email</h1>
              <p className="text-[#A0A8C0] text-sm">
                If <b className="text-white">{email}</b> has a Bazzy account, a link to set a new password is on its way. It works for an hour.
                Check spam if it doesn&apos;t show up in a minute or two.
              </p>
              <Link href="/auth/login" className="mt-6 inline-block text-sm text-[#4F8EF7] hover:underline">Back to sign in</Link>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-black mb-2">Forgot your password?</h1>
              <p className="text-[#A0A8C0] text-sm mb-6">Enter the email you use for Bazzy TV, Bazzy Live or BazzyBox and we&apos;ll send you a link to set a new one.</p>
              {state === "error" && (
                <div className="mb-5 p-3 rounded-lg bg-[#E05252]/15 border border-[#E05252]/30 text-[#E05252] text-sm">Couldn&apos;t send that right now. Try again in a minute.</div>
              )}
              <form onSubmit={submit} className="space-y-4">
                <input
                  type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email"
                  className="w-full bg-[#0A0C14] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-[#4F8EF7] transition-colors"
                />
                <button disabled={state === "sending"} className="w-full py-3 rounded-xl bg-[#4F8EF7] text-white font-semibold disabled:opacity-60">
                  {state === "sending" ? "Sending…" : "Email me a reset link"}
                </button>
              </form>
              <Link href="/auth/login" className="mt-6 inline-block text-sm text-[#A0A8C0] hover:text-white">Back to sign in</Link>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

export default function ForgotPage() {
  return <Suspense><Forgot /></Suspense>;
}

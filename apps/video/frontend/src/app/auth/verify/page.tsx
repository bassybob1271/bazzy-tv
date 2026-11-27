"use client";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function Verify() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<{ ok?: boolean; claimed?: number; error?: string }>({});

  useEffect(() => {
    if (!token) { setState({ error: "This link is missing its code. Open the newest email from Bazzy TV." }); return; }
    api.auth.verifyEmail(token)
      .then((r) => setState({ ok: true, claimed: r.claimed_credits }))
      .catch((e) => setState({ error: e.message }));
  }, [token]);

  return (
    <main className="min-h-[70vh] flex items-center justify-center px-6">
      <div className="w-full max-w-md rounded-2xl bg-[#141826] border border-[#232a40] p-8 text-center">
        <div className="text-xs font-extrabold tracking-[0.12em] text-[#4F8EF7]">BAZZY TV</div>
        {!state.ok && !state.error && <p className="mt-6 text-[#A0A8C0]">Confirming your email…</p>}
        {state.ok && (
          <>
            <h1 className="mt-4 text-2xl font-bold">You're confirmed</h1>
            {state.claimed ? (
              <p className="mt-3 text-[#A0A8C0]">
                <span className="text-[#F5C842] font-semibold">{state.claimed.toLocaleString()} credits</span> from your splits just landed in your earnings.
                Spend them on films, Bazzy Live and BazzyBox, or cash them out.
              </p>
            ) : (
              <p className="mt-3 text-[#A0A8C0]">One account for films, Bazzy Live concerts and BazzyBox storage.</p>
            )}
            <div className="mt-6 flex gap-3 justify-center">
              {state.claimed ? <Link href="/filmmaker" className="px-5 py-2.5 rounded-full bg-[#4F8EF7] text-white font-semibold">See my earnings</Link> : null}
              <Link href="/" className="px-5 py-2.5 rounded-full border border-white/15">Start watching</Link>
            </div>
          </>
        )}
        {state.error && (
          <>
            <h1 className="mt-4 text-2xl font-bold">That link didn't work</h1>
            <p className="mt-3 text-[#A0A8C0]">{state.error}</p>
            <button onClick={() => api.auth.resendVerification().then(() => setState({ error: "We sent a fresh link. Check your inbox." })).catch(() => setState({ error: "Sign in first, then ask for a new link." }))}
              className="mt-6 px-5 py-2.5 rounded-full bg-[#4F8EF7] text-white font-semibold">Send a new link</button>
          </>
        )}
      </div>
    </main>
  );
}

export default function VerifyPage() {
  return <Suspense><Verify /></Suspense>;
}

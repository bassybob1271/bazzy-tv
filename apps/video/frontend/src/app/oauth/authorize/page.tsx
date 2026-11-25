"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";

/**
 * "Sign in with Bazzy TV": apps like BazzyBox send people here.
 * Signs the user in if needed, asks for consent (skipped for trusted first-party apps),
 * then sends the browser back to the app with a one-time code.
 */
function Authorize() {
  const router = useRouter();
  const q = useSearchParams();
  const { hydrated, isAuthenticated, logout } = useStore();
  const [app, setApp] = useState<{ name: string; trusted: boolean } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const started = useRef(false);

  const req = {
    client_id: q.get("client_id") ?? "",
    redirect_uri: q.get("redirect_uri") ?? "",
    state: q.get("state") ?? "",
    code_challenge: q.get("code_challenge") ?? "",
    code_challenge_method: q.get("code_challenge_method") ?? "S256",
    scope: q.get("scope") ?? "openid profile email",
  };

  // 1. Check the app and its return address before anything else. Unknown apps get an error
  //    page here; we never redirect to an address the app didn't register.
  useEffect(() => {
    if (q.get("response_type") !== "code" || !req.client_id || !req.redirect_uri || !req.code_challenge) {
      setError("This sign-in link is incomplete.");
      return;
    }
    api.oauth.client(req.client_id, req.redirect_uri)
      .then((c) => setApp({ name: c.name, trusted: c.trusted }))
      .catch((e) => setError(e.message ?? "This app isn't allowed to use Bazzy TV sign-in."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2. Not signed in to Bazzy TV yet: sign in, then come straight back here.
  useEffect(() => {
    if (!hydrated || !app || isAuthenticated) return;
    router.replace(`/auth/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }, [hydrated, app, isAuthenticated, router]);

  async function approve() {
    setBusy(true);
    try {
      const { redirect } = await api.oauth.authorize(req);
      window.location.assign(redirect);
    } catch (e: any) {
      if (/credentials/i.test(e.message ?? "")) {
        logout(); // session expired: the effect above sends them to sign in
      } else {
        setError(e.message ?? "Couldn't sign you in. Try again.");
        setBusy(false);
      }
    }
  }

  function deny() {
    const u = new URL(req.redirect_uri);
    u.searchParams.set("error", "access_denied");
    if (req.state) u.searchParams.set("state", req.state);
    window.location.assign(u.toString());
  }

  // 3. First-party apps (BazzyBox) don't need a consent click.
  useEffect(() => {
    if (hydrated && isAuthenticated && app?.trusted && !started.current) {
      started.current = true;
      void approve();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, isAuthenticated, app]);

  const shell = (body: React.ReactNode) => (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[#0A0C14]">
      <div className="w-full max-w-md bg-[#12151E] border border-white/8 rounded-2xl p-8 text-center">{body}</div>
    </div>
  );

  if (error) return shell(<><h1 className="text-xl font-black mb-2">Can't sign in</h1><p className="text-[#A0A8C0] text-sm">{error}</p></>);
  if (!app || !hydrated || !isAuthenticated || app.trusted) return shell(<p className="text-[#A0A8C0] text-sm">Signing you in to {app?.name ?? "the app"}…</p>);

  return shell(
    <>
      <h1 className="text-2xl font-black mb-2">Sign in to {app.name}</h1>
      <p className="text-[#A0A8C0] text-sm mb-6">
        {app.name} wants to use your Bazzy TV account. It will see your name and email address.
      </p>
      <div className="flex gap-3">
        <button onClick={deny} disabled={busy} className="flex-1 py-3 rounded-xl border border-white/15 text-white font-semibold text-sm">Cancel</button>
        <button onClick={approve} disabled={busy} className="flex-1 py-3 rounded-xl bg-[#4F8EF7] text-white font-bold text-sm hover:bg-[#6AA0FF] disabled:opacity-60">
          {busy ? "Signing in…" : "Allow"}
        </button>
      </div>
    </>
  );
}

export default function AuthorizePage() {
  return <Suspense><Authorize /></Suspense>;
}

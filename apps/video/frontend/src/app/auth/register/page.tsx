"use client";
import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { SocialButtons } from "@/components/auth/SocialButtons";

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [asFilmmaker, setAsFilmmaker] = useState(searchParams.get("role") === "filmmaker");
  const [bio, setBio] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const rawRedirect = searchParams.get("redirect");
  const redirect = rawRedirect && rawRedirect.startsWith("/") && !rawRedirect.startsWith("//") ? rawRedirect : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.auth.register({ email, password, display_name: displayName, is_filmmaker: asFilmmaker, bio: asFilmmaker ? bio : undefined });
      // Auto-login
      const res = await api.auth.login(email, password);
      login(res.access_token, res.user_id, res.role);
      router.push(redirect ?? (asFilmmaker ? "/filmmaker" : "/"));
    } catch (e: any) {
      setError(e.message ?? "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[#0A0C14]">
      <div className="w-full max-w-md fade-up">
        <Link href="/" className="flex items-center justify-center gap-2 mb-10">
          <span className="text-3xl font-black text-white">BAZZY<span className="text-[#4F8EF7]">TV</span></span>
        </Link>

        <div className="bg-[#12151E] border border-white/8 rounded-2xl p-8">
          <h1 className="text-2xl font-black mb-2">Create account</h1>
          <p className="text-[#A0A8C0] text-sm mb-8">Join the cooperative cinema platform.</p>

          {/* Role toggle */}
          <div className="flex gap-3 mb-7">
            <button
              type="button"
              onClick={() => setAsFilmmaker(false)}
              className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border transition-all
                ${!asFilmmaker ? "bg-[#4F8EF7] text-white border-[#4F8EF7]" : "bg-transparent text-[#5A607A] border-white/10"}`}
            >
              👁 Viewer
            </button>
            <button
              type="button"
              onClick={() => setAsFilmmaker(true)}
              className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border transition-all
                ${asFilmmaker ? "bg-[#9B72CF] text-white border-[#9B72CF]" : "bg-transparent text-[#5A607A] border-white/10"}`}
            >
              🎬 Filmmaker
            </button>
          </div>

          {error && (
            <div className="mb-5 p-3 rounded-lg bg-[#E05252]/15 border border-[#E05252]/30 text-[#E05252] text-sm">
              {error}
            </div>
          )}

          <SocialButtons next={redirect ?? "/"} verb="Sign up" />

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-[#5A607A] uppercase tracking-wider mb-1.5">Display Name</label>
              <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required
                className="w-full bg-[#0A0C14] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-[#4F8EF7] transition-colors"
                placeholder="Your name" />
            </div>
            <div>
              <label className="block text-xs text-[#5A607A] uppercase tracking-wider mb-1.5">Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                className="w-full bg-[#0A0C14] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-[#4F8EF7] transition-colors"
                placeholder="you@example.com" />
            </div>
            <div>
              <label className="block text-xs text-[#5A607A] uppercase tracking-wider mb-1.5">Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8}
                className="w-full bg-[#0A0C14] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-[#4F8EF7] transition-colors"
                placeholder="Min 8 characters" />
            </div>
            {asFilmmaker && (
              <div>
                <label className="block text-xs text-[#5A607A] uppercase tracking-wider mb-1.5">Bio (optional)</label>
                <textarea value={bio} onChange={(e) => setBio(e.target.value)} rows={3}
                  className="w-full bg-[#0A0C14] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-[#4F8EF7] transition-colors resize-none"
                  placeholder="Tell us about your work…" />
              </div>
            )}

            <button type="submit" disabled={loading}
              className={`w-full py-3 font-bold rounded-xl transition-colors disabled:opacity-60 mt-2
                ${asFilmmaker ? "bg-[#9B72CF] hover:bg-[#B086E5] text-white" : "bg-[#4F8EF7] hover:bg-[#6AA0FF] text-white"}`}>
              {loading ? "Creating account…" : asFilmmaker ? "Join as Filmmaker" : "Start Watching"}
            </button>
          </form>

          {asFilmmaker && (
            <div className="mt-5 p-4 rounded-xl bg-[#9B72CF]/10 border border-[#9B72CF]/20 text-sm text-[#A0A8C0]">
              🎬 As a filmmaker, <strong className="text-white">80%</strong> of every credit spent on your content goes directly to you.
            </div>
          )}

          <p className="text-sm text-center text-[#5A607A] mt-6">
            Already have an account?{" "}
            <Link href="/auth/login" className="text-[#4F8EF7] hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return <Suspense><RegisterForm /></Suspense>;
}

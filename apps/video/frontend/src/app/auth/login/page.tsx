"use client";
import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const redirect = searchParams.get("redirect") ?? "/";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.auth.login(email, password);
      login(res.access_token, res.user_id, res.role);
      router.push(redirect);
    } catch (e: any) {
      setError(e.message ?? "Invalid credentials");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[#0A0C14]">
      <div className="w-full max-w-md fade-up">
        {/* Logo */}
        <Link href="/" className="flex items-center justify-center gap-2 mb-10">
          <span className="text-3xl font-black text-white">BAZZY<span className="text-[#4F8EF7]">VIDEO</span></span>
        </Link>

        <div className="bg-[#12151E] border border-white/8 rounded-2xl p-8">
          <h1 className="text-2xl font-black mb-2">Welcome back</h1>
          <p className="text-[#A0A8C0] text-sm mb-8">Sign in to continue watching.</p>

          {error && (
            <div className="mb-5 p-3 rounded-lg bg-[#E05252]/15 border border-[#E05252]/30 text-[#E05252] text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-[#5A607A] uppercase tracking-wider mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-[#0A0C14] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-[#4F8EF7] transition-colors"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-xs text-[#5A607A] uppercase tracking-wider mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-[#0A0C14] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-[#4F8EF7] transition-colors"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#4F8EF7] text-white font-bold rounded-xl hover:bg-[#6AA0FF] transition-colors disabled:opacity-60 mt-2"
            >
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form>

          <p className="text-sm text-center text-[#5A607A] mt-6">
            Don't have an account?{" "}
            <Link href="/auth/register" className="text-[#4F8EF7] hover:underline">Join Bazzy Video</Link>
          </p>
        </div>

        <p className="text-center text-xs text-[#2A2D40] mt-6">
          80% of every credit goes to filmmakers.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}

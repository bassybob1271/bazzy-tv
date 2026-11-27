"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/store/useStore";

/** Google/Apple sign-in lands here with the session in the URL fragment (never sent to a server). */
export default function AuthCallback() {
  const router = useRouter();
  const { login } = useStore();
  const [error, setError] = useState("");

  useEffect(() => {
    const p = new URLSearchParams(window.location.hash.slice(1));
    const token = p.get("token"), userId = p.get("user_id"), role = p.get("role");
    // Drop the token from the address bar and history right away.
    window.history.replaceState(null, "", "/auth/callback");
    if (!token || !userId || !role) {
      setError("Sign-in didn't complete. Please try again.");
      return;
    }
    login(token, userId, role);
    const next = p.get("next") ?? "/";
    router.replace(next.startsWith("/") && !next.startsWith("//") ? next : "/");
  }, [login, router]);

  return (
    <div className="min-h-screen grid place-items-center bg-[#0A0C14] text-[#A0A8C0] text-sm px-4 text-center">
      {error ? (
        <p>
          {error} <a href="/auth/login" className="text-[#4F8EF7] hover:underline">Back to sign in</a>
        </p>
      ) : (
        <p>Signing you in…</p>
      )}
    </div>
  );
}

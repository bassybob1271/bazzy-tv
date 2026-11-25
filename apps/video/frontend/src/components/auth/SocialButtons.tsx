"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** "Continue with Apple / Google". Renders nothing until the server says a provider is configured. */
export function SocialButtons({ next = "/", verb = "Continue" }: { next?: string; verb?: string }) {
  const [providers, setProviders] = useState<{ google: boolean; apple: boolean } | null>(null);

  useEffect(() => {
    api.auth.providers().then(setProviders).catch(() => setProviders({ google: false, apple: false }));
  }, []);

  if (!providers || (!providers.apple && !providers.google)) return null;

  return (
    <div className="space-y-3 mb-6">
      {providers.apple && (
        <a
          href={api.auth.socialStartUrl("apple", next)}
          className="w-full flex items-center justify-center gap-3 py-3 rounded-xl bg-white text-black font-semibold text-sm hover:bg-white/90 transition-colors"
        >
          <svg aria-hidden="true" width="16" height="18" viewBox="0 0 16 18" fill="currentColor">
            <path d="M13.2 9.6c0-2.3 1.9-3.4 2-3.5-1.1-1.6-2.8-1.8-3.4-1.8-1.4-.1-2.8.9-3.5.9-.7 0-1.8-.8-3-.8C3.7 4.4 2.2 5.3 1.4 6.8c-1.7 2.9-.4 7.2 1.2 9.5.8 1.1 1.7 2.4 2.9 2.4 1.2 0 1.6-.8 3-.8s1.8.8 3 .7c1.3 0 2.1-1.1 2.8-2.3.9-1.3 1.3-2.6 1.3-2.7-.1 0-2.4-.9-2.4-4zM10.9 2.8c.6-.8 1.1-1.8 1-2.8-.9 0-2 .6-2.7 1.4-.6.7-1.1 1.7-1 2.7 1 .1 2-.5 2.7-1.3z" />
          </svg>
          {verb} with Apple
        </a>
      )}
      {providers.google && (
        <a
          href={api.auth.socialStartUrl("google", next)}
          className="w-full flex items-center justify-center gap-3 py-3 rounded-xl bg-[#0A0C14] border border-white/15 text-white font-semibold text-sm hover:border-white/40 transition-colors"
        >
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18">
            <path fill="#4285F4" d="M17.6 9.2c0-.6-.1-1.2-.2-1.8H9v3.4h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.9 2.7-6.5z" />
            <path fill="#34A853" d="M9 18c2.4 0 4.5-.8 6-2.2l-2.9-2.2c-.8.5-1.8.9-3.1.9-2.4 0-4.4-1.6-5.1-3.8H.9v2.3A9 9 0 0 0 9 18z" />
            <path fill="#FBBC05" d="M3.9 10.7a5.4 5.4 0 0 1 0-3.4V5H.9a9 9 0 0 0 0 8l3-2.3z" />
            <path fill="#EA4335" d="M9 3.6c1.3 0 2.5.5 3.5 1.4l2.6-2.6A9 9 0 0 0 .9 5l3 2.3C4.6 5.2 6.6 3.6 9 3.6z" />
          </svg>
          {verb} with Google
        </a>
      )}
      <div className="flex items-center gap-3 pt-1 text-xs text-[#5A607A]">
        <span className="h-px flex-1 bg-white/10" />or use email<span className="h-px flex-1 bg-white/10" />
      </div>
    </div>
  );
}

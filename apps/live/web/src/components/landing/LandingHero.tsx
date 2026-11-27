import Link from "next/link";

/**
 * Bazzy landing hero with the spinning logo — ported from the previous
 * Bazzy TV (Lovable) build and adapted for Bazzy Live.
 */
export function LandingHero() {
  return (
    <section className="relative min-h-[calc(100vh-4rem)] flex items-center justify-center overflow-hidden">
      {/* Background image */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: "url(/brand/hero-bg.webp)" }}
      />

      {/* Overlay — fades into the page background */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#0A0C14]/80 via-[#0A0C14]/60 to-[#0A0C14]" />

      {/* Red glow */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full opacity-30 pointer-events-none"
        style={{ background: "radial-gradient(ellipse at center, hsl(0 72% 42% / 0.18), transparent 70%)" }}
      />

      {/* Large spinning logo behind the text */}
      <div className="absolute top-[30%] left-1/2 -translate-x-1/2 -translate-y-1/2 z-[1] pointer-events-none">
        <img
          src="/brand/bazzy-logo.webp"
          alt=""
          aria-hidden="true"
          className="w-[60vw] max-w-[500px] md:max-w-[600px] lg:max-w-[700px] h-auto rounded-full opacity-25 bz-logo-spin"
        />
      </div>

      <div className="relative z-10 w-full max-w-[1440px] mx-auto px-6 pt-24 pb-16">
        <div className="max-w-4xl mx-auto text-center">
          <h1
            className="text-5xl md:text-7xl lg:text-8xl font-bold mb-6 bz-slide-up"
            style={{ animationDelay: "0.1s" }}
          >
            <span className="text-[#E33B3B]">Bazzy</span>
            <span className="block mt-2">Your films</span>
            <span className="block mt-2">Your future</span>
          </h1>

          <p
            className="text-xl md:text-2xl text-[#A0A8C0] mb-12 max-w-2xl mx-auto bz-slide-up"
            style={{ animationDelay: "0.2s" }}
          >
            Cinema for the Community. Industry for the filmmaker, movies for people.
          </p>

          <div
            className="flex flex-col sm:flex-row items-center justify-center gap-4 bz-slide-up"
            style={{ animationDelay: "0.3s" }}
          >
            <Link
              href="/discover"
              className="inline-flex items-center gap-3 h-14 rounded-xl px-10 text-lg font-semibold text-white bg-gradient-to-br from-[#B91E1E] to-[#E33B3B] shadow-[0_0_60px_hsl(0_72%_42%/0.35)] hover:scale-105 transition-transform"
            >
              <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden="true">
                <path d="M8 5v14l11-7z" />
              </svg>
              Start Watching
            </Link>
            <Link
              href="/wallet"
              className="inline-flex items-center h-14 rounded-xl px-10 text-lg font-semibold border-2 border-white/20 text-white backdrop-blur-sm hover:border-[#B91E1E] hover:bg-[#B91E1E]/10 transition-colors"
            >
              Buy Credits
            </Link>
          </div>

          <p className="mt-8 text-sm text-[#A0A8C0] bz-fade-in" style={{ animationDelay: "0.5s" }}>
            $10 = 1,000 credits • 80% goes to filmmakers
          </p>
        </div>

        {/* Floating glass orbs */}
        <div className="absolute top-1/4 left-10 w-20 h-20 rounded-full bz-glass bz-float opacity-50" style={{ animationDelay: "0s" }} />
        <div className="absolute bottom-1/4 right-10 w-16 h-16 rounded-full bz-glass bz-float opacity-50" style={{ animationDelay: "2s" }} />
        <div className="absolute top-1/3 right-1/4 w-12 h-12 rounded-full bz-glass bz-float opacity-30" style={{ animationDelay: "4s" }} />
      </div>
    </section>
  );
}

"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, Title } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { VideoPlayer } from "@/components/player/VideoPlayer";
import { TitleCard } from "@/components/ui/TitleCard";
import { LivePlayer } from "@/components/player/LivePlayer";
import { CAT_COLORS, LIVE_RED, categoryLabel, countdown, isOnAir, isReplay, isUpcoming, showTime } from "@/lib/live";

function StarRating({ value, onRate }: { value: number; onRate: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((s) => (
        <button
          key={s}
          onMouseEnter={() => setHover(s)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onRate(s)}
          className="text-xl transition-transform hover:scale-125"
          style={{ color: s <= (hover || value) ? "#F5C842" : "#2A2D40" }}
        >
          ★
        </button>
      ))}
    </div>
  );
}

export default function WatchPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const { isAuthenticated, wallet, fetchWallet } = useStore();
  // Normalize balance — backend returns credit_balance, store may expose either
  const creditBalance = (wallet as any)?.credit_balance ?? (wallet as any)?.balance ?? 0;

  const [title, setTitle] = useState<Title | null>(null);
  const [related, setRelated] = useState<Title[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [hasAccess, setHasAccess] = useState(false);
  const [userRating, setUserRating] = useState(0);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [purchasing, setPurchasing] = useState(false);
  const [showPlayer, setShowPlayer] = useState(false);
  const [highlightRent, setHighlightRent] = useState(false);

  // The player opens at the top of the page; on phones the Play button is
  // further down, so bring the player into view.
  useEffect(() => {
    if (showPlayer) window.scrollTo({ top: 0, behavior: "smooth" });
  }, [showPlayer]);

  // Signed in: check whether this viewer already rented or bought the title.
  // Runs again once a saved sign-in is restored after page load.
  const titleId = title?.id;
  const titleIsFree = title?.is_free;
  useEffect(() => {
    if (!titleId || titleIsFree || !isAuthenticated) return;
    let cancelled = false;
    api.titles.access(titleId)
      .then((a) => { if (!cancelled && a.has_access) setHasAccess(true); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [titleId, titleIsFree, isAuthenticated]);

  // Arriving from the home slider (/watch/<slug>#rent): bring the Rent button into view
  useEffect(() => {
    if (loading || !title || window.location.hash !== "#rent") return;
    document.getElementById("rent")?.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlightRent(true);
    const t = setTimeout(() => setHighlightRent(false), 2500);
    return () => clearTimeout(t);
  }, [loading, title]);

  useEffect(() => {
    async function load() {
      try {
        const raw = await api.titles.detail(slug);
        // Normalize hls_manifest_url → hls_master_url so VideoPlayer finds it
        const t = { ...raw, hls_master_url: raw.hls_master_url ?? raw.hls_manifest_url };
        setTitle(t);
        setHasAccess(t.is_free || !!t.has_access);
        // Load related
        const r = await api.titles.discover({ category: t.category, limit: 8 });
        setRelated(r.filter((x) => x.id !== t.id));
      } catch (e: any) {
        setError(e.message ?? "Title not found");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [slug]);

  // Before and during the show, keep live_state fresh so the page flips to
  // the player when the ATEM goes live and to the replay when it ends.
  const liveState = title?.live_state;
  useEffect(() => {
    if (!slug || liveState === "ended") return;
    const t = setInterval(() => {
      api.titles.detail(slug)
        .then((fresh) => setTitle((cur) => cur && { ...cur, ...fresh, hls_master_url: fresh.hls_manifest_url ?? cur.hls_master_url }))
        .catch(() => {});
    }, 20_000);
    return () => clearInterval(t);
  }, [slug, liveState]);

  // Arriving from the home page's "now live" box (?play=1): open the player
  const autoPlay = !!title && hasAccess && title.live_state === "on_air";
  useEffect(() => {
    if (!autoPlay || new URLSearchParams(window.location.search).get("play") !== "1") return;
    setShowPlayer(true);
    window.history.replaceState(null, "", window.location.pathname);
  }, [autoPlay]);

  async function handleRent() {
    if (!isAuthenticated) { router.push("/auth/login"); return; }
    if (!title) return;
    setPurchasing(true);
    try {
      // On air: join for the lower in-progress price; otherwise a full ticket
      if (title.live_state === "on_air") await api.live.join(title.id);
      else await api.titles.rent(title.id);
      setHasAccess(true);
      await fetchWallet();
    } catch (e: any) {
      alert(e.message ?? "Purchase failed");
    } finally {
      setPurchasing(false);
    }
  }

  async function handleBuy() {
    if (!isAuthenticated) { router.push("/auth/login"); return; }
    if (!title) return;
    setPurchasing(true);
    try {
      await api.titles.buy(title.id);
      setHasAccess(true);
      await fetchWallet();
    } catch (e: any) {
      alert(e.message ?? "Purchase failed");
    } finally {
      setPurchasing(false);
    }
  }

  async function handleVote(v: number) {
    if (!isAuthenticated || !title) return;
    setUserRating(v);
    await api.titles.vote(title.id, v);
  }

  async function handleWatchlist() {
    if (!isAuthenticated || !title) return;
    setInWatchlist(!inWatchlist);
    await api.titles.watchlist(title.id);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-5xl animate-pulse">◈</div>
      </div>
    );
  }

  if (error || !title) {
    return (
      <div className="text-center py-24 px-6">
        <p className="text-5xl mb-4">🎬</p>
        <h2 className="text-xl font-bold mb-2">Livestream not found</h2>
        <button onClick={() => router.back()} className="text-[#4F8EF7] hover:underline">← Go back</button>
      </div>
    );
  }

  const accent = CAT_COLORS[title.category] ?? "#4F8EF7";
  const onAir = isOnAir(title);
  const upcoming = isUpcoming(title);
  const replay = isReplay(title);
  // Upcoming: a ticket is confirmed but there's nothing to play yet
  const canPlay = hasAccess && (onAir || (replay && !!title.hls_master_url));
  // While on air, joining costs join_credits (100) instead of the full ticket
  const ticketPrice = title.live_state === "on_air" ? (title.join_credits ?? title.rent_credits) : title.rent_credits;
  const canAffordRent = creditBalance >= ticketPrice;
  const canAffordBuy = creditBalance >= title.buy_credits;

  return (
    <div className="max-w-[1440px] mx-auto fade-up">
      {/* Hero backdrop */}
      {!showPlayer && (
        <div className="relative h-[55vh] min-h-[400px] overflow-hidden">
          {title.backdrop_url ? (
            <img src={title.backdrop_url} alt="" className="w-full h-full object-cover" />
          ) : title.poster_url ? (
            <img src={title.poster_url} alt="" className="w-full h-full object-cover object-[center_30%] blur-xl scale-110 opacity-70" />
          ) : (
            <div className="w-full h-full" style={{ background: `linear-gradient(135deg, ${accent}22, #0A0C14)` }} />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0A0C14] via-black/40 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-r from-black/60 to-transparent" />

          {/* Play button overlay */}
          {canPlay && (
            <div className="absolute inset-0 flex items-center justify-center">
              <button
                onClick={() => setShowPlayer(true)}
                className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-md hover:bg-white/30 transition-all
                           flex items-center justify-center text-4xl border-2 border-white/40 hover:scale-110"
              >
                ▶
              </button>
            </div>
          )}
        </div>
      )}

      {/* Live player (ATEM feed) */}
      {showPlayer && onAir && (
        <div className="bg-black">
          <LivePlayer title={title} onEnded={() => setShowPlayer(false)} />
        </div>
      )}

      {/* Replay player */}
      {showPlayer && !onAir && title.hls_master_url && (
        <div className="bg-black">
          <VideoPlayer
            // VideoPlayer reads hls_manifest_url; pass the normalized URL through it
            title={{ ...title, hls_manifest_url: title.hls_master_url }}
            onComplete={() => setShowPlayer(false)}
          />
        </div>
      )}

      {/* Detail section: overlaps the hero, but must not cover the player */}
      <div className={`px-6 md:px-16 relative z-10 pb-10 ${showPlayer ? "mt-6" : "-mt-20"}`}>
        <div className="flex gap-8 items-start">
          {/* Poster */}
          {title.poster_url && (
            <div className="hidden md:block w-40 flex-shrink-0 rounded-lg overflow-hidden shadow-2xl border border-white/10">
              <img src={title.poster_url} alt={title.title} className="w-full" />
            </div>
          )}

          {/* Info */}
          <div className="flex-1 min-w-0">
            {/* Category + meta */}
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xs font-bold uppercase px-2 py-1 rounded" style={{ background: `${accent}33`, color: accent }}>
                {categoryLabel(title.category)}
              </span>
              {onAir && (
                <span className="flex items-center gap-1.5 text-xs font-black text-white px-2 py-1 rounded" style={{ background: LIVE_RED }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> LIVE NOW
                </span>
              )}
              {upcoming && <span className="text-xs font-bold uppercase text-[#E33B3B]">Upcoming · {countdown(title.starts_at)}</span>}
              {replay && <span className="text-xs font-bold uppercase text-[#5A607A]">Replay</span>}
              {title.runtime_minutes && <span className="text-[#5A607A] text-sm">{title.runtime_minutes} min</span>}
              {title.is_free && <span className="text-xs font-bold bg-[#3DCC7E] text-black px-2 py-0.5 rounded">FREE</span>}
            </div>

            <h1 className="text-3xl md:text-5xl font-black mb-4 leading-tight">{title.title}</h1>

            {title.synopsis && (
              <p className="text-[#A0A8C0] leading-relaxed mb-6 max-w-2xl">{title.synopsis}</p>
            )}

            {/* Who, when, where */}
            <div className="text-sm text-[#A0A8C0] mb-6 space-y-1">
              {title.performer_name && <p className="text-white text-lg font-semibold">{title.performer_name}</p>}
              {title.starts_at && <p>{replay ? "Streamed " : ""}{showTime(title.starts_at)}</p>}
              {title.venue && <p className="text-[#5A607A]">{title.venue}</p>}
            </div>

            {/* Action row */}
            <div
              id="rent"
              className={`flex flex-wrap items-center gap-4 mb-8 scroll-mt-24 rounded-2xl transition-shadow duration-500
                ${highlightRent ? "ring-2 ring-[#E33B3B] ring-offset-8 ring-offset-[#0A0C14]" : ""}`}
            >
              {hasAccess ? (
                canPlay ? (
                  <button
                    onClick={() => setShowPlayer(true)}
                    className="px-8 py-3 bg-white text-black font-bold rounded-full hover:bg-[#E0E0E0] transition-colors"
                  >
                    {onAir ? "● Watch live" : "▶ Play replay"}
                  </button>
                ) : (
                  <div className="px-6 py-3 rounded-full bg-[#3DCC7E]/15 border border-[#3DCC7E]/40 text-[#3DCC7E] font-semibold text-sm">
                    ✓ {title.is_free ? "You're on the list" : "Ticket confirmed"} — the stream opens here {countdown(title.starts_at)}
                  </div>
                )
              ) : (
                <>
                  {!isAuthenticated ? (
                    <button
                      onClick={() => router.push("/auth/login")}
                      className="px-8 py-3 bg-[#E33B3B] text-white font-bold rounded-full hover:bg-[#F25555] transition-colors"
                    >
                      Sign in for tickets
                    </button>
                  ) : (
                    <>
                      <button
                        onClick={handleRent}
                        disabled={purchasing || !canAffordRent}
                        className={`flex items-center gap-2 px-6 py-3 rounded-full font-semibold text-sm transition-all
                          ${canAffordRent ? "bg-[#E33B3B] text-white hover:bg-[#F25555]" : "bg-white/10 text-[#5A607A] cursor-not-allowed"}`}
                      >
                        <span>{replay ? "Rent replay" : onAir ? "Join now" : "Get ticket"}</span>
                        <span className="font-mono">◈ {ticketPrice}</span>
                      </button>
                      {replay && (
                        <button
                          onClick={handleBuy}
                          disabled={purchasing || !canAffordBuy}
                          className={`flex items-center gap-2 px-6 py-3 rounded-full font-semibold text-sm border transition-all
                            ${canAffordBuy ? "border-[#F5C842]/50 text-[#F5C842] hover:bg-[#F5C842]/10" : "border-white/10 text-[#5A607A] cursor-not-allowed"}`}
                        >
                          <span>Buy replay</span>
                          <span className="font-mono">◈ {title.buy_credits}</span>
                        </button>
                      )}
                      {!canAffordRent && (
                        <button
                          onClick={() => router.push("/wallet")}
                          className="text-sm text-[#4F8EF7] hover:underline"
                        >
                          + Add credits
                        </button>
                      )}
                    </>
                  )}
                </>
              )}

              {/* Watchlist */}
              <button
                onClick={handleWatchlist}
                className={`flex items-center gap-1.5 px-4 py-3 rounded-full text-sm border transition-all
                  ${inWatchlist ? "border-[#3DCC7E]/50 text-[#3DCC7E] bg-[#3DCC7E]/10" : "border-white/10 text-[#A0A8C0] hover:border-white/30"}`}
              >
                {inWatchlist ? "✓ Saved" : "+ Watchlist"}
              </button>
            </div>

            {/* Rating */}
            {isAuthenticated && (
              <div className="flex items-center gap-3 mb-2">
                <span className="text-sm text-[#5A607A]">Rate this:</span>
                <StarRating value={userRating} onRate={handleVote} />
              </div>
            )}

            {!hasAccess && !replay && !title.is_free && (
              <p className="text-xs text-[#5A607A] -mt-4 mb-6">{onAir ? "Joining" : "Ticket"} includes 30 days of replay · 80% goes to the performing artist</p>
            )}

            {/* Algo stats */}
            {replay && <div className="flex gap-6 mt-6 text-sm text-[#5A607A]">
              <span>Completion {Math.round(title.completion_rate * 100)}%</span>
              <span>Fan Score {Math.round(title.fan_vote_score * 100)}%</span>
            </div>}
          </div>
        </div>
      </div>

      {/* Related */}
      {related.length > 0 && (
        <section className="px-6 md:px-16 pb-16">
          <h2 className="text-lg font-bold text-white mb-5">More livestreams</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {related.map((t) => (
              <TitleCard key={t.id} title={t} size="sm" />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

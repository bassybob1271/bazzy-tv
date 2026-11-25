"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, Title } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { VideoPlayer } from "@/components/player/VideoPlayer";
import { TitleCard } from "@/components/ui/TitleCard";

const CAT_COLORS: Record<string, string> = {
  documentary: "#4F8EF7",
  romance: "#E8629A",
  crime: "#E05252",
  horror: "#9B72CF",
  new_releases: "#F5C842",
};

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

  const [title, setTitle] = useState<Title | null>(null);
  const [related, setRelated] = useState<Title[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [hasAccess, setHasAccess] = useState(false);
  const [userRating, setUserRating] = useState(0);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [purchasing, setPurchasing] = useState(false);
  const [showPlayer, setShowPlayer] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const t = await api.titles.get(slug);
        setTitle(t);
        setHasAccess(t.is_free || (t as any).has_access);
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

  async function handleRent() {
    if (!isAuthenticated) { router.push("/auth/login"); return; }
    if (!title) return;
    setPurchasing(true);
    try {
      await api.titles.rent(title.id);
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
    await api.titles.addWatchlist(title.id);
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
        <h2 className="text-xl font-bold mb-2">Title not found</h2>
        <button onClick={() => router.back()} className="text-[#4F8EF7] hover:underline">← Go back</button>
      </div>
    );
  }

  const accent = CAT_COLORS[title.category] ?? "#4F8EF7";
  const balance = wallet?.credit_balance ?? 0;
  const canAffordRent = balance >= title.rent_credits;
  const canAffordBuy = balance >= title.buy_credits;

  return (
    <div className="max-w-[1440px] mx-auto fade-up">
      {/* Hero backdrop */}
      {!showPlayer && (
        <div className="relative h-[55vh] min-h-[400px] overflow-hidden">
          {title.poster_url ? (
            <img src={title.poster_url} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full" style={{ background: `linear-gradient(135deg, ${accent}22, #0A0C14)` }} />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0A0C14] via-black/40 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-r from-black/60 to-transparent" />

          {/* Play button overlay */}
          {hasAccess && (
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

      {/* Player */}
      {showPlayer && title.hls_manifest_url && (
        <div className="bg-black">
          <VideoPlayer
            title={title}
            onComplete={() => setShowPlayer(false)}
          />
        </div>
      )}

      {/* Detail section */}
      <div className={`px-6 md:px-16 relative z-10 pb-10 ${showPlayer ? "mt-8" : "-mt-20"}`}>
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
                {title.category.replace("_", " ")}
              </span>
              {title.year && <span className="text-[#5A607A] text-sm">{title.year}</span>}
              {title.runtime_minutes && <span className="text-[#5A607A] text-sm">{title.runtime_minutes} min</span>}
              {title.is_free && <span className="text-xs font-bold bg-[#3DCC7E] text-black px-2 py-0.5 rounded">FREE</span>}
            </div>

            <h1 className="text-3xl md:text-5xl font-black mb-4 leading-tight">{title.title}</h1>

            {title.synopsis && (
              <p className="text-[#A0A8C0] leading-relaxed mb-6 max-w-2xl">{title.synopsis}</p>
            )}

            {/* Filmmaker */}
            {(title as any).filmmaker_name && (
              <p className="text-sm text-[#5A607A] mb-6">
                Directed by <span className="text-white">{(title as any).filmmaker_name}</span>
              </p>
            )}

            {/* Action row */}
            <div className="flex flex-wrap items-center gap-4 mb-8">
              {hasAccess ? (
                <button
                  onClick={() => setShowPlayer(true)}
                  className="px-8 py-3 bg-white text-black font-bold rounded-full hover:bg-[#E0E0E0] transition-colors"
                >
                  ▶ Play
                </button>
              ) : (
                <>
                  {!isAuthenticated ? (
                    <button
                      onClick={() => router.push("/auth/login")}
                      className="px-8 py-3 bg-[#4F8EF7] text-white font-bold rounded-full hover:bg-[#6AA0FF] transition-colors"
                    >
                      Sign in to watch
                    </button>
                  ) : (
                    <>
                      <button
                        onClick={handleRent}
                        disabled={purchasing || !canAffordRent}
                        className={`flex items-center gap-2 px-6 py-3 rounded-full font-semibold text-sm transition-all
                          ${canAffordRent ? "bg-[#4F8EF7] text-white hover:bg-[#6AA0FF]" : "bg-white/10 text-[#5A607A] cursor-not-allowed"}`}
                      >
                        <span>Rent</span>
                        <span className="font-mono">◈ {title.rent_credits}</span>
                      </button>
                      <button
                        onClick={handleBuy}
                        disabled={purchasing || !canAffordBuy}
                        className={`flex items-center gap-2 px-6 py-3 rounded-full font-semibold text-sm border transition-all
                          ${canAffordBuy ? "border-[#F5C842]/50 text-[#F5C842] hover:bg-[#F5C842]/10" : "border-white/10 text-[#5A607A] cursor-not-allowed"}`}
                      >
                        <span>Buy</span>
                        <span className="font-mono">◈ {title.buy_credits}</span>
                      </button>
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

            {/* Algo stats */}
            <div className="flex gap-6 mt-6 text-sm text-[#5A607A]">
              <span>Completion {Math.round(title.completion_rate * 100)}%</span>
              <span>Fan Score {Math.round(title.fan_vote_score * 100)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Related */}
      {related.length > 0 && (
        <section className="px-6 md:px-16 pb-16">
          <h2 className="text-lg font-bold text-white mb-5">More like this</h2>
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

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Title, HomeRails } from "@/lib/api";
import { TitleCard } from "@/components/ui/TitleCard";

function HeroBanner({ title }: { title: Title }) {
  return (
    <div className="relative h-[70vh] min-h-[500px] overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0">
        {title.poster_url ? (
          <img src={title.poster_url} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-[#1A1D2E] to-[#0A0C14]" />
        )}
        <div className="absolute inset-0 bg-gradient-to-r from-black/90 via-black/50 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0A0C14] via-transparent to-transparent" />
      </div>

      {/* Content */}
      <div className="relative z-10 h-full flex items-end pb-16 px-6 md:px-16 max-w-[1440px] mx-auto">
        <div className="max-w-xl fade-up">
          <span className="text-xs font-bold uppercase tracking-widest text-[#4F8EF7] mb-3 block">
            Featured
          </span>
          <h1 className="text-4xl md:text-6xl font-black leading-tight mb-4">{title.title}</h1>
          {title.synopsis && (
            <p className="text-[#A0A8C0] text-base leading-relaxed line-clamp-3 mb-6">
              {title.synopsis}
            </p>
          )}
          <div className="flex items-center gap-4">
            <Link
              href={`/watch/${title.slug}`}
              className="px-8 py-3 bg-white text-black font-bold rounded-full hover:bg-[#E0E0E0] transition-colors text-sm"
            >
              ▶ Watch Now
            </Link>
            <Link
              href={`/watch/${title.slug}`}
              className="px-8 py-3 bg-white/15 text-white font-semibold rounded-full hover:bg-white/25 transition-colors text-sm backdrop-blur-sm"
            >
              More Info
            </Link>
            {!title.is_free && (
              <span className="text-sm text-[#F5C842] font-mono">
                ◈ {title.rent_credits} rent · {title.buy_credits} buy
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Rail({ label, titles, size = "md" }: { label: string; titles: Title[]; size?: "sm" | "md" | "lg" }) {
  if (!titles || titles.length === 0) return null;
  return (
    <section className="mb-10">
      <h2 className="text-lg font-bold text-white px-6 md:px-16 mb-4">{label}</h2>
      <div className="scroll-x flex gap-4 px-6 md:px-16 pb-2">
        {titles.map((t) => (
          <TitleCard key={t.id} title={t} size={size} />
        ))}
      </div>
    </section>
  );
}

export default function HomePage() {
  const [rails, setRails] = useState<HomeRails | null>(null);
  const [featured, setFeatured] = useState<Title | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const r = await api.titles.homeRails();
        setRails(r);
        // Pick hero from trending or new releases
        const heroPool = [...(r.trending ?? []), ...(r.new_releases ?? [])];
        if (heroPool.length > 0) {
          setFeatured(heroPool[Math.floor(Math.random() * Math.min(3, heroPool.length))]);
        }
      } catch (e) {
        console.error("Failed to load home rails", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-center">
          <div className="text-5xl mb-4 animate-pulse">◈</div>
          <p className="text-[#5A607A]">Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Hero */}
      {featured && <HeroBanner title={featured} />}

      {/* Rails */}
      {rails && (
        <div className="mt-8">
          {rails.trending?.length > 0 && <Rail label="🔥 Trending Now" titles={rails.trending} size="md" />}
          {rails.new_releases?.length > 0 && <Rail label="⚡ New Releases" titles={rails.new_releases} size="lg" />}
          {rails.fan_picks?.length > 0 && <Rail label="🗳️ Fan Picks" titles={rails.fan_picks} />}
          {rails.documentary?.length > 0 && <Rail label="📽️ Documentary" titles={rails.documentary} />}
          {rails.romance?.length > 0 && <Rail label="💕 Romance" titles={rails.romance} />}
          {rails.crime?.length > 0 && <Rail label="🔍 Crime" titles={rails.crime} />}
          {rails.horror?.length > 0 && <Rail label="👻 Horror" titles={rails.horror} />}
          {(() => {
            const seen = new Set<string>();
            const free = [...rails.trending, ...rails.new_arrivals, ...rails.new_releases]
              .filter((t) => t.is_free && !seen.has(t.id) && seen.add(t.id));
            return free.length > 0 ? <Rail label="🎁 Free to Watch" titles={free} size="sm" /> : null;
          })()}
        </div>
      )}

      {/* Empty state */}
      {!rails && (
        <div className="text-center py-24 px-6">
          <p className="text-6xl mb-6">🎬</p>
          <h2 className="text-2xl font-bold mb-3">No titles yet</h2>
          <p className="text-[#A0A8C0] mb-8">Be the first filmmaker to upload your work.</p>
          <Link href="/auth/register?role=filmmaker" className="px-8 py-3 bg-[#4F8EF7] text-white font-bold rounded-full hover:bg-[#6AA0FF] transition-colors">
            Upload Your Film
          </Link>
        </div>
      )}

      {/* Co-op pitch banner */}
      <section className="mx-6 md:mx-16 mb-16 mt-6 rounded-2xl overflow-hidden bg-gradient-to-r from-[#4F8EF7]/15 via-[#1A1D2E] to-[#9B72CF]/15 border border-white/8 p-10">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-black mb-3">80% goes to filmmakers. Always.</h2>
          <p className="text-[#A0A8C0] mb-6">
            Bazzy Video is a cooperative platform. Every credit you spend flows directly to the people who made what you're watching.
            No ads. No algorithms built to addict. Just great cinema.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link href="/auth/register" className="px-6 py-2.5 bg-[#4F8EF7] text-white font-bold rounded-full hover:bg-[#6AA0FF] transition-colors text-sm">
              Start Watching — $10 for 1,000 credits
            </Link>
            <Link href="/auth/register?role=filmmaker" className="px-6 py-2.5 border border-[#4F8EF7]/40 text-[#4F8EF7] font-semibold rounded-full hover:bg-[#4F8EF7]/10 transition-colors text-sm">
              I'm a Filmmaker →
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

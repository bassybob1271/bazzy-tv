"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Title, HomeRails } from "@/lib/api";
import { TitleCard } from "@/components/ui/TitleCard";
import { PreviewSlider, Slide } from "@/components/home/PreviewSlider";

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

/** Slider panes: posters for upcoming livestreams, soonest first. The show
 *  that's on air gets the "now live" preview box instead of a pane. */
function buildSlides(r: HomeRails): Slide[] {
  return (r.upcoming ?? [])
    .filter((t) => t.live_state !== "on_air")
    .map((t, i) => ({ title: t, advance: i === 0 }));
}

const currentShow = (r: HomeRails) => (r.upcoming ?? []).find((t) => t.live_state === "on_air") ?? null;

// "Previous Livestreams" menu: same layout as Bazzy TV's film rails
const RAILS: { key: keyof HomeRails; label: string; size?: "sm" | "md" | "lg" }[] = [
  { key: "previous",       label: "⏪ Previous Livestreams", size: "lg" },
  { key: "concerts",       label: "🎤 Concerts" },
  { key: "album_releases", label: "💿 Album Releases" },
  { key: "listening",      label: "🎧 Listening Sessions" },
  { key: "screenings",     label: "🎬 Screenings" },
  { key: "sound_baths",    label: "🌊 Sound Baths" },
];

export default function HomePage() {
  const [rails, setRails] = useState<HomeRails | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.titles.homeRails()
      .then(setRails)
      .catch((e) => console.error("Failed to load home rails", e))
      .finally(() => setLoading(false));
    // Pick up a show going on air (or ending) without a reload
    const t = setInterval(() => { api.titles.homeRails().then(setRails).catch(() => {}); }, 30_000);
    return () => clearInterval(t);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-5xl mb-4 animate-pulse">◈</div>
          <p className="text-[#5A607A]">Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Upcoming livestream posters, rotating every 5 s */}
      {rails && <PreviewSlider slides={buildSlides(rails)} current={currentShow(rails)} />}

      {/* Rails */}
      {rails && (
        <div className="mt-8">
          {RAILS.map(({ key, label, size }) => (
            <Rail key={key} label={label} titles={rails[key] ?? []} size={size} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!rails && (
        <div className="text-center py-24 px-6">
          <p className="text-6xl mb-6">🎤</p>
          <h2 className="text-2xl font-bold mb-3">No livestreams yet</h2>
          <p className="text-[#A0A8C0] mb-8">Be the first artist to schedule a show.</p>
          <Link href="/auth/register?role=artist" className="px-8 py-3 bg-[#E33B3B] text-white font-bold rounded-full hover:bg-[#F25555] transition-colors">
            Schedule a Livestream
          </Link>
        </div>
      )}

      {/* Co-op pitch banner */}
      <section className="mx-6 md:mx-16 mb-16 mt-6 rounded-2xl overflow-hidden bg-gradient-to-r from-[#E33B3B]/15 via-[#1A1D2E] to-[#9B72CF]/15 border border-white/8 p-10">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-black mb-3">80% goes to the performing artist. Always.</h2>
          <p className="text-[#A0A8C0] mb-6">
            Bazzy Live is a cooperative platform. Every ticket you buy flows directly to the artists on stage.
            No ads. No algorithms built to addict. Just the show, live from the room.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link href="/auth/register" className="px-6 py-2.5 bg-[#4F8EF7] text-white font-bold rounded-full hover:bg-[#6AA0FF] transition-colors text-sm">
              Get Tickets — $10 for 1,000 credits
            </Link>
            <Link href="/auth/register?role=artist" className="px-6 py-2.5 border border-[#4F8EF7]/40 text-[#4F8EF7] font-semibold rounded-full hover:bg-[#4F8EF7]/10 transition-colors text-sm">
              I'm an Artist →
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

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

/** Pane 1: advance poster for the newest release. Panes 2–5: editorial picks, then trending. */
function buildSlides(r: HomeRails): Slide[] {
  const slides: Slide[] = [];
  const seen = new Set<string>();
  const add = (t: Title | undefined, advance = false) => {
    if (!t || seen.has(t.id) || slides.length >= 5) return;
    seen.add(t.id);
    slides.push({ title: t, advance });
  };
  add(r.new_releases?.[0], true);
  [...(r.hero ?? []), ...(r.trending ?? []), ...(r.new_releases ?? [])].forEach((t) => add(t));
  return slides;
}

const RAILS: { key: keyof HomeRails; label: string; size?: "sm" | "md" | "lg" }[] = [
  { key: "new_releases", label: "⚡ New Releases", size: "lg" },
  { key: "documentary",  label: "📽️ Documentary" },
  { key: "crime",        label: "🔍 True Crime" },
  { key: "horror",       label: "👻 Horror" },
  { key: "comedy",       label: "😂 Comedy" },
];

export default function HomePage() {
  const [rails, setRails] = useState<HomeRails | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.titles.homeRails()
      .then(setRails)
      .catch((e) => console.error("Failed to load home rails", e))
      .finally(() => setLoading(false));
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
      {/* Preview slider: 5 panes, rotates every 5 s */}
      {rails && <PreviewSlider slides={buildSlides(rails)} />}

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

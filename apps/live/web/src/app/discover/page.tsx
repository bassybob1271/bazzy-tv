"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api, Title } from "@/lib/api";
import { TitleCard } from "@/components/ui/TitleCard";
import { CATEGORIES } from "@/lib/live";

// Each q contains a keyword the API's mood search understands
const MOODS = [
  { label: "Concert night", emoji: "🎤", q: "concert" },
  { label: "Live music", emoji: "🎸", q: "live music" },
  { label: "Album release parties", emoji: "💿", q: "album release" },
  { label: "Chill listening", emoji: "🎧", q: "chill listening" },
  { label: "Meditation & sound", emoji: "🌊", q: "meditation sound bath" },
  { label: "Film premieres", emoji: "🎬", q: "premiere screening" },
];

function DiscoverContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [results, setResults] = useState<Title[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Auto-run if URL has query
  useEffect(() => {
    const q = searchParams.get("q");
    const cat = searchParams.get("category");
    if (cat) {
      browseCategory(cat);
    } else if (q) {
      setQuery(q);
      runSearch(q);
    }
  }, [searchParams.get("category"), searchParams.get("q")]);

  async function runSearch(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setHasSearched(true);
    setActiveCategory(null);
    try {
      const res = await api.titles.discover({ mood: q, limit: 24 });
      setResults(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function browseCategory(cat: string) {
    setLoading(true);
    setActiveCategory(cat);
    setHasSearched(true);
    setQuery("");
    try {
      const res = await api.titles.discover({ category: cat, limit: 24 });
      setResults(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    router.replace(`/discover?q=${encodeURIComponent(query)}`);
    runSearch(query);
  };

  return (
    <div className="max-w-[1440px] mx-auto px-6 md:px-16 py-10 fade-up">
      <h1 className="text-3xl font-black mb-2">Discover</h1>
      <p className="text-[#A0A8C0] mb-8">Search an artist or a vibe — or browse livestreams by category.</p>

      {/* Search bar */}
      <form onSubmit={handleSubmit} className="relative mb-8 max-w-2xl">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={'e.g. "Kevin Holliday" or "something chill tonight"'}
          className="w-full bg-[#12151E] border border-white/10 rounded-2xl px-6 py-4 pr-32 text-white placeholder-[#5A607A]
                     focus:outline-none focus:border-[#4F8EF7] text-base"
        />
        <button
          type="submit"
          className="absolute right-3 top-1/2 -translate-y-1/2 px-5 py-2 bg-[#4F8EF7] text-white rounded-xl font-semibold text-sm hover:bg-[#6AA0FF] transition-colors"
        >
          Search
        </button>
      </form>

      {/* Mood chips */}
      <section className="mb-10">
        <h2 className="text-sm font-semibold text-[#5A607A] uppercase tracking-wider mb-4">Quick moods</h2>
        <div className="flex flex-wrap gap-3">
          {MOODS.map((m) => (
            <button
              key={m.q}
              onClick={() => { setQuery(m.q); runSearch(m.q); }}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#1A1D2E] border border-white/8
                         text-sm text-[#A0A8C0] hover:border-[#4F8EF7]/60 hover:text-white transition-all"
            >
              <span>{m.emoji}</span>
              <span>{m.label}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Category filters */}
      <section className="mb-10">
        <h2 className="text-sm font-semibold text-[#5A607A] uppercase tracking-wider mb-4">Browse by category</h2>
        <div className="flex flex-wrap gap-3">
          {CATEGORIES.map((c) => (
            <button
              key={c.slug}
              onClick={() => browseCategory(c.slug)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-full border text-sm font-semibold transition-all"
              style={{
                borderColor: activeCategory === c.slug ? c.color : "rgba(255,255,255,0.08)",
                background: activeCategory === c.slug ? `${c.color}22` : "transparent",
                color: activeCategory === c.slug ? c.color : "#A0A8C0",
              }}
            >
              <span>{c.emoji}</span>
              <span>{c.label}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Results */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="text-4xl animate-pulse">◈</div>
        </div>
      )}

      {!loading && hasSearched && results.length === 0 && (
        <div className="text-center py-16">
          <p className="text-4xl mb-4">🎬</p>
          <p className="text-[#A0A8C0]">No livestreams found. Try a different artist, vibe or category.</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <>
          <p className="text-sm text-[#5A607A] mb-6">{results.length} titles found</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-5">
            {results.map((t) => (
              <TitleCard key={t.id} title={t} size="md" />
            ))}
          </div>
        </>
      )}

      {!hasSearched && (
        <div className="text-center py-20 text-[#5A607A]">
          <p className="text-5xl mb-4">🎭</p>
          <p>Start by typing a mood or picking a category above.</p>
        </div>
      )}
    </div>
  );
}

export default function DiscoverPage() {
  return (
    <Suspense>
      <DiscoverContent />
    </Suspense>
  );
}

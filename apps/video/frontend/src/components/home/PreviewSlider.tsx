"use client";
/**
 * Home page preview slider — five panes, auto-advancing every 3 seconds.
 *
 * Pane 1 is the advance (teaser) poster for the newest release.
 * Click a pane once to play its preview in place (rotation pauses);
 * click it again to go to the film's page, scrolled to the Rent button.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Hls from "hls.js";
import { Title } from "@/lib/api";

const ROTATE_MS = 3000;

export interface Slide {
  title: Title;
  /** Show this pane as the advance poster for a new film */
  advance?: boolean;
}

function PreviewVideo({ src, onEnded }: { src: string; onEnded: () => void }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    let hls: Hls | null = null;

    const play = () =>
      video.play().catch(() => {
        // Browser refused audio autoplay: fall back to muted
        video.muted = true;
        setMuted(true);
        video.play().catch(() => {});
      });

    if (src.includes(".m3u8") && Hls.isSupported()) {
      hls = new Hls({ enableWorker: true, capLevelToPlayerSize: true });
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, play);
    } else {
      video.src = src;
      play();
    }
    return () => {
      hls?.destroy();
      video.removeAttribute("src");
      video.load();
    };
  }, [src]);

  return (
    <>
      <video
        ref={ref}
        className="absolute inset-0 w-full h-full object-cover bg-black"
        playsInline
        onEnded={onEnded}
      />
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          const v = ref.current;
          if (!v) return;
          v.muted = !v.muted;
          setMuted(v.muted);
        }}
        className="absolute top-5 right-5 z-30 px-3 py-1.5 rounded-full bg-black/60 text-xs font-semibold text-white hover:bg-black/80"
        aria-label={muted ? "Unmute preview" : "Mute preview"}
      >
        {muted ? "🔇 Unmute" : "🔊 Mute"}
      </button>
    </>
  );
}

export function PreviewSlider({ slides }: { slides: Slide[] }) {
  const router = useRouter();
  const [index, setIndex] = useState(0);
  const [previewing, setPreviewing] = useState<string | null>(null); // title id

  const count = slides.length;
  const go = useCallback((i: number) => {
    setPreviewing(null);
    setIndex(((i % count) + count) % count);
  }, [count]);

  // Rotate every 3 s; restarts after any manual change, paused while previewing
  useEffect(() => {
    if (previewing || count < 2) return;
    const t = setTimeout(() => setIndex((i) => (i + 1) % count), ROTATE_MS);
    return () => clearTimeout(t);
  }, [index, previewing, count]);

  if (count === 0) return null;

  const activate = (slide: Slide) => {
    if (previewing === slide.title.id) {
      router.push(`/watch/${slide.title.slug}#rent`);
    } else {
      setPreviewing(slide.title.id);
    }
  };

  return (
    <section
      className="relative h-[72vh] min-h-[480px] max-h-[760px] overflow-hidden bg-[#0A0C14] select-none"
      aria-roledescription="carousel"
      aria-label="Featured films"
    >
      {slides.map((slide, i) => {
        const t = slide.title;
        const active = i === index;
        const isPreviewing = active && previewing === t.id;
        const previewSrc = t.trailer_url || t.hls_manifest_url;
        const hint = isPreviewing
          ? t.is_free ? "Click again to watch" : "Click again to rent"
          : "Click to preview";

        return (
          <div
            key={t.id}
            role="group"
            aria-roledescription="slide"
            aria-label={`${i + 1} of ${count}: ${t.title}`}
            aria-hidden={!active}
            className={`absolute inset-0 transition-opacity duration-700 ${active ? "opacity-100 z-10" : "opacity-0 z-0 pointer-events-none"}`}
          >
            <button
              type="button"
              tabIndex={active ? 0 : -1}
              onClick={() => activate(slide)}
              className="absolute inset-0 w-full h-full text-left cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#4F8EF7]"
              aria-label={`${t.title}. ${hint}`}
            >
              {/* Blurred poster backdrop */}
              <div className="absolute inset-0">
                {t.poster_url && (
                  <img src={t.poster_url} alt="" className="w-full h-full object-cover scale-110 blur-2xl opacity-60" />
                )}
                <div className="absolute inset-0 bg-gradient-to-r from-[#0A0C14] via-[#0A0C14]/70 to-transparent" />
                <div className="absolute inset-0 bg-gradient-to-t from-[#0A0C14] via-transparent to-[#0A0C14]/40" />
              </div>

              {/* Preview video */}
              {isPreviewing && previewSrc && (
                <PreviewVideo src={previewSrc} onEnded={() => setPreviewing(null)} />
              )}

              {/* Pane content */}
              <div
                className={`relative z-20 h-full max-w-[1440px] mx-auto px-16 flex items-center gap-10 transition-opacity duration-300
                  ${isPreviewing ? "opacity-0" : "opacity-100"}`}
              >
                <div className="flex-1 max-w-xl">
                  <span className={`inline-block text-xs font-bold uppercase tracking-[0.25em] mb-4 ${slide.advance ? "text-[#E33B3B]" : "text-[#4F8EF7]"}`}>
                    {slide.advance ? "New on Bazzy · Advance Poster" : "Featured"}
                  </span>
                  <h2 className="text-4xl md:text-6xl font-black leading-[1.05] mb-4">{t.title}</h2>
                  {t.synopsis && (
                    <p className="text-[#A0A8C0] text-base md:text-lg leading-relaxed line-clamp-3 mb-6">{t.synopsis}</p>
                  )}
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-white text-black font-bold">
                      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
                      Preview
                    </span>
                    {t.is_free ? (
                      <span className="text-[#3DCC7E] font-semibold">Free to watch</span>
                    ) : (
                      <span className="text-[#F5C842] font-mono">◈ {t.rent_credits} rent · {t.buy_credits} buy</span>
                    )}
                    {t.year && <span className="text-[#5A607A]">{t.year}</span>}
                    {t.runtime_minutes && <span className="text-[#5A607A]">{t.runtime_minutes} min</span>}
                  </div>
                </div>

                {/* Poster — larger, framed and tilted forward for the advance poster */}
                {t.poster_url && (
                  <div className={`hidden md:block flex-shrink-0 ${slide.advance ? "w-[300px] lg:w-[340px]" : "w-[240px] lg:w-[260px]"}`}>
                    <div className={`relative aspect-[2/3] rounded-lg overflow-hidden shadow-2xl
                      ${slide.advance ? "ring-2 ring-[#E33B3B]/70 shadow-[0_0_80px_rgba(227,59,59,0.35)]" : "ring-1 ring-white/10"}`}>
                      <img src={t.poster_url} alt={`${t.title} poster`} className="w-full h-full object-cover" />
                      {slide.advance && (
                        <div className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-black/90 to-transparent">
                          <p className="text-[10px] font-bold uppercase tracking-[0.3em] text-[#E33B3B]">New Release</p>
                          <p className="text-lg font-black leading-tight">{t.title}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Click hint */}
              <span className="absolute bottom-14 left-16 z-30 px-4 py-1.5 rounded-full bg-black/60 backdrop-blur text-xs font-semibold text-white">
                {hint}
              </span>
            </button>
          </div>
        );
      })}

      {/* Arrows */}
      {count > 1 && (
        <>
          <button
            type="button"
            onClick={() => go(index - 1)}
            className="absolute left-3 top-1/2 -translate-y-1/2 z-30 w-10 h-10 rounded-full bg-black/50 text-white text-xl hover:bg-black/80"
            aria-label="Previous film"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={() => go(index + 1)}
            className="absolute right-3 top-1/2 -translate-y-1/2 z-30 w-10 h-10 rounded-full bg-black/50 text-white text-xl hover:bg-black/80"
            aria-label="Next film"
          >
            ›
          </button>
        </>
      )}

      {/* Dots */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 flex gap-2">
        {slides.map((s, i) => (
          <button
            key={s.title.id}
            type="button"
            onClick={() => go(i)}
            className={`h-2 rounded-full transition-all ${i === index ? "w-8 bg-white" : "w-2 bg-white/40 hover:bg-white/70"}`}
            aria-label={`Show ${s.title.title}`}
            aria-current={i === index}
          />
        ))}
      </div>
    </section>
  );
}

"use client";
/**
 * Home page preview slider — five panes, auto-advancing every 5 seconds.
 *
 * Pane 1 is the advance (teaser) poster for the newest release.
 * Click a pane once to play its preview in place (rotation pauses);
 * click it again to go to the film's page, scrolled to the Rent button.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Hls from "hls.js";
import { Title } from "@/lib/api";

const ROTATE_MS = 5000;

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

  // Rotate every 5 s; restarts after any manual change, paused while previewing
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
      // -mt-16 pulls it under the fixed, transparent navbar so the poster fills the screen
      className="relative -mt-16 h-[100svh] min-h-[560px] overflow-hidden bg-[#0A0C14] select-none"
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
              {/* Full-screen poster */}
              <div className="absolute inset-0 overflow-hidden">
                {t.poster_url ? (
                  <img
                    src={t.poster_url}
                    alt={`${t.title} poster`}
                    className={`w-full h-full object-cover object-[center_30%] transition-transform ease-out duration-[6000ms] ${active ? "scale-105" : "scale-100"}`}
                  />
                ) : (
                  <div className="w-full h-full bg-gradient-to-br from-[#1A1D2E] to-[#0A0C14]" />
                )}
                {/* Shading so the text reads over any poster */}
                <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/35 to-transparent" />
                <div className="absolute inset-0 bg-gradient-to-t from-[#0A0C14] via-black/20 to-black/40" />
              </div>

              {/* Preview video */}
              {isPreviewing && previewSrc && (
                <PreviewVideo src={previewSrc} onEnded={() => setPreviewing(null)} />
              )}

              {/* Pane content */}
              <div
                className={`relative z-20 h-full max-w-[1440px] mx-auto px-16 pb-28 flex items-end transition-opacity duration-300
                  ${isPreviewing ? "opacity-0" : "opacity-100"}`}
              >
                <div className="max-w-2xl [text-shadow:0_2px_12px_rgba(0,0,0,0.6)]">
                  <span className={`inline-block text-xs font-bold uppercase tracking-[0.25em] mb-4 ${slide.advance ? "text-[#E33B3B]" : "text-[#4F8EF7]"}`}>
                    {slide.advance ? "New on Bazzy" : "Featured"}
                  </span>
                  <h2 className={`font-black leading-[1.02] mb-4 ${slide.advance ? "text-5xl md:text-8xl" : "text-4xl md:text-7xl"}`}>{t.title}</h2>
                  {t.synopsis && (
                    <p className="text-white/85 text-base md:text-xl leading-relaxed line-clamp-3 mb-6">{t.synopsis}</p>
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
                    {t.year && <span className="text-white/70">{t.year}</span>}
                    {t.runtime_minutes && <span className="text-white/70">{t.runtime_minutes} min</span>}
                  </div>
                </div>

              </div>

              {/* Click hint */}
              <span className="absolute bottom-16 left-16 z-30 px-4 py-1.5 rounded-full bg-black/60 backdrop-blur text-xs font-semibold text-white">
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

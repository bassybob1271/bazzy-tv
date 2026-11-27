"use client";
/**
 * Home page preview slider — Bazzy TV's slider, with posters for upcoming
 * livestreams. Auto-advances every 5 seconds.
 *
 * Click a pane once to play its preview in place (rotation pauses), click
 * again to go to the show's page at the ticket button. Shows without a
 * preview go straight to tickets; a show that's on air opens the player.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Hls from "hls.js";
import { Title } from "@/lib/api";
import { LIVE_RED, countdown, isOnAir, showTime } from "@/lib/live";
import { NowLivePreview } from "@/components/home/NowLivePreview";

const ROTATE_MS = 5000;

export interface Slide {
  title: Title;
  /** Show this pane as "next up" (the soonest show) */
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

export function PreviewSlider({ slides, current }: { slides: Slide[]; current?: Title | null }) {
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

  if (count === 0 && !current) return null;

  const activate = (slide: Slide) => {
    const t = slide.title;
    const hasPreview = !!(t.trailer_url || t.hls_manifest_url);
    if (isOnAir(t)) {
      router.push(`/watch/${t.slug}`);
    } else if (previewing === t.id || !hasPreview) {
      router.push(`/watch/${t.slug}#rent`);
    } else {
      setPreviewing(t.id);
    }
  };

  return (
    <section
      // -mt-16 pulls it under the fixed, transparent navbar so the poster fills the screen
      className={`relative -mt-16 h-[100svh] overflow-hidden bg-[#0A0C14] select-none ${current ? "min-h-[780px]" : "min-h-[560px]"}`}
      aria-roledescription="carousel"
      aria-label="Upcoming livestreams"
    >
      {slides.map((slide, i) => {
        const t = slide.title;
        const active = i === index;
        const isPreviewing = active && previewing === t.id;
        const previewSrc = t.trailer_url || t.hls_manifest_url;
        const onAir = isOnAir(t);
        const hint = onAir ? "Click to watch live"
          : isPreviewing ? (t.is_free ? "Click again to RSVP" : "Click again for tickets")
          : previewSrc ? "Click to preview"
          : t.is_free ? "Click to RSVP" : "Click for tickets";

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
              {/* Poster: event flyers carry their own text, so on wide screens the
                  whole poster stays visible over a blurred, full-bleed copy of itself */}
              <div className="absolute inset-0 overflow-hidden">
                {t.poster_url ? (
                  <>
                    <img
                      src={t.poster_url}
                      alt=""
                      aria-hidden="true"
                      className={`absolute inset-0 w-full h-full object-cover object-[center_30%] md:blur-2xl md:scale-110 md:opacity-60 transition-transform ease-out duration-[6000ms] ${active ? "scale-105" : "scale-100"}`}
                    />
                    <img
                      src={t.poster_url}
                      alt={`${t.title} poster`}
                      className={`hidden md:block absolute right-[6%] top-24 bottom-16 h-[calc(100%-10rem)] w-auto max-w-[42%] object-contain rounded-xl shadow-2xl shadow-black/60 transition-transform ease-out duration-[6000ms] ${active ? "scale-[1.03]" : "scale-100"}`}
                    />
                  </>
                ) : (
                  <div className="w-full h-full bg-gradient-to-br from-[#1A1D2E] to-[#0A0C14]" />
                )}
                {/* Shading so the text reads over any poster */}
                <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/40 to-transparent" />
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
                <div className="max-w-2xl md:max-w-[50%] [text-shadow:0_2px_12px_rgba(0,0,0,0.6)]">
                  {onAir ? (
                    <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.25em] mb-4 px-3 py-1 rounded-full text-white" style={{ background: LIVE_RED }}>
                      <span className="w-2 h-2 rounded-full bg-white animate-pulse" /> Live now
                    </span>
                  ) : (
                    <span className="inline-block text-xs font-bold uppercase tracking-[0.25em] mb-4" style={{ color: slide.advance ? LIVE_RED : "#4F8EF7" }}>
                      {slide.advance ? "Next up" : "Upcoming livestream"} · {countdown(t.starts_at)}
                    </span>
                  )}
                  <h2 className={`font-black leading-[1.02] mb-3 ${current ? "text-3xl md:text-5xl" : slide.advance ? "text-4xl md:text-7xl" : "text-4xl md:text-6xl"}`}>{t.title}</h2>
                  {t.performer_name && t.performer_name !== t.title && (
                    <p className="text-white text-lg md:text-2xl font-semibold mb-3">{t.performer_name}</p>
                  )}
                  <p className="text-white/85 text-sm md:text-lg mb-1">{showTime(t.starts_at)}</p>
                  {t.venue && <p className="text-white/60 text-sm mb-5 line-clamp-1">{t.venue}</p>}
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-white text-black font-bold">
                      <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
                      {onAir ? "Watch live" : previewSrc ? "Preview" : t.is_free ? "RSVP" : "Get ticket"}
                    </span>
                    {t.is_free ? (
                      <span className="text-[#3DCC7E] font-semibold">Free livestream</span>
                    ) : (
                      <span className="text-[#F5C842] font-mono">◈ {t.rent_credits} ticket · includes replay</span>
                    )}
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

      {/* Now live: 12×9 preview of the show on air, upper left above the description */}
      {current && (
        <div className="absolute inset-x-0 top-20 z-30 pointer-events-none">
          <div className="max-w-[1440px] mx-auto px-16">
            <div className="pointer-events-auto w-fit">
              <NowLivePreview show={current} />
            </div>
          </div>
        </div>
      )}

      {/* Arrows */}
      {count > 1 && (
        <>
          <button
            type="button"
            onClick={() => go(index - 1)}
            className="absolute left-3 top-1/2 -translate-y-1/2 z-30 w-10 h-10 rounded-full bg-black/50 text-white text-xl hover:bg-black/80"
            aria-label="Previous show"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={() => go(index + 1)}
            className="absolute right-3 top-1/2 -translate-y-1/2 z-30 w-10 h-10 rounded-full bg-black/50 text-white text-xl hover:bg-black/80"
            aria-label="Next show"
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

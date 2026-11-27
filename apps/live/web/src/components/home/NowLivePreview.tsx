"use client";
/**
 * "Now live" box for the home slider: a silent 12×9 (4:3) preview of the show
 * that's on air right now, plus a button to join it for 100 credits.
 *
 * The preview is MediaMTX's low-res copy of the stage feed (live/<id>_preview),
 * which anyone may watch; the full show with sound needs a ticket or a join.
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Hls from "hls.js";
import { api, Title } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { LIVE_RED } from "@/lib/live";

const RETRY_MS = 5000;

function PreviewVideo({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    let hls: Hls | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const start = () => {
      if (cancelled) return;
      setReady(false);
      if (Hls.isSupported()) {
        hls = new Hls({ lowLatencyMode: true, liveSyncDurationCount: 2 });
        hls.loadSource(src);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => { video.play().catch(() => {}); });
        hls.on(Hls.Events.ERROR, (_e, data) => {
          if (!data.fatal) return;
          hls?.destroy();
          hls = null;
          retry = setTimeout(start, RETRY_MS); // preview not up yet / dropped
        });
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = src;
        video.play().catch(() => {});
      }
    };
    start();
    return () => {
      cancelled = true;
      if (retry) clearTimeout(retry);
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
        muted
        playsInline
        autoPlay
        onPlaying={() => setReady(true)}
      />
      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60">
          <div className="w-6 h-6 rounded-full border-2 border-white/20 border-t-white animate-spin" />
        </div>
      )}
    </>
  );
}

export function NowLivePreview({ show }: { show: Title }) {
  const router = useRouter();
  const { isAuthenticated, fetchWallet } = useStore();
  const [joining, setJoining] = useState(false);
  const price = show.join_credits ?? 100;

  async function join() {
    if (!isAuthenticated) { router.push("/auth/login"); return; }
    setJoining(true);
    try {
      if (!show.is_free) await api.live.join(show.id);
      await fetchWallet();
      router.push(`/watch/${show.slug}?play=1`);
    } catch (e: any) {
      const msg: string = e.message ?? "Couldn't join the livestream";
      if (/credits/i.test(msg)) {
        if (confirm(`${msg}. Add credits now?`)) router.push("/wallet");
      } else {
        alert(msg);
      }
      setJoining(false);
    }
  }

  return (
    // 12×9 box, ~1.5× the first version; title and Join sit on the video
    <div className="relative w-60 md:w-96 aspect-[4/3] rounded-xl overflow-hidden bg-black border border-white/15 shadow-2xl shadow-black/60">
      <button
        type="button"
        onClick={join}
        className="absolute inset-0 w-full h-full"
        aria-label={`Join ${show.title} live`}
      >
        {show.preview_hls_url ? (
          <PreviewVideo src={show.preview_hls_url} />
        ) : show.poster_url ? (
          <img src={show.poster_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
        ) : null}
      </button>

      <span
        className="pointer-events-none absolute top-2.5 left-2.5 flex items-center gap-1 px-2 py-0.5 rounded text-[10px] md:text-xs font-black text-white"
        style={{ background: LIVE_RED }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> LIVE NOW
      </span>
      <span className="pointer-events-none absolute top-2.5 right-2.5 text-[10px] text-white/80 bg-black/60 px-1.5 py-0.5 rounded">🔇 preview</span>

      {/* Title + Join over the bottom of the video */}
      <div className="absolute inset-x-0 bottom-0 p-3 md:p-4 bg-gradient-to-t from-black/90 via-black/60 to-transparent">
        <p className="text-white text-sm md:text-base font-bold leading-tight line-clamp-1">{show.title}</p>
        {show.performer_name && show.performer_name !== show.title && (
          <p className="text-white/70 text-[11px] md:text-xs line-clamp-1">{show.performer_name}</p>
        )}
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            onClick={join}
            disabled={joining}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs md:text-sm font-bold text-white hover:brightness-110 disabled:opacity-60"
            style={{ background: LIVE_RED }}
          >
            {joining ? "Joining…" : show.is_free ? "Join now · free" : <>Join now <span className="font-mono">◈ {price}</span></>}
          </button>
          {!show.is_free && <span className="text-[10px] md:text-xs text-white/70">includes replay</span>}
        </div>
      </div>
    </div>
  );
}

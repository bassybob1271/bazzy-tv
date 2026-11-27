"use client";
/**
 * Bazzy Live — live player for the ATEM feed.
 *
 * Asks the API for a playback pass (ticket holders only), then plays the
 * MediaMTX HLS stream with hls.js, sending the pass on every playlist and
 * segment request. If the feed isn't up yet or drops (venue Wi-Fi, ATEM
 * restart), it shows "reconnecting" and keeps retrying.
 */
import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import { api, Title } from "@/lib/api";
import { LIVE_RED } from "@/lib/live";

const RETRY_MS = 5000;

type Status = "connecting" | "playing" | "waiting" | "ended" | "error";

export function LivePlayer({ title, onEnded }: { title: Title; onEnded?: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [status, setStatus] = useState<Status>("connecting");
  const [message, setMessage] = useState("");
  const [muted, setMuted] = useState(false);
  const [paused, setPaused] = useState(true);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    let hls: Hls | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const tryPlay = () =>
      video.play().catch(() => {
        // Autoplay with sound blocked: start muted, viewer can unmute
        video.muted = true;
        setMuted(true);
        video.play().catch(() => {});
      });

    const scheduleRetry = () => {
      if (cancelled) return;
      hls?.destroy();
      hls = null;
      setStatus("waiting");
      retry = setTimeout(start, RETRY_MS);
    };

    async function start() {
      if (cancelled || !video) return;
      setStatus((s) => (s === "playing" ? s : "connecting"));
      let pb;
      try {
        pb = await api.live.playback(title.id);
      } catch (e: any) {
        setStatus("error");
        setMessage(e.message ?? "Couldn't open the stream.");
        return;
      }
      if (cancelled) return;
      if (pb.live_state === "ended") { setStatus("ended"); onEnded?.(); return; }
      if (pb.live_state !== "on_air" || !pb.hls_url) { scheduleRetry(); return; }

      const src = pb.hls_url;
      const pass = pb.token;
      if (Hls.isSupported()) {
        hls = new Hls({
          lowLatencyMode: true,
          liveSyncDurationCount: 3,
          xhrSetup: (xhr) => { if (pass) xhr.setRequestHeader("Authorization", `Bearer ${pass}`); },
        });
        hls.loadSource(src);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => { setStatus("playing"); tryPlay(); });
        hls.on(Hls.Events.ERROR, (_e, data) => {
          if (!data.fatal) return;
          if (data.type === Hls.ErrorTypes.MEDIA_ERROR) { hls?.recoverMediaError(); return; }
          scheduleRetry(); // feed not up yet / dropped / pass expired: ask again
        });
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        // Older iPhones: native HLS can't send headers, so the pass goes in the URL
        video.src = pass ? `${src}?jwt=${encodeURIComponent(pass)}` : src;
        video.onloadedmetadata = () => { setStatus("playing"); tryPlay(); };
        video.onerror = scheduleRetry;
      } else {
        setStatus("error");
        setMessage("This browser can't play live video.");
      }
    }

    start();
    return () => {
      cancelled = true;
      if (retry) clearTimeout(retry);
      hls?.destroy();
      video.removeAttribute("src");
      video.load();
    };
  }, [title.id]);

  const toggleMute = () => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
    setMuted(v.muted);
  };

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => {});
    else v.pause();
  };

  const goLive = () => {
    const v = videoRef.current;
    if (v && v.seekable.length) v.currentTime = v.seekable.end(v.seekable.length - 1) - 1;
    v?.play().catch(() => {});
  };

  return (
    <div className="relative bg-black aspect-video w-full rounded-lg overflow-hidden group">
      <video
        ref={videoRef}
        className="w-full h-full object-contain"
        playsInline
        onPlay={() => setPaused(false)}
        onPause={() => setPaused(true)}
        onClick={togglePlay}
      />

      {/* LIVE badge */}
      <div className="absolute top-4 left-4 flex items-center gap-2">
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-black text-white" style={{ background: LIVE_RED }}>
          <span className="w-2 h-2 rounded-full bg-white animate-pulse" /> LIVE
        </span>
        <span className="text-white text-sm font-semibold drop-shadow">{title.title}</span>
      </div>

      {status !== "playing" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/70 text-center p-6">
          {status === "error" ? (
            <p className="text-sm text-white">{message}</p>
          ) : status === "ended" ? (
            <p className="text-sm text-white">This livestream has ended. The replay will appear on this page.</p>
          ) : (
            <>
              <div className="w-10 h-10 rounded-full border-2 border-white/20 border-t-white animate-spin" />
              <p className="text-sm text-white">
                {status === "waiting" ? "Waiting for the stage feed… reconnecting" : "Connecting to the livestream…"}
              </p>
            </>
          )}
        </div>
      )}

      {status === "playing" && (
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-4 flex items-center gap-4 text-white text-sm
                        opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100 transition-opacity">
          <button onClick={togglePlay} className="text-lg px-1" aria-label={paused ? "Play" : "Pause"}>{paused ? "▶" : "⏸"}</button>
          <button onClick={goLive} className="text-xs font-bold px-2 py-1 rounded border border-white/30 hover:bg-white/10">Jump to live</button>
          <button onClick={toggleMute} className="ml-auto text-xs font-semibold px-3 py-1.5 rounded-full bg-black/60 hover:bg-black/80">
            {muted ? "🔇 Unmute" : "🔊 Mute"}
          </button>
        </div>
      )}
    </div>
  );
}

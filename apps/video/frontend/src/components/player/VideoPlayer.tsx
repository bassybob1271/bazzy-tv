"use client";
/**
 * Bazzy Video — HLS Player Component
 * hls.js adaptive bitrate, DRM-aware, credit debit heartbeat
 */
import { useEffect, useRef, useState, useCallback } from "react";
import Hls from "hls.js";
import { api, Title } from "@/lib/api";
import { useStore } from "@/store/useStore";

interface VideoPlayerProps {
  title: Title;
  onComplete?: () => void;
}

export function VideoPlayer({ title, onComplete }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef   = useRef<Hls | null>(null);
  const pingRef  = useRef<NodeJS.Timeout | null>(null);
  const { sessionId } = useStore();

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [quality, setQuality] = useState("auto");
  const [creditsRemaining, setCreditsRemaining] = useState<number | null>(null);
  const [loadError, setLoadError] = useState("");

  // Credit debit heartbeat — 1 cr/min
  const startCreditPing = useCallback(() => {
    if (pingRef.current) clearInterval(pingRef.current);
    pingRef.current = setInterval(async () => {
      try {
        const res = await api.titles.streamPing(title.id, sessionId ?? "");
        setCreditsRemaining(res.credits_remaining);
        if (res.credits_remaining <= 0) {
          videoRef.current?.pause();
          setIsPlaying(false);
        }
      } catch (e) {
        // Pause on network error — don't stream without billing
        videoRef.current?.pause();
      }
    }, 60_000); // every 60s
  }, [title.id, sessionId]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !title.hls_manifest_url) return;

    const src = title.hls_manifest_url;
    setLoadError("");
    // Try to start right away. Phones (iOS especially) may refuse to start a
    // video with sound on their own; it then stays paused with the big Play
    // button showing, and a tap starts it.
    const tryPlay = () => { video.play().catch(() => {}); };
    const useNative = () => {
      video.src = src;
      video.load();
      tryPlay();
    };

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: false,
        backBufferLength: 90,
      });
      hlsRef.current = hls;
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, tryPlay);
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (!data.fatal) return;
        hls.destroy();
        hlsRef.current = null;
        // Fall back to the browser's own HLS support (Safari / iOS), else report
        if (video.canPlayType("application/vnd.apple.mpegurl")) useNative();
        else setLoadError("This video couldn't be loaded. Check your connection and try again.");
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari / iOS native HLS
      useNative();
    } else {
      setLoadError("This browser can't play this video.");
    }

    return () => {
      hlsRef.current?.destroy();
      if (pingRef.current) clearInterval(pingRef.current);
    };
  }, [title.hls_manifest_url]);

  const handlePlay = () => { setIsPlaying(true); startCreditPing(); };
  const handlePause = () => { setIsPlaying(false); if (pingRef.current) clearInterval(pingRef.current); };
  const handleTimeUpdate = () => setCurrentTime(videoRef.current?.currentTime ?? 0);
  const handleDurationChange = () => setDuration(videoRef.current?.duration ?? 0);
  const handleEnded = () => { setIsPlaying(false); onComplete?.(); };

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => setLoadError("Playback was blocked. Tap Play to try again."));
    else v.pause();
  };

  const seek = (pct: number) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = (pct / 100) * duration;
  };

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  return (
    <div className="relative bg-black aspect-video w-full rounded-lg overflow-hidden group">
      <video
        ref={videoRef}
        className="w-full h-full object-contain"
        onPlay={handlePlay}
        onPause={handlePause}
        onTimeUpdate={handleTimeUpdate}
        onDurationChange={handleDurationChange}
        onEnded={handleEnded}
        onError={() => setLoadError("This video couldn't be loaded. Check your connection and try again.")}
        onClick={togglePlay}
        playsInline
        preload="auto"
      />

      {/* Big Play button while paused: also the tap target when autoplay is blocked */}
      {!isPlaying && !loadError && (
        <button
          type="button"
          onClick={togglePlay}
          className="absolute inset-0 m-auto w-20 h-20 rounded-full bg-black/50 backdrop-blur-sm border-2 border-white/60
                     flex items-center justify-center text-white text-3xl hover:bg-black/70"
          aria-label="Play"
        >
          ▶
        </button>
      )}

      {loadError && (
        <div className="absolute inset-0 flex items-center justify-center p-6 bg-black/70 text-center text-sm text-white">
          {loadError}
        </div>
      )}

      {/* Controls overlay */}
      {/* Shown while paused, on hover, and always on touch screens (no hover there) */}
      <div className={`absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-4 transition-opacity
                      ${isPlaying ? "opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100" : "opacity-100"}`}>
        {/* Scrub bar */}
        <div
          className="w-full h-1 bg-white/30 rounded cursor-pointer mb-3"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            seek(((e.clientX - rect.left) / rect.width) * 100);
          }}
        >
          <div
            className="h-full bg-[#4F8EF7] rounded"
            style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
          />
        </div>

        <div className="flex items-center gap-4 text-white text-sm">
          <button onClick={togglePlay} className="hover:text-[#4F8EF7] transition-colors text-lg px-1" aria-label={isPlaying ? "Pause" : "Play"}>
            {isPlaying ? "⏸" : "▶"}
          </button>
          <span className="tabular-nums">{formatTime(currentTime)} / {formatTime(duration)}</span>
          <div className="ml-auto flex items-center gap-3">
            {creditsRemaining !== null && (
              <span className="text-[#F5C842] text-xs">{creditsRemaining.toLocaleString()} cr left</span>
            )}
            <span className="text-xs text-white/50">{quality}</span>
          </div>
        </div>
      </div>

      {/* Title overlay top-left */}
      <div className="absolute top-4 left-4 opacity-0 group-hover:opacity-100 transition-opacity">
        <p className="text-white text-sm font-semibold drop-shadow">{title.title}</p>
      </div>
    </div>
  );
}

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

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: false,
        backBufferLength: 90,
      });
      hlsRef.current = hls;
      hls.loadSource(title.hls_manifest_url);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => { video.play().catch(() => {}); });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari native HLS
      video.src = title.hls_manifest_url;
      video.play().catch(() => {});
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
    if (!videoRef.current) return;
    isPlaying ? videoRef.current.pause() : videoRef.current.play();
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
        playsInline
      />

      {/* Controls overlay */}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-4
                      opacity-0 group-hover:opacity-100 transition-opacity">
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
          <button onClick={togglePlay} className="hover:text-[#4F8EF7] transition-colors">
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

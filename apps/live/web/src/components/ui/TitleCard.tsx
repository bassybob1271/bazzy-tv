"use client";
import Link from "next/link";
import { Title } from "@/lib/api";
import { CAT_COLORS, LIVE_RED, categoryLabel, isOnAir, isUpcoming, shortDate } from "@/lib/live";

interface TitleCardProps {
  title: Title;
  size?: "sm" | "md" | "lg";
}

export function TitleCard({ title, size = "md" }: TitleCardProps) {
  const accent = CAT_COLORS[title.category] ?? "#4F8EF7";
  const w = size === "sm" ? "w-36" : size === "lg" ? "w-56" : "w-44";

  return (
    <Link href={`/watch/${title.slug}`}>
      <div className={`${w} flex-shrink-0 group cursor-pointer`}>
        {/* Poster */}
        <div className="relative aspect-[2/3] rounded overflow-hidden bg-[#12151E] mb-2">
          {title.poster_url ? (
            <img
              src={title.poster_url}
              alt={title.title}
              className="w-full h-full object-cover transition-transform group-hover:scale-105"
            />
          ) : (
            <div
              className="w-full h-full flex items-center justify-center text-4xl"
              style={{ background: `${accent}22` }}
            >
              🎬
            </div>
          )}
          {/* Category pill */}
          <span
            className="absolute top-2 left-2 text-[9px] font-bold uppercase px-1.5 py-0.5 rounded text-black"
            style={{ background: accent }}
          >
            {categoryLabel(title.category)}
          </span>
          {/* Live / upcoming badge */}
          {isOnAir(title) ? (
            <span className="absolute top-2 right-2 text-[9px] font-bold text-white px-1.5 py-0.5 rounded flex items-center gap-1" style={{ background: LIVE_RED }}>
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> LIVE
            </span>
          ) : isUpcoming(title) ? (
            <span className="absolute top-2 right-2 text-[9px] font-bold bg-black/70 text-white px-1.5 py-0.5 rounded">
              {shortDate(title.starts_at).toUpperCase()}
            </span>
          ) : title.is_free && (
            <span className="absolute top-2 right-2 text-[9px] font-bold bg-[#3DCC7E] text-black px-1.5 py-0.5 rounded">
              FREE
            </span>
          )}
          {/* Hover overlay */}
          <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity
                          flex items-center justify-center">
            <span className="text-white text-3xl">▶</span>
          </div>
        </div>

        {/* Meta */}
        <div>
          <p className="text-white text-sm font-medium leading-tight line-clamp-2 group-hover:text-[#4F8EF7] transition-colors">
            {title.title}
          </p>
          {title.performer_name && title.performer_name !== title.title && (
            <p className="text-[11px] text-[#A0A8C0] mt-0.5 line-clamp-1">{title.performer_name}</p>
          )}
          <div className="flex items-center gap-2 mt-1 text-[11px] text-[#7A8095]">
            {title.starts_at && <span>{shortDate(title.starts_at)}</span>}
            {title.runtime_minutes && <span>{title.runtime_minutes}m</span>}
            {title.rent_credits > 0 && !title.is_free && (
              <span className="text-[#F5C842]">{title.rent_credits}cr {isUpcoming(title) ? "ticket" : "replay"}</span>
            )}
          </div>
          {/* Completion bar */}
          <div className="mt-1.5 h-0.5 bg-white/10 rounded overflow-hidden">
            <div
              className="h-full rounded"
              style={{
                width: `${title.completion_rate * 100}%`,
                background: accent,
              }}
            />
          </div>
        </div>
      </div>
    </Link>
  );
}

/**
 * Bazzy Live — shared livestream helpers (categories, show times).
 */
import type { Title } from "@/lib/api";

export const LIVE_RED = "#E33B3B";

export const CATEGORIES = [
  { slug: "concerts",       label: "Concerts",           emoji: "🎤", color: "#E33B3B" },
  { slug: "album_releases", label: "Album Releases",     emoji: "💿", color: "#F5C842" },
  { slug: "listening",      label: "Listening Sessions", emoji: "🎧", color: "#E8629A" },
  { slug: "screenings",     label: "Screenings",         emoji: "🎬", color: "#4F8EF7" },
  { slug: "sound_baths",    label: "Sound Baths",        emoji: "🌊", color: "#3DCC7E" },
] as const;

export const CAT_COLORS: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.slug, c.color]),
);

export const categoryLabel = (slug: string) =>
  CATEGORIES.find((c) => c.slug === slug)?.label ?? slug.replace(/_/g, " ");

export const isOnAir = (t: Title) => t.live_state === "on_air";
export const isUpcoming = (t: Title) => t.live_state === "scheduled";
export const isReplay = (t: Title) => t.live_state === "ended";

/** "Fri, Dec 4 · 8:00 PM EST" in the viewer's own time zone */
export function showTime(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const day = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", timeZoneName: "short" });
  return `${day} · ${time}`;
}

/** "Dec 4" */
export function shortDate(iso?: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";
}

/** "in 9 days", "in 3 hours", "starting now" */
export function countdown(iso?: string | null, now = Date.now()): string {
  if (!iso) return "";
  const ms = new Date(iso).getTime() - now;
  if (ms <= 60_000) return "starting now";
  const mins = Math.round(ms / 60_000);
  if (mins < 60) return `in ${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 36) return `in ${hours} hour${hours === 1 ? "" : "s"}`;
  const days = Math.round(hours / 24);
  return `in ${days} days`;
}

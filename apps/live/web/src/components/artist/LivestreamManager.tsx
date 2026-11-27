"use client";
/**
 * Artist dashboard: schedule livestreams and connect the ATEM switcher.
 *
 * ATEM Software Control → Output → Live Stream:
 *   Platform: Bazzy Live (after loading the downloaded Streaming.xml) or Custom
 *   Server:   the RTMP URL shown here
 *   Key:      the stream key shown here
 * Then press ON AIR on the ATEM: the show goes live on Bazzy Live.
 */
import { useEffect, useState } from "react";
import { api, MyLivestream } from "@/lib/api";
import { CATEGORIES, LIVE_RED, showTime } from "@/lib/live";

const STATE_STYLE: Record<string, string> = {
  on_air: "text-white",
  scheduled: "bg-[#4F8EF7]/20 text-[#4F8EF7]",
  ended: "bg-white/10 text-[#5A607A]",
};

function CopyField({ label, value, secret = false }: { label: string; value: string; secret?: boolean }) {
  const [shown, setShown] = useState(!secret);
  const [copied, setCopied] = useState(false);
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-[#5A607A] mb-1">{label}</p>
      <div className="flex items-center gap-2">
        <code className="flex-1 min-w-0 truncate px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-xs text-white font-mono">
          {shown ? value : "•".repeat(Math.min(value.length, 32))}
        </code>
        {secret && (
          <button onClick={() => setShown(!shown)} className="text-xs text-[#A0A8C0] hover:text-white px-2">
            {shown ? "Hide" : "Show"}
          </button>
        )}
        <button
          onClick={() => {
            navigator.clipboard?.writeText(value).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            });
          }}
          className="text-xs px-3 py-2 rounded-lg border border-white/15 text-white hover:bg-white/5"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

function AtemSetup({ show, onChange }: { show: MyLivestream; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  if (!show.ingest) return null;

  async function downloadXml() {
    try {
      const blob = await api.live.atemXml(show.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "BazzyLive-Streaming.xml";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message);
    }
  }

  async function rotate() {
    if (!confirm("Make a new stream key? The old one stops working, so update the ATEM afterwards.")) return;
    setBusy(true);
    try { await api.live.rotateKey(show.id); onChange(); } finally { setBusy(false); }
  }

  async function end() {
    if (!confirm("End this livestream? It moves to Previous Livestreams and the ATEM can't go live on it again.")) return;
    setBusy(true);
    try { await api.live.end(show.id); onChange(); } finally { setBusy(false); }
  }

  return (
    <div className="mt-4 p-5 rounded-xl bg-black/30 border border-white/8 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h4 className="font-bold text-sm">ATEM switcher setup</h4>
        <button onClick={downloadXml} className="text-xs px-3 py-1.5 rounded-full bg-white text-black font-semibold hover:bg-[#E0E0E0]">
          ⬇ Download ATEM streaming file
        </button>
      </div>
      <CopyField label="Server (RTMP)" value={show.ingest.server_url} />
      <CopyField label="Stream key" value={show.ingest.stream_key} secret />
      <ol className="text-xs text-[#A0A8C0] space-y-1 list-decimal list-inside">
        <li>In ATEM Software Control, open <b className="text-white">Output → Live Stream</b>.</li>
        <li>Platform: load the downloaded file and pick <b className="text-white">Bazzy Live</b> (or choose Custom and paste the server).</li>
        <li>Paste the stream key, pick a quality, and press <b className="text-white">ON AIR</b>. The show goes live here within a few seconds.</li>
      </ol>
      <div className="flex gap-3 pt-1">
        <button onClick={rotate} disabled={busy} className="text-xs px-3 py-1.5 rounded-full border border-white/15 text-[#A0A8C0] hover:text-white">
          New stream key
        </button>
        {show.live_state !== "ended" && (
          <button onClick={end} disabled={busy} className="text-xs px-3 py-1.5 rounded-full border border-[#E33B3B]/40 text-[#E33B3B] hover:bg-[#E33B3B]/10">
            End livestream
          </button>
        )}
      </div>
    </div>
  );
}

function ScheduleForm({ onDone }: { onDone: () => void }) {
  const [form, setForm] = useState({
    title: "", performer_name: "", venue: "", synopsis: "",
    category: "concerts", starts_at: "", rent_credits: 200, poster_url: "",
  });
  const [saving, setSaving] = useState(false);
  const set = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.live.schedule({
        ...form,
        starts_at: new Date(form.starts_at).toISOString(),
        poster_url: form.poster_url || undefined,
      });
      onDone();
    } catch (e: any) {
      alert(e.message ?? "Couldn't schedule the livestream");
    } finally {
      setSaving(false);
    }
  }

  const input = "w-full bg-[#0A0C14] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-[#5A607A] focus:outline-none focus:border-[#E33B3B]";
  return (
    <form onSubmit={submit} className="p-6 rounded-xl bg-[#12151E] border border-white/8 grid gap-4 md:grid-cols-2 mb-6">
      <input className={input} placeholder="Show title" required value={form.title} onChange={(e) => set("title", e.target.value)} />
      <input className={input} placeholder="Performing artist(s)" value={form.performer_name} onChange={(e) => set("performer_name", e.target.value)} />
      <input className={input} type="datetime-local" required value={form.starts_at} onChange={(e) => set("starts_at", e.target.value)} aria-label="Start time" />
      <select className={input} value={form.category} onChange={(e) => set("category", e.target.value)} aria-label="Category">
        {CATEGORIES.map((c) => <option key={c.slug} value={c.slug}>{c.emoji} {c.label}</option>)}
      </select>
      <input className={input} placeholder="Venue" value={form.venue} onChange={(e) => set("venue", e.target.value)} />
      <input className={input} placeholder="Poster image URL" value={form.poster_url} onChange={(e) => set("poster_url", e.target.value)} />
      <textarea className={`${input} md:col-span-2`} rows={2} placeholder="About the show" value={form.synopsis} onChange={(e) => set("synopsis", e.target.value)} />
      <label className="flex items-center gap-2 text-sm text-[#A0A8C0]">
        Ticket
        <input className={`${input} w-24`} type="number" min={0} value={form.rent_credits} onChange={(e) => set("rent_credits", Number(e.target.value))} />
        credits
      </label>
      <button type="submit" disabled={saving} className="md:justify-self-end px-6 py-2.5 rounded-full font-bold text-sm text-white" style={{ background: LIVE_RED }}>
        {saving ? "Scheduling…" : "Schedule livestream"}
      </button>
      <p className="md:col-span-2 text-xs text-[#5A607A]">
        New shows are listed once an admin approves them. 80% of every ticket goes to you.
      </p>
    </form>
  );
}

export function LivestreamManager() {
  const [shows, setShows] = useState<MyLivestream[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState(false);

  const load = () => api.live.mine().then(setShows).catch(() => {});
  useEffect(() => { load(); }, []);

  return (
    <section>
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-xl font-bold">Your Livestreams</h2>
        <button
          onClick={() => setScheduling(!scheduling)}
          className="text-sm px-4 py-2 rounded-full border border-[#E33B3B]/40 text-[#E33B3B] hover:bg-[#E33B3B]/10 transition-colors"
        >
          {scheduling ? "Cancel" : "+ Schedule livestream"}
        </button>
      </div>

      {scheduling && <ScheduleForm onDone={() => { setScheduling(false); load(); }} />}

      {shows.length === 0 ? (
        <div className="text-center py-16 text-[#5A607A]">
          <p className="text-4xl mb-3">🎤</p>
          <p>No livestreams scheduled yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {shows.map((s) => (
            <div key={s.id} className="p-5 rounded-xl bg-[#12151E] border border-white/8">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-white truncate">{s.title}</p>
                  <p className="text-xs text-[#5A607A]">
                    {showTime(s.starts_at)}{s.status !== "live" && ` · ${s.status === "review" ? "awaiting approval" : s.status}`}
                  </p>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded font-bold uppercase ${STATE_STYLE[s.live_state] ?? ""}`}
                  style={s.live_state === "on_air" ? { background: LIVE_RED } : undefined}
                >
                  {s.live_state === "on_air" ? "● On air" : s.live_state}
                </span>
                <span className="text-xs text-[#F5C842] font-mono">◈ {s.rent_credits}</span>
                {s.ingest && (
                  <button
                    onClick={() => setOpen(open === s.id ? null : s.id)}
                    className="text-xs px-3 py-1.5 rounded-full border border-white/15 text-white hover:bg-white/5"
                  >
                    {open === s.id ? "Close" : "ATEM setup"}
                  </button>
                )}
              </div>
              {open === s.id && <AtemSetup show={s} onChange={load} />}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

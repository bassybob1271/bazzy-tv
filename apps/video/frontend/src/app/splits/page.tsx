"use client";
/**
 * Split sheets: a band (or filmmaker) lists everyone who made a show or film, with a role and a
 * percentage. Every sale's creator share is divided by it. People not on Bazzy yet are emailed a join
 * link; their cut is held until they sign up and confirm that email.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SplitSheet, type SplitShareRow, type SplitStatement } from "@/lib/api";
import { useStore } from "@/store/useStore";

const ROLES = ["band", "venue", "producer", "engineer", "opener", "manager", "lighting", "video", "other"];
const COLORS = ["#4F8EF7", "#F5C842", "#3DD68C", "#E05297", "#9B7BFF", "#FF8A4C", "#38C6D9", "#C9D25A", "#E05252"];
const blankRow = (): SplitShareRow => ({ email: "", name: "", role: "producer", percent: 0 });
const round2 = (n: number) => Math.round(n * 100) / 100;

type Draft = { id?: string; name: string; app: "live" | "tv"; source_ref: string; shares: SplitShareRow[] };

export default function SplitsPage() {
  const router = useRouter();
  const { hydrated, isAuthenticated } = useStore();
  const [sheets, setSheets] = useState<SplitSheet[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [statement, setStatement] = useState<SplitStatement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  async function load() {
    setSheets(await api.splits.list());
  }

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated) { router.push("/auth/login?redirect=/splits"); return; }
    load().catch((e) => setError(e.message));
  }, [hydrated, isAuthenticated]);

  const total = useMemo(() => round2((draft?.shares ?? []).reduce((a, s) => a + (Number(s.percent) || 0), 0)), [draft]);

  function startNew() {
    setStatement(null);
    setError("");
    setDraft({ name: "", app: "live", source_ref: "", shares: [{ email: "", name: "", role: "band", percent: 100 }] });
  }

  async function open(s: SplitSheet) {
    setError("");
    setDraft(s.owner ? { id: s.id, name: s.name, app: s.app, source_ref: s.source_ref, shares: s.shares.map((x) => ({ ...x, name: x.name ?? "" })) } : null);
    setStatement(await api.splits.statement(s.id));
  }

  function setRow(i: number, patch: Partial<SplitShareRow>) {
    setDraft((d) => d && { ...d, shares: d.shares.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  }

  function evenSplit() {
    setDraft((d) => {
      if (!d || !d.shares.length) return d;
      const n = d.shares.length;
      const each = Math.floor(10000 / n);
      const first = 10000 - each * (n - 1); // leftover cents to the first line, like payouts
      return { ...d, shares: d.shares.map((r, i) => ({ ...r, percent: (i === 0 ? first : each) / 100 })) };
    });
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError("");
    try {
      const shares = draft.shares.map((s) => ({ ...s, name: s.name || null, percent: Number(s.percent) }));
      const saved = draft.id
        ? await api.splits.update(draft.id, { name: draft.name, shares })
        : await api.splits.create({ name: draft.name, app: draft.app, source_ref: draft.source_ref, shares });
      await load();
      await open(saved);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function copy(url: string, email: string) {
    await navigator.clipboard.writeText(url).catch(() => {});
    setCopied(email);
    setTimeout(() => setCopied(""), 1800);
  }

  return (
    <main className="max-w-6xl mx-auto px-5 py-10">
      <div className="flex flex-wrap items-end gap-4 mb-8">
        <div className="flex-1 min-w-[260px]">
          <h1 className="text-3xl font-bold">Splits</h1>
          <p className="text-[#A0A8C0] mt-1 max-w-2xl">
            Pay everyone who made the show: the venue, producers, engineers, openers, the band. Every ticket or rental is divided automatically.
            Anyone not on Bazzy gets an invite, and their cut waits for them.
          </p>
        </div>
        <button onClick={startNew} className="px-5 py-2.5 rounded-full bg-[#4F8EF7] text-white font-semibold hover:bg-[#6AA0FF]">
          + New split
        </button>
      </div>

      <div className="grid lg:grid-cols-[300px_1fr] gap-6">
        {/* Sheets */}
        <aside className="flex flex-col gap-2">
          {sheets.length === 0 && <p className="text-sm text-[#5A607A] p-4 rounded-xl border border-dashed border-white/10">No splits yet. Make one for your next show.</p>}
          {sheets.map((s) => (
            <button key={s.id} onClick={() => open(s)}
              className={`text-left p-4 rounded-xl border transition-colors ${statement?.sheet.id === s.id ? "border-[#4F8EF7]/60 bg-[#4F8EF7]/10" : "border-white/10 bg-[#141826] hover:border-white/25"}`}>
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/10 text-[#A0A8C0]">{s.app === "live" ? "Live show" : "Film"}</span>
                {!s.owner && <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#F5C842]/15 text-[#F5C842]">You're on it</span>}
              </div>
              <div className="font-semibold mt-1.5 truncate">{s.name}</div>
              <SplitBar shares={s.shares} className="mt-2 h-1.5" />
              <div className="text-xs text-[#5A607A] mt-1.5">{s.shares.length} {s.shares.length === 1 ? "person" : "people"}</div>
            </button>
          ))}
        </aside>

        <section className="flex flex-col gap-6 min-w-0">
          {/* Editor */}
          {draft && (
            <div className="rounded-2xl bg-[#141826] border border-[#232a40] p-6">
              <div className="grid md:grid-cols-[1fr_160px_1fr] gap-3">
                <Field label="Name">
                  <input className="inp" placeholder="Greenhouse BK, Fri Dec 5" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                </Field>
                <Field label="For">
                  <select className="inp" disabled={!!draft.id} value={draft.app} onChange={(e) => setDraft({ ...draft, app: e.target.value as "live" | "tv" })}>
                    <option value="live">A live show</option>
                    <option value="tv">A film</option>
                  </select>
                </Field>
                <Field label={draft.app === "live" ? "Show ID (from Bazzy Live)" : "Film ID"}>
                  <input className="inp font-mono" disabled={!!draft.id} placeholder={draft.app === "live" ? "show-dec5" : "title id"} value={draft.source_ref} onChange={(e) => setDraft({ ...draft, source_ref: e.target.value })} />
                </Field>
              </div>

              <div className="mt-6 flex items-center gap-3">
                <h2 className="font-semibold">Who gets paid</h2>
                <span className={`ml-auto text-sm font-mono tabular-nums ${total === 100 ? "text-[#3DD68C]" : "text-[#F5C842]"}`}>{total}% of 100%</span>
              </div>
              <SplitBar shares={draft.shares} className="mt-2 h-3" />

              <div className="mt-4 flex flex-col gap-2">
                {draft.shares.map((r, i) => (
                  <div key={i} className="grid grid-cols-[10px_1.4fr_1fr_130px_96px_32px] gap-2 items-center">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                    <input className="inp" type="email" placeholder="email@example.com" value={r.email} onChange={(e) => setRow(i, { email: e.target.value })} />
                    <input className="inp" placeholder="Name (optional)" value={r.name ?? ""} onChange={(e) => setRow(i, { name: e.target.value })} />
                    <input className="inp" list="split-roles" value={r.role} onChange={(e) => setRow(i, { role: e.target.value })} />
                    <div className="relative">
                      <input className="inp pr-6 text-right tabular-nums" type="number" min={0} max={100} step={0.01} value={r.percent}
                        onChange={(e) => setRow(i, { percent: e.target.value === "" ? 0 : Number(e.target.value) })} />
                      <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#5A607A] text-sm">%</span>
                    </div>
                    <button aria-label="Remove" disabled={draft.shares.length === 1}
                      onClick={() => setDraft({ ...draft, shares: draft.shares.filter((_, j) => j !== i) })}
                      className="h-9 rounded-lg text-[#5A607A] hover:text-[#E05252] disabled:opacity-30">✕</button>
                  </div>
                ))}
                <datalist id="split-roles">{ROLES.map((x) => <option key={x} value={x} />)}</datalist>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button onClick={() => setDraft({ ...draft, shares: [...draft.shares, blankRow()] })} className="px-4 py-2 rounded-full border border-white/15 text-sm hover:border-white/30">+ Add person</button>
                <button onClick={evenSplit} className="px-4 py-2 rounded-full border border-white/15 text-sm hover:border-white/30">Split evenly</button>
                <span className="text-xs text-[#5A607A] ml-1">Leftover credits from rounding go to the first line: put the band first.</span>
                <button onClick={save} disabled={busy || total !== 100 || !draft.name || !draft.source_ref}
                  className="ml-auto px-6 py-2.5 rounded-full bg-[#4F8EF7] text-white font-semibold disabled:bg-white/10 disabled:text-[#5A607A]">
                  {busy ? "Saving…" : draft.id ? "Save changes" : "Create split & send invites"}
                </button>
              </div>
              {draft.id && <p className="text-xs text-[#5A607A] mt-3">Changes apply to sales from now on. Past sales keep the split they were paid under. New people are emailed an invite.</p>}
              {error && <p className="text-sm text-[#E05252] mt-3">{error}</p>}
            </div>
          )}

          {/* Statement */}
          {statement && (
            <div className="rounded-2xl bg-[#141826] border border-[#232a40] p-6">
              <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
                <h2 className="font-semibold text-lg">{statement.sheet.name}</h2>
                <span className="text-sm text-[#A0A8C0]">{statement.sales.toLocaleString()} {statement.sales === 1 ? "sale" : "sales"}</span>
                <span className="ml-auto text-sm"><span className="font-mono text-[#F5C842]">{statement.total_credits.toLocaleString()}</span> <span className="text-[#5A607A]">credits paid out</span></span>
              </div>
              <div className="mt-4 divide-y divide-white/5">
                {statement.sheet.shares.map((s, i) => {
                  const p = statement.people.find((x) => x.email === s.email);
                  return (
                    <div key={s.email} className="py-3 flex flex-wrap items-center gap-3">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate">{s.name || s.email}</div>
                        <div className="text-xs text-[#5A607A] truncate">{s.role} · {s.percent}%{s.name ? ` · ${s.email}` : ""}</div>
                      </div>
                      {p && p.held_credits > 0 && (
                        <span className="flex items-center gap-2 text-xs">
                          <span className="px-2 py-1 rounded-full bg-[#F5C842]/15 text-[#F5C842]">{p.held_credits.toLocaleString()} waiting for them to join</span>
                          {p.join_url && (
                            <button onClick={() => copy(p.join_url!, p.email)} className="px-2.5 py-1 rounded-full border border-white/15 hover:border-white/30">
                              {copied === p.email ? "Copied" : "Copy invite link"}
                            </button>
                          )}
                        </span>
                      )}
                      <span className="font-mono tabular-nums w-24 text-right">{(p?.credits ?? 0).toLocaleString()}</span>
                    </div>
                  );
                })}
              </div>
              {statement.recent.length === 0 && <p className="text-sm text-[#5A607A] mt-2">No sales yet. Payments show here as tickets sell.</p>}
            </div>
          )}

          {!draft && !statement && (
            <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center text-[#5A607A]">
              Pick a split, or make a new one for your next show.
            </div>
          )}
        </section>
      </div>

      <style jsx>{`
        :global(.inp) {
          width: 100%; height: 2.25rem; padding: 0 0.75rem; border-radius: 0.5rem;
          background: #0B0D14; border: 1px solid #232a40; color: #E8ECF7; font-size: 0.875rem;
        }
        :global(.inp:focus) { outline: none; border-color: #4F8EF7; }
        :global(.inp:disabled) { opacity: 0.6; }
      `}</style>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-xs text-[#A0A8C0]">
      {label}
      {children}
    </label>
  );
}

function SplitBar({ shares, className = "" }: { shares: { percent: number; email: string }[]; className?: string }) {
  return (
    <div className={`flex w-full overflow-hidden rounded-full bg-white/5 ${className}`}>
      {shares.map((s, i) => (
        <div key={i} title={`${s.email || "?"} ${s.percent}%`} style={{ width: `${Math.max(0, Math.min(100, Number(s.percent) || 0))}%`, background: COLORS[i % COLORS.length] }} className="transition-[width] duration-200" />
      ))}
    </div>
  );
}

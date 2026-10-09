"use client";
import { useEffect, useState } from "react";
import { api, useOwner } from "@/lib/api";
import { categoryName, checkName, ms, reasonName, statusName } from "@/lib/format";
import type { Result } from "@/lib/types";
import { Pill } from "./States";

function Score({ label, value, max = 5 }: { label: string; value?: number; max?: number }) {
  return (
    <div>
      <dt className="text-xs text-ink-soft">{label}</dt>
      <dd className="mt-0.5 font-display text-xl">{value ?? "n/a"}<span className="text-sm text-ink-faint">/{max}</span></dd>
    </div>
  );
}

export function LabelForm({ result, onSaved }: { result: Result; onSaved?: () => void }) {
  const owner = useOwner();
  const [halluc, setHalluc] = useState(result.label?.hallucination ?? false);
  const [note, setNote] = useState(result.label?.note ?? "");
  const [saved, setSaved] = useState<string | null>(result.label ? (result.label.passed ? "Marked correct" : "Marked wrong") : null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setHalluc(result.label?.hallucination ?? false); setNote(result.label?.note ?? "");
    setSaved(result.label ? (result.label.passed ? "Marked correct" : "Marked wrong") : null);
  }, [result]);

  if (!owner) {
    return <p className="text-sm text-ink-soft">Human labels are added by the project owner. {result.label && `Owner's label: ${result.label.passed ? "correct" : "wrong"}.`}</p>;
  }
  async function save(passed: boolean) {
    setErr(null);
    try {
      await api(`/admin/results/${result.id}/label`, { method: "POST", owner: true, body: JSON.stringify({ passed, hallucination: halluc, note }) });
      setSaved(passed ? "Marked correct" : "Marked wrong");
      onSaved?.();
    } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save the label."); }
  }
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={halluc} onChange={(e) => setHalluc(e.target.checked)} className="accent-fail" />
        Contains a made-up fact
      </label>
      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="Optional note"
        className="w-full rounded border border-rule bg-sheet px-3 py-2 text-sm" />
      <div className="flex flex-wrap items-center gap-3">
        <button onClick={() => save(true)} className="rounded bg-pass px-3 py-1.5 text-sm text-sheet">Mark correct</button>
        <button onClick={() => save(false)} className="rounded bg-fail px-3 py-1.5 text-sm text-sheet">Mark wrong</button>
        {saved && <span className="text-sm text-ink-soft">{saved}</span>}
        {err && <span className="text-sm text-fail">{err}</span>}
      </div>
    </div>
  );
}

export default function ResultPanel({ result, onClose, onLabeled }: { result: Result; onClose?: () => void; onLabeled?: () => void }) {
  const j = result.judge;
  return (
    <article className="rounded-md border border-rule bg-sheet">
      <header className="flex flex-wrap items-start gap-3 border-b border-rule px-5 py-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm text-ink-soft">{result.case_key}, {categoryName[result.category] ?? result.category}</p>
          <h3 className="mt-1 font-display text-lg leading-snug">{result.question}</h3>
        </div>
        <Pill tone={result.passed ? "pass" : "fail"}>{result.passed ? "Passed" : "Failed"}</Pill>
        {onClose && <button onClick={onClose} className="text-sm text-ink-soft hover:text-ink">Close</button>}
      </header>

      <div className="grid gap-x-8 gap-y-6 px-5 py-5 lg:grid-cols-[1.4fr_1fr]">
        <section className="space-y-5">
          <div>
            <h4 className="text-sm font-semibold">Bot answer <span className="font-normal text-ink-soft">({statusName[result.status] ?? result.status})</span></h4>
            <p className="mt-1.5 max-w-prose whitespace-pre-wrap leading-relaxed">{result.answer}</p>
          </div>
          <div>
            <h4 className="text-sm font-semibold">What we expected</h4>
            <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-soft">
              {result.expected_behavior} Acceptable outcomes: {result.expected_statuses.map((s) => statusName[s] ?? s).join(", ")}.
            </p>
          </div>
          <details className="group">
            <summary className="cursor-pointer text-sm font-semibold">
              Policy excerpts the bot saw ({result.context.length})
            </summary>
            {result.context.length === 0 ? (
              <p className="mt-2 text-sm text-ink-soft">None. Retrieval confidence was below the threshold, so the bot answered without context.</p>
            ) : (
              <ol className="mt-2 space-y-3">
                {result.context.map((c) => (
                  <li key={c.chunk_id} className="border-l-2 border-rule pl-3 text-sm">
                    <p className="text-ink-soft">[{c.n}] {c.title}{c.section ? `, ${c.section}` : ""}</p>
                    <p className="mt-1 leading-relaxed">{c.content}</p>
                  </li>
                ))}
              </ol>
            )}
          </details>
        </section>

        <aside className="space-y-6">
          <div>
            <h4 className="text-sm font-semibold">Rule checks</h4>
            <ul className="mt-2 space-y-1.5 text-sm">
              {Object.entries(result.checks).map(([k, v]) => (
                <li key={k} className="flex items-center gap-2">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${v ? "bg-pass" : k === "latency_ok" ? "bg-watch" : "bg-fail"}`} aria-hidden />
                  <span>{checkName[k] ?? k}</span>
                  <span className="sr-only">{v ? "passed" : "failed"}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-semibold">LLM judge</h4>
            {!j || j.error ? (
              <p className="mt-2 text-sm text-fail">{j?.error ?? "Not judged."}</p>
            ) : (
              <>
                <dl className="mt-2 grid grid-cols-3 gap-3">
                  <Score label="Grounded" value={j.grounded} />
                  <Score label="Helpful" value={j.helpful} />
                  <div>
                    <dt className="text-xs text-ink-soft">Confidence</dt>
                    <dd className="mt-0.5 font-display text-xl">{j.confidence != null ? Math.round(j.confidence * 100) : "n/a"}<span className="text-sm text-ink-faint">%</span></dd>
                  </div>
                </dl>
                <p className="mt-3 text-sm">
                  {j.hallucination ? <Pill tone="fail">Made-up fact detected</Pill> : <Pill tone="pass">No made-up facts</Pill>}{" "}
                  {j.safe === false && <Pill tone="fail">Unsafe</Pill>}
                </p>
                <p className="mt-3 text-sm leading-relaxed text-ink-soft">{j.rationale}</p>
              </>
            )}
          </div>
          <div className="text-sm text-ink-soft">
            Took {ms(result.trace.total_ms)}, best excerpt match {result.trace.top_similarity?.toFixed(2)}
            {result.trace.gated ? ", answered without excerpts" : ""}.
          </div>
          {result.needs_review && (
            <div className="rounded border border-watch/40 bg-watch-tint px-3 py-3">
              <h4 className="text-sm font-semibold">Why this needs a human</h4>
              <ul className="mt-1 list-disc pl-5 text-sm">
                {result.review_reasons.map((r) => <li key={r}>{reasonName[r] ?? r}</li>)}
              </ul>
              <div className="mt-3"><LabelForm result={result} onSaved={onLabeled} /></div>
            </div>
          )}
        </aside>
      </div>
    </article>
  );
}

"use client";
import { useState } from "react";
import ResultPanel from "@/components/ResultPanel";
import { ErrorNote, Loading, Pill } from "@/components/States";
import { useApi, useOwner } from "@/lib/api";
import { categoryName, reasonName } from "@/lib/format";
import type { Agreement, Result } from "@/lib/types";

function kappaWords(k: number | null) {
  if (k == null) return "Not enough labels yet.";
  if (k >= 0.8) return "Almost perfect agreement. The judge can be trusted on cases like these.";
  if (k >= 0.6) return "Substantial agreement. Good enough for regression tracking, with spot checks.";
  if (k >= 0.4) return "Moderate agreement. Treat the judge's verdicts as a signal, not a decision.";
  return "Weak agreement. The rubric or the judge model needs work before its scores mean much.";
}

export default function ReviewPage() {
  const owner = useOwner();
  const agree = useApi<Agreement>("/metrics/judge-agreement");
  const queue = useApi<Result[]>("/review/queue");
  const [open, setOpen] = useState<number | null>(null);
  const [showLabeled, setShowLabeled] = useState(false);

  const items = (queue.data ?? []).filter((r) => showLabeled || !r.label);
  const refresh = () => { agree.reload(); queue.reload(); };
  const cm = agree.data?.confusion;

  return (
    <div>
      <h1 className="font-display text-3xl font-bold">Human review</h1>
      <p className="mt-2 max-w-prose text-ink-soft">
        An LLM judge is only useful if it agrees with people. Cases where the judge was unsure, contradicted itself, or
        disagreed with the rule checks come here, along with a random 10% audit sample. Human labels then measure how far the judge can be trusted.
      </p>

      <section className="mt-8 grid gap-8 rounded-md border border-rule bg-sheet p-6 md:grid-cols-[1fr_auto]">
        <div>
          <p className="text-sm text-ink-soft">Judge vs human agreement, beyond chance (Cohen&apos;s kappa)</p>
          <p className="mt-1 font-display text-5xl font-bold">{agree.data?.cohen_kappa ?? "n/a"}</p>
          <p className="mt-2 max-w-md text-sm leading-relaxed">{kappaWords(agree.data?.cohen_kappa ?? null)}</p>
          <p className="mt-2 text-sm text-ink-soft">Based on {agree.data?.labeled ?? 0} labeled cases, {agree.data?.agreement_pct ?? "n/a"}% raw agreement.</p>
        </div>
        {cm && (
          <table className="self-center text-center text-sm" aria-label="Judge versus human confusion table">
            <thead><tr><th /><th className="px-3 pb-2 font-medium text-ink-soft">Human: correct</th><th className="px-3 pb-2 font-medium text-ink-soft">Human: wrong</th></tr></thead>
            <tbody>
              <tr><th className="pr-3 text-right font-medium text-ink-soft">Judge: pass</th>
                <td className="border border-rule bg-pass-tint px-6 py-3 font-display text-xl">{cm.both_pass}</td>
                <td className="border border-rule bg-fail-tint px-6 py-3 font-display text-xl">{cm.judge_pass_human_fail}</td></tr>
              <tr><th className="pr-3 text-right font-medium text-ink-soft">Judge: fail</th>
                <td className="border border-rule bg-fail-tint px-6 py-3 font-display text-xl">{cm.judge_fail_human_pass}</td>
                <td className="border border-rule bg-pass-tint px-6 py-3 font-display text-xl">{cm.both_fail}</td></tr>
            </tbody>
          </table>
        )}
      </section>

      <section className="mt-10">
        <div className="flex flex-wrap items-center gap-4">
          <h2 className="font-display text-xl font-bold">Queue</h2>
          <label className="flex items-center gap-2 text-sm text-ink-soft">
            <input type="checkbox" checked={showLabeled} onChange={(e) => setShowLabeled(e.target.checked)} /> Include already labeled
          </label>
          {!owner && <span className="text-sm text-ink-soft">Read-only. Labels are added by the project owner.</span>}
        </div>
        {queue.loading && <Loading what="the review queue" slow={queue.slow} />}
        {queue.error && <ErrorNote message={queue.error} retry={queue.reload} />}
        {queue.data && items.length === 0 && <p className="mt-6 text-ink-soft">Nothing waiting for review.</p>}
        <ul className="mt-4 space-y-3">
          {items.map((r) => (
            <li key={r.id}>
              {open === r.id ? <ResultPanel result={r} onClose={() => setOpen(null)} onLabeled={refresh} /> : (
                <button onClick={() => setOpen(r.id)} className="flex w-full flex-wrap items-center gap-3 rounded-md border border-rule bg-sheet px-4 py-3 text-left hover:border-ink-faint">
                  <span className="text-sm text-ink-soft">Run {r.run_id}, {r.case_key}</span>
                  <span className="min-w-0 flex-1">{r.question}</span>
                  <span className="text-xs text-ink-soft">{categoryName[r.category]}</span>
                  {r.label ? <Pill tone="plain">Labeled</Pill> : <Pill tone="watch">{reasonName[r.review_reasons[0]] ?? "Review"}</Pill>}
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

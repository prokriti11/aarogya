"use client";
import { useEffect, useMemo, useState } from "react";
import ResultPanel from "@/components/ResultPanel";
import { ErrorNote, Loading, Pill } from "@/components/States";
import VitalsStrip, { StripLegend } from "@/components/VitalsStrip";
import { useApi } from "@/lib/api";
import { categoryName, categoryOrder, ms, pct, statusName, when } from "@/lib/format";
import type { Result, Run } from "@/lib/types";

type Filter = "all" | "failed" | "review";

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="border-t border-rule pt-3">
      <dt className="text-sm text-ink-soft">{label}</dt>
      <dd className="mt-1 font-display text-2xl">{value}</dd>
      <dd className="mt-1 text-xs leading-snug text-ink-faint">{hint}</dd>
    </div>
  );
}

export default function RunPage({ params }: { params: { id: string } }) {
  const [pollMs, setPollMs] = useState<number | undefined>(3000);
  const run = useApi<Run>(`/runs/${params.id}`, pollMs);
  const running = run.data?.status === "running" || run.data?.status === "queued";
  const results = useApi<Result[]>(`/runs/${params.id}/results`, running ? 3000 : undefined);
  useEffect(() => { if (run.data && !running) setPollMs(undefined); }, [run.data, running]);

  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<Result | null>(null);

  const shown = useMemo(() => (results.data ?? []).filter((r) =>
    filter === "all" ? true : filter === "failed" ? !r.passed : r.needs_review), [results.data, filter]);

  if (run.loading) return <Loading what="this run" slow={run.slow} />;
  if (run.error || !run.data) return <ErrorNote message={run.error ?? "Run not found."} retry={run.reload} />;
  const r = run.data, s = r.summary;

  return (
    <div>
      <header className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <h1 className="font-display text-3xl font-bold">Run {r.id}</h1>
        <p className="text-ink-soft">{r.model}, judged by {r.judge_model}, {when(r.created_at)}</p>
        {r.status === "failed" && <Pill tone="fail">Failed: {r.error}</Pill>}
      </header>

      {running && (
        <div className="mt-6" role="status">
          <p className="text-sm text-ink-soft">Testing {r.completed} of {r.total} cases. Results appear as they finish.</p>
          <div className="mt-2 h-2 rounded-full bg-sheet"><div className="h-2 rounded-full bg-pass transition-all" style={{ width: `${r.total ? (r.completed / r.total) * 100 : 0}%` }} /></div>
        </div>
      )}

      {results.data && results.data.length > 0 && (
        <section className="mt-8">
          <VitalsStrip results={results.data} size="lg" onSelect={setSelected} selectedId={selected?.id} />
          <StripLegend />
        </section>
      )}

      {selected && <div className="mt-6"><ResultPanel result={selected} onClose={() => setSelected(null)} onLabeled={results.reload} /></div>}

      {s && (
        <section className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,15rem)_1fr]">
          <div>
            <p className="text-sm text-ink-soft">Passed</p>
            <p className="font-display text-5xl font-bold text-pass">{pct(s.pass_rate)}</p>
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">A case passes only if every rule check passes and the judge agrees the answer is grounded, helpful, and safe.</p>
          </div>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-3">
            <Stat label="Behaved as expected" value={pct(s.status_accuracy)} hint="Answered, declined, or clarified when it should have" />
            <Stat label="Answers with made-up facts" value={pct(s.hallucination_rate)} hint="Share of answers with a claim the excerpts don't support" />
            <Stat label="Groundedness" value={s.avg_grounded != null ? `${s.avg_grounded} / 5` : "n/a"} hint="Judge's average, answered cases only" />
            <Stat label="Answers properly cited" value={pct(s.citation_validity)} hint="Cited, and every citation points to a real excerpt" />
            <Stat label="Response time" value={`${ms(s.latency_p50_ms)}`} hint={`Typical; slowest 5% take ${ms(s.latency_p95_ms)}`} />
            <Stat label="Cost per 1,000 chats" value={s.est_cost_per_1k_conversations_usd != null ? `$${s.est_cost_per_1k_conversations_usd}` : "n/a"} hint="At the provider's list price for this model" />
          </dl>
        </section>
      )}

      {s && (
        <section className="mt-12">
          <h2 className="font-display text-xl font-bold">By type of question</h2>
          <ul className="mt-4 space-y-3">
            {categoryOrder.filter((c) => s.by_category[c]).map((c) => {
              const b = s.by_category[c];
              return (
                <li key={c} className="grid grid-cols-[10rem_1fr_4.5rem] items-center gap-4 text-sm">
                  <span>{categoryName[c]}</span>
                  <div className="h-3 rounded-sm bg-fail-tint" aria-hidden><div className="h-3 rounded-sm bg-pass" style={{ width: `${b.pass_rate ?? 0}%` }} /></div>
                  <span className="text-right">{b.passed}/{b.total}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {results.data && (
        <section className="mt-12">
          <div className="flex flex-wrap items-center gap-4">
            <h2 className="font-display text-xl font-bold">Every case</h2>
            <div className="flex gap-1 rounded border border-rule bg-sheet p-0.5 text-sm" role="tablist">
              {([["all", "All"], ["failed", "Failed"], ["review", "Needs review"]] as [Filter, string][]).map(([k, l]) => (
                <button key={k} role="tab" aria-selected={filter === k} onClick={() => setFilter(k)}
                  className={`rounded px-3 py-1 ${filter === k ? "bg-ink text-sheet" : "text-ink-soft hover:text-ink"}`}>{l}</button>
              ))}
            </div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-ink/20 text-ink-soft">
                <tr><th className="py-2 pr-3 font-medium">Case</th><th className="py-2 pr-3 font-medium">Question</th>
                  <th className="py-2 pr-3 font-medium">Bot did</th><th className="py-2 pr-3 font-medium">Grounded</th><th className="py-2 font-medium">Result</th></tr>
              </thead>
              <tbody>
                {shown.map((x) => (
                  <tr key={x.id} onClick={() => { setSelected(x); window.scrollTo({ top: 0, behavior: "smooth" }); }}
                    className={`cursor-pointer border-b border-rule hover:bg-sheet ${selected?.id === x.id ? "bg-sheet" : ""}`}>
                    <td className="py-2.5 pr-3 text-ink-soft">{x.case_key}</td>
                    <td className="max-w-md py-2.5 pr-3">{x.question}</td>
                    <td className="py-2.5 pr-3">{statusName[x.status] ?? x.status}</td>
                    <td className="py-2.5 pr-3">{x.judge?.grounded ?? "n/a"}</td>
                    <td className="py-2.5"><span className="flex gap-1.5">
                      <Pill tone={x.passed ? "pass" : "fail"}>{x.passed ? "Pass" : "Fail"}</Pill>
                      {x.needs_review && <Pill tone="watch">Review</Pill>}
                    </span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {shown.length === 0 && <p className="py-6 text-ink-soft">No cases match this filter.</p>}
          </div>
        </section>
      )}
    </div>
  );
}

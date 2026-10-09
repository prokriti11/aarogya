"use client";
import { useEffect, useState } from "react";
import { ErrorNote, Loading, Pill } from "@/components/States";
import { useApi } from "@/lib/api";
import { categoryName, ms, pct, statusName } from "@/lib/format";
import type { Comparison, Run, RunSummary } from "@/lib/types";

const metrics: { key: keyof RunSummary; label: string; fmt: (v: number | null) => string; higherIsBetter: boolean }[] = [
  { key: "pass_rate", label: "Passed", fmt: pct, higherIsBetter: true },
  { key: "status_accuracy", label: "Behaved as expected", fmt: pct, higherIsBetter: true },
  { key: "hallucination_rate", label: "Answers with made-up facts", fmt: pct, higherIsBetter: false },
  { key: "citation_validity", label: "Answers properly cited", fmt: pct, higherIsBetter: true },
  { key: "latency_p50_ms", label: "Typical response time", fmt: ms, higherIsBetter: false },
  { key: "est_cost_per_1k_conversations_usd", label: "Cost per 1,000 chats", fmt: (v) => (v == null ? "n/a" : `$${v}`), higherIsBetter: false },
];

function delta(a: number | null, b: number | null, higherIsBetter: boolean) {
  if (a == null || b == null || a === b) return { text: "no change", cls: "text-ink-faint" };
  const better = higherIsBetter ? b > a : b < a;
  const d = Math.round((b - a) * 100) / 100;
  return { text: `${d > 0 ? "+" : ""}${d}`, cls: better ? "text-pass" : "text-fail" };
}

export default function ComparePage() {
  const runs = useApi<Run[]>("/runs");
  const done = (runs.data ?? []).filter((r) => r.status === "done");
  const [a, setA] = useState<number | null>(null);
  const [b, setB] = useState<number | null>(null);
  useEffect(() => {
    if (done.length >= 2 && a == null && b == null) { setA(done[1].id); setB(done[0].id); }
  }, [done, a, b]);
  const cmp = useApi<Comparison>(a && b && a !== b ? `/compare?a=${a}&b=${b}` : null);
  const ra = done.find((r) => r.id === a), rb = done.find((r) => r.id === b);
  const changed = cmp.data?.cases.filter((c) => c.change !== "same") ?? [];

  if (runs.loading) return <Loading what="runs" slow={runs.slow} />;
  if (runs.error) return <ErrorNote message={runs.error} retry={runs.reload} />;

  const picker = (value: number | null, set: (n: number) => void, label: string) => (
    <label className="flex flex-col gap-1 text-sm text-ink-soft">{label}
      <select value={value ?? ""} onChange={(e) => set(Number(e.target.value))} className="rounded border border-rule bg-sheet px-2 py-1.5 text-ink">
        {done.map((r) => <option key={r.id} value={r.id}>Run {r.id}: {r.model}</option>)}
      </select>
    </label>
  );

  return (
    <div>
      <h1 className="font-display text-3xl font-bold">Compare two runs</h1>
      <p className="mt-2 max-w-prose text-ink-soft">See what changed between versions, case by case. A regression is a case that passed before and fails now.</p>
      {done.length < 2 ? <p className="mt-8 text-ink-soft">You need at least two finished runs to compare.</p> : (
        <>
          <div className="mt-6 flex flex-wrap gap-4">{picker(a, setA, "Before")}{picker(b, setB, "After")}</div>

          {ra?.summary && rb?.summary && (
            <table className="mt-8 w-full max-w-2xl text-left text-sm">
              <thead className="border-b border-ink/20 text-ink-soft"><tr><th className="py-2 font-medium">Metric</th><th className="py-2 font-medium">Before</th><th className="py-2 font-medium">After</th><th className="py-2 font-medium">Change</th></tr></thead>
              <tbody>
                {metrics.map((m) => {
                  const va = ra.summary![m.key] as number | null, vb = rb.summary![m.key] as number | null;
                  const d = delta(va, vb, m.higherIsBetter);
                  return <tr key={m.key} className="border-b border-rule"><td className="py-2.5">{m.label}</td><td>{m.fmt(va)}</td><td>{m.fmt(vb)}</td><td className={d.cls}>{d.text}</td></tr>;
                })}
              </tbody>
            </table>
          )}

          {cmp.loading && <Loading what="the comparison" />}
          {cmp.data && (
            <section className="mt-10">
              <h2 className="font-display text-xl font-bold">
                {cmp.data.regressions} regressions, {cmp.data.fixes} fixes
              </h2>
              {changed.length === 0 && <p className="mt-3 text-ink-soft">Every case had the same outcome in both runs.</p>}
              <ul className="mt-5 space-y-5">
                {changed.map((c) => (
                  <li key={c.case_key} className="rounded-md border border-rule bg-sheet p-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <Pill tone={c.change === "fix" ? "pass" : "fail"}>{c.change === "fix" ? "Fixed" : "Regressed"}</Pill>
                      <span className="text-sm text-ink-soft">{c.case_key}, {categoryName[c.category] ?? c.category}</span>
                    </div>
                    <p className="mt-2 font-medium">{c.question}</p>
                    <div className="mt-3 grid gap-4 text-sm md:grid-cols-2">
                      {([["Before", c.a], ["After", c.b]] as const).map(([lbl, side]) => (
                        <div key={lbl} className={`border-l-2 pl-3 ${side.passed ? "border-pass" : "border-fail"}`}>
                          <p className="text-ink-soft">{lbl}: {statusName[side.status] ?? side.status}</p>
                          <p className="mt-1 leading-relaxed">{side.answer}</p>
                        </div>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}

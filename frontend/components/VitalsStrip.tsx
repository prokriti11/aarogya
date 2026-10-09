"use client";
import type { Result } from "@/lib/types";
import { categoryName, categoryOrder } from "@/lib/format";

/**
 * One tick per test case, grouped by category, read like a patient-monitor strip.
 * Height = judge's groundedness score; colour = outcome; amber cap = routed to human review.
 */
export default function VitalsStrip({ results, onSelect, selectedId, size = "md" }: {
  results: Result[]; onSelect?: (r: Result) => void; selectedId?: number; size?: "md" | "lg";
}) {
  const groups = categoryOrder
    .map((c) => ({ c, items: results.filter((r) => r.category === c) }))
    .filter((g) => g.items.length);
  const h = size === "lg" ? 140 : 80;
  const w = size === "lg" ? "w-[13px]" : "w-[9px]";

  return (
    <div className="chart-paper overflow-x-auto rounded-md border border-rule bg-sheet px-4 pb-3 pt-5">
      <div className="flex min-w-max items-end gap-8">
        {groups.map(({ c, items }) => (
          <div key={c}>
            <div className="flex items-end gap-[5px]" style={{ height: h }}>
              {items.map((r, i) => {
                const score = r.judge?.grounded ?? 1;
                const tone = r.passed ? "bg-pass" : "bg-fail";
                return (
                  <button key={r.id} onClick={() => onSelect?.(r)}
                    aria-label={`${r.case_key}: ${r.passed ? "passed" : "failed"}${r.needs_review ? ", needs review" : ""}`}
                    title={`${r.case_key}: ${r.question}`}
                    className={`tick relative ${w} rounded-t-sm ${tone} ${selectedId === r.id ? "ring-2 ring-ink ring-offset-2" : ""} hover:opacity-80`}
                    style={{ height: `${20 + (score / 5) * 80}%`, animationDelay: `${i * 18}ms` }}>
                    {r.needs_review && <span className="absolute -top-2 left-0 h-[5px] w-full rounded-sm bg-watch" />}
                  </button>
                );
              })}
            </div>
            <div className="mt-2 border-t border-ink/20 pt-1.5 text-xs text-ink-soft">{categoryName[c] ?? c}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function StripLegend() {
  return (
    <p className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-soft">
      <span><span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-sm bg-pass align-middle" />Passed</span>
      <span><span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-sm bg-fail align-middle" />Failed</span>
      <span><span className="mr-1.5 inline-block h-1.5 w-2.5 rounded-sm bg-watch align-middle" />Sent to human review</span>
      <span>Taller means better grounded in the policy text</span>
    </p>
  );
}

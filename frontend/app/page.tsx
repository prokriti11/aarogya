"use client";
import Link from "next/link";
import { useMemo } from "react";
import VitalsStrip, { StripLegend } from "@/components/VitalsStrip";
import { ErrorNote, Loading } from "@/components/States";
import { GITHUB_URL, useApi } from "@/lib/api";
import { pct } from "@/lib/format";
import type { Result, Run } from "@/lib/types";

const pipeline = [
  ["Retrieve", "Hybrid search over the policy PDFs: meaning-based vectors plus exact keyword matching, merged by rank."],
  ["Gate", "If no excerpt is a close enough match, the model gets no context at all, so it can't improvise from weak text."],
  ["Answer", "The model replies in a fixed structure: answered, not found, off-topic, or a clarifying question, with citations."],
  ["Check", "Rule checks verify behaviour, citation validity, required and forbidden phrases, and latency."],
  ["Judge", "A separate model from a different family scores groundedness, helpfulness, and safety against a written rubric."],
  ["Review", "Uncertain or disputed cases go to a human. Their labels measure how far the judge can be trusted."],
];

export default function Home() {
  const runs = useApi<Run[]>("/runs");
  const latest = useMemo(() => runs.data?.find((r) => r.status === "done") ?? null, [runs.data]);
  const results = useApi<Result[]>(latest ? `/runs/${latest.id}/results` : null);

  return (
    <div>
      <section className="pt-6">
        <div className="max-w-3xl">
          <h1 className="font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl">
            A support bot for health insurance, and the tests that keep it honest.
          </h1>
          <p className="mt-5 max-w-prose text-lg leading-relaxed text-ink-soft">
            Aarogya answers policyholder questions from real policy wordings. Every version is run against the same
            41 test cases, from routine coverage questions to prompt-injection attempts, before anyone trusts it.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/chat" className="rounded bg-ink px-4 py-2.5 text-sheet hover:bg-ink/90">Ask the bot a question</Link>
            <Link href="/runs" className="rounded border border-ink/30 px-4 py-2.5 hover:border-ink">See the test results</Link>
            {GITHUB_URL && <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="px-2 py-2.5 text-ink-soft underline hover:text-ink">Read the code</a>}
          </div>
        </div>

        <div className="mt-12">
          {latest && results.data ? (
            <>
              <div className="mb-3 flex items-baseline justify-between gap-4">
                <p className="text-sm text-ink-soft">Latest run, {latest.model}</p>
                <Link href={`/runs/${latest.id}`} className="font-display text-3xl font-bold text-pass">
                  {pct(latest.summary?.pass_rate)} <span className="text-base font-medium text-ink-soft">passed</span>
                </Link>
              </div>
              <VitalsStrip results={results.data} size="lg" />
              <StripLegend />
            </>
          ) : runs.error ? (
            <ErrorNote message={runs.error} retry={runs.reload} />
          ) : runs.loading || results.loading || (latest && !results.data && !results.error) ? (
            <Loading what="the latest test run" slow={runs.slow || results.slow} />
          ) : (
            <p className="rounded-md border border-dashed border-rule p-8 text-ink-soft">No completed test runs yet.</p>
          )}
        </div>
      </section>

      <section className="mt-20 border-t border-rule pt-10">
        <h2 className="font-display text-2xl font-bold">How each answer is produced and tested</h2>
        <ol className="mt-8 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
          {pipeline.map(([title, text], i) => (
            <li key={title} className="flex gap-4">
              <span className="font-display text-2xl font-bold text-pass/70">{i + 1}</span>
              <div>
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-soft">{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

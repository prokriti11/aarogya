"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorNote, Loading, Pill } from "@/components/States";
import { api, useApi, useOwner } from "@/lib/api";
import { ms, pct, when } from "@/lib/format";
import type { Bot, Run, Suite } from "@/lib/types";

function StartRun({ onStarted }: { onStarted: (id: number) => void }) {
  const bots = useApi<Bot[]>("/bots");
  const suites = useApi<Suite[]>("/suites");
  const [bot, setBot] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const suite = suites.data?.[0];

  async function start() {
    if (!suite) return;
    setBusy(true); setErr(null);
    try {
      const r = await api<{ run_id: number }>("/admin/runs", { method: "POST", owner: true, body: JSON.stringify({ suite_id: suite.id, bot: bot || bots.data?.[0]?.name }) });
      onStarted(r.run_id);
    } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't start the run."); }
    finally { setBusy(false); }
  }
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-rule bg-sheet px-4 py-3">
      <span className="text-sm">Run {suite ? `${suite.cases} cases` : "the test suite"} against</span>
      <select value={bot} onChange={(e) => setBot(e.target.value)} className="rounded border border-rule bg-sheet px-2 py-1 text-sm">
        {bots.data?.map((b) => <option key={b.name} value={b.name}>{b.model}</option>)}
      </select>
      <button onClick={start} disabled={busy || !suite} className="rounded bg-ink px-3 py-1.5 text-sm text-sheet disabled:opacity-40">
        {busy ? "Starting…" : "Start run"}
      </button>
      {err && <span className="text-sm text-fail">{err}</span>}
    </div>
  );
}

export default function RunsPage() {
  const runs = useApi<Run[]>("/runs", 5000);
  const owner = useOwner();
  const router = useRouter();

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold">Test runs</h1>
          <p className="mt-2 max-w-prose text-ink-soft">Each run sends every test case to one model version, then scores the answers with rule checks and an LLM judge.</p>
        </div>
        {owner && <StartRun onStarted={(id) => router.push(`/runs/${id}`)} />}
      </div>

      {runs.loading && <Loading what="test runs" slow={runs.slow} />}
      {runs.error && <ErrorNote message={runs.error} retry={runs.reload} />}
      {runs.data && runs.data.length === 0 && <p className="mt-10 text-ink-soft">No runs yet. Sign in as the owner to start one.</p>}

      {runs.data && runs.data.length > 0 && (
        <div className="mt-8 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-ink/20 text-ink-soft">
              <tr>
                <th className="py-2 pr-4 font-medium">Run</th><th className="py-2 pr-4 font-medium">Model</th>
                <th className="py-2 pr-4 font-medium">Passed</th><th className="py-2 pr-4 font-medium">Made-up facts</th>
                <th className="py-2 pr-4 font-medium">Typical response time</th><th className="py-2 pr-4 font-medium">Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.data.map((r) => (
                <tr key={r.id} className="border-b border-rule hover:bg-sheet">
                  <td className="py-3 pr-4"><Link href={`/runs/${r.id}`} className="font-medium underline-offset-2 hover:underline">Run {r.id}</Link></td>
                  <td className="py-3 pr-4">{r.model}</td>
                  <td className="py-3 pr-4">
                    {r.status === "done" ? <span className="font-display text-lg">{pct(r.summary?.pass_rate)}</span>
                      : r.status === "running" ? <Pill tone="watch">Running {r.completed}/{r.total}</Pill>
                      : r.status === "failed" ? <Pill tone="fail">Failed</Pill> : <Pill tone="plain">Queued</Pill>}
                  </td>
                  <td className="py-3 pr-4">{pct(r.summary?.hallucination_rate)}</td>
                  <td className="py-3 pr-4">{ms(r.summary?.latency_p50_ms)}</td>
                  <td className="py-3 pr-4 text-ink-soft">{when(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

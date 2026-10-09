export const pct = (v: number | null | undefined) => (v == null ? "n/a" : `${v}%`);
export const ms = (v: number | null | undefined) =>
  v == null ? "n/a" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${v} ms`;

export const categoryName: Record<string, string> = {
  in_scope: "Policy questions", not_in_kb: "Not in documents", out_of_scope: "Off-topic",
  ambiguous: "Ambiguous", adversarial: "Adversarial", multilingual: "Hindi and Hinglish",
};
export const categoryOrder = ["in_scope", "not_in_kb", "ambiguous", "out_of_scope", "adversarial", "multilingual"];

export const statusName: Record<string, string> = {
  answered: "Answered", not_found: "Not found", out_of_scope: "Off-topic", clarify: "Asked to clarify", error: "Error",
};
export const checkName: Record<string, string> = {
  status_match: "Behaved as expected", no_error: "No runtime error", no_invalid_citations: "Citations point to real excerpts",
  has_citation: "Answer is cited", must_include: "Contains required terms", must_not_include: "Avoids forbidden phrases",
  latency_ok: "Within latency budget",
};
export const reasonName: Record<string, string> = {
  judge_inconsistent: "Judge's verdict contradicts its own scores", low_judge_confidence: "Judge wasn't confident",
  checks_vs_judge_disagree: "Rule checks and judge disagree", random_sample: "Random audit sample",
  judge_error: "Judge failed to respond",
};
export const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

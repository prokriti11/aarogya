export type BotStatus = "answered" | "not_found" | "out_of_scope" | "clarify" | "error";

export interface Bot { name: string; model: string; top_k: number; min_similarity: number }

export interface Citation { n: number; title: string; section: string | null; pages: [number, number]; snippet: string }
export interface ContextChunk { n: number; chunk_id: string; title: string; section: string | null; content: string }

export interface Trace {
  retrieval_ms: number; llm_ms?: number; total_ms: number; top_similarity: number; gated: boolean; model: string;
  prompt_tokens?: number; completion_tokens?: number; invalid_citations?: number[]; uncited_answer?: boolean; error?: string;
}

export interface ChatResponse {
  conversation_id: string; status: BotStatus; answer: string; citations: Citation[]; context: ContextChunk[]; trace: Trace;
}

export interface CategoryStat { total: number; passed: number; pass_rate: number | null }

export interface RunSummary {
  cases: number; pass_rate: number | null; status_accuracy: number | null; hallucination_rate: number | null;
  avg_grounded: number | null; citation_validity: number | null; gated_rate: number | null;
  latency_p50_ms: number | null; latency_p95_ms: number | null; prompt_tokens: number; completion_tokens: number;
  est_cost_per_1k_conversations_usd: number | null; needs_review: number; by_category: Record<string, CategoryStat>;
}

export interface Run {
  id: number; suite: string; bot: string; model: string; judge_model: string;
  status: "queued" | "running" | "done" | "failed"; total: number; completed: number;
  summary: RunSummary | null; error: string | null; created_at: string; finished_at: string | null;
}

export interface Judge {
  rationale?: string; grounded?: number; hallucination?: boolean; helpful?: number; safe?: boolean;
  verdict?: string; rule_verdict?: string; confidence?: number; error?: string;
}

export interface Result {
  id: number; run_id: number; case_key: string; category: string; question: string; expected_statuses: string[];
  expected_behavior: string; status: BotStatus; answer: string; context: ContextChunk[]; trace: Trace;
  checks: Record<string, boolean>; judge: Judge | null; passed: boolean; needs_review: boolean;
  review_reasons: string[]; label: { passed: boolean; hallucination: boolean; note: string } | null;
}

export interface Suite { id: number; name: string; description: string; cases: number }

export interface CompareCase {
  case_key: string; category: string; question: string; change: "regression" | "fix" | "same";
  a: { result_id: number; passed: boolean; status: string; answer: string };
  b: { result_id: number; passed: boolean; status: string; answer: string };
}
export interface Comparison { regressions: number; fixes: number; cases: CompareCase[] }

export interface Agreement {
  labeled: number; agreement_pct: number | null; cohen_kappa: number | null;
  confusion: { both_pass: number; both_fail: number; judge_pass_human_fail: number; judge_fail_human_pass: number };
}

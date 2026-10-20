"""Eval runner, deterministic checks, run metrics, run-vs-run diff, and judge/human agreement."""
import asyncio
import hashlib
import json
import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from .config import settings
from .db import SessionLocal
from .judge import build_judge_input, judge
from .llm import LLMError
from .models import BotVersion, EvalResult, EvalRun, HumanLabel, TestCase, TestSuite
from .rag import run_turn

# USD per 1M tokens (input, output), Groq list prices as of Aug 2026. Verify at groq.com/pricing before quoting.
PRICING = {
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
}

SEED_FILE = Path(__file__).parent.parent / "seeds" / "suite_v1.json"
log = logging.getLogger("uvicorn.error")
CASE_ATTEMPTS = 3
CASE_TIMEOUT_S = 600   # one case = bot call + judge call (slow thinking judge), including backoff


# ----------------------------- seeding -----------------------------

async def seed_suite():
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    async with SessionLocal() as s:
        if await s.scalar(select(TestSuite).where(TestSuite.name == data["name"])):
            return
        suite = TestSuite(name=data["name"], description=data["description"])
        suite.cases = [TestCase(**c) for c in data["cases"]]
        s.add(suite)
        await s.commit()


async def fail_interrupted_runs():
    """A free host can restart mid-run; don't leave runs stuck in 'running' forever."""
    async with SessionLocal() as s:
        await s.execute(update(EvalRun).where(EvalRun.status.in_(["queued", "running"]))
                        .values(status="failed", error="interrupted by server restart"))
        await s.commit()


# ----------------------------- checks -----------------------------

HARD_CHECKS = {"status_match", "has_citation", "no_invalid_citations", "must_include", "must_not_include", "no_error"}


def run_checks(case: TestCase, out: dict) -> dict:
    ans = out["answer"].lower()
    c = {"status_match": out["status"] in case.expected_statuses,
         "no_error": out["status"] != "error",
         "no_invalid_citations": not out["trace"].get("invalid_citations")}
    if out["status"] == "answered":
        c["has_citation"] = len(out["citations"]) > 0
    if case.must_include:
        c["must_include"] = all(any(alt.strip().lower() in ans for alt in term.split("|")) for term in case.must_include)
    if case.must_not_include:
        c["must_not_include"] = not any(t.lower() in ans for t in case.must_not_include)
    c["latency_ok"] = out["trace"].get("total_ms", 0) <= settings.latency_budget_ms   # soft: reported, not gating
    return c


def _sampled(run_id: int, case_key: str) -> bool:
    h = int(hashlib.sha1(f"{run_id}:{case_key}".encode()).hexdigest(), 16)
    return h % 100 < settings.review_sample_pct


# ----------------------------- runner -----------------------------

async def _eval_case(run_id: int, bot_id: int, case: TestCase, sem: asyncio.Semaphore):
    """Retry transient failures (network blips, DB drops, timeouts). If a case still fails,
    record it as an error result so the run always finishes instead of stalling."""
    async with sem:
        last: Exception | None = None
        for attempt in range(1, CASE_ATTEMPTS + 1):
            try:
                await asyncio.wait_for(_eval_case_once(run_id, bot_id, case), CASE_TIMEOUT_S)
                return
            except Exception as e:  # noqa: BLE001 - any failure is retried, then recorded
                last = e
                log.warning("run %s case %s attempt %s/%s failed: %r", run_id, case.case_key, attempt, CASE_ATTEMPTS, e)
                if attempt < CASE_ATTEMPTS:
                    await asyncio.sleep(5 * attempt)
        try:
            async with SessionLocal() as s:
                s.add(EvalResult(run_id=run_id, case_id=case.id, status="error",
                                 answer=f"Case failed after {CASE_ATTEMPTS} attempts: {last!r}"[:600],
                                 context=[], trace={}, checks={"no_error": False}, judge={"error": repr(last)[:300]},
                                 passed=False, needs_review=False, review_reasons=[]))
                await s.execute(update(EvalRun).where(EvalRun.id == run_id).values(completed=EvalRun.completed + 1))
                await s.commit()
        except Exception as e:  # noqa: BLE001
            log.error("run %s case %s could not be recorded: %r", run_id, case.case_key, e)


async def _judge_and_score(run_id: int, case: TestCase, context: list, status: str, answer: str,
                           checks: dict) -> tuple[dict, bool, list]:
    """Judge one bot answer and combine with the deterministic checks -> (judge, passed, review_reasons)."""
    hard_ok = all(v for k, v in checks.items() if k in HARD_CHECKS)
    reasons, judge_dict, judge_pass = [], None, False
    try:
        j, meta = await judge(build_judge_input(case.question, case.category, case.expected_statuses,
                                                case.expected_behavior, context, status, answer))
        judge_pass = j.rule_verdict() == "pass"
        judge_dict = {**j.model_dump(), "rule_verdict": j.rule_verdict(), **meta}
        if j.verdict != j.rule_verdict():
            reasons.append("judge_inconsistent")
        if j.confidence < 0.7:
            reasons.append("low_judge_confidence")
    except (LLMError, ValueError) as e:
        judge_dict = {"error": str(e)[:300]}
        reasons.append("judge_error")
    if hard_ok != judge_pass and "judge_error" not in reasons:
        reasons.append("checks_vs_judge_disagree")
    if _sampled(run_id, case.case_key):
        reasons.append("random_sample")

    return judge_dict, hard_ok and judge_pass, reasons


async def rejudge_errors(run_id: int, everything: bool = False) -> int:
    """Re-run the judge for results whose judge call errored (rate limits etc.), or for every result
    with everything=True (e.g. after switching judge model, so one run has one judge). The bot's
    answers are kept as they were. Returns how many judge errors remain."""
    async with SessionLocal() as s:
        rows = [r for r in (await s.scalars(select(EvalResult).where(EvalResult.run_id == run_id)
                                            .options(selectinload(EvalResult.case)))).all()
                if everything or (r.judge and "error" in r.judge)]
    for i, r in enumerate(rows, 1):
        judge_dict, passed, reasons = await _judge_and_score(run_id, r.case, r.context, r.status, r.answer, r.checks)
        async with SessionLocal() as s:
            await s.execute(update(EvalResult).where(EvalResult.id == r.id).values(
                judge=judge_dict, passed=passed, needs_review=bool(reasons), review_reasons=reasons))
            await s.commit()
        print(f"  re-judged {i}/{len(rows)} {r.case.case_key}: {'error' if 'error' in judge_dict else judge_dict['rule_verdict']}")
    async with SessionLocal() as s:
        run = await s.get(EvalRun, run_id)
        run.summary = await compute_summary(s, run_id)
        if everything:
            run.judge_model = settings.judge_model
        await s.commit()
        remaining = len([r for r in (await s.scalars(select(EvalResult).where(EvalResult.run_id == run_id))).all()
                         if r.judge and "error" in r.judge])
    return remaining


async def _eval_case_once(run_id: int, bot_id: int, case: TestCase):
    async with SessionLocal() as s:
        bot = await s.get(BotVersion, bot_id)
        out = await run_turn(s, bot, case.question, channel="eval")
    checks = run_checks(case, out)
    hard_ok = all(v for k, v in checks.items() if k in HARD_CHECKS)

    judge_dict, passed, reasons = await _judge_and_score(run_id, case, out["context"], out["status"],
                                                         out["answer"], checks)

    async with SessionLocal() as s:
        s.add(EvalResult(run_id=run_id, case_id=case.id, status=out["status"], answer=out["answer"],
                         context=out["context"], trace=out["trace"], checks=checks, judge=judge_dict,
                         passed=passed, needs_review=bool(reasons), review_reasons=reasons))
        await s.execute(update(EvalRun).where(EvalRun.id == run_id).values(completed=EvalRun.completed + 1))
        await s.commit()


async def execute_run(run_id: int):
    async with SessionLocal() as s:
        run = await s.get(EvalRun, run_id)
        cases = (await s.scalars(select(TestCase).where(TestCase.suite_id == run.suite_id))).all()
        run.status, run.total = "running", len(cases)
        bot_id = run.bot_version_id
        await s.commit()
    sem = asyncio.Semaphore(settings.eval_concurrency)
    try:
        results = await asyncio.gather(*[_eval_case(run_id, bot_id, c, sem) for c in cases], return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        async with SessionLocal() as s:
            run = await s.get(EvalRun, run_id)
            run.summary = await compute_summary(s, run_id)
            run.status = "done" if len(errors) < len(cases) else "failed"
            run.error = f"{len(errors)} cases errored: {errors[0]!r}"[:500] if errors else None
            run.finished_at = datetime.now(timezone.utc)
            await s.commit()
    except Exception as e:  # never leave a run stuck
        async with SessionLocal() as s:
            await s.execute(update(EvalRun).where(EvalRun.id == run_id).values(status="failed", error=repr(e)[:500]))
            await s.commit()


# ----------------------------- metrics -----------------------------

def _pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


def _percentile(xs: list[int], p: float) -> int | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


async def compute_summary(s, run_id: int) -> dict:
    # query the model directly: s.get() may return a cached EvalRun whose .bot isn't loaded (async lazy-load fails)
    model = await s.scalar(select(BotVersion.model).join(EvalRun, EvalRun.bot_version_id == BotVersion.id)
                           .where(EvalRun.id == run_id))
    rows = (await s.scalars(select(EvalResult).where(EvalResult.run_id == run_id)
                            .options(selectinload(EvalResult.case)))).all()
    n = len(rows)
    answered = [r for r in rows if r.status == "answered"]
    judged = [r for r in rows if r.judge and "error" not in r.judge]
    lat = [r.trace.get("total_ms") for r in rows if r.trace.get("total_ms")]
    p_tok = sum(r.trace.get("prompt_tokens") or 0 for r in rows)
    c_tok = sum(r.trace.get("completion_tokens") or 0 for r in rows)
    price = PRICING.get(model)
    cost_per_1k = round(1000 * (p_tok * price[0] + c_tok * price[1]) / 1e6 / n, 4) if price and n else None

    by_cat: dict[str, dict] = {}
    for r in rows:
        b = by_cat.setdefault(r.case.category, {"total": 0, "passed": 0})
        b["total"] += 1; b["passed"] += r.passed
    for b in by_cat.values():
        b["pass_rate"] = _pct(b["passed"], b["total"])

    halluc = [r for r in judged if r.status == "answered" and r.judge.get("hallucination")]
    grounded = [r.judge["grounded"] for r in judged if r.status == "answered"]
    return {
        "cases": n,
        "pass_rate": _pct(sum(r.passed for r in rows), n),
        "status_accuracy": _pct(sum(r.checks.get("status_match", False) for r in rows), n),
        "hallucination_rate": _pct(len(halluc), len([r for r in judged if r.status == "answered"])),
        "avg_grounded": round(statistics.mean(grounded), 2) if grounded else None,
        "citation_validity": _pct(sum(r.checks.get("has_citation", False) and r.checks.get("no_invalid_citations", False)
                                      for r in answered), len(answered)),
        "gated_rate": _pct(sum(bool(r.trace.get("gated")) for r in rows), n),
        "latency_p50_ms": _percentile(lat, 0.5),
        "latency_p95_ms": _percentile(lat, 0.95),
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "est_cost_per_1k_conversations_usd": cost_per_1k,
        "needs_review": sum(r.needs_review for r in rows),
        "by_category": by_cat,
    }


async def compare_runs(s, a_id: int, b_id: int) -> dict:
    """Per-case diff keyed on case_key, so it works across suite edits."""
    async def load(rid):
        rows = (await s.scalars(select(EvalResult).where(EvalResult.run_id == rid)
                                .options(selectinload(EvalResult.case)))).all()
        return {r.case.case_key: r for r in rows}
    a, b = await load(a_id), await load(b_id)
    diff = []
    for key in sorted(set(a) & set(b)):
        ra, rb = a[key], b[key]
        change = ("regression" if ra.passed and not rb.passed else
                  "fix" if not ra.passed and rb.passed else "same")
        diff.append({"case_key": key, "category": rb.case.category, "question": rb.case.question, "change": change,
                     "a": {"result_id": ra.id, "passed": ra.passed, "status": ra.status, "answer": ra.answer},
                     "b": {"result_id": rb.id, "passed": rb.passed, "status": rb.status, "answer": rb.answer}})
    return {"regressions": sum(d["change"] == "regression" for d in diff),
            "fixes": sum(d["change"] == "fix" for d in diff), "cases": diff}


def cohen_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    n = len(pairs)
    if n == 0:
        return None
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return round((po - pe) / (1 - pe), 3) + 0.0 if pe < 1 else None


async def judge_agreement(s) -> dict:
    rows = (await s.execute(select(EvalResult, HumanLabel).join(HumanLabel, HumanLabel.result_id == EvalResult.id))).all()
    pairs = [((r.judge or {}).get("rule_verdict") == "pass", h.passed) for r, h in rows if r.judge and "error" not in r.judge]
    cm = {"both_pass": 0, "both_fail": 0, "judge_pass_human_fail": 0, "judge_fail_human_pass": 0}
    for j, h in pairs:
        cm["both_pass" if j and h else "both_fail" if not j and not h else
           "judge_pass_human_fail" if j else "judge_fail_human_pass"] += 1
    return {"labeled": len(pairs), "agreement_pct": _pct(sum(j == h for j, h in pairs), len(pairs)),
            "cohen_kappa": cohen_kappa(pairs), "confusion": cm}

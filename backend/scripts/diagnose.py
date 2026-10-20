"""Show why cases failed in one run.  Usage (from backend/):  python -m scripts.diagnose 6"""
import asyncio
import sys
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.evals import HARD_CHECKS
from app.models import EvalResult


async def main(run_id: int):
    async with SessionLocal() as s:
        rows = (await s.scalars(select(EvalResult).where(EvalResult.run_id == run_id)
                                .options(selectinload(EvalResult.case)))).all()
    print(f"Run {run_id}: {len(rows)} results, {sum(r.passed for r in rows)} passed\n")
    why = Counter()
    for r in sorted(rows, key=lambda r: (r.case.category, r.case.case_key)):
        if r.passed:
            continue
        failed_checks = [k for k, v in (r.checks or {}).items() if k in HARD_CHECKS and not v]
        j = r.judge or {}
        if "error" in j:
            judge = "JUDGE ERROR: " + str(j["error"])[:90]
            why["judge error"] += 1
        else:
            judge = (f"judge {j.get('rule_verdict')} (grounded {j.get('grounded')}, halluc {j.get('hallucination')}, "
                     f"helpful {j.get('helpful')}, safe {j.get('safe')})")
            if j.get("rule_verdict") != "pass":
                why["judge said fail"] += 1
        for k in failed_checks:
            why["check failed: " + k] += 1
        print(f"{r.case.case_key:8} {r.case.category:13} status={r.status:13} checks_failed={failed_checks or '-'}")
        print(f"         {judge}")
        if "error" not in j and j.get("rationale"):
            print(f"         why: {j['rationale'][:160]}")
    print("\nFailure reasons:")
    for k, v in why.most_common():
        print(f"  {v:3}  {k}")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 6))

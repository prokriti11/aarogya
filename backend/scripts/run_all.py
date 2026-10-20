"""Run the full eval for every bot version, unattended.

Usage (from backend/):  python -m scripts.run_all
- Finds a Gemini judge model your key can actually use, and saves it to .env
- Runs the 41-case suite against each bot version, one after another
- Prints progress and a results summary

Runs in this process (the API server doesn't need to be running). Results land in the
same Neon database, so they show up on the website immediately.
"""
import asyncio
import re
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import select, update

from app.config import settings
from app.db import SessionLocal
from app.evals import execute_run, rejudge_errors, seed_suite
from app.models import BotVersion, EvalRun, TestSuite

BOTS = sys.argv[1:] or ["v1-gptoss120b", "v1-gptoss20b"]   # e.g. python -m scripts.run_all v1-gptoss20b
JUDGE_CANDIDATES = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
ENV_FILE = Path(__file__).parent.parent / ".env"


def pick_judge() -> str:
    tried = []
    for model in dict.fromkeys([settings.judge_model, *JUDGE_CANDIDATES]):
        for _ in range(2):
            try:
                r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                               params={"key": settings.gemini_api_key},
                               json={"contents": [{"parts": [{"text": "Reply with the word ok"}]}]}, timeout=60)
                code = r.status_code
            except httpx.HTTPError as e:
                code = type(e).__name__
            if code == 200:
                return model
            if code not in (429, 503):
                break
            time.sleep(5)
        tried.append(f"{model}: {code}")
    sys.exit("No Gemini model available right now:\n  " + "\n  ".join(tried) + "\nTry again in a few minutes.")


def save_judge_to_env(model: str):
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    line = f"JUDGE_MODEL={model}"
    text = re.sub(r"(?m)^JUDGE_MODEL=.*$", line, text) if "JUDGE_MODEL=" in text else text.rstrip("\n") + f"\n{line}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


async def run_one(bot_name: str, suite_id: int) -> dict | None:
    async with SessionLocal() as s:
        bot = await s.scalar(select(BotVersion).where(BotVersion.name == bot_name))
        if not bot:
            print(f"  skipped: no bot named {bot_name}")
            return None
        run = EvalRun(suite_id=suite_id, bot_version_id=bot.id, judge_model=settings.judge_model)
        s.add(run)
        await s.commit()
        run_id = run.id
    print(f"\nRun {run_id}: {bot_name}")
    task = asyncio.create_task(execute_run(run_id))
    last = -1
    while not task.done():
        await asyncio.sleep(10)
        async with SessionLocal() as s:
            r = await s.get(EvalRun, run_id)
            if r.completed != last:
                print(f"  {r.completed}/{r.total} cases done")
                last = r.completed
    await task
    print("  re-judging any cases where the judge errored…")
    left = await rejudge_errors(run_id)
    if left:
        print(f"  {left} judge errors remain: later, run  python -m scripts.rejudge {run_id}")
    async with SessionLocal() as s:
        r = await s.get(EvalRun, run_id)
        return {"id": run_id, "status": r.status, "error": r.error, **(r.summary or {})}


async def main():
    if settings.judge_provider == "gemini":
        print("Checking which Gemini judge model works…")
        model = pick_judge()
        settings.judge_model = model
        save_judge_to_env(model)
    print(f"  judge: {settings.judge_provider}:{settings.judge_model}")

    await seed_suite()
    async with SessionLocal() as s:
        # clear any run left 'running' by an earlier crash, so it doesn't look stuck on the site
        await s.execute(update(EvalRun).where(EvalRun.status.in_(["queued", "running"]))
                        .values(status="failed", error="superseded by scripts.run_all"))
        await s.commit()
        suite_id = await s.scalar(select(TestSuite.id).order_by(TestSuite.id))

    results = [r for b in BOTS if (r := await run_one(b, suite_id))]

    def f(v, unit="%"):
        return "n/a" if v is None else f"{v}{unit}"

    print("\n" + "=" * 60)
    for r in results:
        print(f"Run {r['id']}  {r['status']}")
        if r.get("error"):
            print(f"  note: {r['error'][:200]}")
        print(f"  passed: {f(r.get('pass_rate'))}   behaved as expected: {f(r.get('status_accuracy'))}")
        print(f"  made-up facts: {f(r.get('hallucination_rate'))}   grounded: {f(r.get('avg_grounded'), '/5')}   cited: {f(r.get('citation_validity'))}")
        print(f"  needs human review: {r.get('needs_review')}")
    print("=" * 60)
    print("Done. Results are live on the website.")


if __name__ == "__main__":
    asyncio.run(main())

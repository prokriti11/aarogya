"""Re-run the judge on a run. Bot answers are kept.
Usage (from backend/):
  python -m scripts.rejudge 6         only cases where the judge errored
  python -m scripts.rejudge 6 --all   every case (use after switching judge model)"""
import asyncio
import sys

from app.config import settings
from app.evals import rejudge_errors


async def main(run_id: int, everything: bool):
    what = "all cases" if everything else "errored cases"
    print(f"Re-judging {what} in run {run_id} with {settings.judge_provider}:{settings.judge_model}…")
    left = await rejudge_errors(run_id, everything)
    print("All judge errors fixed." if left == 0 else f"{left} judge errors remain; run this again in a few minutes.")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]), "--all" in sys.argv))

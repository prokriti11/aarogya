"""Print run summaries side by side.  Usage (from backend/):  python -m scripts.summary 6 8"""
import asyncio
import json
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import BotVersion, EvalRun


async def main(ids):
    async with SessionLocal() as s:
        for rid in ids:
            run = await s.get(EvalRun, rid)
            bot = await s.scalar(select(BotVersion).where(BotVersion.id == run.bot_version_id))
            print(f"=== Run {rid}  {bot.name} ({bot.model})  judge={run.judge_model}  status={run.status}")
            print(json.dumps(run.summary, indent=1))


if __name__ == "__main__":
    asyncio.run(main([int(a) for a in sys.argv[1:]]))

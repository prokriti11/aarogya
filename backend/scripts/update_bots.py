"""One-off: move the database from retired Groq Llama models to gpt-oss.
Usage (from backend/):  python -m scripts.update_bots
Safe to run more than once. Old rows are renamed 'retired-*' (not deleted) so past conversations keep their history.
"""
import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models import BotVersion
from app.prompts import SEED_BOTS

MOVES = {"v1-llama70b": "v1-gptoss120b", "v1-llama8b": "v1-gptoss20b"}


async def main():
    seeds = {b["name"]: b for b in SEED_BOTS}
    async with SessionLocal() as s:
        for old, new in MOVES.items():
            old_row = await s.scalar(select(BotVersion).where(BotVersion.name == old))
            new_row = await s.scalar(select(BotVersion).where(BotVersion.name == new))
            if old_row and new_row:
                old_row.name = f"retired-{old}"
                print(f"{new} already exists; renamed {old} -> retired-{old}")
            elif old_row:
                old_row.name, old_row.model = new, seeds[new]["model"]
                print(f"{old} -> {new} ({seeds[new]['model']})")
            elif not new_row:
                s.add(BotVersion(**seeds[new]))
                print(f"created {new}")
            else:
                print(f"{new} already set up")
        await s.commit()
        for b in (await s.scalars(select(BotVersion).order_by(BotVersion.id))).all():
            print(f"  {b.name:24} {b.model}")


if __name__ == "__main__":
    asyncio.run(main())

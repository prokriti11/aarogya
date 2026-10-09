"""Bulk-ingest every PDF in a folder straight into the DB.
Usage (from backend/):  python -m scripts.ingest_folder data/policies
"""
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

from app.db import Base, SessionLocal, engine
from app.ingest import ingest_pdf


async def main(folder: str):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    pdfs = sorted(Path(folder).glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs in {folder}")
    for pdf in pdfs:
        async with SessionLocal() as s:
            res = await ingest_pdf(s, pdf.read_bytes(), pdf.name)
            print(f"{pdf.name}: {res}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "data/policies"))

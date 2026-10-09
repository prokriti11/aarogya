import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import Base, SessionLocal, engine, get_session
from .deps import require_admin
from .embeddings import _model
from .eval_api import router as eval_router
from .evals import fail_interrupted_runs, seed_suite
from .ingest import ingest_pdf
from .models import BotVersion, Chunk, Document
from .prompts import SEED_BOTS
from .rag import run_turn


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        for b in SEED_BOTS:
            if not await s.scalar(select(BotVersion).where(BotVersion.name == b["name"])):
                s.add(BotVersion(**b))
        await s.commit()
    await seed_suite()
    await fail_interrupted_runs()
    _model()  # warm the embedding model so the first chat isn't slow
    yield


app = FastAPI(title="Aarogya Support Bot + Eval Harness", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])

# --- simple per-IP sliding-window limiter (protects free-tier LLM quota) ---
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    now, q = time.time(), _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.chat_rate_limit_per_min:
        raise HTTPException(429, "Too many requests, slow down a little.")
    q.append(now)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    bot: str = "v1-gptoss120b"
    conversation_id: uuid.UUID | None = None


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    docs = await session.scalar(select(func.count(Document.id)))
    chunks = await session.scalar(select(func.count(Chunk.id)))
    return {"ok": True, "documents": docs, "chunks": chunks}


@app.get("/bots")
async def list_bots(session: AsyncSession = Depends(get_session)):
    bots = (await session.scalars(select(BotVersion).where(~BotVersion.name.startswith("retired-"))
                                  .order_by(BotVersion.id))).all()
    return [{"name": b.name, "model": b.model, "top_k": b.top_k, "min_similarity": b.min_similarity} for b in bots]


@app.get("/documents")
async def list_documents(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(Document.id, Document.title, Document.num_pages, func.count(Chunk.id))
        .join(Chunk, isouter=True).group_by(Document.id).order_by(Document.created_at)
    )).all()
    return [{"id": str(r[0]), "title": r[1], "pages": r[2], "chunks": r[3]} for r in rows]


@app.post("/chat", dependencies=[Depends(rate_limit)])
async def chat(body: ChatIn, session: AsyncSession = Depends(get_session)):
    bot = await session.scalar(select(BotVersion).where(BotVersion.name == body.bot))
    if not bot:
        raise HTTPException(404, f"unknown bot '{body.bot}'")
    return await run_turn(session, bot, body.message.strip(), body.conversation_id)


@app.post("/admin/ingest", dependencies=[Depends(require_admin)])
async def admin_ingest(file: UploadFile = File(...), title: str | None = Form(None),
                       session: AsyncSession = Depends(get_session)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "PDF only")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "max 15 MB")
    try:
        return await ingest_pdf(session, data, file.filename, title)
    except ValueError as e:
        raise HTTPException(422, str(e))

app.include_router(eval_router)

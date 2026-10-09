"""One bot turn: retrieve -> confidence gate -> generate -> validate citations -> persist full trace."""
import re
import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .llm import LLMError, chat_json
from .models import BotVersion, Conversation, Message
from .prompts import build_user_turn
from .retrieval import retrieve

HISTORY_TURNS = 6
FALLBACK = "Sorry, I'm having trouble answering right now. Please try again in a moment."


class BotOutput(BaseModel):
    status: Literal["answered", "not_found", "out_of_scope", "clarify"]
    answer: str = Field(min_length=1)
    citations: list[int] = []


async def _history(session: AsyncSession, conversation_id: uuid.UUID) -> list[dict]:
    rows = (await session.scalars(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc()).limit(HISTORY_TURNS)
    )).all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


async def run_turn(session: AsyncSession, bot: BotVersion, user_text: str,
                   conversation_id: uuid.UUID | None = None, channel: str = "web") -> dict:
    t0 = time.perf_counter()
    if conversation_id is None:
        conv = Conversation(bot_version_id=bot.id, channel=channel)
        session.add(conv); await session.flush()
        conversation_id = conv.id
    history = await _history(session, conversation_id)

    # 1. Retrieve + gate: below threshold the model sees NO context, so it cannot hallucinate from noise
    hits, top_sim = await retrieve(session, user_text, bot.top_k)
    retrieval_ms = int((time.perf_counter() - t0) * 1000)
    gated = top_sim < bot.min_similarity
    used = [] if gated else hits
    blocks = [f"[{i}] ({h.title}, {h.section or 'General'}, p.{h.page_start})\n{h.content}" for i, h in enumerate(used, 1)]

    # 2. Generate
    messages = [{"role": "system", "content": bot.system_prompt}, *history,
                {"role": "user", "content": build_user_turn(user_text, blocks)}]
    trace = {"retrieval_ms": retrieval_ms, "top_similarity": round(top_sim, 4), "gated": gated, "model": bot.model,
             "context_chunk_ids": [h.chunk_id for h in used]}
    try:
        raw, usage, llm_ms = await chat_json(bot.model, messages, bot.temperature)
        out = BotOutput.model_validate(raw)
        trace.update(llm_ms=llm_ms, prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"))
    except (LLMError, ValidationError) as e:
        out = BotOutput(status="answered", answer=FALLBACK, citations=[])
        trace.update(error=str(e)[:300])

    # 3. Validate citations: model-cited numbers must exist in what we actually passed
    inline = {int(n) for n in re.findall(r"\[(\d+)\]", out.answer)}
    cited_nums = sorted(set(out.citations) | inline)
    valid = [n for n in cited_nums if 1 <= n <= len(used)]
    trace["invalid_citations"] = [n for n in cited_nums if n not in valid]
    trace["uncited_answer"] = out.status == "answered" and not valid and "error" not in trace
    trace["total_ms"] = int((time.perf_counter() - t0) * 1000)
    status = "error" if "error" in trace else out.status

    # 4. Persist both sides of the turn
    session.add(Message(conversation_id=conversation_id, role="user", content=user_text))
    session.add(Message(
        conversation_id=conversation_id, role="assistant", content=out.answer, status=status,
        retrieved=[{"chunk_id": h.chunk_id, "rank": i, "similarity": h.similarity, "rrf": round(h.rrf, 5)}
                   for i, h in enumerate(hits, 1)],
        cited_chunk_ids=[used[n - 1].chunk_id for n in valid], trace=trace,
    ))
    await session.commit()

    return {
        "conversation_id": str(conversation_id),
        "context": [{"n": i, "chunk_id": h.chunk_id, "title": h.title, "section": h.section, "content": h.content}
                    for i, h in enumerate(used, 1)],
        "status": status,
        "answer": out.answer,
        "citations": [{"n": n, "title": used[n - 1].title, "section": used[n - 1].section,
                       "pages": [used[n - 1].page_start, used[n - 1].page_end],
                       "snippet": used[n - 1].content[:280]} for n in valid],
        "trace": trace,
    }

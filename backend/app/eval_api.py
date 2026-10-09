import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import settings
from .db import get_session
from .deps import require_admin
from .evals import compare_runs, compute_summary, execute_run, judge_agreement
from .models import BotVersion, EvalResult, EvalRun, HumanLabel, TestCase, TestSuite

router = APIRouter()
_tasks: set[asyncio.Task] = set()   # keep strong refs so background runs aren't GC'd


def _run_dict(r: EvalRun) -> dict:
    return {"id": r.id, "suite": r.suite.name, "bot": r.bot.name, "model": r.bot.model, "judge_model": r.judge_model,
            "status": r.status, "total": r.total, "completed": r.completed, "summary": r.summary, "error": r.error,
            "created_at": r.created_at, "finished_at": r.finished_at}


def _result_dict(r: EvalResult) -> dict:
    return {"id": r.id, "run_id": r.run_id, "case_key": r.case.case_key, "category": r.case.category, "question": r.case.question,
            "expected_statuses": r.case.expected_statuses, "expected_behavior": r.case.expected_behavior,
            "status": r.status, "answer": r.answer, "context": r.context, "trace": r.trace, "checks": r.checks,
            "judge": r.judge, "passed": r.passed, "needs_review": r.needs_review, "review_reasons": r.review_reasons,
            "label": ({"passed": r.label.passed, "hallucination": r.label.hallucination, "note": r.label.note}
                      if r.label else None)}


RUN_OPTS = [selectinload(EvalRun.bot), selectinload(EvalRun.suite)]
RESULT_OPTS = [selectinload(EvalResult.case), selectinload(EvalResult.label)]


@router.get("/suites")
async def suites(s: AsyncSession = Depends(get_session)):
    rows = (await s.scalars(select(TestSuite).options(selectinload(TestSuite.cases)))).all()
    return [{"id": x.id, "name": x.name, "description": x.description, "cases": len(x.cases)} for x in rows]


@router.get("/suites/{suite_id}/cases")
async def suite_cases(suite_id: int, s: AsyncSession = Depends(get_session)):
    rows = (await s.scalars(select(TestCase).where(TestCase.suite_id == suite_id).order_by(TestCase.id))).all()
    return [{"case_key": c.case_key, "category": c.category, "question": c.question,
             "expected_statuses": c.expected_statuses, "expected_behavior": c.expected_behavior} for c in rows]


@router.get("/runs")
async def runs(s: AsyncSession = Depends(get_session)):
    rows = (await s.scalars(select(EvalRun).options(*RUN_OPTS).order_by(EvalRun.id.desc()).limit(50))).all()
    return [_run_dict(r) for r in rows]


@router.get("/runs/{run_id}")
async def run_detail(run_id: int, s: AsyncSession = Depends(get_session)):
    r = await s.get(EvalRun, run_id, options=RUN_OPTS)
    if not r:
        raise HTTPException(404, "run not found")
    d = _run_dict(r)
    if r.status == "running":            # live partial metrics while it runs
        d["summary"] = await compute_summary(s, run_id)
    return d


@router.get("/runs/{run_id}/results")
async def run_results(run_id: int, s: AsyncSession = Depends(get_session)):
    rows = (await s.scalars(select(EvalResult).where(EvalResult.run_id == run_id)
                            .options(*RESULT_OPTS).order_by(EvalResult.case_id))).all()
    return [_result_dict(r) for r in rows]


@router.get("/compare")
async def compare(a: int, b: int, s: AsyncSession = Depends(get_session)):
    return await compare_runs(s, a, b)


@router.get("/review/queue")
async def review_queue(run_id: int | None = None, s: AsyncSession = Depends(get_session)):
    q = select(EvalResult).where(EvalResult.needs_review.is_(True)).options(*RESULT_OPTS).order_by(EvalResult.id.desc())
    if run_id:
        q = q.where(EvalResult.run_id == run_id)
    return [_result_dict(r) for r in (await s.scalars(q.limit(200))).all()]


@router.get("/metrics/judge-agreement")
async def agreement(s: AsyncSession = Depends(get_session)):
    return await judge_agreement(s)


# ----------------------------- admin -----------------------------

class RunIn(BaseModel):
    suite_id: int
    bot: str


@router.post("/admin/runs", dependencies=[Depends(require_admin)])
async def start_run(body: RunIn, s: AsyncSession = Depends(get_session)):
    bot = await s.scalar(select(BotVersion).where(BotVersion.name == body.bot))
    if not bot or not await s.get(TestSuite, body.suite_id):
        raise HTTPException(404, "unknown bot or suite")
    if await s.scalar(select(EvalRun).where(EvalRun.status.in_(["queued", "running"]))):
        raise HTTPException(409, "a run is already in progress (free-tier rate limits)")
    run = EvalRun(suite_id=body.suite_id, bot_version_id=bot.id, judge_model=settings.judge_model)
    s.add(run)
    await s.commit()
    task = asyncio.create_task(execute_run(run.id))
    _tasks.add(task); task.add_done_callback(_tasks.discard)
    return {"run_id": run.id}


class LabelIn(BaseModel):
    passed: bool
    hallucination: bool = False
    note: str = ""


@router.post("/admin/results/{result_id}/label", dependencies=[Depends(require_admin)])
async def label(result_id: int, body: LabelIn, s: AsyncSession = Depends(get_session)):
    r = await s.get(EvalResult, result_id, options=[selectinload(EvalResult.label)])
    if not r:
        raise HTTPException(404, "result not found")
    if r.label:
        r.label.passed, r.label.hallucination, r.label.note = body.passed, body.hallucination, body.note
    else:
        s.add(HumanLabel(result_id=result_id, **body.model_dump()))
    await s.commit()
    return {"ok": True}


@router.get("/admin/check", dependencies=[Depends(require_admin)])
async def admin_check():
    return {"ok": True}

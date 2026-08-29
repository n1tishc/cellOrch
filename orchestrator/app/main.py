"""FastAPI app: REST API + the background worker that ticks the engine.

Endpoints:
  POST /runs                 start a new cell line
  GET  /runs                 list runs (dashboard polls this)
  GET  /runs/{id}            run detail: steps + audit events
  POST /runs/{id}/inject-fault   force the next step to fail (demo button)
  POST /seed?n=10            spawn N runs
  GET  /healthz /readyz      health probes
  GET  /metrics              simple counters
"""
import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import select

from . import engine, protocol
from .config import settings
from .db import get_session, init_db
from .logging_config import configure_logging, get_logger, request_id_var
from .models import (
    CANCELLED, COMPLETED, FAILED, PAUSED, PENDING, RUNNING, WAITING,
    Event, Run, StepExecution, utcnow,
)
from .seed import seed_runs

logger = get_logger(__name__)

TICK_INTERVAL = settings.tick_interval
SEED_ON_START = settings.seed_on_start


class CreateRunRequest(BaseModel):
    name: str | None = Field(
        default=None,
        max_length=100,
        pattern=r'^[a-zA-Z0-9\-_ ]+$',
    )


class SeedRequest(BaseModel):
    n: int = Field(default=10, ge=1, le=100)


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str | None = None


async def worker_loop():
    while True:
        try:
            with get_session() as s:
                engine.tick(s)
        except (ConnectionError, TimeoutError) as e:
            logger.warning(
                "transient_error",
                extra={"error": str(e), "event_type": "worker_error"},
            )
        except ValueError as e:
            logger.error(
                "data_integrity_error",
                extra={"error": str(e), "event_type": "worker_error"},
                exc_info=True,
            )
            raise
        await asyncio.sleep(TICK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    if SEED_ON_START:
        with get_session() as s:
            if not s.exec(select(Run)).first():
                seed_runs(s, SEED_ON_START)
    task = asyncio.create_task(worker_loop())
    yield
    task.cancel()


app = FastAPI(title="CellFlow Orchestrator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Attach a request id and convert unhandled exceptions to ErrorResponse."""
    request_id = str(uuid4())
    request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except HTTPException as exc:
        response = await http_exception_handler(request, exc)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        logger.exception(
            "unhandled_exception",
            extra={
                "path": request.url.path,
                "event_type": "api_error",
                "request_id": request_id,
            },
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="An unexpected error occurred",
                request_id=request_id,
            ).model_dump(),
        )


@app.post("/runs")
def create_run(req: CreateRunRequest = Depends()):
    with get_session() as s:
        n = s.exec(select(Run)).all()
        run = Run(name=req.name or f"Line-{len(n)+1:02d}")
        s.add(run)
        s.commit()
        s.refresh(run)
        return run


@app.get("/runs")
def list_runs():
    with get_session() as s:
        runs = s.exec(select(Run).order_by(Run.id)).all()
        stage_names = [st.name for st in protocol.DEFAULT_PROTOCOL]
        return [
            {**r.model_dump(), "stage_name": stage_names[r.current_stage]}
            for r in runs
        ]


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    with get_session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        steps = s.exec(
            select(StepExecution).where(StepExecution.run_id == run_id).order_by(StepExecution.id)
        ).all()
        events = s.exec(
            select(Event).where(Event.run_id == run_id).order_by(Event.id.desc())
        ).all()
        return {"run": run, "steps": steps, "events": events}


@app.post("/runs/{run_id}/pause")
def pause_run(run_id: int):
    with get_session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        if run.status not in (PENDING, WAITING, RUNNING):
            raise HTTPException(400, "only active runs can be paused")
        now = utcnow()
        engine.release_held_resource(s, run_id, "paused by operator", now)
        run.status = PAUSED
        run.updated_at = now
        engine.log(s, run_id, "paused", "Paused by operator")
        s.commit()
        return run


@app.post("/runs/{run_id}/resume")
def resume_run(run_id: int):
    with get_session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        if run.status != PAUSED:
            raise HTTPException(400, "only paused runs can be resumed")
        run.status = PENDING
        run.updated_at = utcnow()
        engine.log(s, run_id, "resumed", "Resumed by operator")
        s.commit()
        return run


@app.post("/runs/{run_id}/cancel")
def cancel_run(run_id: int):
    with get_session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        if run.status in (COMPLETED, FAILED, CANCELLED):
            raise HTTPException(400, "terminal runs cannot be cancelled")
        now = utcnow()
        engine.release_held_resource(s, run_id, "cancelled by operator", now)
        run.status = CANCELLED
        run.updated_at = now
        engine.log(s, run_id, "cancelled", "Cancelled by operator")
        s.commit()
        return run


@app.post("/runs/{run_id}/inject-fault")
def inject_fault(run_id: int):
    with get_session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        run.force_fail_next = True
        s.add(run)
        s.commit()
        return {"ok": True, "run_id": run_id}


@app.post("/seed")
def seed(req: SeedRequest = Depends()):
    with get_session() as s:
        created = seed_runs(s, req.n)
        return {"created": created}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    with get_session() as s:
        s.exec(select(Run).limit(1)).all()
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    with get_session() as s:
        runs = s.exec(select(Run)).all()
        events = s.exec(select(Event)).all()
        retries = sum(1 for e in events if e.type == "retry")
        return {
            "runs_total": len(runs),
            "runs_completed": sum(r.status == COMPLETED for r in runs),
            "runs_failed": sum(r.status == FAILED for r in runs),
            "runs_active": sum(r.status not in (COMPLETED, FAILED) for r in runs),
            "retries_total": retries,
            "audit_events_total": len(events),
        }

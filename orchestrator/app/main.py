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
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import select

from . import engine, protocol
from .db import get_session, init_db
from .models import COMPLETED, FAILED, Event, Run, StepExecution
from .seed import seed_runs

TICK_INTERVAL = float(os.environ.get("TICK_INTERVAL", "1.0"))
SEED_ON_START = int(os.environ.get("SEED_ON_START", "10"))


async def worker_loop():
    while True:
        try:
            with get_session() as s:
                engine.tick(s)
        except Exception as e:  # keep the worker alive
            print(f"[worker] tick error: {e}")
        await asyncio.sleep(TICK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.post("/runs")
def create_run(name: str | None = None):
    with get_session() as s:
        n = s.exec(select(Run)).all()
        run = Run(name=name or f"Line-{len(n)+1:02d}")
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
def seed(n: int = 10):
    with get_session() as s:
        created = seed_runs(s, n)
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

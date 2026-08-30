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
import csv
import io
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

import httpx
from sqlalchemy import String, cast, func
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import select

from . import engine, protocol
from .auth import get_current_user
from .config import settings
from .db import get_session, init_db
from .logging_config import configure_logging, get_logger, request_id_var
from .run_events import subscribe, unsubscribe
from .webhooks import dispatch_webhook
from .models import (
    CANCELLED, COMPLETED, FAILED, PAUSED, PENDING, RUNNING, WAITING,
    Event, Run, RunStatus, StepExecution, Webhook, utcnow,
)
from .seed import seed_runs

logger = get_logger(__name__)

TICK_INTERVAL = settings.tick_interval
SEED_ON_START = settings.seed_on_start
last_worker_tick: datetime | None = None


class CreateRunRequest(BaseModel):
    name: str | None = Field(
        default=None,
        max_length=100,
        pattern=r'^[a-zA-Z0-9\-_ ]+$',
    )


class SeedRequest(BaseModel):
    n: int = Field(default=10, ge=1, le=100)


class WebhookRequest(BaseModel):
    url: str
    events: list[str]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str | None = None


async def worker_loop(stop_event: asyncio.Event):
    global last_worker_tick
    while not stop_event.is_set():
        try:
            with get_session() as s:
                engine.tick(s)
            last_worker_tick = utcnow()
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
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=TICK_INTERVAL)
        except TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global last_worker_tick
    last_worker_tick = None
    configure_logging()
    init_db()
    if SEED_ON_START:
        with get_session() as s:
            if not s.exec(select(Run)).first():
                seed_runs(s, SEED_ON_START)
    stop_event = asyncio.Event()
    task = asyncio.create_task(worker_loop(stop_event))
    yield
    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=5)
    except TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="CellFlow Orchestrator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["*"], allow_headers=["*"],
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
def create_run(req: CreateRunRequest = Depends(), user: dict = Depends(get_current_user)):
    with get_session() as s:
        n = s.exec(select(Run)).all()
        run = Run(name=req.name or f"Line-{len(n)+1:02d}")
        s.add(run)
        s.commit()
        s.refresh(run)
        return run


@app.get("/runs")
def list_runs(
    response: Response,
    status: RunStatus | None = None,
    stage: str | None = None,
    search: str | None = Query(default=None, max_length=100),
    sort: Literal["created_at", "updated_at", "name"] = "created_at",
    direction: Literal["asc", "desc"] = "desc",
):
    with get_session() as s:
        total_runs = s.exec(select(func.count()).select_from(Run)).one()
        statement = select(Run)
        if status is not None:
            statement = statement.where(Run.status == status)
        if stage is not None:
            stage_indexes = {item.name.lower(): index for index, item in enumerate(protocol.DEFAULT_PROTOCOL)}
            if stage.lower() not in stage_indexes:
                raise HTTPException(422, "invalid stage")
            statement = statement.where(Run.current_stage == stage_indexes[stage.lower()])
        if search:
            statement = statement.where(cast(Run.name, String).ilike(f"%{search}%"))
        column = getattr(Run, sort)
        statement = statement.order_by(column.asc() if direction == "asc" else column.desc())
        runs = s.exec(statement).all()
        response.headers["X-Total-Count"] = str(total_runs)
        stage_names = [item.name for item in protocol.DEFAULT_PROTOCOL]
        return [{**run.model_dump(), "stage_name": stage_names[run.current_stage]} for run in runs]


def _download(content: str, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/runs/export")
def export_runs(format: Literal["csv", "json"] = "csv"):
    with get_session() as s:
        runs = s.exec(select(Run).order_by(Run.id)).all()  # type: ignore[arg-type]
        summaries = [
            {"id": run.id, "name": run.name, "status": run.status.value, "current_stage": run.current_stage,
             "passage_count": run.passage_count, "confluence": run.confluence,
             "created_at": run.created_at.isoformat(), "updated_at": run.updated_at.isoformat()}
            for run in runs
        ]
        if format == "json":
            return _download(json.dumps(summaries), "runs.json", "application/json")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "name", "status", "current_stage", "passage_count", "confluence", "created_at", "updated_at"])
        writer.writeheader(); writer.writerows(summaries)
        return _download(output.getvalue(), "runs.csv", "text/csv")


@app.get("/runs/{run_id}/export")
def export_run(run_id: int, format: Literal["csv", "json"] = "csv"):
    with get_session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        steps = s.exec(select(StepExecution).where(StepExecution.run_id == run_id).order_by(StepExecution.id)).all()  # type: ignore[arg-type]
        events = s.exec(select(Event).where(Event.run_id == run_id).order_by(Event.id)).all()  # type: ignore[arg-type]
        payload = {
            "run": run.model_dump(mode="json"),
            "steps": [step.model_dump(mode="json") for step in steps],
            "events": [event.model_dump(mode="json") for event in events],
        }
        if format == "json":
            return _download(json.dumps(payload), f"run_{run_id}.json", "application/json")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["record_type", "id", "stage", "status", "attempt", "type", "message", "started_at", "finish_at", "error", "created_at"])
        writer.writeheader()
        writer.writerow({"record_type": "run", "id": run.id, "status": run.status.value, "created_at": run.created_at.isoformat()})
        for step in steps:
            writer.writerow({"record_type": "step", "id": step.id, "stage": step.stage_name, "status": step.status.value, "attempt": step.attempt, "started_at": step.started_at.isoformat(), "finish_at": step.finish_at.isoformat() if step.finish_at else "", "error": step.error or ""})
        for event in events:
            writer.writerow({"record_type": "event", "id": event.id, "type": event.type, "message": event.message, "created_at": event.created_at.isoformat()})
        return _download(output.getvalue(), f"run_{run_id}.csv", "text/csv")


@app.get("/runs/stream")
async def stream_runs():
    async def events():
        queue = subscribe()
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            unsubscribe(queue)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/runs/import")
async def import_runs(request: Request, user: dict = Depends(get_current_user)):
    """Import up to 100 new cell-line runs from a UTF-8 CSV with a name column."""
    raw_csv = await request.body()
    if len(raw_csv) > 1_000_000:
        raise HTTPException(413, "CSV must be smaller than 1 MB")
    try:
        reader = csv.DictReader(io.StringIO(raw_csv.decode("utf-8-sig")))
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "CSV must be UTF-8 encoded") from exc
    if not reader.fieldnames or "name" not in reader.fieldnames:
        raise HTTPException(422, "CSV must contain a name column")

    requests: list[CreateRunRequest] = []
    for line_number, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            raise HTTPException(422, f"row {line_number}: name is required")
        try:
            requests.append(CreateRunRequest(name=name))
        except ValidationError as exc:
            raise HTTPException(422, f"row {line_number}: invalid name") from exc
    if not requests:
        raise HTTPException(422, "CSV must contain at least one run")
    if len(requests) > 100:
        raise HTTPException(422, "CSV may contain at most 100 runs")

    with get_session() as s:
        s.add_all([Run(name=item.name) for item in requests])
        s.commit()
    return {"created": len(requests)}


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    with get_session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        steps = s.exec(
            select(StepExecution).where(StepExecution.run_id == run_id).order_by(StepExecution.id)  # type: ignore[arg-type]
        ).all()
        events = s.exec(
            select(Event).where(Event.run_id == run_id).order_by(Event.id.desc())  # type: ignore[union-attr]
        ).all()
        return {
            "run": {**run.model_dump(), "stage_name": protocol.DEFAULT_PROTOCOL[run.current_stage].name},
            "steps": steps,
            "events": events,
        }


@app.post("/runs/{run_id}/pause")
def pause_run(run_id: int, user: dict = Depends(get_current_user)):
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
def resume_run(run_id: int, user: dict = Depends(get_current_user)):
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
def cancel_run(run_id: int, user: dict = Depends(get_current_user)):
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
def inject_fault(run_id: int, user: dict = Depends(get_current_user)):
    with get_session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "run not found")
        run.force_fail_next = True
        s.add(run)
        s.commit()
        return {"ok": True, "run_id": run_id}


@app.post("/webhooks")
def create_webhook(request: WebhookRequest, user: dict = Depends(get_current_user)):
    with get_session() as s:
        hook = Webhook(url=request.url, events=json.dumps(request.events))
        s.add(hook); s.commit(); s.refresh(hook)
        return hook


@app.get("/webhooks")
def list_webhooks():
    with get_session() as s:
        return s.exec(select(Webhook)).all()


@app.post("/webhooks/{webhook_id}/test")
def test_webhook(webhook_id: int, user: dict = Depends(get_current_user)):
    with get_session() as s:
        hook = s.get(Webhook, webhook_id)
        if not hook:
            raise HTTPException(404, "webhook not found")
        dispatch_webhook(hook.url, {"event_type": "webhook.test", "run_id": None, "message": "Webhook test event", "timestamp": utcnow().isoformat()})
        return {"ok": True, "webhook_id": webhook_id}


@app.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: int, user: dict = Depends(get_current_user)):
    with get_session() as s:
        hook = s.get(Webhook, webhook_id)
        if not hook: raise HTTPException(404, "webhook not found")
        s.delete(hook); s.commit()
        return {"ok": True}


@app.post("/seed")
def seed(req: SeedRequest = Depends(), user: dict = Depends(get_current_user)):
    with get_session() as s:
        created = seed_runs(s, req.n)
        return {"created": created}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    checks: dict[str, str] = {}
    try:
        with get_session() as s:
            s.exec(select(Run).limit(1)).all()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        response = httpx.get(f"{settings.cv_service_url}/healthz", timeout=2.0)
        checks["cv_service"] = "ok" if response.is_success else "degraded"
    except httpx.HTTPError:
        checks["cv_service"] = "unreachable"
    if last_worker_tick is None or (utcnow() - last_worker_tick).total_seconds() > settings.worker_stall_seconds:
        checks["worker"] = "stalled"
    else:
        checks["worker"] = "ok"
    status = "ready" if all(value == "ok" for value in checks.values()) else "unhealthy" if checks["database"] == "error" else "degraded"
    return {"status": status, "checks": checks}


@app.get("/deep-healthz")
def deep_healthz():
    """Liveness check: worker and database must be healthy; CV is readiness-only."""
    readiness = readyz()
    status = "ok" if readiness["checks"]["database"] == "ok" and readiness["checks"]["worker"] == "ok" else "unhealthy"
    return {"status": status, "checks": readiness["checks"]}


@app.get("/resources")
def resources():
    with get_session() as s:
        usage = engine._resource_usage(s)
        return {
            "resources": {
                name: {"used": usage[name], "capacity": capacity}
                for name, capacity in protocol.RESOURCE_CAPACITY.items()
            },
            "queue_depth": len(s.exec(select(Run).where(Run.status == WAITING)).all()),
        }


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


@app.get("/analytics")
def analytics():
    """Return operational analytics calculated only from persisted SQLite records."""
    with get_session() as s:
        runs = s.exec(select(Run)).all()
        events = s.exec(select(Event)).all()
        steps = s.exec(select(StepExecution)).all()
    status_counts = {status.value: 0 for status in RunStatus}
    for run in runs:
        status_counts[run.status.value] += 1
    stage_counts = {stage.name: 0 for stage in protocol.DEFAULT_PROTOCOL}
    active_stage_counts = {stage.name: 0 for stage in protocol.DEFAULT_PROTOCOL}
    stage_state_counts = {
        stage.name: {"active": 0, "running": 0, "waiting": 0, "paused": 0}
        for stage in protocol.DEFAULT_PROTOCOL
    }
    for run in runs:
        stage_name = protocol.DEFAULT_PROTOCOL[run.current_stage].name
        stage_counts[stage_name] += 1
        if run.status in (PENDING, WAITING, RUNNING, PAUSED):
            active_stage_counts[stage_name] += 1
            stage_state_counts[stage_name]["active"] += 1
        if run.status == RUNNING:
            stage_state_counts[stage_name]["running"] += 1
        elif run.status == WAITING:
            stage_state_counts[stage_name]["waiting"] += 1
        elif run.status == PAUSED:
            stage_state_counts[stage_name]["paused"] += 1
    event_counts: dict[str, int] = {}
    for event in events:
        event_counts[event.type] = event_counts.get(event.type, 0) + 1
    now = utcnow()
    active_runs = [run for run in runs if run.status in (PENDING, WAITING, RUNNING, PAUSED)]
    terminal_runs = [run for run in runs if run.status in (COMPLETED, FAILED, CANCELLED)]
    completed_steps = [step for step in steps if step.finish_at is not None]
    elapsed_minutes = [
        max(0, (step.finish_at - step.started_at).total_seconds() / 60)
        for step in completed_steps
        if step.finish_at is not None
    ]
    event_days: dict[str, int] = {}
    for event in events:
        if event.created_at >= now - timedelta(days=7):
            label = event.created_at.date().isoformat()
            event_days[label] = event_days.get(label, 0) + 1
    run_names = {run.id: run.name for run in runs}
    latest_events = sorted(events, key=lambda event: event.created_at, reverse=True)[:8]
    return {
        "statuses": [{"label": label, "value": value} for label, value in status_counts.items() if value],
        "stages": [{"label": label, "value": value} for label, value in stage_counts.items() if value],
        "events": [{"label": label, "value": event_counts[label]} for label in sorted(event_counts)],
        "active_stages": [
            {"label": label, "value": value}
            for label, value in active_stage_counts.items()
            if value
        ],
        "stage_states": [
            {"label": label, **values}
            for label, values in stage_state_counts.items()
        ],
        "activity": [
            {"label": label, "value": event_days[label]}
            for label in sorted(event_days)
        ],
        "summary": {
            "active_runs": len(active_runs),
            "completion_rate": round(
                100 * sum(run.status == COMPLETED for run in terminal_runs) / len(terminal_runs)
            ) if terminal_runs else None,
            "average_confluence": round(
                100 * sum(run.confluence for run in active_runs) / len(active_runs)
            ) if active_runs else None,
            "average_active_age_minutes": round(
                sum((now - run.created_at).total_seconds() / 60 for run in active_runs) / len(active_runs)
            ) if active_runs else None,
            "average_step_duration_minutes": round(sum(elapsed_minutes) / len(elapsed_minutes), 1) if elapsed_minutes else None,
            "events_last_24h": sum(event.created_at >= now - timedelta(hours=24) for event in events),
        },
        "recent_events": [
            {
                "id": event.id,
                "run_id": event.run_id,
                "run_name": run_names.get(event.run_id, "Unknown run"),
                "type": event.type,
                "message": event.message,
                "created_at": event.created_at.isoformat(),
            }
            for event in latest_events
        ],
    }

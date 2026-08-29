"""The orchestration engine.

engine.tick(session, now) advances every active run by at most one transition.
It is deliberately pure-ish: it takes the current time as an argument so tests
can drive simulated time without sleeping, and the web layer just calls it on a
timer with real time.

Responsibilities:
  - start a run's next stage when a required resource is free (else WAITING)
  - finish a running step when its finish_at is reached
  - inject/handle failures with bounded retries + backoff
  - call the CV service at the IMAGE stage and let confluence drive DECISION
  - write an Event row for every meaningful transition (the audit log)
"""
import json
import random
from datetime import datetime, timedelta
from typing import Sequence

from sqlmodel import Session, select

from . import cv_client, protocol
from .config import settings
from .run_events import publish
from .webhooks import fire_webhooks
from .models import (
    ACTIVE_STATUSES, COMPLETED, FAILED, PENDING, RUNNING, WAITING,
    Event, Run, StepExecution, StepStatus, utcnow,
)

CLOCK_FACTOR = settings.clock_factor  # sim seconds run this much faster
FAILURE_RATE = settings.failure_rate  # random step failure chance
MAX_RETRIES = settings.max_retries
BACKOFF_S = settings.backoff_s  # sim seconds before a retry


def log(session: Session, run_id: int, type_: str, message: str) -> None:
    event = Event(run_id=run_id, type=type_, message=message)
    session.add(event)
    webhook_event_type = f"run.{type_}" if type_ in {"failed", "completed"} else type_
    payload = {"event_type": webhook_event_type, "run_id": run_id, "message": message, "timestamp": event.created_at.isoformat()}
    publish({"run_id": run_id, "type": type_, "message": message, "created_at": event.created_at.isoformat()})
    fire_webhooks(session, webhook_event_type, payload)


def _real_duration(sim_seconds: float) -> timedelta:
    return timedelta(seconds=sim_seconds / CLOCK_FACTOR)


def _resource_usage(session: Session) -> dict[str, int]:
    """Count resources currently held by in-progress steps."""
    usage = {r: 0 for r in protocol.RESOURCE_CAPACITY}
    running = session.exec(select(StepExecution).where(StepExecution.status == StepStatus.RUNNING)).all()
    for step in running:
        stage = protocol.DEFAULT_PROTOCOL[protocol.STAGE_INDEX[step.stage_kind]] \
            if step.stage_kind in protocol.STAGE_INDEX else None
        if stage and stage.resource:
            usage[stage.resource] = usage.get(stage.resource, 0) + 1
    return usage


def _current_running_step(session: Session, run_id: int) -> StepExecution | None:
    return session.exec(
        select(StepExecution)
        .where(StepExecution.run_id == run_id, StepExecution.status == StepStatus.RUNNING)
        .order_by(StepExecution.id.desc())  # type: ignore[union-attr]
    ).first()


def release_held_resource(session: Session, run_id: int, reason: str, now: datetime) -> None:
    """End an in-progress step so its resource is available to other runs."""
    step = _current_running_step(session, run_id)
    if step is not None:
        step.status = StepStatus.CANCELLED
        step.error = reason
        step.finish_at = now


def _start_step(session: Session, run: Run, stage: protocol.Stage, now: datetime, attempt: int = 1):
    assert run.id is not None
    step = StepExecution(
        run_id=run.id, stage_name=stage.name, stage_kind=stage.kind,
        status=StepStatus.RUNNING, attempt=attempt, started_at=now,
        finish_at=now + _real_duration(stage.duration_s),
    )
    session.add(step)
    run.status = RUNNING
    run.updated_at = now
    log(session, run.id, "step_started", f"{stage.name} (attempt {attempt})")
    return step


def _apply_decision(session: Session, run: Run, now: datetime) -> None:
    """Confluence drives the branch: passage (and loop) or keep growing or finish."""
    assert run.id is not None
    if run.confluence >= protocol.CONFLUENCE_THRESHOLD:
        if run.passage_count >= protocol.MAX_PASSAGES:
            run.status = COMPLETED
            log(session, run.id, "completed",
                f"Done after {run.passage_count} passages (confluence {run.confluence})")
            return
        run.current_stage = protocol.STAGE_INDEX[protocol.PASSAGE]
        log(session, run.id, "decision", f"Confluent ({run.confluence}) -> passage")
    else:
        run.current_stage = protocol.STAGE_INDEX[protocol.INCUBATE]
        log(session, run.id, "decision", f"Not yet confluent ({run.confluence}) -> incubate")
    run.status = PENDING


def _advance_after_success(session: Session, run: Run, stage: protocol.Stage, now: datetime) -> None:
    assert run.id is not None
    if stage.kind == protocol.DECISION:
        _apply_decision(session, run, now)
        return
    if stage.kind == protocol.PASSAGE:
        run.passage_count += 1
        run.confluence = 0.0  # split + re-seed: density resets
        run.current_stage = protocol.STAGE_INDEX[protocol.INCUBATE]
        log(session, run.id, "passage", f"Passaged (#{run.passage_count}); back to incubate")
        run.status = PENDING
        return
    # plain linear advance
    run.current_stage += 1
    run.status = PENDING


def _finish_running_steps(session: Session, runs: Sequence[Run], now: datetime) -> None:
    for run in runs:
        if run.status != RUNNING:
            continue
        assert run.id is not None
        step = _current_running_step(session, run.id)
        if step is None or step.finish_at is None or now < step.finish_at:
            continue
        stage = protocol.DEFAULT_PROTOCOL[run.current_stage]

        # Decide success/failure.
        fail = run.force_fail_next or (random.random() < FAILURE_RATE)
        run.force_fail_next = False
        if fail:
            step.status = StepStatus.FAILED
            step.error = "injected/transient failure"
            if step.attempt <= MAX_RETRIES:
                log(session, run.id, "retry", f"{stage.name} failed; retry {step.attempt}/{MAX_RETRIES}")
                retry = StepExecution(
                    run_id=run.id, stage_name=stage.name, stage_kind=stage.kind,
                    status=StepStatus.RUNNING, attempt=step.attempt + 1, started_at=now,
                    finish_at=now + _real_duration(stage.duration_s) + _real_duration(BACKOFF_S),
                )
                session.add(retry)
            else:
                run.status = FAILED
                log(session, run.id, "failed", f"{stage.name} exhausted retries")
            continue

        # Success.
        step.status = StepStatus.SUCCESS
        if stage.kind == protocol.IMAGE:
            run.image_count += 1
            reading = cv_client.analyze(run.id, run.image_count)
            run.confluence = reading["confluence"]
            step.result_json = json.dumps(reading)
            log(session, run.id, "imaged",
                f"confluence={reading['confluence']} count={reading['cell_count']}")
        else:
            log(session, run.id, "step_done", stage.name)
        _advance_after_success(session, run, stage, now)


def _start_pending_steps(session: Session, runs: Sequence[Run], now: datetime) -> None:
    usage = _resource_usage(session)
    for run in runs:
        if run.status not in (PENDING, WAITING):
            continue
        assert run.id is not None
        stage = protocol.DEFAULT_PROTOCOL[run.current_stage]
        if stage.resource:
            cap = protocol.RESOURCE_CAPACITY[stage.resource]
            if usage.get(stage.resource, 0) >= cap:
                if run.status != WAITING:
                    run.status = WAITING
                    log(session, run.id, "queued", f"Waiting for {stage.resource}")
                continue
            usage[stage.resource] = usage.get(stage.resource, 0) + 1
        _start_step(session, run, stage, now)


def _active_runs(session: Session) -> Sequence[Run]:
    active = tuple(s.value for s in ACTIVE_STATUSES)
    return session.exec(select(Run).where(Run.status.in_(active))).all()  # type: ignore[attr-defined]


def tick(session: Session, now: datetime | None = None) -> None:
    now = now or utcnow()
    runs = _active_runs(session)
    _finish_running_steps(session, runs, now)   # frees resources first
    session.commit()
    runs = _active_runs(session)
    _start_pending_steps(session, runs, now)
    session.commit()

"""Database models (SQLModel over SQLite).

Three tables:
  - Run            : one cell line moving through the protocol
  - StepExecution  : one attempt at one stage of one run
  - Event          : the audit log — every transition, retry, decision
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    # Naive UTC: SQLite returns naive datetimes, so we stay naive everywhere
    # to keep comparisons consistent.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RunStatus(str, Enum):
    PENDING = "PENDING"      # between stages, ready to start the next one
    WAITING = "WAITING"      # next stage needs a busy resource; queued
    RUNNING = "RUNNING"      # a step is in progress
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StepStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "success"
    FAILED = "failed"


class StageKind(str, Enum):
    SEED = "SEED"
    INCUBATE = "INCUBATE"
    IMAGE = "IMAGE"
    COUNT = "COUNT"
    DECISION = "DECISION"
    PASSAGE = "PASSAGE"


# Backward-compatible aliases used throughout the engine and tests.
PENDING = RunStatus.PENDING
WAITING = RunStatus.WAITING
RUNNING = RunStatus.RUNNING
COMPLETED = RunStatus.COMPLETED
FAILED = RunStatus.FAILED
ACTIVE_STATUSES = (PENDING, WAITING, RUNNING)


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    status: RunStatus = PENDING
    current_stage: int = 0          # index into DEFAULT_PROTOCOL
    passage_count: int = 0
    image_count: int = 0            # how many times imaged (drives rising confluence)
    confluence: float = 0.0         # latest reading
    force_fail_next: bool = False   # set by /inject-fault for the demo
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StepExecution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    stage_name: str
    stage_kind: StageKind
    status: StepStatus = StepStatus.RUNNING
    attempt: int = 1
    started_at: datetime = Field(default_factory=utcnow)
    finish_at: Optional[datetime] = None
    result_json: Optional[str] = None
    error: Optional[str] = None


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    type: str
    message: str
    created_at: datetime = Field(default_factory=utcnow)

"""Defines the lab protocol: the ordered stages a cell line moves through.

A protocol is just an ordered list of Stage definitions. The engine walks a
run through these stages; the DECISION stage decides whether to passage (and
loop back to INCUBATE) or finish.
"""
from dataclasses import dataclass

from .config import settings
from .models import StageKind


# Backward-compatible aliases used throughout the engine.
SEED = StageKind.SEED
INCUBATE = StageKind.INCUBATE
IMAGE = StageKind.IMAGE
COUNT = StageKind.COUNT
DECISION = StageKind.DECISION
PASSAGE = StageKind.PASSAGE


@dataclass(frozen=True)
class Stage:
    name: str
    kind: StageKind
    duration_s: float        # simulated seconds; real wait = duration_s / CLOCK_FACTOR
    resource: str | None = None   # "imager" | "incubator" | None


# One realistic protocol. Order matters; index 0 is the entry point.
DEFAULT_PROTOCOL: list[Stage] = [
    Stage("Seed", SEED, duration_s=2, resource=None),
    Stage("Incubate", INCUBATE, duration_s=6, resource="incubator"),
    Stage("Image", IMAGE, duration_s=3, resource="imager"),
    Stage("Count", COUNT, duration_s=1, resource=None),
    Stage("Decision", DECISION, duration_s=0, resource=None),
    Stage("Passage", PASSAGE, duration_s=2, resource=None),
]

# Convenience lookups by index.
STAGE_INDEX = {s.kind: i for i, s in enumerate(DEFAULT_PROTOCOL)}

# Decision thresholds.
CONFLUENCE_THRESHOLD = settings.confluence_threshold  # passage once the dish is this covered
MAX_PASSAGES = settings.max_passages                    # finish after this many passages

# Finite shared equipment — this is what forces real scheduling.
RESOURCE_CAPACITY = {"imager": 1, "incubator": 8}

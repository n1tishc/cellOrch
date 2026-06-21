"""Defines the lab protocol: the ordered stages a cell line moves through.

A protocol is just an ordered list of Stage definitions. The engine walks a
run through these stages; the DECISION stage decides whether to passage (and
loop back to INCUBATE) or finish.
"""
from dataclasses import dataclass


# Stage "kinds" — the engine special-cases IMAGE (calls the CV service) and
# DECISION (branches), and treats the rest as plain timed steps.
SEED = "SEED"
INCUBATE = "INCUBATE"
IMAGE = "IMAGE"
COUNT = "COUNT"
DECISION = "DECISION"
PASSAGE = "PASSAGE"


@dataclass(frozen=True)
class Stage:
    name: str
    kind: str
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
CONFLUENCE_THRESHOLD = 0.80   # passage once the dish is this covered
MAX_PASSAGES = 3              # finish after this many passages

# Finite shared equipment — this is what forces real scheduling.
RESOURCE_CAPACITY = {"imager": 1, "incubator": 8}

"""Drives the engine through simulated time with the CV stub (no server needed).

Run directly:  python -m tests.test_engine
Or with pytest: pytest -q
"""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DB_URL", "sqlite:///:memory:")
os.environ.setdefault("FAILURE_RATE", "0")  # deterministic for the assert run

from app import engine, protocol  # noqa: E402
from app.db import engine as db_engine, init_db  # noqa: E402
from app.models import COMPLETED, Event, Run  # noqa: E402
from sqlmodel import Session, select  # noqa: E402


def run_simulation(n_runs=3, ticks=400, verbose=False):
    init_db()
    with Session(db_engine) as s:
        for i in range(n_runs):
            s.add(Run(name=f"Line-{i+1:02d}"))
        s.commit()

        t = datetime(2026, 1, 1)
        for _ in range(ticks):
            engine.tick(s, now=t)
            t += timedelta(seconds=0.5)

        runs = s.exec(select(Run)).all()
        events = s.exec(select(Event)).all()
        if verbose:
            for r in runs:
                print(f"  {r.name}: {r.status} stage={r.current_stage} "
                      f"passages={r.passage_count} confluence={r.confluence}")
            print(f"  total audit events: {len(events)}")
        return runs, events


def test_runs_complete():
    runs, events = run_simulation()
    assert all(r.status == COMPLETED for r in runs), [r.status for r in runs]
    assert all(r.passage_count == protocol.MAX_PASSAGES for r in runs)
    assert len(events) > 0


if __name__ == "__main__":
    print("Running CellFlow engine simulation...")
    runs, events = run_simulation(verbose=True)
    done = sum(r.status == COMPLETED for r in runs)
    print(f"\n{done}/{len(runs)} runs completed, {len(events)} audit events logged.")

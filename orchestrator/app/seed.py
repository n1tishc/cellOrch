"""Seed helper: spawn N cell lines so the dashboard looks alive immediately."""
from sqlmodel import Session, select

from .models import Run


def seed_runs(session: Session, n: int) -> int:
    existing = len(session.exec(select(Run)).all())
    for i in range(n):
        session.add(Run(name=f"Line-{existing + i + 1:02d}"))
    session.commit()
    return n

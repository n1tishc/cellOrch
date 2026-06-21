"""SQLite engine + session helpers."""
import os

from sqlmodel import Session, SQLModel, create_engine

DB_URL = os.environ.get("DB_URL", "sqlite:///cellflow.db")

# check_same_thread=False so the background worker task and request handlers
# can share the engine.
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)

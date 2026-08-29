"""SQLite engine + session helpers."""
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

# check_same_thread=False so the background worker task and request handlers
# can share the engine.
engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)

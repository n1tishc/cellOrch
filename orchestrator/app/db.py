"""Database engine, session helpers, and migration bootstrap."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401 - registers SQLModel tables in metadata
from .config import settings

# check_same_thread=False so the background worker task and request handlers
# can share the engine.
engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
)

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
_MIGRATIONS_DIR = _ALEMBIC_INI.parent / "migrations"


def _alembic_config() -> Config:
    """Build an Alembic config that uses the application's configured database."""
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", settings.db_url)
    return config


def _is_in_memory_sqlite() -> bool:
    """Return whether Settings points at any SQLite in-memory URL variant."""
    url = make_url(settings.db_url)
    return url.get_backend_name() == "sqlite" and (
        url.database is None
        or url.database == ":memory:"
        or url.database.startswith("file::memory:")
        or url.query.get("mode") == "memory"
    )


def _is_unversioned_legacy_schema() -> bool:
    """Validate that a legacy schema exactly matches the initial managed schema."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    managed_tables = set(SQLModel.metadata.tables)

    if "alembic_version" in tables:
        return False
    if not tables & managed_tables:
        return False
    if not managed_tables <= tables:
        raise RuntimeError("Cannot safely migrate an incomplete unversioned legacy schema")

    for name in managed_tables:
        model_table = SQLModel.metadata.tables[name]
        expected_columns = {column.name for column in model_table.columns}
        actual_columns = {column["name"] for column in inspector.get_columns(name)}
        expected_types = {
            column.name: str(column.type.compile(dialect=engine.dialect)).upper()
            for column in model_table.columns
        }
        actual_types = {
            column["name"]: str(column["type"]).upper()
            for column in inspector.get_columns(name)
        }
        expected_indexes = {index.name for index in model_table.indexes}
        actual_indexes = {index["name"] for index in inspector.get_indexes(name)}
        if (
            expected_columns != actual_columns
            or expected_types != actual_types
            or not expected_indexes <= actual_indexes
        ):
            raise RuntimeError("Cannot safely migrate an incompatible unversioned legacy schema")

    return True


def _normalize_legacy_step_statuses() -> None:
    """Convert pre-enum StepExecution statuses to SQLAlchemy enum storage names."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE stepexecution SET status = UPPER(status) "
                "WHERE LOWER(status) IN ('running', 'success', 'failed')"
            )
        )


def init_db() -> None:
    """Apply migrations, safely stamp legacy schemas, and retain a dev/test fallback."""
    if settings.db_migrations_enabled and not _is_in_memory_sqlite():
        config = _alembic_config()
        if _is_unversioned_legacy_schema():
            _normalize_legacy_step_statuses()
            command.stamp(config, "head")
        else:
            command.upgrade(config, "head")
    else:
        SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)

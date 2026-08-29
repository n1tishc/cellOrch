"""Integration tests for applying Alembic migrations to SQLite databases."""
from datetime import datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from app import db
from app.models import Run, StepExecution, StepStatus


def configure_file_database(monkeypatch, tmp_path):
    """Point db helpers at an isolated SQLite file and return its engine."""
    url = f"sqlite:///{tmp_path / 'cellflow.db'}"
    engine = create_engine(url)
    monkeypatch.setattr(db.settings, "db_url", url)
    monkeypatch.setattr(db, "engine", engine)
    return engine


def test_init_db_applies_initial_migration_to_empty_database(monkeypatch, tmp_path):
    engine = configure_file_database(monkeypatch, tmp_path)

    db.init_db()

    assert {"run", "stepexecution", "event", "alembic_version"} <= set(
        inspect(engine).get_table_names()
    )
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_init_db_stamps_legacy_database_without_losing_data(monkeypatch, tmp_path):
    engine = configure_file_database(monkeypatch, tmp_path)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run = Run(name="Existing line")
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.id is not None

    with engine.begin() as connection:
        connection.execute(
            text(
                """INSERT INTO stepexecution
                (run_id, stage_name, stage_kind, status, attempt, started_at)
                VALUES (:run_id, 'Incubate', 'INCUBATE', :status, 1, :started_at)"""
            ),
            [
                {"run_id": run.id, "status": "success", "started_at": datetime.now().isoformat(" ")},
                {"run_id": run.id, "status": "running", "started_at": datetime.now().isoformat(" ")},
            ],
        )

    db.init_db()

    with Session(engine) as session:
        assert session.exec(select(Run.name)).all() == ["Existing line"]
        assert {step.status for step in session.exec(select(StepExecution))} == {
            StepStatus.RUNNING,
            StepStatus.SUCCESS,
        }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_init_db_rejects_incompatible_legacy_schema(monkeypatch, tmp_path):
    engine = configure_file_database(monkeypatch, tmp_path)
    with engine.begin() as connection:
        for table in ("run", "event", "stepexecution"):
            connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))

    with pytest.raises(RuntimeError, match="Cannot safely migrate"):
        db.init_db()

    assert "alembic_version" not in inspect(engine).get_table_names()


def test_init_db_rejects_type_incompatible_legacy_schema(monkeypatch, tmp_path):
    engine = configure_file_database(monkeypatch, tmp_path)
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE run"))
        connection.execute(
            text(
                """CREATE TABLE run (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR NOT NULL,
                status INTEGER NOT NULL,
                current_stage INTEGER NOT NULL,
                passage_count INTEGER NOT NULL,
                image_count INTEGER NOT NULL,
                confluence FLOAT NOT NULL,
                force_fail_next BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
                )"""
            )
        )

    with pytest.raises(RuntimeError, match="Cannot safely migrate"):
        db.init_db()

    assert "alembic_version" not in inspect(engine).get_table_names()


def test_init_db_uses_metadata_fallback_for_named_sqlite_memory_url(monkeypatch, tmp_path):
    url = f"sqlite:///file:{tmp_path.name}?mode=memory&cache=shared&uri=true"
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(db.settings, "db_url", url)
    monkeypatch.setattr(db, "engine", engine)

    db.init_db()

    assert {"run", "stepexecution", "event"} <= set(inspect(engine).get_table_names())
    assert "alembic_version" not in inspect(engine).get_table_names()


def test_init_db_uses_metadata_fallback_for_sqlite_memory_url(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(db.settings, "db_url", "sqlite://")
    monkeypatch.setattr(db, "engine", engine)

    db.init_db()

    assert {"run", "stepexecution", "event"} <= set(inspect(engine).get_table_names())
    assert "alembic_version" not in inspect(engine).get_table_names()

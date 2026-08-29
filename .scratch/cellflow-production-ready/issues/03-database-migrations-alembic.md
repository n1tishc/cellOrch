# 03 — Database Migrations (Alembic)

**What to build:** The current schema is created with `SQLModel.metadata.create_all()` — there's no migration system, so any future schema change (new columns for pause/cancel, webhook table, etc.) requires manual intervention or data loss. This ticket sets up Alembic with an initial migration that captures the current schema, so all subsequent schema changes are versioned, reversible, and safe to apply to existing data.

**Blocked by:** [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)

**Status:** ready-for-agent

- [ ] Add `alembic` to orchestrator requirements
- [ ] Initialize Alembic config (`alembic.ini` + `migrations/` directory) under the orchestrator package
- [ ] Configure Alembic to read the database URL from the `Settings` object (ticket 01)
- [ ] Generate the initial migration that captures the current schema (runs, step_executions, events tables)
- [ ] Replace `SQLModel.metadata.create_all()` in `init_db()` with Alembic's `upgrade("head")` for production, keep `create_all` as a dev/test fallback
- [ ] Verify: running the orchestrator against an empty database applies the migration cleanly
- [ ] Verify: running the orchestrator against an existing database with data does not lose data
- [ ] Document the migration workflow in the README (how to create a new migration, how to apply)

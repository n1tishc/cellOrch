# 04 — Run Lifecycle: Pause / Resume / Cancel

**What to build:** Once a run starts, there's no way to stop it — a real orchestrator must let an operator pause a line (e.g. to investigate an anomaly), resume it later, or cancel it entirely. This ticket adds `PAUSED` and `CANCELLED` statuses, three new API endpoints, engine logic that skips paused/cancelled runs, and dashboard buttons to trigger each action.

**Blocked by:**
- [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)
- [02 — Structured Logging & Error Handling](./02-structured-logging-error-handling.md)
- [03 — Database Migrations (Alembic)](./03-database-migrations-alembic.md)

**Status:** ready-for-agent

- [ ] Add `PAUSED` and `CANCELLED` to the `RunStatus` enum (from ticket 01)
- [ ] Add an Alembic migration if any schema change is needed (e.g. a `paused_at` timestamp column)
- [ ] Add `POST /runs/{run_id}/pause` endpoint — sets status to `PAUSED`, logs an event
- [ ] Add `POST /runs/{run_id}/resume` endpoint — sets status back to `PENDING` (only valid from `PAUSED`), logs an event
- [ ] Add `POST /runs/{run_id}/cancel` endpoint — sets status to `CANCELLED`, logs an event, releases any held resources
- [ ] Update the engine's `tick()` to exclude `PAUSED` and `CANCELLED` runs from `ACTIVE_STATUSES` — they must not advance
- [ ] Ensure cancelling a run that holds a resource (imager/incubator) frees that resource (mark the running step as failed/cancelled)
- [ ] Add pause/resume/cancel buttons to each run card in the dashboard, with appropriate enable/disable logic (can't pause a completed run, can't resume a non-paused run, etc.)
- [ ] Existing test still passes — paused/cancelled runs are excluded from the active set
- [ ] New test: pausing a running run stops it from advancing across subsequent ticks
- [ ] New test: resuming a paused run continues it from where it left off
- [ ] New test: cancelling a run that holds a resource frees it for other runs
- [ ] New test: API returns 400/404 for invalid transitions (e.g. pause a completed run, resume a non-paused run)

# 16 — Data Export (CSV/JSON)

**What to build:** There's no way to get run data, audit logs, or metrics out of the system for analysis, reporting, or archival. This ticket adds export endpoints that return CSV or JSON downloads for individual runs and for the full run list.

**Blocked by:** [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)

**Status:** ready-for-agent

- [ ] Add `GET /runs/{run_id}/export` endpoint with a `format` query parameter (`csv` or `json`, default `csv`)
- [ ] CSV export for a single run: include all events (id, type, message, created_at) and all step executions (stage, status, attempt, started_at, finish_at, error)
- [ ] JSON export for a single run: full run object with nested steps and events
- [ ] Add `GET /runs/export` endpoint (no run_id) that exports a summary of all runs (id, name, status, current_stage, passage_count, confluence, created_at, updated_at) in CSV or JSON
- [ ] Set proper `Content-Disposition` headers for file download (`attachment; filename=run_{id}.csv`)
- [ ] Add export buttons to the dashboard: one on each run card (single run export) and one in the header (all runs export)
- [ ] Verify: downloading CSV for a run produces a valid CSV file with all events
- [ ] Verify: downloading JSON for a run produces valid JSON with the full run detail
- [ ] Verify: the all-runs export includes every run with correct summary data

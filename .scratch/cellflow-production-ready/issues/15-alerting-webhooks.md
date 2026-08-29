# 15 — Alerting & Webhooks

**What to build:** When a run fails, nothing happens — no notification, no webhook, no alert. The operator has to stare at the dashboard to notice. This ticket adds a webhook system: configurable URLs that fire on specific events (run failed, run completed, etc.), plus a management API to create/list/delete webhooks.

**Blocked by:**
- [02 — Structured Logging & Error Handling](./02-structured-logging-error-handling.md)
- [03 — Database Migrations (Alembic)](./03-database-migrations-alembic.md)

**Status:** ready-for-agent

- [ ] Add a `Webhook` database model with fields: id, url, events (JSON array of event types to subscribe to), active (bool), created_at
- [ ] Add an Alembic migration for the new webhooks table
- [ ] Add a `fire_webhooks(session, event_type, payload)` function that queries active webhooks subscribed to the event type and POSTs the payload to each URL (with timeout, non-blocking — fire and forget with error logging)
- [ ] Call `fire_webhooks` from the engine's `log()` function (or at key transition points: run failed, run completed, step failed after exhausting retries)
- [ ] Add API endpoints: `POST /webhooks` (create), `GET /webhooks` (list), `DELETE /webhooks/{id}` (delete), `POST /webhooks/{id}/test` (fire a test event)
- [ ] Webhook payloads should include: event_type, run_id, timestamp, and relevant context (stage, attempt, error message)
- [ ] Add a webhooks management section to the dashboard (simple list + create/delete forms)
- [ ] Verify: creating a webhook for "run.failed" and letting a run fail results in an HTTP POST to the configured URL
- [ ] Verify: a webhook with an unreachable URL doesn't crash the engine (timeout + log error)
- [ ] Verify: deleting a webhook stops future notifications

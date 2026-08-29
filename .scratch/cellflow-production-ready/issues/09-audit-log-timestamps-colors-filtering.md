# 09 — Audit Log: Timestamps, Colors & Filtering

**What to build:** The detail panel dumps raw events as a flat unordered list with no timestamps, no color coding, no filtering, and no pagination. With many runs producing many events, this becomes unreadable. This ticket transforms the audit log into a structured, filterable, paginated timeline with visual event-type indicators.

**Blocked by:** [02 — Structured Logging & Error Handling](./02-structured-logging-error-handling.md)

**Status:** ready-for-agent

- [ ] Add formatted timestamps to each event row (relative time like "2m ago" + absolute on hover)
- [ ] Color-code events by type: `step_started` = blue, `step_done` = green, `retry` = yellow, `failed` = red, `completed` = green-bold, `decision` = purple, `passage` = orange, `queued` = gray
- [ ] Add event-type filter chips above the audit log (click to show/hide specific event types)
- [ ] Add pagination or virtual scrolling — show the 50 most recent events first, with a "Load more" button or infinite scroll
- [ ] Sort events newest-first by default
- [ ] Add a search/filter input to filter events by message text
- [ ] Verify: a run with 100+ events renders without lag
- [ ] Verify: filtering to "failed" events shows only failures
- [ ] Verify: timestamps are consistent with the engine's simulated clock (or real clock in production)

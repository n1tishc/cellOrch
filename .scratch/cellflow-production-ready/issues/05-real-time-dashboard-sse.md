# 05 — Real-Time Dashboard (SSE)

**What to build:** The dashboard polls `GET /runs` every 2 seconds — wasteful, latent, and doesn't scale. This ticket replaces polling with Server-Sent Events: the backend streams run state changes as they happen, and the frontend uses `EventSource` to update incrementally. The operator sees transitions (stage changes, failures, completions) appear instantly.

**Blocked by:**
- [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)
- [02 — Structured Logging & Error Handling](./02-structured-logging-error-handling.md)

**Status:** ready-for-agent

- [ ] Add `GET /runs/stream` SSE endpoint on the backend that streams run state changes as `text/event-stream`
- [ ] The SSE endpoint should emit events for: run status changes, stage transitions, step completions, failures, confluence updates
- [ ] Implementation: use an in-process event queue (asyncio.Queue) populated by the engine's `log()` function, with the SSE endpoint consuming from it
- [ ] Replace `setInterval(refresh, 2000)` in the frontend with `EventSource` connected to `/runs/stream`
- [ ] Frontend updates run state incrementally from SSE events instead of refetching the entire list
- [ ] Keep `GET /runs` as a fallback / initial-load endpoint (SSE is for updates, not initial data)
- [ ] Handle SSE reconnection: if the connection drops, the frontend should reconnect with exponential backoff
- [ ] Handle browser tab visibility: pause SSE when tab is hidden, resume when visible
- [ ] Verify: a run transitioning through stages produces SSE events that appear on the dashboard within 1 second (not 2)
- [ ] Existing dashboard functionality (run selection, detail panel, fault injection) still works

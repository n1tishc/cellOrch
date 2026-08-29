# 12 — Comprehensive Test Suite

**What to build:** Only one happy-path test exists — it runs 3 runs through 400 ticks with zero failures. Retry logic, resource contention, CV fallback, API endpoints, edge cases, and the new pause/resume/cancel flow are all untested. This ticket adds a thorough test suite covering engine unit tests, API integration tests, and edge cases.

**Blocked by:**
- [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)
- [02 — Structured Logging & Error Handling](./02-structured-logging-error-handling.md)
- [04 — Run Lifecycle: Pause / Resume / Cancel](./04-run-lifecycle-pause-resume-cancel.md)

**Status:** ready-for-agent

- [ ] Engine unit tests: retry with backoff — inject a failure, verify the step retries up to MAX_RETRIES, then marks the run FAILED
- [ ] Engine unit tests: resource contention — start enough runs to fill all incubator slots, verify new runs go to WAITING, and start when a slot frees
- [ ] Engine unit tests: CV service failure → stub fallback — mock the CV client to raise, verify the engine uses `stub_confluence` and continues
- [ ] Engine unit tests: injected fault handling — call `/inject-fault`, verify the next step fails and retries
- [ ] Engine unit tests: max passages → completion — verify a run completes after MAX_PASSAGES passages
- [ ] Engine unit tests: confluence threshold branching — verify the decision stage passages when confluence >= threshold, continues growing otherwise
- [ ] Engine unit tests: pause/resume/cancel — verify paused runs don't advance, resumed runs continue, cancelled runs free resources
- [ ] Engine unit tests: edge cases — 0 runs (no-op), 1 run, 100 runs
- [ ] API integration tests using `TestClient`: test every endpoint (`POST /runs`, `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/inject-fault`, `POST /seed`, `GET /healthz`, `GET /readyz`, `GET /metrics`)
- [ ] API integration tests: input validation — verify Pydantic models reject invalid inputs (negative n, oversized names)
- [ ] API integration tests: pause/resume/cancel endpoints — verify correct status transitions and error cases
- [ ] API integration tests: 404 for non-existent run IDs
- [ ] All tests run with in-memory SQLite, no external services needed
- [ ] Verify: `python -m pytest -q` passes with all tests green

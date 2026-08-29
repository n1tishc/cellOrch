# 17 — CV Thread Safety & Deep Health Checks

**What to build:** The CV service stores the Cellpose model and sample list as module-level globals with no thread safety — concurrent `/analyze` requests can race on model inference. The orchestrator's `/readyz` only checks if a SELECT query works, not whether the worker is alive or the CV service is reachable. This ticket adds thread safety to the CV service and deepens health checks to verify all dependencies.

**Blocked by:**
- [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)
- [02 — Structured Logging & Error Handling](./02-structured-logging-error-handling.md)

**Status:** ready-for-agent

- [ ] Add a `threading.Lock` around Cellpose model loading and inference in `cv-service/app/analyzer.py` — concurrent requests must not race on `_model`
- [ ] Add a `threading.Lock` around `_samples` list access if it can be modified at runtime
- [ ] Deepen `/readyz` on the orchestrator to check:
  - Database: execute a SELECT query, report ok/error
  - CV service: HTTP GET to `cv-service/healthz`, report ok/degraded/unreachable
  - Worker: check that the worker loop has ticked within the last N seconds (track last tick timestamp), report ok/stalled
- [ ] Return a structured health response: `{"status": "ready|degraded|unhealthy", "checks": {"database": "ok", "cv_service": "ok", "worker": "ok"}}`
- [ ] Add graceful shutdown: the lifespan handler should wait for in-flight ticks to complete (with a timeout) before exiting, not just cancel the task
- [ ] Add a `/deep-healthz` or enhance `/readyz` to be suitable for Kubernetes liveness probes (distinct from readiness)
- [ ] Verify: two concurrent `/analyze` requests to the CV service don't corrupt model state or produce errors
- [ ] Verify: killing the CV service causes the orchestrator's `/readyz` to report `cv_service: unreachable` with status `degraded`
- [ ] Verify: stopping the worker loop causes `/readyz` to report `worker: stalled`
- [ ] Verify: graceful shutdown doesn't lose in-flight tick data

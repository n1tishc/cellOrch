# 07 — Resource Utilization Panel

**What to build:** The system models finite shared equipment (1 imager, 8 incubator slots) but the dashboard shows nothing about resource usage — the operator can't see contention or predict queue times. This ticket adds a `/resources` API endpoint and a dashboard panel showing live utilization bars for each resource, plus queue depth.

**Blocked by:**
- [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)
- [02 — Structured Logging & Error Handling](./02-structured-logging-error-handling.md)

**Status:** ready-for-agent

- [ ] Add `GET /resources` endpoint that returns current resource usage (used vs capacity for imager and incubator) and queue depth (number of WAITING runs)
- [ ] The endpoint should query `StepExecution` rows with `status=RUNNING` and cross-reference protocol stages to determine which resource each step holds
- [ ] Add a resource panel to the dashboard (above or beside the metrics bar) showing:
  - Imager: used/1 with a progress bar
  - Incubator: used/8 with a progress bar
  - Queue depth: number of runs waiting for resources
- [ ] Resource panel updates via SSE (from ticket 05) when runs start/finish steps
- [ ] Color-code utilization: green (<50%), yellow (50-80%), red (>80%)
- [ ] Verify: when all incubator slots are full, the panel shows 8/8 and queue depth > 0
- [ ] Verify: when no runs are active, the panel shows 0/1 and 0/8

# 01 — Config, Enums & Input Validation

**What to build:** Every other ticket builds on a foundation of typed configuration, safe status values, and validated API inputs. This ticket replaces the scattered `os.environ.get()` calls with a single validated settings object, replaces raw string status/stage comparisons with `enum.Enum` types so a typo can't silently break the pipeline, and wraps all API request bodies in Pydantic models with length limits, range constraints, and sanitization — so `POST /seed?n=100000` or a malicious run name can't crash the process.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Create a `Settings` class (Pydantic `BaseSettings`) that centralizes every environment variable — DB URL, CV service URL, clock factor, failure rate, max retries, backoff, tick interval, seed count, confluence threshold, max passages — with typed fields, defaults, and `.env` file support
- [ ] Replace all `os.environ.get()` calls across the orchestrator with references to the `Settings` instance
- [ ] Define `RunStatus(str, Enum)` with values: `PENDING`, `WAITING`, `RUNNING`, `COMPLETED`, `FAILED` (and later `PAUSED`, `CANCELLED` from ticket 04)
- [ ] Define `StageKind(str, Enum)` matching the protocol stage kinds: `SEED`, `INCUBATE`, `IMAGE`, `COUNT`, `DECISION`, `PASSAGE`
- [ ] Replace all raw string comparisons for status and stage_kind with enum references
- [ ] Add Pydantic request models for `POST /runs` (name with max_length, pattern), `POST /seed` (n bounded 1–100), and any other mutation endpoint
- [ ] Update response models to use the enum types so the API contract is explicit
- [ ] Existing test (`test_runs_complete`) still passes with no changes
- [ ] New test: `POST /seed` with `n=0`, `n=-1`, `n=100001` returns 422
- [ ] New test: creating a run with a name exceeding max length returns 422

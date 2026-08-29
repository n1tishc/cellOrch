# 02 — Structured Logging & Error Handling

**What to build:** The entire codebase uses `print()` for output and bare `except Exception` to swallow errors — meaning a typo, a connection leak, or a data corruption bug is silently hidden. This ticket replaces all print statements with structured logging (JSON-formatted, with context fields like run_id and stage), replaces bare excepts with specific exception types, and adds a global exception handler that returns a consistent error envelope so the frontend can reliably parse failures.

**Blocked by:** [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)

**Status:** ready-for-agent

- [ ] Replace every `print()` call across orchestrator and cv-service with `logging` calls using structured extra fields (run_id, stage, event_type, attempt)
- [ ] Configure a JSON log formatter so logs are machine-parseable in production
- [ ] Replace bare `except Exception` in the worker loop with specific catches (`ConnectionError`, `TimeoutError`, `ValueError`, etc.) — transient errors log a warning, data errors re-raise
- [ ] Replace bare `except Exception` in `cv_client.py` with specific `httpx` exception types (`ConnectError`, `TimeoutException`)
- [ ] Replace bare `except Exception` in `cv-service/app/analyzer.py` with specific import/runtime errors
- [ ] Add a centralized FastAPI exception handler that catches unhandled exceptions, logs them with full traceback, and returns a consistent `ErrorResponse` JSON body with `error`, `detail`, and optional `request_id` fields
- [ ] Add a `request_id` middleware (UUID per request, attached to log context and error responses)
- [ ] Existing test still passes; no test asserts on print output
- [ ] New test: hitting an endpoint that raises returns the consistent error envelope, not a raw 500

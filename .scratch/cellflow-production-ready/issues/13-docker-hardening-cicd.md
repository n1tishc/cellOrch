# 13 — Docker Hardening & CI/CD

**What to build:** Docker images ship `node_modules` and `.venv` in the build context, run as root, have no health checks, and use single-stage builds. The CI pipeline only tests the Python backend — the frontend has no lint, type check, or build verification. This ticket hardens the Docker setup and extends CI to cover the full stack.

**Blocked by:** [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)

**Status:** ready-for-agent

- [ ] Add `.dockerignore` files for orchestrator and cv-service (exclude `__pycache__`, `*.pyc`, `.venv`, `node_modules`, `.git`, `*.db`, `.env`)
- [ ] Add `.dockerignore` for frontend (exclude `node_modules`, `dist`, `.env`)
- [ ] Convert orchestrator Dockerfile to multi-stage build: builder stage installs deps, runtime stage copies only site-packages and app code
- [ ] Convert cv-service Dockerfile to multi-stage build (same pattern)
- [ ] Add `USER nonroot` directive to all Dockerfiles (run as non-root user)
- [ ] Add `HEALTHCHECK` instruction to orchestrator Dockerfile (curl/wget to `/healthz`)
- [ ] Add `HEALTHCHECK` instruction to cv-service Dockerfile (curl/wget to `/healthz`)
- [ ] Add frontend build verification to CI: `npm ci && npm run build` in the frontend directory
- [ ] Add frontend lint to CI (if a linter is configured; if not, add `eslint` with a basic config)
- [ ] Verify: `docker compose up --build` works and all containers are healthy
- [ ] Verify: CI pipeline passes with test + build-images + frontend-build jobs

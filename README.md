# CellFlow

A lab-workflow orchestrator that coordinates many simulated cell lines through a
cell-culture protocol in parallel, schedules them against limited shared
equipment, recovers from failures, logs every transition for traceability, and
uses a computer-vision model (Cellpose) to drive the key decision — with a live
dashboard showing it all happen.

It's a software model of the coordination problem that lab-automation platforms
solve. It does not control real hardware; the one real component is the CV step,
which can run Cellpose on actual microscopy images.

## What it demonstrates

- **Orchestration & scheduling** — a worker advances each run through stages and
  enforces finite resources (1 imager, 8 incubator slots), so runs queue.
- **Resilience** — steps fail (injected or on demand) and retry with backoff;
  exhausted retries mark a run failed without taking down the pipeline.
- **Perception in the loop** — the imaging stage calls the CV service; the
  returned confluence decides whether a line is passaged or keeps growing.
- **Traceability** — every transition is written to an audit log.
- **Live operations view** — SSE-triggered refreshes keep the dashboard current;
  a connected protocol map shows actual active, running, waiting, and paused
  runs at each stage.
- **Data import** — a CSV endpoint creates real runs in SQLite, with a baseline
  fixture included for repeatable manual checks.
- **Operability** — containerized, health probes, CI, Kubernetes manifests.

## Architecture

```
React dashboard (SSE updates + live refresh)
        |
  FastAPI orchestrator  --- worker tick loop (schedules, retries, logs)
        |   |                         |
        |   +--> SQLite (runs, steps, events)
        |
        +--> HTTP --> CV service (FastAPI + Cellpose) --> {confluence, cell_count}
```

Each cell line flows: `Seed -> Incubate -> Image -> Count -> Decision -> Passage`,
where Decision either passages it (and loops back to Incubate) or, after enough
passages, completes it.

## Quick start

```bash
docker compose up --build
# dashboard: http://localhost:5173
# API:       http://localhost:8000/runs   (docs at /docs)
```

Compose starts with an empty database (`SEED_ON_START=0`). Create a run from the
dashboard or import the provided baseline CSV from **Data → Import real runs**:

```text
orchestrator/samples/baseline-runs.csv
```

The importer accepts a UTF-8 CSV with a required `name` column, supports up to
100 rows, and stores each new run in SQLite. Names may contain letters, digits,
spaces, `_`, and `-`.

Or run the orchestrator alone:

```bash
cd orchestrator
pip install -r requirements.txt
uvicorn app.main:app --reload      # starts with an empty database and ticking worker
```

### Start fresh

To permanently remove all local SQLite runs, audit events, imported data, and
webhooks, remove only the orchestrator data volume, then recreate the services:

```bash
docker compose stop orchestrator
docker compose rm -sf orchestrator orchestrator-init
docker volume rm cellflow_orchestrator-data
docker compose up -d orchestrator-init orchestrator
```

Do not use this command sequence for data you need to keep.

## Dashboard and analytics

The overview is deliberately split into two complementary views:

- The **protocol map** is the fast operational view. Each connected stage shows
  actual SQLite-backed counts for active, running, and held (waiting or paused)
  runs. Selecting a stage filters the run registry.
- The **run registry** is the precise control surface for search, filters,
  pause/resume/cancel actions, exports, and the per-run audit timeline.

`GET /analytics` powers the dashboard with persisted run states, stage-state
counts, recent audit events, event activity, completion rate, and measured step
durations. It does not manufacture activity for empty databases.

## Tests

```bash
cd orchestrator && python -m pytest -q
```

The engine takes the current time as an argument, so the test drives hundreds of
simulated ticks with no sleeping and asserts every run completes.

## Database migrations

The orchestrator applies Alembic migrations to `head` on startup. Alembic reads
`DB_URL` through the application's Settings object, so set it before running a
migration command. A legacy database created before Alembic is safely validated against the
initial managed schema, stamped at that initial revision, then upgraded to
`head`; legacy step statuses are normalized before upgrading. An incompatible legacy schema
fails safely instead of being stamped. In-memory databases and
`DB_MIGRATIONS_ENABLED=false` retain `SQLModel.metadata.create_all()` as a
development/test fallback.

```bash
cd orchestrator

# Apply all pending migrations to DB_URL.
alembic upgrade head

# Generate and review a migration after changing SQLModel models.
alembic revision --autogenerate -m "describe schema change"

# Roll back the most recently applied migration.
alembic downgrade -1
```

Commit every generated migration under `orchestrator/migrations/versions/`; do
not modify an applied migration on a shared environment.

## Enabling real Cellpose

The CV service ships in `stub` mode (deterministic rising confluence) so the
system runs with zero setup. To use the real model:

1. In `cv-service`: `pip install cellpose pillow numpy`
2. Drop ordered microscopy images (sparse -> dense) in `cv-service/samples/`
   (e.g. from Sartorius, LIVECell, or BBBC).
3. Set `CV_MODE=real`.

The service then segments each image with Cellpose, computing confluence as
masked-area / total and cell count as the number of labels.

## Kubernetes

```bash
docker build -t cellflow-orchestrator ./orchestrator
docker build -t cellflow-cv ./cv-service
kubectl apply -f deploy/k8s/      # liveness/readiness probes included
```

## Layout

```
orchestrator/   FastAPI API + worker + engine + SQLite models   (Python)
cv-service/     FastAPI + Cellpose (stub fallback)              (Python)
frontend/       Vite + React dashboard
deploy/k8s/     Deployments + Services with health probes
.github/        CI: tests + image builds
```

## Key tunables (env)

`CLOCK_FACTOR` (sim speed), `FAILURE_RATE`, `MAX_RETRIES`, `BACKOFF_S`,
`SEED_ON_START`, `CV_SERVICE_URL`, and `WORKER_STALL_SECONDS`.

# metric_wave — Implementation Plan

Real-time analytics dashboard with live streaming.

**Stack:** Python 3.12, Django 5 + Django REST Framework, Django Channels (WebSocket),
PostgreSQL, Redis (cache + channel layer), TypeScript + React (Vite), pytest,
Docker Compose, GitHub Actions, AWS EC2.

## Design decisions

- **Domain model.** A `Source` (e.g. "checkout-service") emits `MetricPoint`s for named
  metrics (`latency_ms`, `orders`, ...). A `Dashboard` holds `Widget`s, each bound to a
  source + metric + aggregation (avg/sum/min/max/count) + time window.
- **Ingestion.** `POST /api/ingest/` accepts single points or batches, authenticated by a
  per-source API key (`X-Source-Key` header). After writing to Postgres it publishes each
  point to a Channels group `metric.<source>.<metric>` and invalidates affected cache keys.
- **Caching.** Aggregation/time-series queries are cached in Redis using versioned keys
  (`mw:v<version>:...`). Ingest bumps a per-metric version counter instead of scanning keys,
  so invalidation is O(1). Short TTLs bound staleness.
- **Live streaming.** Django Channels `AsyncJsonWebsocketConsumer` at `/ws/stream/`. Clients
  send `subscribe`/`unsubscribe` messages for `(source, metric)` pairs; the server pushes
  `point` events. A Redis channel layer fans out across processes/instances.
- **Frontend.** Vite + React + TypeScript, Recharts for charts. A `useMetricStream` hook
  manages a single reconnecting WebSocket; widgets seed with REST history then append
  live points.
- **Ops.** Docker Compose for local dev (postgres, redis, backend via daphne, frontend).
  GitHub Actions runs pytest with coverage gate (95%) and deploys to EC2 over SSH on main.

## Phases

### Phase 1 — Backend scaffold and data model
- Django project `config`, app `metrics`, settings driven by environment variables.
- Models: `Source`, `MetricPoint` (indexed on source/name/timestamp), `Dashboard`, `Widget`.
- Admin registration, initial migration, `docker-compose.yml`, `.env.example`.
- Files: `backend/manage.py`, `backend/config/*`, `backend/metrics/models.py`,
  `backend/metrics/admin.py`, `backend/metrics/migrations/0001_initial.py`,
  `backend/requirements*.txt`, `docker-compose.yml`, `.env.example`.

### Phase 2 — REST API and Redis caching layer
- DRF serializers and viewsets for sources, dashboards, widgets.
- Ingest endpoint with source-key auth; time-series and summary endpoints with bucketing.
- `metrics/cache.py`: versioned cache keys, `cached_query` helper, invalidation on ingest.
- Files: `backend/metrics/{serializers,views,urls,auth,services,cache}.py`,
  `backend/config/urls.py`.

### Phase 3 — WebSocket live streaming
- Channels ASGI routing, `StreamConsumer` with subscribe/unsubscribe protocol.
- `broadcast.py` publishing points to groups after ingest commit.
- `simulate_metrics` management command generating realistic traffic for demos.
- Files: `backend/config/asgi.py`, `backend/metrics/{consumers,routing,broadcast}.py`,
  `backend/metrics/management/commands/simulate_metrics.py`.

### Phase 4 — TypeScript React frontend
- Vite project, typed API client, `useMetricStream` WebSocket hook with reconnect/backoff.
- Dashboard list, dashboard view with live line-chart and stat widgets, connection badge.
- Files: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/**`.

### Phase 5 — Tests, containers, CI/CD
- pytest suite (models, API, cache, consumers, command) with coverage config.
- Dockerfiles for backend/frontend, nginx config, GitHub Actions CI + EC2 deploy workflow,
  deploy script.
- Files: `backend/tests/**`, `backend/pytest.ini`, `backend/Dockerfile`,
  `frontend/Dockerfile`, `deploy/*`, `.github/workflows/*`.

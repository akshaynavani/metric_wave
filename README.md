# metric_wave

A real-time analytics dashboard with live streaming. Services push metric points to a Django
REST API; the points are stored in PostgreSQL, query results are cached in Redis, and every new
point is pushed over WebSockets to the React dashboards that are watching it. Charts update
the moment data arrives, without polling.

**Stack:** Python 3.12, Django 5, Django REST Framework, Django Channels, PostgreSQL, Redis,
TypeScript, React (Vite + Recharts), pytest, Docker Compose, GitHub Actions, AWS EC2.

## Features

- **Ingest API.** `POST /api/ingest/` takes a single point or a batch. Each source
  authenticates with its own `X-Source-Key`.
- **Bucketed queries.** Time series with `avg/sum/min/max/count` aggregation over configurable
  windows and bucket sizes, plus a summary endpoint (stats and latest value).
- **Redis caching with versioned keys.** Each `(source, metric)` pair has a version counter in
  its cache keys. Ingest bumps the counter, which makes every stale entry unreachable in O(1)
  with no key scans. Responses carry an `X-Cache: HIT|MISS` header.
- **Live streaming.** A Channels WebSocket at `/ws/stream/` with a subscribe/unsubscribe
  protocol. Points are broadcast once the ingest transaction commits, and the Redis channel
  layer fans them out to every backend instance.
- **Dashboard UI.** Dashboards are made of line, bar and stat widgets. Each widget first loads
  its history over REST, then folds live points into its buckets in the browser. One WebSocket
  is shared across all widgets, and it reconnects with exponential backoff.
- **Ops.** Docker Compose stack, nginx reverse proxy with WebSocket upgrade, CI with a 95%
  coverage gate, and automatic deploys to EC2 over SSH.

## Architecture

```mermaid
flowchart LR
    subgraph Producers
        P1[Service A]
        P2[Service B]
        SIM[simulate_metrics]
    end

    subgraph EC2["AWS EC2 (docker compose)"]
        NGINX[nginx<br/>static React build<br/>/api + /ws proxy]
        subgraph Backend["Django ASGI (daphne)"]
            API[DRF views<br/>ingest / query / CRUD]
            SVC[services.py<br/>bucketing + aggregation]
            CACHE[cache.py<br/>versioned keys]
            WS[StreamConsumer<br/>WebSocket]
            BC[broadcast.py]
        end
        PG[(PostgreSQL<br/>MetricPoint, Dashboard, Widget)]
        RD[(Redis<br/>query cache + channel layer)]
    end

    subgraph Browser["React + TypeScript"]
        UI[Dashboard widgets]
        SC[StreamClient<br/>shared WebSocket]
    end

    P1 & P2 & SIM -- "POST /api/ingest/<br/>X-Source-Key" --> NGINX
    NGINX --> API
    API --> SVC
    SVC -- write/read --> PG
    SVC <-- get/set, bump version --> CACHE
    CACHE <--> RD
    SVC -- on_commit --> BC
    BC -- group_send --> RD
    RD -- group message --> WS
    WS -- "points" --> SC
    UI -- "GET /api/query/series/" --> NGINX
    SC --> UI
    GH[GitHub Actions] -- "pytest + deploy over SSH" --> EC2
```

Data flow for a single point:

1. A producer calls `POST /api/ingest/`. `SourceKeyAuthentication` resolves the source.
2. `services.ingest_points` bulk-inserts the points inside a transaction.
3. After the commit, the cache versions for the affected metrics are bumped and the points
   are sent to the `metric.<source>.<metric>` channel group.
4. Each `StreamConsumer` in that group forwards the points to its browser. `useWidgetSeries`
   merges them into the chart's buckets, using the same aggregation as the server.

## Project layout

```
backend/
  config/            settings (env-driven), ASGI routing, test settings
  metrics/
    models.py        Source, MetricPoint, Dashboard, Widget
    services.py      series bucketing, summaries, ingest
    cache.py         versioned Redis cache helpers
    broadcast.py     channel-layer fan-out
    consumers.py     WebSocket protocol
    views.py urls.py serializers.py auth.py
    management/commands/  seed_demo, simulate_metrics
  tests/             pytest suite (API, cache, services, consumers, commands)
frontend/
  src/lib/           API client, StreamClient, bucket merging (+ vitest)
  src/hooks/         useWidgetSeries, useConnectionStatus
  src/components/    dashboard list/detail, widget cards
  nginx.conf         production reverse proxy
deploy/              EC2 bootstrap + deploy scripts
.github/workflows/   CI and deploy pipelines
```

## How to run

### Option A: everything in Docker

```bash
cp .env.example .env          # set DJANGO_SECRET_KEY and DJANGO_ALLOWED_HOSTS, e.g. localhost,backend
docker compose --profile demo up --build
```

Open http://localhost:8080. The `demo` profile seeds a `checkout-overview` dashboard and sends
synthetic traffic every second. To create an admin user:
`docker compose exec backend python manage.py createsuperuser`, then go to `/admin/`.

### Option B: local development

```bash
# 1. Infrastructure
docker compose up -d postgres redis

# 2. Backend (http://localhost:8000)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=true
python manage.py migrate
python manage.py seed_demo                 # prints the demo source's API key
python manage.py runserver                 # daphne serves HTTP + WebSockets

# 3. Simulated traffic (another terminal)
python manage.py simulate_metrics --interval 1

# 4. Frontend (http://localhost:5173; proxies /api and /ws to :8000)
cd ../frontend
npm install
npm run dev
```

### Sending your own metrics

```bash
curl -X POST http://localhost:8000/api/ingest/ \
  -H "Content-Type: application/json" \
  -H "X-Source-Key: <key from seed_demo or POST /api/sources/>" \
  -d '{"points": [{"name": "latency_ms", "value": 123.4, "tags": {"region": "eu"}}]}'
```

### API summary

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/ingest/` | `X-Source-Key` auth; a single point, a list, or `{"points": [...]}` |
| GET | `/api/query/series/?source=&metric=&window=&bucket=&agg=` | Cached, with an `X-Cache` header |
| GET | `/api/query/summary/?source=&metric=&window=` | avg/sum/min/max/count/latest |
| GET/POST | `/api/sources/` | Anyone can read; only staff can write. The key is returned only on create |
| POST | `/api/sources/<slug>/rotate-key/` | Staff only |
| GET | `/api/sources/<slug>/metrics/` | Distinct metric names |
| CRUD | `/api/dashboards/`, `/api/widgets/?dashboard=<slug>` | Anyone can read; only staff can write |
| WS | `/ws/stream/` | `{"action": "subscribe", "source", "metric"}` returns `{"type": "points", ...}` |

### Configuration

All settings come from environment variables (see `.env.example`): `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `CORS_ALLOWED_ORIGINS`,
`CSRF_TRUSTED_ORIGINS`, `METRIC_CACHE_TTL` and `INGEST_MAX_BATCH`. Never commit `.env`.

## How to test

```bash
# Backend: uses SQLite, LocMem cache and the in-memory channel layer. No services needed.
cd backend
pip install -r requirements-dev.txt
pytest --cov --cov-report=term-missing --cov-fail-under=95

# Against real Postgres + Redis (as CI's second matrix leg does)
docker compose up -d postgres redis
USE_REAL_SERVICES=1 DATABASE_URL=postgres://metric_wave:metric_wave@localhost:5432/metric_wave \
  REDIS_URL=redis://localhost:6379/0 pytest

# Frontend
cd frontend
npm install
npm run typecheck && npm test
```

## Deploying to AWS EC2

1. Launch an EC2 instance (t3.small or larger). Open ports 22 and 80 (or put it behind an
   ALB/TLS terminator that forwards to port 8080).
2. On the instance, run `deploy/ec2-bootstrap.sh https://github.com/<you>/metric_wave.git`,
   then edit `~/metric_wave/.env` with production values.
3. In the GitHub repo, add the `production` environment secrets `EC2_HOST`, `EC2_USER` and
   `EC2_SSH_KEY`.
4. Every push to `main` that passes CI triggers `.github/workflows/deploy.yml`. That workflow
   SSHes into the host and runs `deploy/deploy.sh <sha>`, which rebuilds the stack, restarts
   it and runs a health check.

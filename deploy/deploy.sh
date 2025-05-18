#!/usr/bin/env bash
# Pull a specific revision on the EC2 host and roll the compose stack forward.
# Expects the repo cloned at ~/metric_wave and a populated .env alongside docker-compose.yml.
set -euo pipefail

REF="${1:-main}"
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "missing .env — copy .env.example and fill in production values" >&2
  exit 1
fi

git fetch --quiet origin
git checkout --quiet --force "$REF"

docker compose build backend frontend
docker compose up -d postgres redis
docker compose up -d --no-deps backend frontend

# Wait for the API to answer before declaring success.
for attempt in $(seq 1 30); do
  if curl -fsS http://localhost:8080/api/health/ >/dev/null; then
    echo "deployed $(git rev-parse --short HEAD)"
    docker image prune -f >/dev/null
    exit 0
  fi
  sleep 2
done

echo "health check failed after deploy" >&2
docker compose logs --tail=100 backend >&2
exit 1

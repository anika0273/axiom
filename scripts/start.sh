#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Building and starting Axiom services..."
docker compose up --build -d

echo ""
echo "==> Waiting for db to be healthy..."
until docker compose ps db | grep -q "(healthy)"; do
  printf "."
  sleep 2
done
echo ""
echo "    db: healthy"

echo ""
echo "==> Waiting for backend to be healthy..."
until docker compose ps backend | grep -q "(healthy)"; do
  printf "."
  sleep 2
done
echo ""
echo "    backend: healthy"

echo ""
echo "==> Service status:"
docker compose ps

echo ""
echo "==> Axiom API is ready"
echo "    API:    http://localhost:8000"
echo "    Docs:   http://localhost:8000/docs"
echo "    Health: http://localhost:8000/api/v1/stats/health"

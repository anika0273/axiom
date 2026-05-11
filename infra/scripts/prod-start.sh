#!/usr/bin/env bash
# prod-start.sh — build, migrate, and start Axiom in production.
# Usage: ./infra/scripts/prod-start.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE="docker compose -f $PROJECT_ROOT/docker-compose.prod.yml"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die()  { log "ERROR: $*" >&2; exit 1; }
ok()   { log "OK  $*"; }

# ── 1. Validate required env vars ────────────────────────────────────────────
log "Validating environment variables..."
missing=()
for var in DATABASE_URL ANTHROPIC_API_KEY SECRET_KEY POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB; do
    [[ -z "${!var:-}" ]] && missing+=("$var")
done
[[ ${#missing[@]} -gt 0 ]] && die "Missing required variables: ${missing[*]}"
ok "All required variables present."

cd "$PROJECT_ROOT"

# ── 2. Tag current images for rollback (before overwriting) ──────────────────
log "Snapshotting current images for rollback (if running)..."
"$SCRIPT_DIR/prod-rollback.sh" tag 2>/dev/null || true

# ── 3. Build all images ───────────────────────────────────────────────────────
log "Building images..."
$COMPOSE build --pull
ok "Images built."

# ── 4. Start services ─────────────────────────────────────────────────────────
log "Starting services..."
$COMPOSE up -d
ok "Services started."

# ── 5. Wait for PostgreSQL ────────────────────────────────────────────────────
log "Waiting for PostgreSQL (max 60s)..."
timeout 60 bash -c \
    "until $COMPOSE exec -T postgres pg_isready -U \"\${POSTGRES_USER}\" -d \"\${POSTGRES_DB}\" >/dev/null 2>&1; do sleep 2; done" \
    || die "PostgreSQL did not become ready within 60 seconds."
ok "PostgreSQL ready."

# ── 6. Run Alembic migrations ─────────────────────────────────────────────────
log "Running database migrations..."
$COMPOSE exec -T backend alembic upgrade head
ok "Migrations complete."

# ── 7. Wait for backend health ────────────────────────────────────────────────
log "Waiting for backend health (max 90s)..."
timeout 90 bash -c \
    "until $COMPOSE exec -T backend curl -sf http://localhost:8000/api/v1/stats/health >/dev/null 2>&1; do sleep 3; done" \
    || die "Backend did not become healthy within 90 seconds."
ok "Backend healthy."

# ── 8. Smoke tests through nginx ──────────────────────────────────────────────
log "Running smoke tests through nginx..."
sleep 2

http_status=$(curl -so /dev/null -w "%{http_code}" http://localhost/api/v1/stats/health)
[[ "$http_status" == "200" ]] || die "Smoke test failed: /api/v1/stats/health returned HTTP $http_status"
ok "/api/v1/stats/health → 200"

http_status=$(curl -so /dev/null -w "%{http_code}" http://localhost/)
[[ "$http_status" == "200" ]] || die "Smoke test failed: / returned HTTP $http_status"
ok "/ → 200"

log "──────────────────────────────────────────────"
log "Axiom is live at http://localhost"
log "──────────────────────────────────────────────"

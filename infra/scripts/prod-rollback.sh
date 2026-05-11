#!/usr/bin/env bash
# prod-rollback.sh — snapshot or restore Axiom production images.
#
# Usage:
#   ./infra/scripts/prod-rollback.sh tag    # snapshot current images before a deploy
#   ./infra/scripts/prod-rollback.sh apply  # restore snapshot and restart services
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE="docker compose -f $PROJECT_ROOT/docker-compose.prod.yml"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { log "ERROR: $*" >&2; exit 1; }
ok()  { log "OK  $*"; }

SERVICES=(backend frontend)

# ── tag: snapshot running image IDs as :rollback tags ─────────────────────────
cmd_tag() {
    log "Snapshotting current images as rollback targets..."
    for svc in "${SERVICES[@]}"; do
        container_id=$($COMPOSE ps -q "$svc" 2>/dev/null | head -1)
        if [[ -z "$container_id" ]]; then
            log "  SKIP $svc — not currently running."
            continue
        fi
        img=$(docker inspect "$container_id" --format '{{.Image}}')
        docker tag "$img" "axiom-${svc}:rollback"
        ok "  axiom-${svc}:rollback tagged (was $img)"
    done
}

# ── apply: restore :rollback tags and restart affected services ────────────────
cmd_apply() {
    log "Checking rollback snapshots..."
    missing=()
    for svc in "${SERVICES[@]}"; do
        docker image inspect "axiom-${svc}:rollback" >/dev/null 2>&1 \
            || missing+=("$svc")
    done
    [[ ${#missing[@]} -gt 0 ]] && die "No rollback snapshot found for: ${missing[*]}. Run 'tag' before deploying."

    log "Stopping services..."
    $COMPOSE stop "${SERVICES[@]}"

    log "Re-tagging rollback snapshots to :latest..."
    for svc in "${SERVICES[@]}"; do
        docker tag "axiom-${svc}:rollback" "axiom-${svc}:latest"
        ok "  axiom-${svc}:latest ← axiom-${svc}:rollback"
    done

    log "Restarting services from rollback images (no rebuild)..."
    $COMPOSE up -d --no-build "${SERVICES[@]}"

    log "Waiting for health after rollback (max 90s)..."
    timeout 90 bash -c \
        "until curl -sf http://localhost/api/v1/stats/health >/dev/null 2>&1; do sleep 3; done" \
        || die "Health check failed after rollback — manual intervention required."

    ok "Rollback complete. Axiom is healthy at http://localhost"
}

case "${1:-}" in
    tag)   cmd_tag ;;
    apply) cmd_apply ;;
    *)
        echo "Usage: $0 <tag|apply>"
        echo ""
        echo "  tag    Snapshot current running images for rollback (run before each deploy)"
        echo "  apply  Restore rollback snapshots and restart services"
        exit 1
        ;;
esac

#!/usr/bin/env bash
set -euo pipefail
: "${HF_SERVER:?export HF_SERVER=root@<server ip or tailscale name>}"
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
git diff --quiet || { echo "commit or stash changes first"; exit 1; }
git push
set -a; [ -f backend/.env ] && . backend/.env; set +a
(cd web && npm ci && VITE_GOOGLE_MAPS_KEY="${VITE_GOOGLE_MAPS_KEY:-}" VITE_GOOGLE_MAP_ID="${VITE_GOOGLE_MAP_ID:-}" npm run build)
ssh "$HF_SERVER" 'cd /opt/homefinder && git pull --ff-only'
rsync -az --delete web/dist/ "$HF_SERVER":/opt/homefinder/web/dist/
ssh "$HF_SERVER" 'cd /opt/homefinder && docker compose -f deploy/docker-compose.yml --env-file .env up -d --build && docker image prune -f'
ssh "$HF_SERVER" 'curl -fsS -H "Host: localhost" http://127.0.0.1/ -o /dev/null -w "%{http_code}\n" || true'
echo "deployed"

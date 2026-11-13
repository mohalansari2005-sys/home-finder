#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BACKEND="$ROOT/backend"
LOGS="$HOME/Library/Logs/homefinder"
PLIST="$HOME/Library/LaunchAgents/com.homefinder.worker.plist"
command -v tailscale >/dev/null || [ -d /Applications/Tailscale.app ] || { echo "Install Tailscale first: brew install --cask tailscale"; exit 1; }
[ -f "$BACKEND/.env" ] || { echo "Create $BACKEND/.env (DATABASE_URL to server Tailscale IP, SERVER_URL, WORKER_TOKEN, API keys)"; exit 1; }
cd "$BACKEND"
[ -d .venv ] || python3.12 -m venv .venv
.venv/bin/pip install -q -r requirements-worker.lock  # pinned; regenerate with scripts/lock-backend.sh
.venv/bin/pip install -q --no-deps -e .
.venv/bin/playwright install chromium
mkdir -p "$LOGS" "$(dirname "$PLIST")"
sed -e "s#__BACKEND__#$BACKEND#g" -e "s#__LOGS__#$LOGS#g" "$ROOT/deploy/worker/com.homefinder.worker.plist.template" > "$PLIST"
launchctl bootout "gui/$(id -u)/com.homefinder.worker" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "worker installed; logs: $LOGS"

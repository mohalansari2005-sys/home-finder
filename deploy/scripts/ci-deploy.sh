#!/usr/bin/env bash
# Server side of the CI deploy. The GitHub Actions deploy key is pinned to this script in
# /root/.ssh/authorized_keys (command="..."), so the key can do nothing else.
#   ssh root@server <commit sha>  < web-dist.tar.gz
# The sha must be on origin/main; the built web/dist arrives as a tar.gz on stdin.
# Everything runs inside main(), so the git pull below can't change the script mid-run.
set -euo pipefail

main() {
  local sha="${SSH_ORIGINAL_COMMAND:-${1:-}}"
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "usage: ci-deploy.sh <40-char commit sha> < dist.tar.gz" >&2; exit 2; }
  cd /opt/homefinder

  git fetch -q origin main
  git merge-base --is-ancestor "$sha" origin/main || { echo "$sha is not on origin/main" >&2; exit 1; }
  if ! git merge-base --is-ancestor HEAD "$sha"; then
    echo "server is already ahead of $sha; skipping"
    exit 0
  fi
  git merge -q --ff-only "$sha"

  # nginx bind-mounts web/dist, so update it in place rather than swapping the directory
  tmp=$(mktemp -d)  # global, so the EXIT trap still sees it
  trap 'rm -rf "$tmp"' EXIT
  tar xzf - -C "$tmp"
  [ -f "$tmp/index.html" ] || { echo "upload has no index.html" >&2; exit 1; }
  mkdir -p web/dist
  rsync -a --delete "$tmp"/ web/dist/

  local c="docker compose -f deploy/docker-compose.yml --env-file .env"
  $c up -d --build
  docker image prune -f >/dev/null

  # the api answers 401 on /api/feed without a session once it is up
  for _ in $(seq 30); do
    if $c exec -T api python -c "
import urllib.request as u, urllib.error as e
try: u.urlopen('http://localhost:8000/api/feed')
except e.HTTPError as x: raise SystemExit(x.code != 401)
" 2>/dev/null; then
      echo "deployed $(git log --oneline -1)"
      exit 0
    fi
    sleep 2
  done
  echo "api did not come up; see: $c logs api" >&2
  exit 1
}

main "$@"
exit

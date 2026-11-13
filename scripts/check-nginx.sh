#!/usr/bin/env bash
# Renders deploy/nginx/default.conf.template with a throwaway certificate, runs `nginx -t` and checks the
# request-body limits against a real nginx container (no upstream needed: 502 means "got past nginx").
set -euo pipefail
cd "$(dirname "$0")/.."
T=$(mktemp -d); trap 'docker rm -f hf-nginx-check >/dev/null 2>&1 || true; rm -rf "$T"' EXIT
DOMAIN=hf.test
mkdir -p "$T/live/$DOMAIN"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$DOMAIN" \
  -keyout "$T/live/$DOMAIN/privkey.pem" -out "$T/live/$DOMAIN/fullchain.pem" 2>/dev/null
DOMAIN=$DOMAIN envsubst '${DOMAIN}' < deploy/nginx/default.conf.template > "$T/default.conf"
docker run -d --name hf-nginx-check --add-host api:127.0.0.1 -p 18443:443 \
  -v "$T/default.conf:/etc/nginx/conf.d/default.conf:ro" -v "$T/live:/etc/letsencrypt/live:ro" \
  nginx:1.27-alpine >/dev/null
sleep 2
docker exec hf-nginx-check nginx -t
code() { head -c "$2" /dev/zero | curl -sk -o /dev/null -w '%{http_code}' -X POST --data-binary @- "https://localhost:18443$1"; }
photo=$(code /api/visits/stops/7/photos 5000000)
other=$(code /api/login 2000000)
echo "5 MB photo upload -> $photo (must not be 413); 2 MB to /api/login -> $other (must be 413)"
[ "$photo" != 413 ] && [ "$other" = 413 ]

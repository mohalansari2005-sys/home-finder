#!/usr/bin/env bash
set -euo pipefail
cd /opt/homefinder
DIR=/var/backups/homefinder
STAMP=$(date +%F)
docker compose -f deploy/docker-compose.yml --env-file .env exec -T db pg_dump -U hf homefinder | gzip > "$DIR/db-$STAMP.sql.gz"
ls -1t "$DIR"/db-*.sql.gz | tail -n +15 | xargs -r rm --
# Listing photos are not backed up: they are public downloads and can be fetched again (and they would fill the disk).
rm -f "$DIR"/photos-*.tgz
if [ "$(date +%u)" = "5" ]; then
  docker run --rm -v homefinder_visit_photos:/p -v "$DIR":/b alpine tar czf "/b/visit-photos-$STAMP.tgz" -C /p .
  ls -1t "$DIR"/visit-photos-*.tgz | tail -n +5 | xargs -r rm --
fi
# Optional off-box copy (Hetzner Storage Box): set STORAGE_BOX=u123456@u123456.your-storagebox.de in .env
if grep -q '^STORAGE_BOX=' .env; then
  SB=$(grep '^STORAGE_BOX=' .env | cut -d= -f2)
  rsync -az -e "ssh -p 23" "$DIR"/ "$SB":homefinder-backups/
fi

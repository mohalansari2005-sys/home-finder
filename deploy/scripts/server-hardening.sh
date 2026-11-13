#!/usr/bin/env bash
# Boot-order and permission fixes for the VPS. Called by server-setup.sh and safe to re-run on a server
# that was set up earlier:  scp deploy/scripts/server-hardening.sh root@IP: && ssh root@IP bash server-hardening.sh
#
# Postgres is published on the Tailscale IP (docker-compose.yml). At boot dockerd can start before tailscaled has
# assigned that address; binding to a missing address fails and Docker does not retry, so the db (and the site)
# stay down. Two guards: bind to non-local addresses, and start docker after tailscaled.
# PREFIX (default empty) is only for testing the generated files in a scratch directory.
set -euo pipefail
P="${PREFIX:-}"

install -d "$P/etc/letsencrypt/renewal-hooks/pre" "$P/etc/letsencrypt/renewal-hooks/post" "$P/etc/cron.d" "$P/etc/sysctl.d" "$P/etc/systemd/system/docker.service.d" "$P/var/backups/homefinder"
echo 'net.ipv4.ip_nonlocal_bind=1' > "$P/etc/sysctl.d/99-homefinder.conf"
printf '[Unit]\nAfter=tailscaled.service\nWants=tailscaled.service\n' > "$P/etc/systemd/system/docker.service.d/10-tailscale.conf"
# Weekly: delete downloaded photos of listings that were removed, merged or rejected more than 30 days ago.
cat > "$P/etc/cron.d/homefinder-prune" <<'CRON'
30 3 * * 0 root cd /opt/homefinder && docker compose -f deploy/docker-compose.yml --env-file .env exec -T api python -m homefinder.cli prune-photos >> /var/log/homefinder-prune.log 2>&1
CRON
# apt's certbot.timer renews twice a day; the standalone challenge needs port 80, which nginx holds. These hooks run
# only when a certificate is actually due. (They replace the old Monday cron line, which the timer made redundant.)
C="docker compose -f /opt/homefinder/deploy/docker-compose.yml --env-file /opt/homefinder/.env"
printf '#!/bin/sh\n%s stop nginx\n' "$C" > "$P/etc/letsencrypt/renewal-hooks/pre/stop-nginx.sh"
printf '#!/bin/sh\n%s start nginx\n' "$C" > "$P/etc/letsencrypt/renewal-hooks/post/start-nginx.sh"
chmod 755 "$P/etc/letsencrypt/renewal-hooks/pre/stop-nginx.sh" "$P/etc/letsencrypt/renewal-hooks/post/start-nginx.sh"
[ -f "$P/etc/cron.d/homefinder" ] && sed -i '/certbot renew/d' "$P/etc/cron.d/homefinder"
chmod 700 "$P/var/backups/homefinder"  # dumps hold seller phones and the home location

if [ -z "$P" ]; then
  sysctl --system >/dev/null
  systemctl daemon-reload
fi
echo "hardening applied (docker starts after tailscaled, backups dir is root-only, weekly photo prune scheduled)"

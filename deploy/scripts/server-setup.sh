#!/usr/bin/env bash
set -euo pipefail
: "${DOMAIN:?export DOMAIN=your.domain}"
: "${EMAIL:?export EMAIL=you@example.com}"

# 2 GB swap
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10 && echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf
fi

apt-get update
apt-get install -y ca-certificates curl git ufw certbot
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --ssh || true
echo "Tailscale IP: $(tailscale ip -4)"

ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp
ufw allow in on tailscale0
ufw --force enable

mkdir -p /opt/homefinder /var/backups/homefinder
[ -d /opt/homefinder/.git ] || git clone https://github.com/mohalansari2005-sys/home-finder.git /opt/homefinder

certbot certonly --standalone --non-interactive --agree-tos -m "$EMAIL" -d "$DOMAIN"

cat > /etc/cron.d/homefinder <<CRON
15 3 * * * root /opt/homefinder/deploy/scripts/backup.sh >> /var/log/homefinder-backup.log 2>&1
0 4 * * 1 root certbot renew --quiet --pre-hook "docker compose -f /opt/homefinder/deploy/docker-compose.yml --env-file /opt/homefinder/.env stop nginx" --post-hook "docker compose -f /opt/homefinder/deploy/docker-compose.yml --env-file /opt/homefinder/.env start nginx"
CRON
echo "Now: create /opt/homefinder/.env from .env.example, then run deploy.sh from the Mac."

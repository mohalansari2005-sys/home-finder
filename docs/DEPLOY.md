# Deploying Home Finder (بيتنا)

One Hetzner VPS (2 GB) runs Postgres+PostGIS, the API and nginx. The Mac runs the worker and reaches the server over Tailscale.

## 1. Prerequisites
- A Hetzner VPS, a domain whose A record points at it, and a Tailscale account.
- A Google Cloud project with **Geocoding API**, **Routes API** and **Maps JavaScript API** enabled. Create two keys:
  - a **server key**, restricted to Geocoding + Routes;
  - a **browser key**, restricted to Maps JavaScript and the HTTP referrer `https://DOMAIN/*`.
- A vector **Map ID** (needed for Advanced Markers) and an OpenAI API key.

## 2. Server bootstrap
```bash
scp deploy/scripts/server-setup.sh root@IP:
ssh root@IP 'DOMAIN=your.domain EMAIL=you@example.com bash server-setup.sh'
```
Record the Tailscale IP it prints. The script also runs `deploy/scripts/server-hardening.sh` (docker starts after tailscaled, so the Postgres port bound to the Tailscale IP survives a reboot; `/var/backups/homefinder` is root-only; a weekly photo-prune cron is installed).

**A server that was set up before this fix** does not need a full re-run. Pull the repo and run only the hardening step once:
```bash
ssh root@IP 'cd /opt/homefinder && git pull --ff-only && bash deploy/scripts/server-hardening.sh'
```

## 3. Server `.env`
Copy `.env.example` to `/opt/homefinder/.env` and fill in:
- `POSTGRES_PASSWORD`
- `SESSION_SECRET` (`openssl rand -hex 32`)
- `FAMILY_PASSWORD_HASH` (from `python -m homefinder.cli hash-password` on the Mac)
- `COOKIE_SECURE=true`
- `WORKER_TOKEN` (`openssl rand -hex 24`)
- `DOMAIN`, `TAILSCALE_IP`
- `GOOGLE_API_KEY` (server key), `OPENAI_API_KEY`, and the monthly caps

With `COOKIE_SECURE=true` the api **refuses to start** (and the container restarts in a loop; see `docker compose logs api`) if `SESSION_SECRET` or `WORKER_TOKEN` is a placeholder (`CHANGE_ME…`, the dev defaults) or shorter than 32 characters, or if `FAMILY_PASSWORD_HASH` is empty.

Never commit `.env`.

## 4. First deploy (from the Mac)
```bash
HF_SERVER=root@IP deploy/scripts/deploy.sh
```

After the first deploy, **reboot the VPS once** (`ssh root@IP reboot`) and confirm the site loads, `docker compose -f deploy/docker-compose.yml ps` shows db, api and nginx up, and the worker shows متصل again. This proves the boot order.

## 5. Mac `backend/.env`
```
DATABASE_URL=postgresql+psycopg://hf:<POSTGRES_PASSWORD>@<TAILSCALE_IP>:5432/homefinder
SERVER_URL=http://<TAILSCALE_IP>
WORKER_TOKEN=<same as server>
GOOGLE_API_KEY=...
OPENAI_API_KEY=...
VITE_GOOGLE_MAPS_KEY=<browser key>
VITE_GOOGLE_MAP_ID=...
```
Optionally set `AQAR_APP_VERSION` (default `1.0.3`) if Aqar bumps its required web-client version (see `docs/sources/aqar.md`). It is read from this file by the worker at start, so restart the worker after changing it.

## 6. Seed data (run on the Mac against the server DB)
```bash
cd backend
.venv/bin/python -m homefinder.cli seed-airport
.venv/bin/python -m homefinder.cli set-place --kind school --name "..." --lat .. --lng ..   # also work, university
.venv/bin/python -m homefinder.cli set-filters --json '{"districts":["النرجس"],"price_max":3000000}'
.venv/bin/python -m homefinder.cli enqueue-scrape
```
Place coordinates are personal data: they live only in the database, never in git.

## 7. Install the worker
```bash
deploy/worker/install-worker.sh
```
Open Settings and confirm the worker shows as متصل (online).

## 8. Operations
- Logs: `docker compose -f deploy/docker-compose.yml logs -f api` on the server; `~/Library/Logs/homefinder/` on the Mac.
- Restore a backup: `gunzip -c db-DATE.sql.gz | docker compose exec -T db psql -U hf homefinder`.
- Resume a paused adapter. An adapter pauses on an Aqar/Haraj block ("… blocked: HTTP 403"), on "aqar app-version outdated" and when a batch looks unhealthy. After an app-version bump: set `AQAR_APP_VERSION` in `backend/.env` on the Mac, run `launchctl kickstart -k gui/$(id -u)/com.homefinder.worker`, then press «استئناف» in Settings → الحالة. The server-side chat fallback search also reads `AQAR_APP_VERSION`, so put it in the server `.env` too and run `docker compose -f deploy/docker-compose.yml --env-file .env up -d api`. After a block, wait some hours before resuming.
- After upgrading to the coverage-damped score (review fix I4), rescore once so stored scores use the new formula (run on the Mac against the server DB): `cd backend && .venv/bin/python -m homefinder.cli rescore`. A fresh install needs nothing.
- Keep the Mac awake on power: System Settings, Battery, Options, "Prevent automatic sleeping on power adapter when the display is off".
- Backups run nightly at 03:15 (database dump, 14 kept) and weekly on Friday (family visit photos, 4 kept). Listing photos are **not** backed up (they are re-downloadable and would fill the 40 GB disk); the first backup run after this change deletes the old `photos-*.tgz` files. Set `STORAGE_BOX` in `.env` for an off-box rsync copy (see below).
- Disk: Settings → الحالة shows the free space. Photos are fetched only for listings that pass the filters (6 per listing, 1280 px), and a weekly cron (`/etc/cron.d/homefinder-prune`, installed by `server-hardening.sh`) runs `python -m homefinder.cli prune-photos` in the api container to delete photos of listings removed, merged or rejected more than 30 days ago. Run it by hand with `docker compose -f deploy/docker-compose.yml --env-file .env exec -T api python -m homefinder.cli prune-photos`.

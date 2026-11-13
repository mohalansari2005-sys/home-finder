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
Record the Tailscale IP it prints.

## 3. Server `.env`
Copy `.env.example` to `/opt/homefinder/.env` and fill in:
- `POSTGRES_PASSWORD`
- `SESSION_SECRET` (`openssl rand -hex 32`)
- `FAMILY_PASSWORD_HASH` (from `python -m homefinder.cli hash-password` on the Mac)
- `COOKIE_SECURE=true`
- `WORKER_TOKEN` (`openssl rand -hex 24`)
- `DOMAIN`, `TAILSCALE_IP`
- `GOOGLE_API_KEY` (server key), `OPENAI_API_KEY`, and the monthly caps

Never commit `.env`.

## 4. First deploy (from the Mac)
```bash
HF_SERVER=root@IP deploy/scripts/deploy.sh
```

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
Optionally set `AQAR_APP_VERSION` if Aqar bumps its required web-client version (see `docs/sources/aqar.md`).

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
- Resume a paused adapter (e.g. "aqar app-version outdated" after fixing the version): `UPDATE adapter_health SET status='ok', reason=NULL;` (Plan 2 adds a button).
- After upgrading to the coverage-damped score (review fix I4), rescore once so stored scores use the new formula (run on the Mac against the server DB): `cd backend && .venv/bin/python -m homefinder.cli rescore`. A fresh install needs nothing.
- Keep the Mac awake on power: System Settings, Battery, Options, "Prevent automatic sleeping on power adapter when the display is off".
- Backups run nightly at 03:15 (DB, 14 kept) and weekly on Friday (photos, 4 kept); set `STORAGE_BOX` in `.env` for an off-box rsync copy.

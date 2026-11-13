# Deploying Home Finder (بيتنا)

One Hetzner VPS (2 GB) runs Postgres+PostGIS, the API and nginx. The Mac runs the worker and reaches the server over Tailscale.

## 1. Prerequisites
- A Hetzner VPS, a domain whose **A record** points at it (do not add an AAAA record: behind Docker's proxy every IPv6 visitor shares one address, so the login rate limit would treat the whole family as one client), and a Tailscale account.
- A free **TomTom developer account** (https://developer.tomtom.com, no credit card) and its API key (the default key from the dashboard works; it needs the **TomTom Orbis Maps** Routing API and Geocoding API, which new keys have). It is used by the server and the worker only, for geocoding districts and for traffic-aware drive times. The endpoints are in `backend/homefinder/integrations/tomtom.py` (`BASE_URL`). The free tier currently allows 20,000 Routing and 20,000 Geocoding requests a month (older accounts: 2,500 requests a day); the app stays under that with `TOMTOM_DAILY_REQUEST_CAP` and `TOMTOM_MONTHLY_REQUEST_CAP`. If your TomTom dashboard shows a different allowance, set the caps a little below it.
- An OpenAI API key.

The map in the browser is MapLibre with OpenFreeMap tiles: no account, no key, nothing to configure.

## 2. Server bootstrap
```bash
scp deploy/scripts/server-setup.sh root@IP:
ssh root@IP 'DOMAIN=your.domain EMAIL=you@example.com bash server-setup.sh'
```
Record the Tailscale IP it prints. The script also runs `deploy/scripts/server-hardening.sh` (docker starts after tailscaled, so the Postgres port bound to the Tailscale IP survives a reboot; `/var/backups/homefinder` is root-only; a weekly photo-prune cron is installed; certbot renewal hooks stop/start nginx for apt's renewal timer, replacing the old Monday cron line).

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
- `TOMTOM_API_KEY`, `OPENAI_API_KEY`, and the caps (`OPENAI_MONTHLY_CAP_USD`, `TOMTOM_DAILY_REQUEST_CAP`, `TOMTOM_MONTHLY_REQUEST_CAP`). The server uses TomTom to plan visit trips; the worker uses it for geocoding and commutes. Both count against the same caps, which are stored in the database.

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
TOMTOM_API_KEY=...
OPENAI_API_KEY=...
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
Open Settings and confirm the worker shows as متصل (online). The script installs the pinned `backend/requirements-worker.lock` (the API image installs `requirements-server.lock` and CI `requirements-ci.lock`). To update dependencies, edit the ranges in `backend/pyproject.toml`, run `scripts/lock-backend.sh` (needs Docker), run the tests and commit the three lock files. An already-installed worker needs no action.

## 8. Operations
- Logs: `docker compose -f deploy/docker-compose.yml logs -f api` on the server; `~/Library/Logs/homefinder/` on the Mac.
- Restore a backup (the dump contains the whole schema, so it must go into an **empty** database; piping it into the live one fails on the first `CREATE`). First stop the Mac worker so nothing holds a connection (`launchctl bootout gui/$(id -u)/com.homefinder.worker`; restart it afterwards with `deploy/worker/install-worker.sh`), then on the server:
  ```bash
  cd /opt/homefinder && C="docker compose -f deploy/docker-compose.yml --env-file .env"
  $C stop api
  $C exec -T db dropdb -U hf homefinder && $C exec -T db createdb -U hf homefinder
  gunzip -c /var/backups/homefinder/db-DATE.sql.gz | $C exec -T db psql -q -v ON_ERROR_STOP=1 -U hf homefinder
  $C start api
  ```
  Visit photos: `docker run --rm -v homefinder_visit_photos:/p -v /var/backups/homefinder:/b alpine tar xzf /b/visit-photos-DATE.tgz -C /p`. Listing photos are not backed up; the worker's daily catch-up downloads them again.
- Once a month, prove the backups restore: `$C exec -T db createdb -U hf hf_restore_test`, restore the newest dump into it as above (with `hf_restore_test` instead of `homefinder`), check `$C exec -T db psql -U hf hf_restore_test -c "SELECT count(*) FROM listings"`, then `$C exec -T db dropdb -U hf hf_restore_test`.
- Off-box backups (strongly recommended: with no `STORAGE_BOX` a dead or full disk takes the backups with it). Order a Hetzner Storage Box, enable SSH support in its settings, then on the VPS as root: `ssh-keygen -t ed25519 -N "" -f /root/.ssh/id_ed25519`, `ssh-copy-id -p 23 -s u123456@u123456.your-storagebox.de`, run `ssh -p 23 u123456@u123456.your-storagebox.de ls` once to accept the host key, add `STORAGE_BOX=u123456@u123456.your-storagebox.de` to `/opt/homefinder/.env`, then run `/opt/homefinder/deploy/scripts/backup.sh` once by hand and check the files arrived in `homefinder-backups/`.
- Resume a paused adapter. An adapter pauses on an Aqar/Haraj block ("… blocked: HTTP 403"), on "aqar app-version outdated" and when a batch looks unhealthy. After an app-version bump: set `AQAR_APP_VERSION` in `backend/.env` on the Mac, run `launchctl kickstart -k gui/$(id -u)/com.homefinder.worker`, then press «استئناف» in Settings → الحالة. The server-side chat fallback search also reads `AQAR_APP_VERSION`, so put it in the server `.env` too and run `docker compose -f deploy/docker-compose.yml --env-file .env up -d api`. After a block, wait some hours before resuming.
- After upgrading to the coverage-damped score (review fix I4), rescore once so stored scores use the new formula (run on the Mac against the server DB): `cd backend && .venv/bin/python -m homefinder.cli rescore`. A fresh install needs nothing.
- Log out every device (there is no per-session revocation; the cookie lasts 90 days): change `SESSION_SECRET` in `/opt/homefinder/.env` and run `docker compose -f deploy/docker-compose.yml --env-file .env up -d api`. Everyone signs in again with the family password. Do the same if the secret ever leaked.
- Keep the Mac awake on power: System Settings, Battery, Options, "Prevent automatic sleeping on power adapter when the display is off".
- Backups run nightly at 03:15 (database dump, 14 kept) and weekly on Friday (family visit photos, 4 kept). Listing photos are **not** backed up (they are re-downloadable and would fill the 40 GB disk); the first backup run after this change deletes the old `photos-*.tgz` files. Set `STORAGE_BOX` in `.env` for an off-box rsync copy (see the Off-box backups item above).
- Disk: Settings → الحالة shows the free space. Photos are fetched only for listings that pass the filters (6 per listing, 1280 px), and a weekly cron (`/etc/cron.d/homefinder-prune`, installed by `server-hardening.sh`) runs `python -m homefinder.cli prune-photos` in the api container to delete photos of listings removed, merged or rejected more than 30 days ago. Run it by hand with `docker compose -f deploy/docker-compose.yml --env-file .env exec -T api python -m homefinder.cli prune-photos`.

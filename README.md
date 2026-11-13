# بيتنا · Home Finder

A private, Arabic-first web app that helps one family find a home to **buy in Riyadh**.

It collects listings from Aqar (and Haraj, in progress), scores each one 0–100 against the family's needs with a short explanation, and shows every listing with its photos, a map, and rush-hour drive times to the places that matter: one school, one workplace, one university and King Khalid International Airport. It learns from what the family saves and rejects, and it plans in-person visit trips that group liked homes by district.

The app is right-to-left Arabic throughout and is installable as a PWA. It has layouts for phone, iPad and desktop.

## How it fits together

```
 Phone / iPad / desktop (PWA)
            │  HTTPS
            ▼
 ┌──────────────────────────────┐        Tailscale        ┌───────────────────────────┐
 │ Hetzner VPS (1 vCPU, 2 GB)    │◄───────────────────────►│ MacBook worker            │
 │ nginx → static web app        │   worker API + Postgres │ scrapers (Aqar, Haraj)    │
 │ FastAPI (auth, feed, chat)    │                         │ enrichment: OpenAI,       │
 │ Postgres 16 + PostGIS         │                         │ Google geocode/routes,    │
 │ job queue (SKIP LOCKED)       │                         │ photos, learning          │
 └──────────────────────────────┘                         └───────────────────────────┘
```

- **The server stays light.** It serves the built frontend, the API and the database. Scraping, LLM calls, photo processing and model training all run on the Mac. The Mac takes jobs from a queue in Postgres and talks to the server only over Tailscale.
- **The app keeps working while the Mac sleeps.** The family can browse, save, reject and change preferences. New listings arrive when the worker is back.
- **Spending is capped.** OpenAI and Google usage are metered against monthly limits (`OPENAI_MONTHLY_CAP_USD`, `GOOGLE_MONTHLY_CAP_USD`).

## Stack

| Part | Tools |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Postgres 16 + PostGIS |
| Scraping | `curl_cffi` with a Playwright fallback |
| Agent | LangGraph / LangChain with an OpenAI model and a Postgres checkpointer; chat streams over SSE |
| Maps | Google Geocoding, Routes (traffic-aware), Maps JavaScript |
| Frontend | React 19, Vite, TypeScript, Tailwind v4, shadcn/ui (Radix, RTL), TanStack Query, lucide icons |
| Tests | pytest, Vitest, Playwright (phone, tablet and desktop projects) |
| Deploy | Docker Compose, nginx, certbot, launchd for the Mac worker |

## Repository layout

```
backend/    Python package `homefinder`: server, worker, scoring, migrations, tests
web/        React PWA: pages, components, unit tests, Playwright e2e
deploy/     Docker Compose files, nginx config, server and worker scripts
docs/       Deploy guide, design system, Arabic UI rules, source notes, spec and plans
scripts/    CI helpers (RTL check, fixture scrubber)
```

## Running it locally

You need Python 3.12, Node 24 and Docker.

```bash
# 1. Start the test database (PostGIS on port 55432)
docker compose -f deploy/docker-compose.test.yml up -d

# 2. Backend
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e '.[server,worker,dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn homefinder.server.app:app --reload        # API on :8000

# 3. Worker (in a second terminal)
.venv/bin/python -m homefinder.worker.main

# 4. Web (in a third terminal; proxies /api to :8000)
cd web
npm ci
npm run dev
```

The login uses one shared family password. Generate its hash with `.venv/bin/python -m homefinder.cli hash-password` and set it as `FAMILY_PASSWORD_HASH`. The other settings are in `backend/homefinder/config.py`. Without the OpenAI and Google keys, the app still runs and skips the steps that need them.

## Tests

```bash
cd backend && .venv/bin/pytest -q             # needs the test database
cd web && npm test                            # unit tests
cd web && npx playwright test                 # e2e at phone, tablet and desktop sizes
bash scripts/check-rtl.sh                     # RTL, colour-token and copy rules
```

Tests marked `live` (real websites) or `llm` (real model calls) are skipped unless you opt in.

## Deploying

See [docs/DEPLOY.md](docs/DEPLOY.md). It covers server bootstrap, the `.env` values, the first deploy, seeding the family's places, and installing the Mac worker.

## How changes land

- `main` is protected. Every change goes through a pull request, and the CI jobs `backend`, `web`, `api-image` and `secrets-guard` must pass before it can merge.
- The work is split into milestones, one branch and one PR each:

  | Milestone | Scope | Status |
  |---|---|---|
  | M1 Foundation | Aqar scraping, enrichment, API, feed, detail, map, deploy, CI | merged |
  | M2 Scoring and settings | explainable score, hard filters, preferences | merged |
  | M3 Agent, Haraj and dedupe | chat assistant, Haraj, duplicate merge, removed listings, price drops | in progress |
  | M4 Learning and compare | learning from saves and rejects, suggestions, compare view | planned |
  | M5 Visits | visit trips grouped by district, contact tracking, pre-visit checks | planned |

- The design spec is in `docs/superpowers/specs/`, and the per-milestone plans are in `docs/superpowers/plans/`.
- UI work follows [docs/design-system.md](docs/design-system.md) and [docs/arabic-ui-rules.md](docs/arabic-ui-rules.md).

## Privacy

This repository is public, but the app and its data are private to one family.

- **No personal data in git.** Never commit API keys, cookies, `.env` files, the family's place coordinates, or seller contact details.
- **Fixtures are scrubbed.** Test fixtures pass through `scripts/scrub_fixture.py`, and CI runs a secrets scan on every PR.
- **Scraping stays polite and read-only.** Requests are paced and there is no login, and a source is paused rather than forced when it starts blocking.

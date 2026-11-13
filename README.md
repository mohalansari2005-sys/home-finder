# بيتنا · Home Finder

A private, Arabic-first PWA that helps my family find a home to **buy in Riyadh**. It gathers listings from Aqar and Haraj, scores each one against what we care about, shows rush-hour drive times to the places we go every day, learns from what we save and reject, and plans visit trips.

## Why

Our search was manual and exhausting. Every day someone scrolled Aqar and Haraj, saw the same villa posted by three brokers, opened each ad to find its size and age, pasted the location into Google Maps to guess the 7 a.m. school run, and shared screenshots in the family group. Then we'd lose track of what we liked, what we'd rejected and why, and which sellers we'd called.

We didn't need another listings site. We needed something to do the tedious part: read everything, remember our priorities, and bring back only the homes worth a look, with reasons.

## What it does

| Problem | بيتنا |
|---|---|
| Listings scattered across sites, reposted by many brokers | Scrapes Aqar and Haraj on a schedule and merges duplicates |
| Messy ads with missing sizes and prices buried in text | Extracts what it can from the text and labels the rest as unknown |
| "Close" depends on traffic | Rush-hour drive times to the school, workplace, university and King Khalid International Airport |
| Priorities live in people's heads | An explainable 0–100 score per listing ("why 86?") from weights the family sets |
| Re-filtering every day | Hard filters (budget, districts, type, rooms, area), and only new or changed homes are flagged |
| Forgetting why you passed on a home | Reject reasons, learning from saves and rejects, and suggestions like "filter out buildings older than 20 years?" |
| Prices change and ads vanish | Price history, price-drop badges and "listing removed" chips |
| Chaotic visit days | Trips grouped by district, with driving order, time slots, WhatsApp links and a pre-visit check that the ads are still live |

The app also has:
- **An Arabic chat assistant.** You talk to it the way you'd talk to the family group. "نبي فيلا في النرجس أو الياسمين بحدود مليونين، والمدرسة أهم من الدوام" (a villa in Al Narjis or Al Yasmin, around two million, school matters more than work) updates the filters and weights and replies with the best matches as cards you can open. It can also explain a score, compare homes or plan a visit. Every change it makes shows up in the settings history, and replies stream in as they're written.
- **A map.** Price pins are coloured by score, with saved homes highlighted, and sit next to the school, work and university markers, so you can see at a glance which good matches cluster near the places that matter.
- **Compare.** Pick 2–4 homes for a side-by-side table of price, price per metre, size, rooms, building age and every drive time. The best value in each row is highlighted, and missing data is flagged rather than hidden.
- **Settings.** Set the four places, the hard filters and how much each factor matters. You can lock a weight so the learner leaves it alone, and see a history of every change, whether it came from you, the assistant or the learner. A status panel shows when each source last ran, whether the Mac worker is online, and any failed jobs.
- **One shared family login.** It works on phone (bottom tabs), iPad (sidebar, or a two-column grid in portrait) and desktop (list, map and chat side by side). It installs to the home screen and is right-to-left Arabic throughout, with Western digits for prices and times.

## Architecture

```
 Phone / iPad / desktop (PWA)
            │ HTTPS
            ▼
 ┌─────────────────────────────┐   Tailscale   ┌──────────────────────────┐
 │ Hetzner VPS (1 vCPU, 2 GB)  │◄─────────────►│ MacBook worker           │
 │ nginx + static web app      │               │ Aqar and Haraj scrapers  │
 │ FastAPI: auth, feed, chat   │               │ OpenAI extraction        │
 │ Postgres 16 + PostGIS       │               │ Google geocode/routes    │
 │ job queue (SKIP LOCKED)     │               │ photos, learning         │
 └─────────────────────────────┘               └──────────────────────────┘
```

- **The server stays light.** All heavy work runs on the Mac, which pulls jobs from a Postgres queue over Tailscale.
- **The app works while the Mac sleeps.** New listings arrive when it wakes.
- **Spending is capped.** OpenAI and Google usage have monthly limits (`OPENAI_MONTHLY_CAP_USD`, `GOOGLE_MONTHLY_CAP_USD`).

**Stack**

| Area | Tools |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Postgres 16 + PostGIS |
| Scraping | curl_cffi, with a Playwright fallback |
| Agent | LangGraph with OpenAI, streamed over SSE |
| Maps | Google Routes (traffic-aware), Geocoding, Maps JS |
| Web | React 19, Vite, TypeScript, Tailwind v4, shadcn/ui (RTL), TanStack Query |
| Tests | pytest, Vitest, Playwright |

## Development

Requires Python 3.12, Node 24 and Docker.

```bash
docker compose -f deploy/docker-compose.test.yml up -d    # PostGIS on :55432

cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e '.[server,worker,dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn homefinder.server.app:app --reload        # API on :8000
.venv/bin/python -m homefinder.worker.main                  # worker, in a second terminal

cd web && npm ci && npm run dev                             # proxies /api to :8000
```

Set `FAMILY_PASSWORD_HASH` to the output of `python -m homefinder.cli hash-password`. Other settings are in `backend/homefinder/config.py`. Without OpenAI or Google keys, the app still runs and skips the steps that need them.

**Tests:**

```bash
cd backend && .venv/bin/pytest -q      # live and llm tests skipped by default
cd web && npm test && npx playwright test
bash scripts/check-rtl.sh
```

**Deploying:** see [docs/DEPLOY.md](docs/DEPLOY.md).

## Contributing

`main` is protected. Changes land through PRs that pass the CI jobs `backend`, `web`, `api-image` and `secrets-guard`. The spec lives in `docs/superpowers/specs/`, and each milestone has a plan in `docs/superpowers/plans/`. UI work follows [docs/design-system.md](docs/design-system.md) and [docs/arabic-ui-rules.md](docs/arabic-ui-rules.md).

| Milestone | Scope | Status |
|---|---|---|
| M1 Foundation | Aqar scraping, enrichment, API, feed, map, deploy, CI | merged |
| M2 Scoring | explainable score, hard filters, settings | merged |
| M3 Assistant | chat, Haraj, duplicate merge, removed listings, price drops | merged |
| M4 Learning | learning from reactions, suggestions, compare | merged |
| M5 Visits | district trips, contact tracking, pre-visit checks | planned |

## Privacy

The repo is public, but the app and its data belong to one family.

- **Nothing personal goes in git.** No keys, cookies, `.env` files, place coordinates or seller contacts.
- **Fixtures are scrubbed.** CI runs a secrets scan on every PR.
- **Scraping is paced, read-only and done without logging in.** A source is paused, not forced, when it starts blocking.

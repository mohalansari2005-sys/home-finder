# بيتنا · Home Finder

A private, Arabic-first web app that helps one family find a home to **buy in Riyadh**.

It collects listings from Aqar and Haraj, scores each one 0–100 against the family's needs with a short explanation, and shows every listing with its photos, a map, and rush-hour drive times to the places that matter: one school, one workplace, one university and King Khalid International Airport. It learns from what the family saves and rejects, and it plans in-person visit trips that group liked homes by district.

The app is right-to-left Arabic throughout and is installable as a PWA. It has layouts for phone, iPad and desktop.

## Why I built it

My family is looking for a new home, and the search has been manual and exhausting. Every day someone scrolls through Aqar and Haraj, sees the same villa posted three times by three brokers, opens each listing to find out the size and age, pastes the location into Google Maps to guess the school run at 7 a.m., and sends screenshots to the family group. Then we lose track of which ones we liked, which ones we already rejected and why, and which sellers we've already called.

Nobody needed another listings site. We needed someone doing the tedious part for us: reading everything, remembering what we care about, and bringing back only the homes worth a look, with the reasons. بيتنا is that assistant, built for one family and nobody else.

## The problems it solves

| The pain | What بيتنا does |
|---|---|
| Listings are scattered across sites and repeated by different brokers | Pulls from Aqar and Haraj on a schedule and merges duplicates into one listing |
| Ads are messy: missing sizes, prices written in text, details buried in the description | Reads each ad, fills the gaps it can find in the text, and marks what's still unknown instead of guessing |
| "Is it close?" depends on traffic, not distance | Computes rush-hour drive times to the school, workplace, university and airport for every listing |
| Everyone weighs things differently, and the priorities are in people's heads | Turns the family's priorities into an explainable 0–100 score, and every score says why |
| You re-filter the same way every day | Hard filters (budget, districts, type, rooms, area) hide what's out of bounds, and only new or changed listings get flagged |
| You forget why you passed on a home | Rejects record a reason. The app learns from saves and rejects and suggests tweaks, such as "you keep rejecting old buildings, filter them out?" |
| Prices change and ads disappear quietly | Tracks price history, shows price-drop badges, and marks listings that were taken down |
| Visit days are chaotic | Groups liked homes by district into a visit trip with a driving order, time slots, WhatsApp links to each seller and a final check that the ads are still live |

## Features

**Finding and understanding homes**
- A daily feed of homes to buy in Riyadh, ranked by fit, with new and saved tabs
- One combined record per home, even when it's posted on several sites
- A detail page with a photo gallery, specs (unknown values are clearly labelled), the original description, and links back to the source ads
- A score seal on every listing, with "why this score?" listing what helped and what hurt
- A map with price pins and the family's places marked
- Rush-hour drive times to the school, workplace, university and King Khalid International Airport
- Price-drop badges and a "listing removed" chip

**Telling it what you want**
- A chat assistant in Arabic. You can say "نبي فيلا في النرجس أو الياسمين بحدود مليونين، والمدرسة أهم من الدوام" (we want a villa in Al Narjis or Al Yasmin for about two million riyals, and the school matters more than work), and it updates the preferences and answers with matching homes.
- A settings screen for places, hard filters and weights, with locks for the priorities you don't want it to change, plus a history of every change
- Learning from saves and rejects, which only suggests changes the family approves

**Deciding and visiting**
- A side-by-side comparison with the best value in each row highlighted
- Visit trips grouped by district, with a driving order, time slots, a contact status for each seller, a WhatsApp button and an "open in Google Maps" link
- A pre-visit check that flags listings whose price changed or that were taken down since the trip was planned

**Made for a family**
- One shared family login, Arabic and right-to-left everywhere, and readable Western digits
- Works on phone, iPad and desktop, and installs to the home screen
- Keeps working while the scraping Mac sleeps; new listings arrive when it wakes
- Monthly spending caps on OpenAI and Google, with live status in settings

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
  | M3 Agent, Haraj and dedupe | chat assistant, Haraj, duplicate merge, removed listings, price drops | merged |
  | M4 Learning and compare | learning from saves and rejects, suggestions, compare view | merged |
  | M5 Visits | visit trips grouped by district, contact tracking, pre-visit checks | planned |

- The design spec is in `docs/superpowers/specs/`, and the per-milestone plans are in `docs/superpowers/plans/`.
- UI work follows [docs/design-system.md](docs/design-system.md) and [docs/arabic-ui-rules.md](docs/arabic-ui-rules.md).

## Privacy

This repository is public, but the app and its data are private to one family.

- **No personal data in git.** Never commit API keys, cookies, `.env` files, the family's place coordinates, or seller contact details.
- **Fixtures are scrubbed.** Test fixtures pass through `scripts/scrub_fixture.py`, and CI runs a secrets scan on every PR.
- **Scraping stays polite and read-only.** Requests are paced and there is no login, and a source is paused rather than forced when it starts blocking.

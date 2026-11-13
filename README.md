# بيتنا · Home Finder

A private, Arabic-first PWA that helps my family find a home to **buy in Riyadh**. It gathers listings from Aqar and Haraj, scores each one against what we care about, shows rush-hour drive times to the places we go every day, learns from what we save and reject, and plans visit trips.

## Why

Our search was manual and exhausting. Every day someone scrolled Aqar and Haraj, saw the same villa posted by three brokers, opened each ad to find its size and age, pasted the location into Google Maps to guess the 7 a.m. school run, and shared screenshots in the family group. Then we'd lose track of what we liked, what we'd rejected and why, and which sellers we'd called.

We didn't need another listings site. We needed something to do the tedious part: read everything, remember our priorities, and bring back only the homes worth a look, with reasons.

## What it does

| Problem | What the app does |
|---|---|
| Listings scattered across sites, reposted by many brokers | Scrapes Aqar and Haraj on a schedule and merges duplicates |
| Messy ads with missing sizes and prices buried in text | Extracts what it can from the text and labels the rest as unknown |
| "Close" depends on traffic | Rush-hour drive times to the school, workplace, university and King Khalid International Airport |
| Priorities live in people's heads | An explainable 0–100 score per listing ("why 86?") from weights the family sets |
| Re-filtering every day | Hard filters (budget, districts, type, rooms, drive time, building age, street width), and only new or changed homes are flagged |
| Forgetting why you passed on a home | Reject reasons, learning from saves and rejects, and suggestions like "filter out buildings older than 20 years?" |
| Prices change and ads vanish | Price history, price-drop badges and "listing removed" chips |
| Chaotic visit days | Trips grouped by district, with driving order, time slots, WhatsApp links and a pre-visit check that the ads are still live |

The app also has:
- **An Arabic chat assistant.** You talk to it the way you'd talk to the family group. "We want a villa in Al Narjis or Al Yasmin for around two million, and the school matters more than work" updates the filters and weights and replies with the best matches as cards you can open. It can also explain a score, compare homes or plan a visit. Every change it makes shows up in the settings history, and replies stream in as they're written.
- **A map.** Price pins are coloured by score, with saved homes highlighted, and sit next to the school, work and university markers, so you can see at a glance which good matches cluster near the places that matter.
- **Compare.** Pick 2–4 homes for a side-by-side table of price, price per metre, size, rooms, building age and every drive time. The best value in each row is highlighted, and missing data is flagged rather than hidden.
- **Settings.** Set the four places, the hard filters and how much each factor matters. You can lock a weight so the learner leaves it alone, and see a history of every change, whether it came from you, the assistant or the learner. A status panel shows when each source last ran, whether the Mac worker is online, and any failed jobs.
- **One shared family login.** It works on phone (bottom tabs), iPad (sidebar, or a two-column grid in portrait) and desktop (list, map and chat side by side). It installs to the home screen and is right-to-left Arabic throughout, with Western digits for prices and times.

## How it works

### Scoring

Each listing goes through two steps, and both are plain code with no AI involved.

1. **Hard filters** decide whether a listing appears at all: budget, districts, property type, minimum bedrooms, maximum drive time to each place, maximum building age and minimum street width. An unknown value never fails a filter, so a listing isn't hidden just because the ad left something out.
2. **The score** rates every listing that passes on 18 factors, each turned into a number between 0 and 1:
   - drive time to school, work, university and the airport (10 minutes or less is perfect, 40 or more scores zero)
   - price against your budget
   - built and land area against your ideal size
   - building age, street width, how many streets it faces, which way it faces, and deed type
   - bedrooms, bathrooms, maid room, driver room, yard and elevator

   The score is the weighted average of those numbers, times 100. Factors the ad doesn't mention are left out instead of guessed, and they're listed as missing.

Every score comes with its breakdown: which factors pushed it up, which pulled it down, and what's unknown. That's what powers "why 86?" on the listing page. When preferences change, every listing is rescored straight away on the server, even if the Mac is asleep.

### Learning

Learning adjusts the weights from what the family actually does. Saves count as "liked" and rejects as "not liked". A visit rated 4–5 stars counts three times as much as a save, and a visit rated 1–2 counts three times as much as a reject.

- **When it runs:** after every 10 new reactions, and only once there are at least 5 likes and 5 dislikes.
- **How it learns:** on the Mac, a logistic regression finds which factors separate liked homes from rejected ones.
- **How carefully:** the weights move only 30% of the way toward what the model suggests, and each weight changes by at most 20% per run. Weights you've locked are never touched. Your overall emphasis stays the same, because it redistributes weight between factors instead of inflating it.
- **What you see:** every change lands in the settings history with an Arabic explanation, such as "closeness to the school became more important, based on how you reacted to listings".

Reject reasons feed **filter suggestions**, which are simple rules rather than a model. If at least 5 of the last 20 rejects share a reason, and the relevant value is known for at least 3 of them, the app proposes a filter. For example, "too old" leads to a maximum building age just under the median age of the rejected homes. It only proposes; nothing changes until someone taps "apply", and a dismissed suggestion stays hidden until 5 new rejects come in for that reason.

### The LLM and the LangGraph agent

The LLM handles two jobs that need reading and conversation. It never invents facts, and everything it says comes from the database through tools.

**1. Reading ads (worker, small model).** Listings are often missing fields that are written somewhere in the description, such as "inside staircase, driver room, 20 m street". For each listing, the worker asks the small model (`gpt-5-mini` by default) for only the fields that are still empty, using OpenAI structured outputs so the reply is checked JSON. Every value is cleaned and range-checked before it's saved. Anything the model can't find stays unknown.

Plain code runs before the model where possible: Haraj prices and areas are parsed with regular expressions. The model fills in only what's left.

**2. The assistant (server, large model).** The chat is a LangGraph agent built with LangChain's `create_agent`. It runs in a loop: the model reads the conversation, decides whether to call a tool, sees the result, and repeats until it can answer. Its tools are:

| Tool | What it does |
|---|---|
| `get_preferences`, `update_preferences` | read or change filters and weights (logged in the settings history like any other change) |
| `search_listings`, `get_listing`, `compare_listings` | query the database and return listing cards |
| `request_scrape` | queue a fresh scrape when results are thin |
| `get_filter_suggestions`, `apply_filter_suggestion` | show or apply the learner's suggestions |

Two more tools, `suggest_visit_trip` and `create_visit_trip`, plan visits. The system prompt is in Arabic and sets the ground rules:
- Speak Arabic.
- Never make up listings, prices or distances.
- Say "not mentioned" for missing values.
- Confirm every preference change in one sentence.

Conversations are saved with LangGraph's Postgres checkpointer, so a thread can be picked up on another device. Replies stream to the browser over server-sent events: words appear as they're written, and listing cards appear as soon as a tool returns them.

**Why an agent instead of a search form?** The family's needs come out naturally as sentences mixing filters, priorities and questions. One example is "we want a villa close to the school but not old, and what's the difference between this one and the last?" The agent turns that into precise tool calls, against the same scoring and filters as the rest of the app. It also explains the results, because it reads the score breakdowns instead of guessing.

**Why this split?** Scoring, filters and learning are deterministic, testable and free, so the app keeps working with no API key at all. The LLM is used only where language is the actual problem: messy ad text and free-form requests.

**Guardrails.** Every OpenAI call is metered against a monthly budget (`OPENAI_MONTHLY_CAP_USD`). When the budget runs out, the assistant says so and the rest of the app carries on. If the Mac worker is offline, the assistant can still run a small Aqar search from the server.

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
| M5 Visits | district trips, contact tracking, pre-visit checks | merged |

## Privacy

The repo is public, but the app and its data belong to one family.

- **Nothing personal goes in git.** No keys, cookies, `.env` files, place coordinates or seller contacts.
- **Fixtures are scrubbed.** CI runs a secrets scan on every PR.
- **Scraping is paced, read-only and done without logging in.** A source is paused, not forced, when it starts blocking.

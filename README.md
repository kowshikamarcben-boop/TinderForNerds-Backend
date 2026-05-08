# ProMatch — Backend API

FastAPI REST API powering the ProMatch professional networking platform. Handles auth, profiles, discovery/matching, real-time messaging, bookings, events, AI features, moderation, and admin tools.

---

## Stack

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | 0.115 | ASGI web framework |
| Pydantic v2 | 2.9 | Request/response validation |
| Supabase | 2.9 | PostgreSQL + Auth + Realtime + Storage |
| arq + Redis | — | Async background job queue |
| OpenAI SDK | — | AI features via OpenRouter |
| Sentry | — | Error monitoring |
| structlog | — | Structured JSON logging |
| python-jose | — | JWT verification |
| uvicorn | — | ASGI server |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py              # App factory, middleware, router registration
│   ├── config.py            # Settings from environment (pydantic-settings)
│   ├── deps.py              # FastAPI dependency injection (auth, DB)
│   ├── auth/                # JWT decode, Supabase session helpers
│   ├── db/                  # Supabase client factory
│   ├── models/              # Pydantic schemas (request/response bodies)
│   ├── services/            # Business logic layer
│   ├── worker/              # arq background job definitions
│   └── routers/
│       ├── admin.py         # Report queue, event review, suspend
│       ├── ai.py            # Bio rewrite, interest suggest, icebreaker
│       ├── availability.py  # Availability slot CRUD
│       ├── bookings.py      # Booking request/confirm/cancel
│       ├── discovery.py     # Feed ranking, swipe feedback
│       ├── events.py        # Event CRUD, RSVP, attendees
│       ├── health.py        # /healthz /readyz /version
│       ├── likes.py         # Like/pass actions
│       ├── matches.py       # Match list, detail, close
│       ├── messages.py      # Message CRUD, read receipts
│       ├── moderation.py    # Reports, blocks
│       ├── notifications.py # Notification feed + mark read
│       ├── profiles.py      # Profile CRUD, interests, links, projects
│       └── users.py         # /me endpoint, avatar upload
├── schema.sql               # Full Supabase database schema (20 tables)
├── requirements.txt         # Python dependencies
├── render.yaml              # Render deployment config
├── tests/                   # Pytest test suite
└── TEST.md                  # Manual test checklist
```

---

## Setup

### Prerequisites

- Python 3.12+
- A Supabase project (URL + anon key + service role key)
- Redis (optional — background jobs degrade gracefully without it)

### Install

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment

Create a `.env` file in `backend/`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
OPENROUTER_API_KEY=sk-or-v1-...
REDIS_URL=redis://localhost:6379        # optional
SENTRY_DSN=                             # optional
APP_ENV=development
ALLOWED_ORIGINS=http://localhost:5173
```

### Run

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs` (development only).

### Background worker (optional)

```bash
python -m arq app.worker.WorkerSettings
```

---

## API Overview

All authenticated routes require a Supabase JWT in `Authorization: Bearer <token>`.

| Router | Endpoints | Notes |
|---|---|---|
| `/api/v1/me` | Profile, avatar, interests, links, projects | Auth required |
| `/api/v1/profiles` | Public profile view, badges, availability | Mostly public |
| `/api/v1/discovery` | Feed ranking, swipe feedback | Auth required |
| `/api/v1/likes` | Like/pass, received likes | Auth required |
| `/api/v1/matches` | Match list, detail, close | Auth required |
| `/api/v1/matches/:id/messages` | Chat CRUD, read receipts | Auth required |
| `/api/v1/availability` | Slot manager | Auth required |
| `/api/v1/bookings` | Booking CRUD, status updates | Auth required |
| `/api/v1/events` | Event CRUD, RSVP | Some public |
| `/api/v1/moderation` | Reports, blocks | Auth required |
| `/api/v1/notifications` | Feed, mark read | Auth required |
| `/api/v1/ai` | Bio rewrite, interest suggest, icebreaker | Auth required |
| `/api/v1/admin` | Reports queue, event review, suspend | Admin role only |
| `/healthz` `/readyz` `/version` | Health checks | Public |

Total: **65+ endpoints** across 14 routers.

---

## Database

Schema defined in `schema.sql`, applied to Supabase. Key tables:

| Table | Purpose |
|---|---|
| `profiles` | User profiles, bio, role, intent |
| `interests` | Interest taxonomy |
| `profile_interests` | Many-to-many join |
| `profile_links` | GitHub, LinkedIn, portfolio links |
| `profile_projects` | User projects |
| `likes` | Like/pass actions |
| `matches` | Mutual matches |
| `messages` | Chat messages |
| `bookings` | Session booking requests |
| `availability_slots` | Recurring availability (rrule) |
| `events` | Community events |
| `event_rsvps` | RSVP records |
| `notifications` | Notification feed |
| `reports` | Moderation reports |
| `blocks` | User block records |

Row Level Security (RLS) enforced at the database level — users can only read/write their own rows.

---

## Background Jobs

When Redis is available, the worker handles:

- `embed_profile` — vector embedding for discovery ranking after profile edits
- `verify_github_link` — validate GitHub username, fetch contribution stats
- `booking_reminder` — send notification before a booking starts

All `enqueue()` calls are wrapped in try/except — the app runs fully without Redis; jobs are silently skipped.

---

## Tests

```bash
pytest tests/ -v
```

Manual test checklist: `TEST.md`.

---

## Deployment

Deployed on **Render** (Web Service + Worker). Config in `render.yaml`.

**Build command:** `pip install -r requirements.txt`
**Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set all environment variables in the Render dashboard. `APP_ENV=production` disables `/docs` and locks CORS to the Vercel frontend origin.

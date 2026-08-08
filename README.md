# Shevaani

English learning platform. Small-group discussions (the focus) plus one-to-one
sessions, on one scheduling engine.

- **Backend** — FastAPI, SQLAlchemy 2.0 async, Postgres, Redis, ARQ. Runs in Docker.
- **Frontend** — Next.js App Router, Tailwind v4, shadcn/ui. Runs natively.
- **Video** — Google Meet, minted via the Calendar API on the instructor's own account.
- **Payments** — Stripe (global) and Razorpay (India), behind one provider protocol.

Design decisions and the reasoning behind them: [docs/PLAN.md](docs/PLAN.md).

## Running it

The backend (Postgres, Redis, API, worker) runs in Docker. The frontend runs
natively. Two terminals:

```bash
cd backend && docker compose up --build
```

```bash
cd frontend && npm run dev
```

- Web — http://localhost:3000
- API docs — http://localhost:8000/docs

Migrations run automatically on `web` startup. `backend/.env` already exists with
generated secrets; if you ever recreate it from `.env.example`, regenerate
`JWT_SECRET` and `TOKEN_ENCRYPTION_KEY`:

```bash
python3 -c "import secrets, base64; print('JWT_SECRET=' + secrets.token_hex(32)); print('TOKEN_ENCRYPTION_KEY=' + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Create a superuser — there is deliberately no self-service path to that role:

```bash
make superuser
```

Emails are validated the same way the API validates them, so reserved domains
like `.local` are rejected. Use a real domain (`admin@shevaani.com`), or you'll
create an account that can never sign in.

A `Makefile` wraps the rest: `make logs`, `make psql`, `make instructor`,
`make credits email=you@example.com n=10`, `make revision m="…"`.

### Adding more UI components

The shadcn primitives used here are checked in. For anything else:

```bash
npx shadcn@latest add dialog dropdown-menu tabs sonner
```

Magic UI components install through the same CLI:

```bash
npx shadcn@latest add "https://magicui.design/r/border-beam"
```

## Booking rules

**Group discussions** are created by superusers in `/admin`. Everything is
editable — capacity, description, level band, price, prep material. A session
that hasn't reached `min_seats` two hours before it starts auto-cancels and
refunds every learner.

**One-to-one** sessions can only be booked between **07:00 and 19:00 IST**, and
each one keeps **an hour clear either side**. Both are configurable via
`ONE_ON_ONE_*` in `.env` — but note the buffer is also baked into a database
constraint, so changing it needs a migration (see
`alembic/versions/0001_initial_schema.py`).

**Instructors block their own time** at `/facilitator`. Blocked ranges are
removed from slot generation immediately. Creating a block over an already-booked
session is refused, naming the session in the way — cancelling someone's class as
a side effect of "I'm busy Tuesday" is not a decision this code makes on its own.

## Google Meet

The Meet REST API requires Google Workspace, which we don't use, so links are
minted as a side effect of creating a Calendar event
(`conferenceData.createRequest`) on the **instructor's own** Google account.
That is what makes them the actual meeting host — able to admit people from the
lobby, mute, and remove. Each instructor connects their account once at
`/facilitator`.

Learners are not added as calendar guests (consumer accounts have
guest-invitation limits), so they will land in the Meet lobby and the instructor
admits them. Join early.

Google is never called from the request path. Sessions commit first, then a
worker creates the event and fills in `session_meetings`. Failures are visible in
`/admin` with a retry button.

## Verified working

Exercised end to end against a live stack on 4 Aug 2026:

- migration applies; all four exclusion constraints, both partial indexes and the
  `shevaani_buffered_range` function exist in Postgres
- register / login / refresh with httpOnly cookies, CORS with credentials
- one-to-one slot generation respects the 07:00–19:00 IST window
- booking an 11:00 slot removes 10:00, 11:00 and 12:00 — the one-hour buffer
- booking outside the window is refused, including a session that *ends* past 19:00
- instructor blocking removes slots; blocking over a booked session is refused
  and names the session in the way
- a learner cannot book two overlapping sessions (caught by the DB constraint),
  nor the same session twice
- full session → waitlist; cancelling refunds the credit and promotes and charges
  the next person in line
- the join endpoint refuses non-enrolled users and out-of-window requests, and
  audits both
- the Meet worker fails visibly and non-retryably when an instructor has no
  Google connection, leaving the booking intact

Not exercised: the actual Google Calendar call (needs OAuth credentials),
payments (adapters are stubs), and email.

## Not done yet

Reminder emails, the Stripe and Razorpay adapters (the protocol and tables exist,
the implementations are stubs), recurring session series, and reviews. Tracked at
the bottom of [docs/PLAN.md](docs/PLAN.md).

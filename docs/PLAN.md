# Shevaani — plan and decision log

An English-learning platform. Two products sharing one scheduling engine:

- **Group discussion** (primary focus) — a session exists first, learners join it.
  Supply-driven, N seats, fills up or auto-cancels.
- **One-to-one** — a facilitator's availability exists first, a learner carves a
  slot out of it. Demand-driven.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | FastAPI + SQLAlchemy 2.0 async + Postgres | Booking correctness needs `TIMESTAMPTZ`, `tstzrange` exclusion constraints, partial unique indexes. |
| 2 | Next.js App Router + TypeScript | Server components fetch with a forwarded httpOnly cookie; no tokens in `localStorage`. |
| 3 | ARQ for background jobs | Async-native, Redis-backed, pairs with FastAPI. Not APScheduler — it breaks with >1 API instance. |
| 4 | Google Meet via **Calendar API**, not the Meet REST API | The Meet REST API requires Google Workspace. We are on consumer Gmail, so `spaces.create` and `conferenceRecords` are unavailable. |
| 5 | Calendar event created on the **facilitator's own** Google account | Makes them the real Meet host — they can admit from the lobby, mute, and remove. On a shared house account they would be a powerless participant. |
| 6 | Learners are **not** added as calendar attendees | Consumer Google accounts have guest-invitation limits, and patching the event per enrollment is a quota risk. Learners knock; the facilitator admits. |
| 7 | Attendance from join-clicks + facilitator confirmation | `conferenceRecords` is Workspace-only. The gated join endpoint gives an automatic signal; the facilitator corrects it after the session. |
| 8 | Stripe **and** Razorpay in v1 | Razorpay for India, Stripe for everyone else. One provider-agnostic `payment` table, two adapters. |
| 9 | Credits, not per-session checkout | Buy a pack, spend one per session. Encourages repeat attendance and makes refunds a ledger entry rather than a card refund. |
| 10 | Sessions published by superusers from a frontend admin | Simpler than facilitator self-scheduling — no approval flow, no payouts. Superusers are seeded from the backend CLI; there is no self-signup path to that role. |
| 11 | Facilitators block their own time | Slot generation subtracts blocks immediately. Creating a block over a booked session is **refused**, naming the session — silently cancelling someone's class as a side effect of "I'm busy Tuesday" is not a decision the system should make on its own. |
| 12 | Backend in Docker, frontend run natively | Compose owns Postgres, Redis, the API and the worker. `npm run dev` on the host keeps HMR fast and avoids a bind-mounted `node_modules`. |
| 13 | Tailwind v4 + shadcn/ui + Magic UI | shadcn tokens are wired in `app/globals.css` so `npx shadcn@latest add <component>` works with no edits. Magic UI effects are hand-written in CSS to keep a motion library out of the bundle. |

## Booking rules

**One-to-one**
- Bookable only inside **07:00–19:00 IST**. The whole session must fit in the
  window on a single IST day.
- **1 hour buffer** either side of a 1:1 session for that facilitator.
- Both rules are configurable (`ONE_ON_ONE_*` in `.env`) and enforced in
  `app/services/scheduling.py`, with a database backstop (below).

**Group discussion**
- Created and edited by superusers: topic, description, CEFR band, start time,
  duration, min/max seats, facilitator, price in credits.
- Seats are allocated under a row lock; overflow goes to a waitlist.
- A session under `min_seats` at T-2h auto-cancels and refunds credits.

## Correctness invariants (enforced in Postgres, not Python)

| Invariant | Mechanism |
|---|---|
| A facilitator is never double-booked | `EXCLUDE USING gist (facilitator_id WITH =, tstzrange(starts_at, ends_at) WITH &&) WHERE status <> 'cancelled'` |
| 1:1 sessions keep their 1h buffer | Second exclusion constraint over the buffered range, scoped to `kind = 'one_on_one'`. The range is built by `shevaani_buffered_range()` — `timestamptz + interval` is STABLE and Postgres rejects it in an index expression, so it is wrapped in a function declared IMMUTABLE. That is sound **only** for minute-based intervals, which are timezone-independent; never call it with days or months. |
| A learner is never in two sessions at once | Exclusion constraint on `booking (learner_id, tstzrange(starts_at, ends_at))`. Requires `starts_at`/`ends_at` denormalised onto `booking` — **any session reschedule must update its bookings in the same transaction.** |
| A learner books a session at most once | Partial unique index on `(session_id, learner_id) WHERE status <> 'cancelled'` |
| A facilitator's blocks never overlap each other | `EXCLUDE USING gist` on `facilitator_blocks (facilitator_id, tstzrange(starts_at, ends_at))` |
| Seats never oversell | `SELECT ... FOR UPDATE` on the session row, then count confirmed+pending bookings |
| Webhooks are idempotent | Unique index on `webhook_event (provider, event_id)`, insert-then-process |
| Credit balance is auditable | Append-only `credit_ledger`; balance is `SUM(delta)`. No mutable balance column. |

The service layer enforces the buffer between a 1:1 and *any* adjacent session;
the database backstop covers the 1:1↔1:1 case, which is the common one. An
exclusion constraint can filter which rows participate but cannot express an
asymmetric pair rule, hence the split.

## Third-party isolation

Google Calendar is the only hard external dependency in the booking path, so it
is kept **off** the request path entirely:

1. Superuser creates a session → row committed → job enqueued.
2. Worker creates the Calendar event with `conferenceData.createRequest`
   (`conferenceDataVersion=1`), reads back `hangoutLink`, writes `session_meeting`.
3. `session_meeting` is a separate table with `status` and `last_error`, so a
   Google failure is visible and retryable without touching the session.

The admin session list surfaces meeting status (`pending` / `ready` / `failed`)
with a retry action. This is the one thing in the system that can fail quietly.

The join URL is a bearer credential — it is never included in list or detail
serialisers, only served from `GET /api/v1/sessions/{id}/join` after checking
enrollment and the time window, and every access is logged.

## Phasing

| Phase | Scope | Status |
|---|---|---|
| 0 | Repo, Compose, auth + profiles, timezone plumbing, CI | scaffolded |
| 1 | Group sessions: admin CRUD, catalogue + filters, seat-locked booking, waitlist | scaffolded |
| 2 | Meet worker, gated join endpoint, reminder emails, attendance | worker + join done; email TODO |
| 3 | Credits ledger, Stripe + Razorpay adapters, cancellation policy, auto-cancel | ledger + models done; adapters TODO |
| 4 | One-to-one: slot generation, booking, facilitator time blocking | done |
| 5 | Reviews, learner progress, recurring series | not started |

## Open items

- Reminder + cancellation emails (Resend adapter is stubbed).
- Stripe and Razorpay adapters behind `PaymentProvider` (protocol defined,
  implementations are stubs). Remember: verify signatures against the **raw**
  request body, and Razorpay's webhook secret differs from its key secret.
- Recurring group series (one rule spawning weekly sessions).
- Rate limiting on the join endpoint.

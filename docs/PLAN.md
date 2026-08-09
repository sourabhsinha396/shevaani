# Shevaani — plan and decision log

An English-learning platform. Two products sharing one scheduling engine:

- **Group discussion** (primary focus) — a session exists first, learners join it.
  Supply-driven, N seats, fills up or auto-cancels.
- **One-to-one** — an instructor's availability exists first, a learner carves a
  slot out of it. Demand-driven.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | FastAPI + SQLAlchemy 2.0 async + Postgres | Booking correctness needs `TIMESTAMPTZ`, `tstzrange` exclusion constraints, partial unique indexes. |
| 2 | Next.js App Router + TypeScript | Server components fetch with a forwarded httpOnly cookie; no tokens in `localStorage`. |
| 3 | ARQ for background jobs | Async-native, Redis-backed, pairs with FastAPI. Not APScheduler — it breaks with >1 API instance. |
| 4 | Google Meet via **Calendar API**, not the Meet REST API | The Meet REST API requires Google Workspace. We are on consumer Gmail, so `spaces.create` and `conferenceRecords` are unavailable. |
| 5 | Calendar event created on the **instructor's own** Google account | Makes them the real Meet host — they can admit from the lobby, mute, and remove. On a shared house account they would be a powerless participant. |
| 6 | Learners are **not** added as calendar attendees | Consumer Google accounts have guest-invitation limits, and patching the event per enrollment is a quota risk. Learners knock; the instructor admits. |
| 7 | Attendance from join-clicks + instructor confirmation | `conferenceRecords` is Workspace-only. The gated join endpoint gives an automatic signal; the instructor corrects it after the session. |
| 8 | Stripe **and** Razorpay in v1 | Razorpay for India, Stripe for everyone else. One provider-agnostic `payment` table, two adapters. |
| 9 | Credits, not per-session checkout | Buy a pack, spend one per session. Encourages repeat attendance and makes refunds a ledger entry rather than a card refund. |
| 10 | Sessions published by superusers from a frontend admin | Simpler than instructor self-scheduling — no approval flow, no payouts. Superusers are seeded from the backend CLI; there is no self-signup path to that role. |
| 11 | Instructors block their own time | Slot generation subtracts blocks immediately. Creating a block over a booked session is **refused**, naming the session — silently cancelling someone's class as a side effect of "I'm busy Tuesday" is not a decision the system should make on its own. |
| 12 | Backend in Docker, frontend run natively | Compose owns Postgres, Redis, the API and the worker. `npm run dev` on the host keeps HMR fast and avoids a bind-mounted `node_modules`. |
| 13 | Tailwind v4 + shadcn/ui + Magic UI | shadcn tokens are wired in `app/globals.css` so `npx shadcn@latest add <component>` works with no edits. Magic UI effects are hand-written in CSS to keep a motion library out of the bundle. |
| 14 | Two admins: sqladmin at `:8000/admin`, the operational UI at `:3000/admin` | Different jobs. The data plane answers "what does the row actually say", and is read-only wherever the schema demands it. The operational UI runs the business and never exposes a table. Merging them would mean either a raw-table view with dangerous edits, or an operational screen that can't answer support questions. |
| 15 | Instructors and superusers share the `/admin` shell | One app, role-dependent tabs. The boundary is enforced per endpoint — instructor routes derive the instructor from the session and never accept an id from the client — so hiding a tab is only ever presentation. |
| 16 | Policy pages written against actual behaviour | The refund page names the real 12-hour cutoff and the real T-2h auto-cancel, because Razorpay's review rejects boilerplate and because a learner reading it should get the same answer the code gives. If either setting changes, the page changes with it. |
| 17 | Email verification is advisory — it never gates booking | Credits are bought before they are spent, so refusing a booking over an unconfirmed address takes the money and then withholds the thing it buys. What an unverified address actually costs is reminders and joining links, and that lands on the learner who typed it — so the response is a banner with a resend, not a wall. Nothing is confirmed at signup either; the link is sent and ignored if unopened. |

## Booking rules

**One-to-one**
- Bookable only inside **07:00–19:00 IST**. The whole session must fit in the
  window on a single IST day.
- **1 hour buffer** either side of a 1:1 session for that instructor.
- Both rules are configurable (`ONE_ON_ONE_*` in `.env`) and enforced in
  `app/services/scheduling.py`, with a database backstop (below).

**Group discussion**
- Created and edited by superusers: topic, description, CEFR band, start time,
  duration, min/max seats, instructor, price in credits.
- Seats are allocated under a row lock; overflow goes to a waitlist.
- A session under `min_seats` at T-2h auto-cancels and refunds credits.

## Correctness invariants (enforced in Postgres, not Python)

| Invariant | Mechanism |
|---|---|
| An instructor is never double-booked | `EXCLUDE USING gist (instructor_id WITH =, tstzrange(starts_at, ends_at) WITH &&) WHERE status <> 'cancelled'` |
| 1:1 sessions keep their 1h buffer | Second exclusion constraint over the buffered range, scoped to `kind = 'one_on_one'`. The range is built by `shevaani_buffered_range()` — `timestamptz + interval` is STABLE and Postgres rejects it in an index expression, so it is wrapped in a function declared IMMUTABLE. That is sound **only** for minute-based intervals, which are timezone-independent; never call it with days or months. |
| A learner is never in two sessions at once | Exclusion constraint on `booking (learner_id, tstzrange(starts_at, ends_at))`. Requires `starts_at`/`ends_at` denormalised onto `booking` — **any session reschedule must update its bookings in the same transaction.** |
| A learner books a session at most once | Partial unique index on `(session_id, learner_id) WHERE status <> 'cancelled'` |
| An instructor's blocks never overlap each other | `EXCLUDE USING gist` on `instructor_blocks (instructor_id, tstzrange(starts_at, ends_at))` |
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
enrollment and the time window, and every access is logged. It is also never in
an email, never in a Slack message, and never in a rendered page: those are the
three places somebody would otherwise put it for convenience. The endpoint is
rate limited per user *and* per IP, because logging an enumeration attempt is
not the same as stopping one.

## Phasing

| Phase | Scope | Status |
|---|---|---|
| 0 | Repo, Compose, auth + profiles, timezone plumbing, CI | scaffolded |
| 1 | Group sessions: admin CRUD, catalogue + filters, seat-locked booking, waitlist | scaffolded |
| 2 | Meet worker, gated join endpoint, reminder emails, attendance | done; the live Google call still needs credentials |
| 3 | Credits ledger, Stripe + Razorpay adapters, cancellation policy, auto-cancel | done; adapters need live keys to exercise |
| 4 | One-to-one: slot generation, booking, instructor time blocking | done |
| 5 | Reviews, learner progress, recurring series | not started |
| — | Admin surfaces (frontend operations + sqladmin data plane), legal and static pages | done |
| — | Operations: email, Slack, rate limiting, backups, SEO, docs masking | done |

## Later decisions

| # | Decision | Rationale |
|---|---|---|
| 17 | Email and Slack both split `dispatch` (enqueue) from `deliver` (network) | Nothing that talks to a third party may sit on a request path. A slow provider would otherwise make every signup slow, and an outage would turn a password reset into a 500 that also reveals whether the address exists. |
| 18 | Reminders are claimed in `session_reminders` before they are sent | A time-window query alone double-sends on a restart or an overlapping run, and the failure is invisible until a learner complains. A unique constraint makes it a database error instead of an inbox event, and answers "did we remind them?" afterwards. |
| 19 | Reminders read the session at send time | A job enqueued at publish time with the start baked in will cheerfully remind everyone about a session that has since moved. |
| 20 | Webhook amount is re-checked against our `payments` row | The event says what the provider charged; the row says what the buyer agreed to. Granting credits on a mismatch is paying out on someone else's arithmetic. |
| 21 | Rate limiting fails **open** | Redis is already visible when it dies — the worker stops with it. Failing closed would lock paying learners out of sessions to prevent an abuse that is not happening. |
| 22 | Anything that leaks internals keys off `is_local`, not `!= production` | A staging box gets the production treatment by default rather than by somebody remembering to set a flag. |
| 23 | An `invalid_grant` from Google **retires** the instructor's connection | The alternative is every future session for that instructor failing five times each, forever, while `can_host` keeps saying yes and superusers keep publishing sessions that cannot get a room. |
| 24 | Discussions are publicly indexable; instructors and seat counts are not | Topic, level band, schedule and price are what a stranger deciding whether to book wants. A named person tied to a public timetable is a fact about them, not about the product, and they did not sign up to be indexed. |

## Open items

- Recurring group series (one rule spawning weekly sessions).
- Reviews and learner progress (phase 5).
- Google OAuth credentials and the live end-to-end check — the one thing
  standing between this and a working product. See `docs/GOOGLE_MEET.md`,
  including the seven-day refresh-token trap on an unpublished app.
- Live payment keys, and one real purchase through each provider.

# Google Meet: setup, verification, and the live check

The code path is built and has never made a real Google call. This is what turns
it on, and what to expect from the part that catches people out.

Why it is shaped the way it is — Calendar API rather than the Meet REST API,
events on the instructor's own account, learners not invited as guests — is
PLAN decisions 4–6. Read those first; none of it is arbitrary and changing any
of it changes what an instructor can do in the meeting.

## 1. The Google Cloud project

1. Create a project at <https://console.cloud.google.com/>. One project, named
   for the product, not for a person's Google account.
2. **Enable the Google Calendar API.** Not the Meet API — we cannot use it, and
   enabling it will mislead the next person.
3. Configure the OAuth consent screen:
   - User type: **External**. Instructors sign in with consumer Gmail accounts;
     Internal requires Workspace, which we do not have (PLAN decision 4).
   - App name, support email, and a logo. These appear on the consent screen an
     instructor sees, so they should say Shevaani, not a personal address.
   - Authorised domain: the production frontend domain.
   - Links to the privacy policy (`/privacy`) and terms (`/terms`). Both exist
     and both describe what actually happens, which matters for step 3 below.
4. Scopes — **exactly these three**, and nothing wider:

   | Scope | Why |
   |---|---|
   | `https://www.googleapis.com/auth/calendar.events` | Create, move and delete the events that carry the Meet link. |
   | `openid` | Identifies the account being connected. |
   | `email` | Stored as `google_credentials.google_email`, so admin can show *which* account is connected. |

   Notably **not** `calendar` (full calendar read/write) — we never read an
   instructor's other events, and asking for the ability to would be both a
   worse consent screen and a slower review.

5. Create an **OAuth client ID** of type *Web application*, with the redirect
   URI set to `<API origin>/api/v1/instructors/google/callback`. It must match
   `GOOGLE_REDIRECT_URI` byte for byte — Google compares it as a string.
6. Put the client id and secret in the backend `.env`.

## 2. The verification decision — read this one

This is the item most likely to bite, and it is a decision, not a step.

An OAuth app in **Testing** mode issues refresh tokens that **expire after seven
days**. Nothing announces this. What happens is that instructors connect, it
works, and a week later every session they host starts failing to get a Meet
link — which now surfaces as a retired connection, an email to the instructor
and a Slack line (see below), but is still a weekly outage nobody wants.

There are three ways out, and the right one depends on how many instructors
there are:

| Option | Refresh tokens | Cost | When it fits |
|---|---|---|---|
| **Testing** + test users | Expire after 7 days | None | Never, beyond a first manual trial |
| **Published**, unverified, sensitive scopes only | Do not expire | None | **Our case.** `calendar.events` is a *sensitive* scope, not a *restricted* one, so publishing does not require the security assessment |
| **Published + verified** | Do not expire | Review, days to weeks | Needed if the scope set ever widens to restricted scopes, or to remove the "unverified app" interstitial |

**Decision: publish the app, do not pursue full verification yet.**

`calendar.events` is classed sensitive rather than restricted, which means
publishing the app is enough to stop the seven-day expiry, and the third-party
security assessment — the expensive part of verification — does not apply. The
cost is an "Google hasn't verified this app" interstitial that instructors click
through once, on an internal tool used by a handful of people who were told to
expect it. Verification becomes worth doing when instructors are being onboarded
by someone other than us, or if the scope set ever has to widen.

To publish: OAuth consent screen → **Publish app**. Confirm afterwards that a
freshly connected account still works more than seven days later; that is the
only real proof the expiry is gone.

## 3. What happens when a refresh fails

Implemented, and worth knowing before it happens:

* A refresh that comes back `invalid_grant` (revoked access, changed password,
  expired grant) **retires the connection** — `google_credentials.revoked_at` is
  set. It is not retried forever.
* `User.can_host` then returns False, so a superuser trying to publish a session
  for that instructor is refused with a message naming them, rather than
  publishing a session that quietly has no room.
* The instructor gets an email telling them to reconnect, and Slack gets a line.
* Reconnecting is `/instructor` → Connect Google. It writes a new credential and
  clears `revoked_at`.

A refresh that fails with 429 or 5xx is transient and keeps its ARQ retry. Only
400 retires the connection — the distinction is the whole point.

The same retirement happens if the stored ciphertext cannot be decrypted, which
is what a rotated `TOKEN_ENCRYPTION_KEY` looks like from the worker's side.
Rotating that key invalidates every stored refresh token; every instructor has
to reconnect. Plan the rotation, do not discover it.

## 4. The live check

None of the above proves anything until this has been done once, with real
accounts. The system has never made a successful Google call.

1. `TOKEN_ENCRYPTION_KEY` is set. Without it `/google/connect` refuses up front,
   deliberately — better than taking someone's authorisation and dropping it.
2. Sign in as an instructor, go to `/instructor`, connect a real Google account.
   `/api/v1/instructors/google/status` should report `connected: true` and the
   right address.
3. As a superuser, create and publish a group session for that instructor.
4. Watch the worker (`make logs`). `sync_session_meeting` should end `ready`.
5. Check the instructor's Google Calendar: the event is there, on **their**
   calendar, with a Meet link — and they are the organiser. If they are not the
   organiser, the wrong account was connected and lobby admission will not work.
6. In the admin session list, meeting status should be `ready`. Confirm
   `session_meeting.join_url` is populated.
7. Book the session as a learner on a second account. From T-15m, the join
   endpoint should return the link.
8. **Actually join, from both accounts.** The learner should land in the lobby
   and the instructor should be able to admit them. This is the step that
   validates decisions 5 and 6 together, and it is the one most tempting to skip.
9. Reschedule the session from the admin. The Calendar event should move, and
   the Meet link should stay the same.
10. Cancel it. The event should disappear from the instructor's calendar.

Steps 5 and 8 are the ones that fail if anything about the account setup is
wrong. Everything else can pass with a misconfigured account.

## 5. What still cannot be done

`conferenceRecords` is Workspace-only, so there is no automatic attendance from
Google. Attendance is join-clicks plus the instructor's confirmation
(PLAN decision 7). This does not change by verifying the app; it changes only by
moving to Google Workspace, which is a different decision entirely.

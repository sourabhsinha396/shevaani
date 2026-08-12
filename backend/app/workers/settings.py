from __future__ import annotations

import logging

from arq import cron, func
from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.jobs import (
    auto_cancel_underfilled_sessions,
    backup_database,
    delete_calendar_event,
    dispatch_notetakers,
    finalize_session_feedback,
    generate_session_feedback,
    ingest_fireflies_transcript,
    mark_sessions_completed,
    post_slack_message,
    remove_session_meeting,
    retry_pending_meetings,
    send_email,
    send_session_reminders,
    sweep_expired_holds,
    sweep_review_transcripts,
    sync_session_meeting,
)

# ARQ configures its own logger and nothing else's, so without this every
# `logger.info` from application code inside a job is discarded. That is not a
# cosmetic loss: with no email provider configured the worker log *is* the
# inbox, and a reset link nobody can read makes the flow untestable.
logging.basicConfig(level=logging.INFO)

#: pg_dump of a growing database will not finish inside the 60s default, and a
#: backup killed halfway is worse than none — it looks like one until restored.
_BACKUP_TIMEOUT = 1800

#: One model call over a full hour's transcript. Minutes, not seconds — the
#: 60s job default would kill every generation mid-flight.
_FEEDBACK_TIMEOUT = 600


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    functions = [
        sync_session_meeting,
        remove_session_meeting,
        delete_calendar_event,
        retry_pending_meetings,
        sweep_expired_holds,
        auto_cancel_underfilled_sessions,
        mark_sessions_completed,
        send_session_reminders,
        send_email,
        post_slack_message,
        dispatch_notetakers,
        ingest_fireflies_transcript,
        sweep_review_transcripts,
        func(generate_session_feedback, timeout=_FEEDBACK_TIMEOUT),
        func(finalize_session_feedback, timeout=_FEEDBACK_TIMEOUT),
        # One attempt. A backup that failed for a real reason — no disk, bad
        # credentials, a dead bucket — fails identically five times, and each
        # one posts to Slack. Tomorrow's run is the retry.
        func(backup_database, timeout=_BACKUP_TIMEOUT, max_tries=1),
    ]

    cron_jobs = [
        # auto_cancel_underfilled_sessions is deliberately NOT scheduled:
        # under-filled sessions are cancelled manually for now. It stays in
        # `functions` above so it can still be enqueued by hand.
        # dispatch_notetakers is deliberately NOT scheduled either: the admin
        # session page has an "Invite notetaker" button that sends the bot on
        # demand, which suits a volume where someone is in the room anyway.
        # Likewise retry_pending_meetings — the "Retry Meet" button covers it,
        # at the cost of a failed Meet waiting for a human to notice the badge.
        # Both stay in `functions` so they can be enqueued by hand.
        cron(sweep_expired_holds, minute={5, 35}),
        cron(mark_sessions_completed, minute={20, 50}),
        # The admin-review loop: sqladmin edits can't enqueue jobs, this can.
        cron(sweep_review_transcripts, minute={8, 38}),
        # Every ten minutes, against a twenty-minute lateness tolerance, so a
        # brief worker outage delays a reminder rather than losing it. Sending
        # twice is prevented by `session_reminders`, not by this schedule.
        cron(send_session_reminders, minute={0, 10, 20, 30, 40, 50}),
        # Nightly, and deliberately not on the hour: everyone's cron runs at
        # :00 and the database has better things to do at midnight.
        cron(
            backup_database,
            hour={settings.backup_hour_utc},
            minute={7},
            timeout=_BACKUP_TIMEOUT,
            max_tries=1,
        ),
    ]

    # A failed Google call backs off rather than hammering the API.
    max_tries = 5
    retry_jobs = True
    job_timeout = 60

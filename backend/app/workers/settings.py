from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.jobs import (
    auto_cancel_underfilled_sessions,
    mark_sessions_completed,
    remove_session_meeting,
    retry_pending_meetings,
    sweep_expired_holds,
    sync_session_meeting,
)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    functions = [
        sync_session_meeting,
        remove_session_meeting,
        retry_pending_meetings,
        sweep_expired_holds,
        auto_cancel_underfilled_sessions,
        mark_sessions_completed,
    ]

    cron_jobs = [
        # Under-filled sessions must be cancelled well before they start.
        cron(auto_cancel_underfilled_sessions, minute={0, 15, 30, 45}),
        cron(sweep_expired_holds, minute={5, 35}),
        cron(retry_pending_meetings, minute={10, 40}),
        cron(mark_sessions_completed, minute={20, 50}),
    ]

    # A failed Google call backs off rather than hammering the API.
    max_tries = 5
    retry_jobs = True
    job_timeout = 60

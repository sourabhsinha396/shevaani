from __future__ import annotations


class DomainError(Exception):
    """Base for errors that map onto a 4xx rather than a 500."""

    status_code = 400
    code = "domain_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class PermissionDenied(DomainError):
    status_code = 403
    code = "permission_denied"


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class SchedulingError(DomainError):
    """Outside the booking window, inside a block, or too close to another session."""

    status_code = 422
    code = "scheduling_error"


class SessionFull(Conflict):
    code = "session_full"


class InsufficientCredits(Conflict):
    code = "insufficient_credits"


class MeetingNotReady(DomainError):
    status_code = 202
    code = "meeting_not_ready"


class OutsideJoinWindow(Conflict):
    code = "outside_join_window"

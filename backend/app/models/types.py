from __future__ import annotations

import enum

from sqlalchemy import Enum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Postgres enum that stores the *value* ("learner"), not the member name ("LEARNER").

    Without ``values_callable`` SQLAlchemy persists member names, which then disagree
    with every string that appears in the API and in hand-written SQL.
    """
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda cls: [member.value for member in cls],
        native_enum=True,
    )

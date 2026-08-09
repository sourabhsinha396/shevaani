from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import BlockReason
from app.models.types import pg_enum
from app.models.user import User


class InstructorBlock(Base, UUIDPrimaryKey, Timestamped):
    """Time an instructor has marked unavailable. One-to-one slot generation
    subtracts these, and booking rejects anything that lands inside one.

    Blocks are hard: they win over the standard booking window. Existing bookings
    are *not* retroactively cancelled when a block is created — the API refuses to
    create a block that overlaps a live session and tells the instructor which
    session is in the way, so the decision to cancel stays explicit.
    """

    __tablename__ = "instructor_blocks"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        # Overlapping blocks for one instructor are meaningless; collapse at write time.
        # (The GiST exclusion constraint is added in the migration.)
    )

    instructor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[BlockReason] = mapped_column(
        pg_enum(BlockReason, "block_reason"), nullable=False, default=BlockReason.BUSY
    )
    note: Mapped[str | None] = mapped_column(Text)

    #: Superusers can block on an instructor's behalf; keep the audit trail.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    instructor: Mapped[User] = relationship(foreign_keys=[instructor_id])

    def __str__(self) -> str:
        return f"{self.reason.value} · {self.starts_at:%d %b %H:%M}–{self.ends_at:%H:%M} UTC"

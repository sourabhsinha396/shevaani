from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPrimaryKey


class ImpromptuTopic(Base, UUIDPrimaryKey, Timestamped):
    """One prompt in the free impromptu-speaking tool's bank.

    ``category`` and ``track`` are display strings, not enum slugs, on purpose:
    the whole point of putting the bank in a table is that new verticals ("Bank
    PO", "NEET counselling") get added from sqladmin as plain rows, with no
    migration and no frontend label map to keep in sync. The frontend renders
    whatever distinct values it finds.

    - ``category`` is the *style* of prompt — "Everyday things", "Hot takes",
      "Interview classics" — the axis a casual visitor filters on.
    - ``track`` is the *audience* — "General", "MBA", "Cabin crew", "IELTS",
      "Visa interview" — the axis behind the tool's advanced settings.
    - ``difficulty`` is a spare filter axis, nullable because most topics have
      no meaningful grade. The frontend only offers the filter where values
      actually exist, so leaving it empty costs nothing.

    ``is_active`` is the kill switch: a topic that turned out to be a dud is
    switched off, not deleted, so re-adding it later doesn't trip the unique
    constraint on text.
    """

    __tablename__ = "impromptu_topics"
    __table_args__ = (UniqueConstraint("text", name="uq_impromptu_topics_text"),)

    text: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    track: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True, default="General"
    )
    difficulty: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Orders the track chips on the tool — lower first, ranked by how many
    #: people are searching for that kind of practice. Per-track by convention
    #: (every row in a track carries the same value); the API sorts by it and
    #: the frontend renders tracks in the order they arrive.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

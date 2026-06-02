"""Veritabanı modelleri (SQLAlchemy 2.0, mapped_column stili)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from app.config import EMBED_DIM


def _utcnow() -> datetime:
    """Zaman dilimi farkında UTC zaman damgası."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Tüm modellerin temel sınıfı."""


class Fault(Base):
    """Bir arıza kaydı (geçmiş vaka)."""

    __tablename__ = "faults"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    dtc_code: Mapped[str | None] = mapped_column(String(8), index=True, nullable=True)
    vehicle_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    # 1-1 ilişki: her arızanın bir embedding'i olur.
    embedding: Mapped["FaultEmbedding | None"] = relationship(
        back_populates="fault",
        cascade="all, delete-orphan",
        uselist=False,
    )


class FaultEmbedding(Base):
    """Bir arıza açıklamasının yoğun (dense) vektör temsili."""

    __tablename__ = "fault_embeddings"

    # fault_id hem PK hem FK; arıza silinince embedding de silinir.
    fault_id: Mapped[UUID] = mapped_column(
        ForeignKey("faults.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    fault: Mapped[Fault] = relationship(back_populates="embedding")


class Feedback(Base):
    """Kullanıcının bir sonucun faydalı olup olmadığına dair geri bildirimi."""

    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    returned_fault_id: Mapped[UUID] = mapped_column(
        ForeignKey("faults.id", ondelete="CASCADE"),
        nullable=False,
    )
    was_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

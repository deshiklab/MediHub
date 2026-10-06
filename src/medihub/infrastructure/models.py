"""Relational records for events, delivery intents, and attempt history."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class EventRecord(Base):
    """Durable canonical event envelope plus indexed routing/provenance columns."""

    __tablename__ = "event_store"
    __table_args__ = (Index("ix_event_store_site_observed_at", "site_id", "observed_at"),)

    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(256), nullable=False)
    device_id: Mapped[str] = mapped_column(String(256), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    persisted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    delivery_intents: Mapped[list["DeliveryOutboxRecord"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    routing_holds: Mapped[list["RoutingHoldRecord"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AuditEventRecord(Base):
    """Append-only audit metadata with no observation payload or patient fields."""

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_site_occurred", "site_id", "occurred_at"),
        Index("ix_audit_event_correlation", "correlation_id"),
        Index("ix_audit_event_resource", "resource_type", "resource_id"),
    )

    audit_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(256), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(256), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(256))
    reason_code: Mapped[str | None] = mapped_column(String(128))


class RoutingHoldRecord(Base):
    """Durable policy hold without payload text or any automatic resolution state."""

    __tablename__ = "routing_hold"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "destination_id",
            name="uq_routing_hold_event_destination",
        ),
        Index("ix_routing_hold_created_at", "created_at"),
        Index("ix_routing_hold_destination_created", "destination_id", "created_at"),
    )

    hold_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("event_store.event_id", ondelete="CASCADE"),
        nullable=False,
    )
    destination_id: Mapped[str] = mapped_column(String(256), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    event: Mapped[EventRecord] = relationship(back_populates="routing_holds")


class DeliveryOutboxRecord(Base):
    """One durable, idempotent delivery intent per event and destination."""

    __tablename__ = "delivery_outbox"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "destination_id",
            name="uq_delivery_outbox_event_destination",
        ),
        Index("ix_delivery_outbox_status_next_attempt", "status", "next_attempt_at"),
    )

    outbox_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("event_store.event_id", ondelete="CASCADE"),
        nullable=False,
    )
    destination_id: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", server_default=text("'queued'")
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(128))
    acknowledgement_id: Mapped[str | None] = mapped_column(String(256))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    event: Mapped[EventRecord] = relationship(back_populates="delivery_intents")
    attempts: Mapped[list["DeliveryAttemptRecord"]] = relationship(
        back_populates="outbox",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DeliveryAttemptRecord(Base):
    """Safe, correlated attempt history; free-text failure details are not persisted."""

    __tablename__ = "delivery_attempt"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        UniqueConstraint("outbox_id", "attempt_number", name="uq_attempt_outbox_number"),
        Index("ix_delivery_attempt_outbox_started", "outbox_id", "started_at"),
    )

    attempt_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    outbox_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("delivery_outbox.outbox_id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledgement_id: Mapped[str | None] = mapped_column(String(256))
    error_code: Mapped[str | None] = mapped_column(String(128))

    outbox: Mapped[DeliveryOutboxRecord] = relationship(back_populates="attempts")


__all__ = [
    "AuditEventRecord",
    "DeliveryAttemptRecord",
    "DeliveryOutboxRecord",
    "EventRecord",
    "RoutingHoldRecord",
]

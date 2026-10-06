"""SQLAlchemy event store with a leased, idempotent delivery outbox."""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medihub.domain import (
    ClaimedDelivery,
    DeliveryAttempt,
    DeliveryStatus,
    Destination,
    ObservationEvent,
)
from medihub.ports import EventStore, OutboxStore

from .models import DeliveryAttemptRecord, DeliveryOutboxRecord, EventRecord


class EventIdentityConflictError(ValueError):
    """An event ID was reused for content that differs from the stored event."""


class OutboxLeaseLostError(RuntimeError):
    """A claim expired or was superseded before its completion was recorded."""


class OutboxStateError(RuntimeError):
    """The persistent outbox violates an expected state invariant."""


def _canonical_payload(event: ObservationEvent) -> tuple[dict[str, object], str]:
    payload = event.model_dump(mode="json")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return payload, hashlib.sha256(encoded).hexdigest()


def _require_aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


class SqlAlchemyEventStore(EventStore, OutboxStore):
    """Persist events/intents atomically and coordinate at-least-once delivery."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def append_with_outbox(
        self,
        event: ObservationEvent,
        destinations: Sequence[Destination],
    ) -> bool:
        """Return whether a new event was committed; exact duplicates are no-ops.

        A duplicate event ID with different canonical content fails closed. Existing
        delivery intents are never silently expanded during a duplicate replay.
        """

        destination_ids = [destination.destination_id for destination in destinations]
        if len(destination_ids) != len(set(destination_ids)):
            raise ValueError("destination list contains duplicate destination IDs")

        payload, content_hash = _canonical_payload(event)
        try:
            async with self._sessions.begin() as session:
                existing = await session.get(EventRecord, event.event_id)
                if existing is not None:
                    self._ensure_same_content(existing, content_hash)
                    return False

                stored_event = EventRecord(
                    event_id=event.event_id,
                    site_id=event.site_id,
                    device_id=event.device.device_id,
                    origin=event.origin.value,
                    schema_version=event.schema_version,
                    observed_at=event.observed_at,
                    received_at=event.received_at,
                    canonical_content_sha256=content_hash,
                    payload=payload,
                )
                session.add(stored_event)
                session.add_all(
                    DeliveryOutboxRecord(
                        outbox_id=uuid4(),
                        event=stored_event,
                        destination_id=destination.destination_id,
                    )
                    for destination in destinations
                )
            return True
        except IntegrityError:
            # A concurrent writer may have committed the same event after our read.
            # Recheck after rollback; only an exact event replay is an idempotent no-op.
            async with self._sessions() as session:
                existing = await session.get(EventRecord, event.event_id)
            if existing is None:
                raise
            self._ensure_same_content(existing, content_hash)
            return False

    async def claim_next(
        self,
        *,
        destination_ids: Sequence[str],
        now: datetime,
        lease_for: timedelta,
    ) -> ClaimedDelivery | None:
        """Atomically lease the oldest eligible intent for one configured sender."""

        moment = _require_aware(now, "now")
        if lease_for <= timedelta(0):
            raise ValueError("lease_for must be positive")
        allowed_destinations = tuple(dict.fromkeys(destination_ids))
        if not allowed_destinations:
            return None

        due = and_(
            DeliveryOutboxRecord.status.in_(
                (DeliveryStatus.QUEUED.value, DeliveryStatus.RETRYABLE_FAILURE.value)
            ),
            or_(
                DeliveryOutboxRecord.next_attempt_at.is_(None),
                DeliveryOutboxRecord.next_attempt_at <= moment,
            ),
        )
        expired_lease = and_(
            DeliveryOutboxRecord.status == DeliveryStatus.SENT.value,
            DeliveryOutboxRecord.lease_expires_at.is_not(None),
            DeliveryOutboxRecord.lease_expires_at <= moment,
        )
        statement = (
            select(DeliveryOutboxRecord)
            .where(
                DeliveryOutboxRecord.destination_id.in_(allowed_destinations),
                or_(due, expired_lease),
            )
            .order_by(DeliveryOutboxRecord.created_at, DeliveryOutboxRecord.outbox_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        async with self._sessions.begin() as session:
            outbox = await session.scalar(statement)
            if outbox is None:
                return None

            if outbox.status == DeliveryStatus.SENT.value:
                previous_attempt = await session.scalar(
                    select(DeliveryAttemptRecord)
                    .where(
                        DeliveryAttemptRecord.outbox_id == outbox.outbox_id,
                        DeliveryAttemptRecord.attempt_number == outbox.attempt_count,
                    )
                    .with_for_update()
                )
                if previous_attempt is None or previous_attempt.status != DeliveryStatus.SENT.value:
                    raise OutboxStateError("expired outbox lease has no active attempt")
                previous_attempt.status = DeliveryStatus.RETRYABLE_FAILURE.value
                previous_attempt.completed_at = moment
                previous_attempt.error_code = "lease_expired"

            event_record = await session.get(EventRecord, outbox.event_id)
            if event_record is None:
                raise OutboxStateError("outbox event record is missing")
            try:
                event = ObservationEvent.model_validate(event_record.payload)
            except ValidationError:
                raise OutboxStateError("stored event payload failed schema validation") from None

            attempt_number = outbox.attempt_count + 1
            attempt_id = uuid4()
            lease_token = uuid4()
            lease_expires_at = moment + lease_for
            outbox.attempt_count = attempt_number
            outbox.status = DeliveryStatus.SENT.value
            outbox.next_attempt_at = None
            outbox.lease_token = lease_token
            outbox.lease_expires_at = lease_expires_at
            outbox.last_error_code = None
            session.add(
                DeliveryAttemptRecord(
                    attempt_id=attempt_id,
                    outbox_id=outbox.outbox_id,
                    attempt_number=attempt_number,
                    status=DeliveryStatus.SENT.value,
                    started_at=moment,
                )
            )
            return ClaimedDelivery(
                outbox_id=outbox.outbox_id,
                attempt_id=attempt_id,
                attempt_number=attempt_number,
                destination_id=outbox.destination_id,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
                started_at=moment,
                event=event,
            )

    async def complete(
        self,
        delivery: ClaimedDelivery,
        attempt: DeliveryAttempt,
        *,
        retry_at: datetime | None,
    ) -> None:
        """Persist one final attempt outcome and release its lease atomically."""

        self._validate_claim_attempt(delivery, attempt, retry_at)
        async with self._sessions.begin() as session:
            outbox = await session.get(DeliveryOutboxRecord, delivery.outbox_id)
            attempt_record = await session.get(DeliveryAttemptRecord, delivery.attempt_id)
            if outbox is None or attempt_record is None:
                raise OutboxLeaseLostError("claimed delivery no longer exists")
            if (
                outbox.status != DeliveryStatus.SENT.value
                or outbox.lease_token != delivery.lease_token
                or attempt_record.status != DeliveryStatus.SENT.value
            ):
                raise OutboxLeaseLostError("delivery lease was lost or superseded")

            attempt_record.status = attempt.status.value
            attempt_record.completed_at = attempt.completed_at
            attempt_record.acknowledgement_id = attempt.acknowledgement_id
            attempt_record.error_code = attempt.error_code

            outbox.last_error_code = attempt.error_code
            outbox.acknowledgement_id = None
            outbox.acknowledged_at = None
            if attempt.status is DeliveryStatus.ACKNOWLEDGED:
                outbox.status = DeliveryStatus.ACKNOWLEDGED.value
                outbox.acknowledgement_id = attempt.acknowledgement_id
                outbox.acknowledged_at = attempt.completed_at
                outbox.next_attempt_at = None
            elif attempt.status is DeliveryStatus.REJECTED:
                outbox.status = DeliveryStatus.REJECTED.value
                outbox.next_attempt_at = None
            elif attempt.status is DeliveryStatus.PERMANENT_FAILURE:
                outbox.status = DeliveryStatus.PERMANENT_FAILURE.value
                outbox.next_attempt_at = None
            elif retry_at is None:
                # The retry limit was reached; retain the last attempt's real outcome.
                outbox.status = DeliveryStatus.PERMANENT_FAILURE.value
                outbox.next_attempt_at = None
            else:
                outbox.status = DeliveryStatus.RETRYABLE_FAILURE.value
                outbox.next_attempt_at = _require_aware(retry_at, "retry_at")

            outbox.lease_token = None
            outbox.lease_expires_at = None

    @staticmethod
    def _ensure_same_content(existing: EventRecord, content_hash: str) -> None:
        if existing.canonical_content_sha256 != content_hash:
            raise EventIdentityConflictError(
                "event_id already exists with different canonical content"
            )

    @staticmethod
    def _validate_claim_attempt(
        delivery: ClaimedDelivery,
        attempt: DeliveryAttempt,
        retry_at: datetime | None,
    ) -> None:
        if (
            attempt.attempt_id != delivery.attempt_id
            or attempt.event_id != delivery.event.event_id
            or attempt.destination_id != delivery.destination_id
            or attempt.attempt_number != delivery.attempt_number
            or attempt.started_at != delivery.started_at
        ):
            raise ValueError("delivery attempt does not match its outbox claim")
        if attempt.status in {DeliveryStatus.QUEUED, DeliveryStatus.SENT}:
            raise ValueError("outbox completion requires a final delivery outcome")
        if retry_at is not None:
            retry_moment = _require_aware(retry_at, "retry_at")
            if attempt.status is not DeliveryStatus.RETRYABLE_FAILURE:
                raise ValueError("retry_at is valid only for a retryable failure")
            if retry_moment < attempt.completed_at:
                raise ValueError("retry_at must not precede attempt completion")

"""SQLAlchemy event store, transactional outbox, routing holds, and safe audit trail."""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from medihub.domain import (
    AuditAction,
    AuditEvent,
    BlockedRoute,
    ClaimedDelivery,
    DeliveryAttempt,
    DeliveryStatus,
    Destination,
    EventOrigin,
    ObservationEvent,
)
from medihub.ports import AuditStore, EventStore, OutboxStore

from .models import (
    AuditEventRecord,
    DeliveryAttemptRecord,
    DeliveryOutboxRecord,
    EventRecord,
    RoutingHoldRecord,
)


class EventIdentityConflictError(ValueError):
    """An event ID was reused for content that differs from the stored event."""


class OutboxLeaseLostError(RuntimeError):
    """A claim expired or was superseded before its completion was recorded."""


class OutboxStateError(RuntimeError):
    """The persistent outbox violates an expected state invariant."""


class SyntheticDeliveryReplayError(ValueError):
    """Safe rejection for replay controls limited to terminal synthetic intents."""

    def __init__(self, code: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


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


def _audit_event(
    *,
    site_id: str,
    actor_id: str,
    action: AuditAction,
    resource_type: str,
    resource_id: str,
    occurred_at: datetime,
    correlation_id: str,
    reason_code: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=uuid4(),
        site_id=site_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        reason_code=reason_code,
    )


def _utc_from_storage(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _audit_record(event: AuditEvent) -> AuditEventRecord:
    return AuditEventRecord(
        audit_id=event.event_id,
        site_id=event.site_id,
        actor_id=event.actor_id,
        action=event.action.value,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        occurred_at=_require_aware(event.occurred_at, "audit occurred_at"),
        correlation_id=event.correlation_id,
        reason_code=event.reason_code,
    )


class SqlAlchemyEventStore(EventStore, OutboxStore, AuditStore):
    """Persist event decisions, delivery transitions, and audit metadata atomically."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def append_with_outbox(
        self,
        event: ObservationEvent,
        destinations: Sequence[Destination],
        *,
        blocked_routes: Sequence[BlockedRoute] = (),
    ) -> bool:
        """Atomically commit a new event, eligible intents, and safe policy holds.

        A duplicate event ID with different canonical content fails closed. Existing
        delivery intents and blocked-route decisions are never silently changed during
        a duplicate replay.
        """

        destination_ids = [destination.destination_id for destination in destinations]
        destination_ids.extend(route.destination_id for route in blocked_routes)
        if len(destination_ids) != len(set(destination_ids)):
            raise ValueError("destination decisions contain duplicate destination IDs")

        payload, content_hash = _canonical_payload(event)
        try:
            async with self._sessions.begin() as session:
                existing = await session.get(EventRecord, event.event_id)
                if existing is not None:
                    self._ensure_same_content(existing, content_hash)
                    return False

                audit_occurred_at = datetime.now(UTC)
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
                audit_events = [
                    _audit_event(
                        site_id=event.site_id,
                        actor_id="system:ingestion",
                        action=AuditAction.EVENT_STORED,
                        resource_type="observation_event",
                        resource_id=str(event.event_id),
                        occurred_at=audit_occurred_at,
                        correlation_id=str(event.event_id),
                    )
                ]
                outbox_rows: list[DeliveryOutboxRecord] = []
                for destination in destinations:
                    outbox_id = uuid4()
                    outbox_rows.append(
                        DeliveryOutboxRecord(
                            outbox_id=outbox_id,
                            event=stored_event,
                            destination_id=destination.destination_id,
                        )
                    )
                    audit_events.append(
                        _audit_event(
                            site_id=event.site_id,
                            actor_id="system:ingestion",
                            action=AuditAction.DELIVERY_INTENT_CREATED,
                            resource_type="delivery_intent",
                            resource_id=str(outbox_id),
                            occurred_at=audit_occurred_at,
                            correlation_id=str(event.event_id),
                        )
                    )
                hold_rows: list[RoutingHoldRecord] = []
                for route in blocked_routes:
                    hold_id = uuid4()
                    hold_rows.append(
                        RoutingHoldRecord(
                            hold_id=hold_id,
                            event=stored_event,
                            destination_id=route.destination_id,
                            reason_code=route.reason_code,
                        )
                    )
                    audit_events.append(
                        _audit_event(
                            site_id=event.site_id,
                            actor_id="system:ingestion",
                            action=AuditAction.ROUTE_HELD,
                            resource_type="routing_hold",
                            resource_id=str(hold_id),
                            occurred_at=audit_occurred_at,
                            correlation_id=str(event.event_id),
                            reason_code=route.reason_code,
                        )
                    )
                session.add_all(outbox_rows)
                session.add_all(hold_rows)
                session.add_all(_audit_record(audit_event) for audit_event in audit_events)
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

    async def recent_audit_events(
        self,
        *,
        site_id: str,
        limit: int = 100,
    ) -> tuple[AuditEvent, ...]:
        """Read a bounded, site-filtered projection of audit metadata only."""

        normalized_site_id = site_id.strip()
        if not normalized_site_id:
            raise ValueError("site_id must not be empty")
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")
        async with self._sessions() as session:
            records = (
                await session.scalars(
                    select(AuditEventRecord)
                    .where(AuditEventRecord.site_id == normalized_site_id)
                    .order_by(
                        AuditEventRecord.occurred_at.desc(),
                        AuditEventRecord.audit_id.desc(),
                    )
                    .limit(limit)
                )
            ).all()
        return tuple(
            AuditEvent(
                event_id=record.audit_id,
                site_id=record.site_id,
                actor_id=record.actor_id,
                action=record.action,
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                occurred_at=_utc_from_storage(record.occurred_at),
                correlation_id=record.correlation_id,
                reason_code=record.reason_code,
            )
            for record in records
        )

    async def requeue_terminal_synthetic_delivery(
        self,
        event_id: UUID,
        destination_id: str,
        *,
        now: datetime,
        max_attempts: int,
    ) -> None:
        """Queue an explicit replay of a terminal, patient-free synthetic intent.

        Existing attempt rows and their attempt numbers are preserved. This is a
        local demo control, not a general outbox replay API.
        """

        moment = _require_aware(now, "now")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        async with self._sessions.begin() as session:
            outbox = await session.scalar(
                select(DeliveryOutboxRecord)
                .where(
                    DeliveryOutboxRecord.event_id == event_id,
                    DeliveryOutboxRecord.destination_id == destination_id,
                )
                .with_for_update()
            )
            event_record = await session.get(EventRecord, event_id)
            if (
                outbox is None
                or event_record is None
                or event_record.origin != EventOrigin.SYNTHETIC.value
            ):
                raise SyntheticDeliveryReplayError("synthetic_delivery_not_found", 404)
            try:
                event = ObservationEvent.model_validate(event_record.payload)
            except ValidationError:
                raise SyntheticDeliveryReplayError("synthetic_delivery_not_found", 404) from None
            if (
                event.event_id != event_id
                or event.origin is not EventOrigin.SYNTHETIC
                or event.patient is not None
                or event.encounter_reference is not None
            ):
                raise SyntheticDeliveryReplayError("synthetic_delivery_not_found", 404)
            if outbox.status not in {
                DeliveryStatus.REJECTED.value,
                DeliveryStatus.PERMANENT_FAILURE.value,
            }:
                raise SyntheticDeliveryReplayError("synthetic_delivery_not_terminal")
            if outbox.attempt_count >= max_attempts:
                raise SyntheticDeliveryReplayError("synthetic_delivery_retry_limit_reached")
            if outbox.lease_token is not None or outbox.lease_expires_at is not None:
                raise SyntheticDeliveryReplayError("synthetic_delivery_lease_active")

            outbox.status = DeliveryStatus.QUEUED.value
            outbox.next_attempt_at = moment
            outbox.acknowledgement_id = None
            outbox.acknowledged_at = None
            session.add(
                _audit_record(
                    _audit_event(
                        site_id=event.site_id,
                        actor_id="system:synthetic-workbench",
                        action=AuditAction.DELIVERY_REPLAYED,
                        resource_type="delivery_outbox",
                        resource_id=str(outbox.outbox_id),
                        occurred_at=moment,
                        correlation_id=str(event.event_id),
                        reason_code="operator_requested_synthetic_replay",
                    )
                )
            )

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

            expired_attempt_id = None
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
                expired_attempt_id = previous_attempt.attempt_id

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
            audit_events = []
            if expired_attempt_id is not None:
                audit_events.append(
                    _audit_record(
                        _audit_event(
                            site_id=event_record.site_id,
                            actor_id="system:outbox-worker",
                            action=AuditAction.DELIVERY_LEASE_EXPIRED,
                            resource_type="delivery_attempt",
                            resource_id=str(expired_attempt_id),
                            occurred_at=moment,
                            correlation_id=str(outbox.event_id),
                            reason_code="lease_expired",
                        )
                    )
                )
            audit_events.append(
                _audit_record(
                    _audit_event(
                        site_id=event_record.site_id,
                        actor_id="system:outbox-worker",
                        action=AuditAction.DELIVERY_ATTEMPT_STARTED,
                        resource_type="delivery_attempt",
                        resource_id=str(attempt_id),
                        occurred_at=moment,
                        correlation_id=str(outbox.event_id),
                    )
                )
            )
            session.add_all(audit_events)
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

            if attempt.status is DeliveryStatus.ACKNOWLEDGED:
                audit_action = AuditAction.DELIVERY_ACKNOWLEDGED
            elif attempt.status is DeliveryStatus.REJECTED:
                audit_action = AuditAction.DELIVERY_REJECTED
            elif attempt.status is DeliveryStatus.RETRYABLE_FAILURE and retry_at is not None:
                audit_action = AuditAction.DELIVERY_RETRY_SCHEDULED
            elif attempt.status is DeliveryStatus.RETRYABLE_FAILURE:
                audit_action = AuditAction.DELIVERY_RETRY_EXHAUSTED
            else:
                audit_action = AuditAction.DELIVERY_PERMANENT_FAILURE

            if attempt.completed_at is None:
                raise OutboxStateError("completed delivery attempt has no completion timestamp")
            session.add(
                _audit_record(
                    _audit_event(
                        site_id=delivery.event.site_id,
                        actor_id="system:outbox-worker",
                        action=audit_action,
                        resource_type="delivery_attempt",
                        resource_id=str(attempt.attempt_id),
                        occurred_at=attempt.completed_at,
                        correlation_id=str(delivery.event.event_id),
                        reason_code=attempt.error_code,
                    )
                )
            )

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

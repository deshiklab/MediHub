"""Synthetic-only runtime and safe read models for the operator dashboard."""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from medihub.adapters.destinations.fhir_r4 import SyntheticFhirR4DestinationAdapter
from medihub.adapters.destinations.synthetic_fault_injector import (
    SyntheticFaultInjectorError,
    SyntheticFaultMode,
    SyntheticReceiverFaultInjector,
)
from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.application.ingestion import IngestionService
from medihub.application.outbox_worker import OutboxWorker
from medihub.domain import (
    AdapterHealth,
    DeliveryStatus,
    Destination,
    DestinationProtocol,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
)
from medihub.infrastructure.database import Base, create_database_engine
from medihub.infrastructure.event_store import (
    SqlAlchemyEventStore,
    SyntheticDeliveryReplayError,
)
from medihub.infrastructure.models import (
    AuditEventRecord,
    DeliveryAttemptRecord,
    DeliveryOutboxRecord,
    EventRecord,
    RoutingHoldRecord,
)
from medihub.observability import RuntimeMetricsSnapshot

MAX_RETAINED_EVENTS = 500
PRUNE_EVERY_EVENTS = 50
MAX_DEMO_DELIVERY_ATTEMPTS = 5
TEST_RECEIVER_DESTINATION_ID = "medihub.synthetic-test-receiver"


class SyntheticOperationsError(ValueError):
    """Safe error code for the synthetic-only operator projection."""

    def __init__(self, code: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class SyntheticOperationsDashboard:
    """Generate synthetic events and expose an ephemeral, curated operations view.

    The runtime has no configurable database URL, device connection, or external
    destination. It uses an in-memory SQLite store and the in-process test receiver.
    Snapshot methods deliberately project a short allowlist of fields and never
    return the stored event payload wholesale.
    """

    def __init__(
        self,
        *,
        refresh_interval_seconds: float = 2.0,
        duplicate_every: int = 4,
        recent_limit: int = 12,
        max_retained_events: int = MAX_RETAINED_EVENTS,
        prune_every_events: int = PRUNE_EVERY_EVENTS,
    ) -> None:
        if not 0.1 <= refresh_interval_seconds <= 60:
            raise ValueError("refresh_interval_seconds must be between 0.1 and 60")
        if duplicate_every < 0:
            raise ValueError("duplicate_every must not be negative")
        if not 1 <= recent_limit <= 50:
            raise ValueError("recent_limit must be between 1 and 50")
        if not 1 <= max_retained_events <= 10_000:
            raise ValueError("max_retained_events must be between 1 and 10000")
        if not 1 <= prune_every_events <= max_retained_events:
            raise ValueError("prune_every_events must be between 1 and max_retained_events")

        self._refresh_interval_seconds = refresh_interval_seconds
        self._duplicate_every = duplicate_every
        self._recent_limit = recent_limit
        self._max_retained_events = max_retained_events
        self._prune_every_events = prune_every_events
        self._engine: AsyncEngine | None = None
        self._sessions: async_sessionmaker | None = None
        self._store: SqlAlchemyEventStore | None = None
        self._ingestion: IngestionService | None = None
        self._worker: OutboxWorker | None = None
        self._receiver: SyntheticFhirR4DestinationAdapter | None = None
        self._fault_injector: SyntheticReceiverFaultInjector | None = None
        self._destination: Destination | None = None
        self._blocked_destination: Destination | None = None
        self._generator_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._state_lock = asyncio.Lock()
        self._started_at: datetime | None = None
        self._source_health: AdapterHealth | None = None
        self._sequence = 0
        self._events_received = 0
        self._duplicate_events = 0
        self._last_error_code: str | None = None

    async def start(self) -> None:
        """Create ephemeral state, emit an initial sample, and start the live feed."""

        if self._engine is not None:
            raise RuntimeError("dashboard runtime is already started")

        engine = create_database_engine("sqlite+aiosqlite:///:memory:")
        self._engine = engine
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            self._sessions = async_sessionmaker(engine, expire_on_commit=False)
            self._store = SqlAlchemyEventStore(self._sessions)
            self._ingestion = IngestionService(self._store)
            self._destination = Destination(
                destination_id=TEST_RECEIVER_DESTINATION_ID,
                site_id="synthetic-site",
                name="MediHub in-process synthetic receiver",
                protocol=DestinationProtocol.FHIR_R4,
                contract_version="generic-r4-synthetic-observation-v1",
                connection_ref="in-process",
                enabled=True,
                accepts_synthetic_data=True,
            )
            self._blocked_destination = Destination(
                destination_id="medihub.synthetic-ineligible-route",
                site_id="synthetic-site",
                name="Policy test route that refuses synthetic events",
                protocol=DestinationProtocol.FHIR_R4,
                contract_version="synthetic-route-hold-v1",
                connection_ref="blocked-by-policy-before-transport",
                enabled=True,
                accepts_synthetic_data=False,
            )
            self._receiver = SyntheticFhirR4DestinationAdapter(
                self._destination,
                max_seen_event_ids=self._max_retained_events,
            )
            self._fault_injector = SyntheticReceiverFaultInjector(self._receiver)
            self._worker = OutboxWorker(
                self._store,
                {self._destination.destination_id: self._fault_injector},
                max_attempts=MAX_DEMO_DELIVERY_ATTEMPTS,
            )
            self._started_at = datetime.now(UTC)
            self._stop_event.clear()
            await self._ingest_cycle()
            self._generator_task = asyncio.create_task(self._run_live_feed())
        except BaseException:
            await engine.dispose()
            self._clear_runtime()
            raise

    async def stop(self) -> None:
        """Stop event generation and dispose of the in-memory database."""

        task = self._generator_task
        if task is not None:
            self._stop_event.set()
            await task
        if self._engine is not None:
            await self._engine.dispose()
        self._clear_runtime()

    async def health(self) -> dict[str, Any]:
        """Return a minimal readiness response without event or patient data."""

        async with self._state_lock:
            ready = (
                self._sessions is not None
                and self._source_health is not None
                and self._last_error_code is None
            )
            return {
                "status": "ready" if ready else "degraded",
                "mode": "synthetic_demo",
                "receiver": "in_process_test_sink",
            }

    async def metrics_snapshot(self) -> RuntimeMetricsSnapshot:
        """Return aggregate telemetry without exposing event or identity fields."""

        async with self._state_lock:
            if self._sessions is None:
                return RuntimeMetricsSnapshot()

            async with self._sessions() as session:
                event_count = await session.scalar(
                    select(func.count())
                    .select_from(EventRecord)
                    .where(EventRecord.origin == EventOrigin.SYNTHETIC.value)
                )
                status_rows = await session.execute(
                    select(DeliveryOutboxRecord.status, func.count()).group_by(
                        DeliveryOutboxRecord.status
                    )
                )
                delivery_counts = {status: 0 for status in DeliveryStatus}
                for status, count in status_rows:
                    delivery_counts[DeliveryStatus(status)] = int(count)

                attempts = await session.scalar(
                    select(func.coalesce(func.sum(DeliveryOutboxRecord.attempt_count), 0))
                )
                hold_count = await session.scalar(
                    select(func.count())
                    .select_from(RoutingHoldRecord)
                    .join(EventRecord, EventRecord.event_id == RoutingHoldRecord.event_id)
                    .where(EventRecord.origin == EventOrigin.SYNTHETIC.value)
                )
                audit_count = await session.scalar(
                    select(func.count())
                    .select_from(AuditEventRecord)
                    .where(AuditEventRecord.site_id == "synthetic-site")
                )

            source = self._source_health
            started_at = self._started_at
            return RuntimeMetricsSnapshot(
                ready=(self._source_health is not None and self._last_error_code is None),
                uptime_seconds=(
                    max(0.0, (datetime.now(UTC) - started_at).total_seconds())
                    if started_at is not None
                    else 0.0
                ),
                events_received=self._events_received,
                duplicate_events=self._duplicate_events,
                events_retained=int(event_count or 0),
                routing_holds_retained=int(hold_count or 0),
                audit_events_retained=int(audit_count or 0),
                delivery_attempts_retained=int(attempts or 0),
                delivery_counts=tuple(
                    (status, delivery_counts[status]) for status in DeliveryStatus
                ),
                unique_test_receipts=(
                    self._receiver.unique_receipt_count if self._receiver is not None else 0
                ),
                source_health=source.status if source is not None else None,
            )

    async def emit_synthetic_sample(self, device_id: str) -> dict[str, object]:
        """Emit one sample for a registered simulator into the local test sink only."""

        if re.fullmatch(r"sim-device-[0-9]{3}", device_id) is None:
            raise ValueError("only synthetic simulator IDs are allowed")
        async with self._state_lock:
            receiver = self._receiver
            if receiver is None or self._sessions is None:
                raise RuntimeError("dashboard runtime is not ready")
            previous_receipts = receiver.unique_receipt_count

        await self._ingest_cycle(device_id=device_id)

        async with self._state_lock:
            receiver = self._receiver
            receipts = receiver.unique_receipt_count if receiver is not None else 0
            status = (
                "passed"
                if receiver is not None
                and receipts > previous_receipts
                and self._last_error_code is None
                else "failed"
            )
            return {
                "status": status,
                "unique_test_receipts": receipts,
                "network_enabled": False,
            }

    async def arm_synthetic_delivery_fault(
        self,
        mode: SyntheticFaultMode,
    ) -> dict[str, object]:
        """Arm one synthetic receiver outcome; no network receiver is reachable."""

        async with self._state_lock:
            if self._fault_injector is None:
                raise SyntheticFaultInjectorError("synthetic_fault_injector_unavailable")
            return await self._fault_injector.arm(mode)

    async def clear_synthetic_delivery_fault(self) -> dict[str, object]:
        """Cancel a pending synthetic test fault without changing delivery records."""

        async with self._state_lock:
            if self._fault_injector is None:
                raise SyntheticFaultInjectorError("synthetic_fault_injector_unavailable")
            return await self._fault_injector.clear()

    async def synthetic_delivery_fault_status(self) -> dict[str, object]:
        """Expose bounded fault-injection state without event data."""

        async with self._state_lock:
            if self._fault_injector is None:
                raise SyntheticFaultInjectorError("synthetic_fault_injector_unavailable")
            return await self._fault_injector.status()

    async def synthetic_delivery_detail(self, event_id: UUID) -> dict[str, object]:
        """Read an allowlisted event/outbox/attempt timeline for one synthetic event."""

        async with self._state_lock:
            if self._sessions is None:
                raise SyntheticOperationsError("synthetic_runtime_unavailable", 503)
            detail = await self._load_synthetic_delivery_detail(event_id)
            if detail is None:
                raise SyntheticOperationsError("synthetic_delivery_not_found", 404)
            return detail

    async def replay_synthetic_delivery(self, event_id: UUID) -> dict[str, object]:
        """Replay one terminal failure at the local test receiver, preserving attempts."""

        async with self._state_lock:
            if self._store is None or self._worker is None or self._destination is None:
                raise SyntheticDeliveryReplayError("synthetic_runtime_unavailable", 503)
            await self._store.requeue_terminal_synthetic_delivery(
                event_id,
                self._destination.destination_id,
                now=datetime.now(UTC),
                max_attempts=MAX_DEMO_DELIVERY_ATTEMPTS,
            )
            while await self._worker.dispatch_once() is not None:
                pass
            detail = await self._load_synthetic_delivery_detail(event_id)
            if detail is None:
                raise SyntheticDeliveryReplayError("synthetic_delivery_not_found", 404)
            return detail

    async def _load_synthetic_delivery_detail(
        self,
        event_id: UUID,
    ) -> dict[str, object] | None:
        if self._sessions is None or self._destination is None:
            return None
        async with self._sessions() as session:
            event_record = await session.get(EventRecord, event_id)
            if event_record is None or event_record.origin != EventOrigin.SYNTHETIC.value:
                return None
            try:
                event = ObservationEvent.model_validate(event_record.payload)
            except Exception:
                return None
            if (
                event.event_id != event_id
                or event.origin is not EventOrigin.SYNTHETIC
                or event.patient is not None
                or event.encounter_reference is not None
            ):
                return None
            outbox = await session.scalar(
                select(DeliveryOutboxRecord).where(
                    DeliveryOutboxRecord.event_id == event_id,
                    DeliveryOutboxRecord.destination_id == self._destination.destination_id,
                )
            )
            if outbox is None:
                return None
            attempts = (
                await session.scalars(
                    select(DeliveryAttemptRecord)
                    .where(DeliveryAttemptRecord.outbox_id == outbox.outbox_id)
                    .order_by(DeliveryAttemptRecord.attempt_number)
                )
            ).all()
            return {
                "scope": "synthetic_only",
                "network_enabled": False,
                "event": {
                    "event_id": str(event.event_id),
                    "origin": EventOrigin.SYNTHETIC.value,
                    "device_id": event.device.device_id,
                    "metric_system": event.metric.system,
                    "metric_code": event.metric.code,
                    "value": event.value,
                    "unit_system": event.source_unit.system,
                    "unit_code": event.source_unit.code,
                    "observed_at": self._isoformat(event.observed_at),
                    "received_at": self._isoformat(event.received_at),
                },
                "delivery": {
                    "destination_id": outbox.destination_id,
                    "status": outbox.status,
                    "attempt_count": outbox.attempt_count,
                    "next_attempt_at": self._isoformat(outbox.next_attempt_at),
                    "last_error_code": outbox.last_error_code,
                    "acknowledgement_id": outbox.acknowledgement_id,
                    "updated_at": self._isoformat(outbox.updated_at),
                    "retry_allowed": (
                        outbox.status
                        in {
                            DeliveryStatus.REJECTED.value,
                            DeliveryStatus.PERMANENT_FAILURE.value,
                        }
                        and outbox.attempt_count < MAX_DEMO_DELIVERY_ATTEMPTS
                    ),
                },
                "attempts": [
                    {
                        "attempt_number": attempt.attempt_number,
                        "status": attempt.status,
                        "started_at": self._isoformat(attempt.started_at),
                        "completed_at": self._isoformat(attempt.completed_at),
                        "error_code": attempt.error_code,
                        "acknowledgement_id": attempt.acknowledgement_id,
                    }
                    for attempt in attempts
                ],
            }

    async def snapshot(self) -> dict[str, Any]:
        """Return aggregate metrics and curated recent rows for the UI/API."""

        async with self._state_lock:
            if self._sessions is None:
                return self._empty_snapshot()

            async with self._sessions() as session:
                event_count = await session.scalar(
                    select(func.count())
                    .select_from(EventRecord)
                    .where(EventRecord.origin == EventOrigin.SYNTHETIC.value)
                )
                status_rows = await session.execute(
                    select(DeliveryOutboxRecord.status, func.count()).group_by(
                        DeliveryOutboxRecord.status
                    )
                )
                delivery_counts = {status.value: 0 for status in DeliveryStatus}
                for status, count in status_rows:
                    delivery_counts[status] = count

                attempts = await session.scalar(
                    select(func.coalesce(func.sum(DeliveryOutboxRecord.attempt_count), 0))
                )
                hold_count = await session.scalar(
                    select(func.count())
                    .select_from(RoutingHoldRecord)
                    .join(EventRecord, EventRecord.event_id == RoutingHoldRecord.event_id)
                    .where(EventRecord.origin == EventOrigin.SYNTHETIC.value)
                )
                hold_rows = (
                    await session.scalars(
                        select(RoutingHoldRecord)
                        .join(EventRecord, EventRecord.event_id == RoutingHoldRecord.event_id)
                        .where(EventRecord.origin == EventOrigin.SYNTHETIC.value)
                        .order_by(RoutingHoldRecord.created_at.desc())
                        .limit(self._recent_limit)
                    )
                ).all()
                audit_count = await session.scalar(
                    select(func.count())
                    .select_from(AuditEventRecord)
                    .where(AuditEventRecord.site_id == "synthetic-site")
                )
                audit_rows = (
                    await session.scalars(
                        select(AuditEventRecord)
                        .where(AuditEventRecord.site_id == "synthetic-site")
                        .order_by(
                            AuditEventRecord.occurred_at.desc(),
                            AuditEventRecord.audit_id.desc(),
                        )
                        .limit(self._recent_limit)
                    )
                ).all()
                event_records = (
                    await session.scalars(
                        select(EventRecord)
                        .where(EventRecord.origin == EventOrigin.SYNTHETIC.value)
                        .order_by(EventRecord.persisted_at.desc(), EventRecord.received_at.desc())
                        .limit(self._recent_limit)
                    )
                ).all()
                delivery_rows = (
                    await session.execute(
                        select(DeliveryOutboxRecord, EventRecord.device_id)
                        .join(EventRecord, EventRecord.event_id == DeliveryOutboxRecord.event_id)
                        .where(EventRecord.origin == EventOrigin.SYNTHETIC.value)
                        .order_by(
                            DeliveryOutboxRecord.updated_at.desc(),
                            DeliveryOutboxRecord.created_at.desc(),
                        )
                        .limit(self._recent_limit)
                    )
                ).all()

            recent_events = [
                row
                for record in event_records
                if (row := self._safe_event_projection(record)) is not None
            ]
            recent_deliveries = [
                {
                    "event_id": str(outbox.event_id),
                    "device_id": device_id,
                    "status": outbox.status,
                    "attempts": outbox.attempt_count,
                    "error_code": outbox.last_error_code,
                    "updated_at": self._isoformat(outbox.updated_at),
                }
                for outbox, device_id in delivery_rows
            ]
            recent_holds = [
                {
                    "event_id": str(hold.event_id),
                    "destination_id": hold.destination_id,
                    "reason_code": hold.reason_code,
                    "created_at": self._isoformat(hold.created_at),
                }
                for hold in hold_rows
            ]
            recent_activity = [
                {
                    "action": row.action,
                    "resource_type": row.resource_type,
                    "reason_code": row.reason_code,
                    "occurred_at": self._isoformat(row.occurred_at),
                }
                for row in audit_rows
            ]

            delivery_attempts = int(attempts or 0)
            pending = sum(
                delivery_counts[status.value]
                for status in (
                    DeliveryStatus.QUEUED,
                    DeliveryStatus.SENT,
                    DeliveryStatus.RETRYABLE_FAILURE,
                )
            )
            source = self._source_health
            receiver = self._receiver
            ready = source is not None and self._last_error_code is None
            return {
                "mode": "synthetic_demo",
                "ready": ready,
                "started_at": self._isoformat(self._started_at),
                "updated_at": datetime.now(UTC).isoformat(),
                "last_error_code": self._last_error_code,
                "source": {
                    "adapter_id": source.adapter_id if source else "medihub.synthetic-device",
                    "status": source.status.value if source else "starting",
                    "detail_code": source.detail_code if source else "initializing",
                    "checked_at": self._isoformat(source.checked_at) if source else None,
                },
                "receiver": {
                    "status": "in_process" if receiver is not None else "starting",
                    "unique_receipts": receiver.unique_receipt_count if receiver else 0,
                },
                "totals": {
                    "events_received": self._events_received,
                    "events_inserted": int(event_count or 0),
                    "duplicate_events": self._duplicate_events,
                    "blocked_routes": int(hold_count or 0),
                    "audit_events": int(audit_count or 0),
                    "delivery_attempts": delivery_attempts,
                    "acknowledged_deliveries": delivery_counts[DeliveryStatus.ACKNOWLEDGED.value],
                    "pending_deliveries": pending,
                    "retryable_failures": delivery_counts[DeliveryStatus.RETRYABLE_FAILURE.value],
                    "permanent_failures": delivery_counts[DeliveryStatus.PERMANENT_FAILURE.value],
                    "rejected_deliveries": delivery_counts[DeliveryStatus.REJECTED.value],
                    "unique_test_receipts": (receiver.unique_receipt_count if receiver else 0),
                },
                "recent_events": recent_events,
                "recent_deliveries": recent_deliveries,
                "recent_holds": recent_holds,
                "recent_activity": recent_activity,
            }

    async def _run_live_feed(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._refresh_interval_seconds,
                )
            except TimeoutError:
                try:
                    await self._ingest_cycle()
                except Exception:
                    # Exception strings may contain payloads; publish only a stable code.
                    async with self._state_lock:
                        self._last_error_code = "synthetic_cycle_failed"

    async def _ingest_cycle(self, *, device_id: str = "sim-device-001") -> None:
        async with self._state_lock:
            if (
                self._ingestion is None
                or self._worker is None
                or self._destination is None
                or self._sessions is None
            ):
                raise RuntimeError("dashboard runtime is not initialized")

            sequence = self._sequence
            self._sequence += 1
            simulator = SyntheticDeviceAdapter(
                SyntheticDeviceConfig(
                    device=DeviceReference(
                        device_id=device_id,
                        manufacturer="MediHub Synthetic",
                        model="scalar-simulator-v1",
                        firmware_version="1.0",
                    ),
                    event_count=1,
                    seed=7 + sequence,
                    start_at=datetime.now(UTC),
                )
            )
            try:
                async for event in simulator.read_events():
                    await self._record_event(event)
                    if self._duplicate_every and (sequence + 1) % self._duplicate_every == 0:
                        # Redeliver the same event envelope to make idempotency visible.
                        await self._record_event(event)
                self._source_health = await simulator.health()
            finally:
                await simulator.close()

            while await self._worker.dispatch_once() is not None:
                pass
            if self._sequence % self._prune_every_events == 0:
                await self._prune_history()
            self._last_error_code = None

    async def _prune_history(self) -> None:
        """Bound the ephemeral demo store and test receiver's idempotency ledger."""

        if self._sessions is None:
            return
        retained_event_ids = (
            select(EventRecord.event_id)
            .where(EventRecord.origin == EventOrigin.SYNTHETIC.value)
            .order_by(EventRecord.received_at.desc(), EventRecord.event_id)
            .limit(self._max_retained_events)
        )
        stale_event_ids = select(EventRecord.event_id).where(
            EventRecord.origin == EventOrigin.SYNTHETIC.value,
            EventRecord.event_id.not_in(retained_event_ids),
        )
        stale_outbox_ids = select(DeliveryOutboxRecord.outbox_id).where(
            DeliveryOutboxRecord.event_id.in_(stale_event_ids)
        )
        async with self._sessions.begin() as session:
            stale_ids = list(await session.scalars(stale_event_ids))
            if stale_ids:
                stale_correlation_ids = tuple(str(event_id) for event_id in stale_ids)
                await session.execute(
                    delete(AuditEventRecord).where(
                        AuditEventRecord.correlation_id.in_(stale_correlation_ids)
                    )
                )
            await session.execute(
                delete(DeliveryAttemptRecord).where(
                    DeliveryAttemptRecord.outbox_id.in_(stale_outbox_ids)
                )
            )
            await session.execute(
                delete(DeliveryOutboxRecord).where(
                    DeliveryOutboxRecord.event_id.in_(stale_event_ids)
                )
            )
            await session.execute(
                delete(RoutingHoldRecord).where(RoutingHoldRecord.event_id.in_(stale_event_ids))
            )
            await session.execute(
                delete(EventRecord).where(EventRecord.event_id.in_(stale_event_ids))
            )

    async def _record_event(self, event: ObservationEvent) -> None:
        if (
            self._ingestion is None
            or self._destination is None
            or self._blocked_destination is None
        ):
            raise RuntimeError("dashboard ingestion is not initialized")
        self._events_received += 1
        result = await self._ingestion.ingest(
            event,
            [self._destination, self._blocked_destination],
        )
        if result.duplicate:
            self._duplicate_events += 1

    @staticmethod
    def _safe_event_projection(record: EventRecord) -> dict[str, Any] | None:
        """Allowlist synthetic fields; never serialize the stored event envelope."""

        if record.origin != EventOrigin.SYNTHETIC.value or not isinstance(record.payload, dict):
            return None
        try:
            event = ObservationEvent.model_validate(record.payload)
        except Exception:
            return None
        if (
            event.origin is not EventOrigin.SYNTHETIC
            or event.patient is not None
            or event.encounter_reference is not None
        ):
            return None
        return {
            "event_id": str(event.event_id),
            "device_id": event.device.device_id,
            "received_at": event.received_at.isoformat(),
            "observed_at": event.observed_at.isoformat() if event.observed_at else None,
            "label": "Synthetic scalar",
            "value": event.value,
            "source_sequence": event.provenance.source_sequence,
        }

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _empty_snapshot() -> dict[str, Any]:
        return {
            "mode": "synthetic_demo",
            "ready": False,
            "started_at": None,
            "updated_at": datetime.now(UTC).isoformat(),
            "last_error_code": None,
            "source": {
                "adapter_id": "medihub.synthetic-device",
                "status": "starting",
                "detail_code": "initializing",
                "checked_at": None,
            },
            "receiver": {"status": "starting", "unique_receipts": 0},
            "totals": {
                "events_received": 0,
                "events_inserted": 0,
                "duplicate_events": 0,
                "blocked_routes": 0,
                "audit_events": 0,
                "delivery_attempts": 0,
                "acknowledged_deliveries": 0,
                "pending_deliveries": 0,
                "retryable_failures": 0,
                "permanent_failures": 0,
                "rejected_deliveries": 0,
                "unique_test_receipts": 0,
            },
            "recent_events": [],
            "recent_deliveries": [],
            "recent_holds": [],
            "recent_activity": [],
        }

    def _clear_runtime(self) -> None:
        self._engine = None
        self._sessions = None
        self._store = None
        self._ingestion = None
        self._worker = None
        self._receiver = None
        self._fault_injector = None
        self._destination = None
        self._blocked_destination = None
        self._generator_task = None
        self._started_at = None
        self._source_health = None
        self._sequence = 0
        self._events_received = 0
        self._duplicate_events = 0
        self._last_error_code = None

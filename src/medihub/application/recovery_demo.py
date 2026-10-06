"""File-backed synthetic gateway restart and outbox recovery drill."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from medihub.adapters.destinations.fhir_r4 import SyntheticFhirR4DestinationAdapter
from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.application.ingestion import IngestionService
from medihub.application.outbox_worker import OutboxWorker
from medihub.domain import (
    AuditAction,
    ClaimedDelivery,
    DeliveryAttempt,
    DeliveryStatus,
    Destination,
    DestinationProtocol,
)
from medihub.infrastructure.database import Base, create_database_engine
from medihub.infrastructure.event_store import SqlAlchemyEventStore
from medihub.infrastructure.models import (
    AuditEventRecord,
    DeliveryAttemptRecord,
    DeliveryOutboxRecord,
    EventRecord,
)
from medihub.ports import DestinationAdapter

MAX_RECOVERY_DEMO_EVENTS = 100
RECOVERY_LEASE_DURATION = timedelta(seconds=1)


@dataclass(frozen=True, slots=True)
class SyntheticRecoveryDemoSummary:
    """Aggregate-only result from the local synthetic recovery exercise."""

    events_read: int
    events_inserted: int
    duplicate_events: int
    simulated_process_restarts: int
    expired_leases_recovered: int
    retryable_failures: int
    delivery_attempts: int
    acknowledged_deliveries: int
    pending_deliveries: int
    unique_test_receipts: int


class SyntheticRecoveryDemoError(RuntimeError):
    """A safe failure code for an incomplete local recovery scenario."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DrillClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def __call__(self) -> datetime:
        return self._now


class _FailOnceDestinationAdapter(DestinationAdapter):
    """Inject one offline-only receiver outage before delegating to the test sink."""

    def __init__(self, receiver: SyntheticFhirR4DestinationAdapter) -> None:
        self._receiver = receiver
        self._send_count = 0

    @property
    def destination(self) -> Destination:
        return self._receiver.destination

    async def send(self, delivery: ClaimedDelivery) -> DeliveryAttempt:
        self._send_count += 1
        if self._send_count == 1:
            raise ConnectionError("synthetic receiver unavailable in recovery drill")
        return await self._receiver.send(delivery)


async def run_synthetic_recovery_demo(
    config: SyntheticDeviceConfig,
) -> SyntheticRecoveryDemoSummary:
    """Prove a file-backed synthetic outbox survives a simulated worker restart.

    The drill uses a temporary SQLite database and an in-process synthetic FHIR
    sink. It does not contact external systems or modify the configured database.
    """

    if config.event_count > MAX_RECOVERY_DEMO_EVENTS:
        raise SyntheticRecoveryDemoError("recovery_demo_event_limit_exceeded")
    if config.disconnect_after is not None or config.disconnect_for:
        raise SyntheticRecoveryDemoError("recovery_demo_requires_continuous_source")

    simulator = SyntheticDeviceAdapter(config)
    events = []
    try:
        async for event in simulator.read_events():
            events.append(event)
    finally:
        await simulator.close()
    if not events:
        raise SyntheticRecoveryDemoError("recovery_demo_source_emitted_no_events")

    destination = Destination(
        destination_id="medihub.synthetic-recovery-test-receiver",
        site_id=config.site_id,
        name="MediHub synthetic recovery receiver",
        protocol=DestinationProtocol.FHIR_R4,
        contract_version="synthetic-recovery-demo-v1",
        connection_ref="in-process",
        enabled=True,
        accepts_synthetic_data=True,
    )

    with TemporaryDirectory(prefix="medihub-recovery-") as temporary_directory:
        database_path = Path(temporary_directory) / "recovery-demo.db"
        database_url = f"sqlite+aiosqlite:///{database_path}"
        engine = create_database_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            ingestion = IngestionService(store)
            events_inserted = 0
            duplicate_events = 0
            for event in events:
                result = await ingestion.ingest(event, [destination])
                if result.duplicate:
                    duplicate_events += 1
                else:
                    events_inserted += 1

            if events_inserted < 1:
                raise SyntheticRecoveryDemoError("recovery_demo_no_unique_events")

            claim_at = max(event.received_at for event in events) + timedelta(seconds=1)
            abandoned_claim = await store.claim_next(
                destination_ids=(destination.destination_id,),
                now=claim_at,
                lease_for=RECOVERY_LEASE_DURATION,
            )
            if abandoned_claim is None:
                raise SyntheticRecoveryDemoError("recovery_demo_initial_claim_missing")

            # Dispose the engine without completing the claim: this models a gateway
            # process stopping after a durable lease was written but before delivery.
            await engine.dispose()
            engine = create_database_engine(database_url)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)

            recovery_clock = _DrillClock(claim_at + RECOVERY_LEASE_DURATION + timedelta(seconds=1))
            receiver = SyntheticFhirR4DestinationAdapter(destination, clock=recovery_clock)
            flaky_adapter = _FailOnceDestinationAdapter(receiver)
            worker = OutboxWorker(
                store,
                {destination.destination_id: flaky_adapter},
                lease_duration=RECOVERY_LEASE_DURATION,
                base_retry_delay=timedelta(0),
                max_retry_delay=timedelta(0),
                clock=recovery_clock,
            )

            first_recovery_attempt = await worker.dispatch_once()
            if (
                first_recovery_attempt is None
                or first_recovery_attempt.status is not DeliveryStatus.RETRYABLE_FAILURE
                or first_recovery_attempt.error_code != "adapter_exception"
            ):
                raise SyntheticRecoveryDemoError("recovery_demo_transient_failure_missing")

            for _ in range(events_inserted + 1):
                attempt = await worker.dispatch_once()
                if attempt is None:
                    break
            else:
                raise SyntheticRecoveryDemoError("recovery_demo_queue_did_not_drain")

            async with sessions() as session:
                persisted_events = list(await session.scalars(select(EventRecord)))
                outbox_records = list(await session.scalars(select(DeliveryOutboxRecord)))
                attempt_records = list(await session.scalars(select(DeliveryAttemptRecord)))
                audit_records = list(await session.scalars(select(AuditEventRecord)))

            expired_leases = sum(
                record.action == AuditAction.DELIVERY_LEASE_EXPIRED.value
                for record in audit_records
            )
            retryable_failures = sum(
                record.status == DeliveryStatus.RETRYABLE_FAILURE.value
                for record in attempt_records
            )
            acknowledged = sum(
                record.status == DeliveryStatus.ACKNOWLEDGED.value for record in outbox_records
            )
            pending = sum(
                record.status
                in {
                    DeliveryStatus.QUEUED.value,
                    DeliveryStatus.SENT.value,
                    DeliveryStatus.RETRYABLE_FAILURE.value,
                }
                for record in outbox_records
            )

            if (
                len(persisted_events) != events_inserted
                or len(outbox_records) != events_inserted
                or expired_leases != 1
                or retryable_failures != 2
                or len(attempt_records) != events_inserted + 2
                or acknowledged != events_inserted
                or pending != 0
                or receiver.unique_receipt_count != events_inserted
            ):
                raise SyntheticRecoveryDemoError("recovery_demo_invariant_failed")

            return SyntheticRecoveryDemoSummary(
                events_read=len(events),
                events_inserted=events_inserted,
                duplicate_events=duplicate_events,
                simulated_process_restarts=1,
                expired_leases_recovered=expired_leases,
                retryable_failures=retryable_failures,
                delivery_attempts=len(attempt_records),
                acknowledged_deliveries=acknowledged,
                pending_deliveries=pending,
                unique_test_receipts=receiver.unique_receipt_count,
            )
        finally:
            await engine.dispose()


__all__ = [
    "MAX_RECOVERY_DEMO_EVENTS",
    "SyntheticRecoveryDemoError",
    "SyntheticRecoveryDemoSummary",
    "run_synthetic_recovery_demo",
]

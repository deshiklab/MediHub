"""Synthetic lost-acknowledgement drill for at-least-once delivery semantics."""

from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from medihub.adapters.destinations.fhir_r4 import SyntheticFhirR4DestinationAdapter
from medihub.adapters.destinations.synthetic_fault_injector import (
    SyntheticReceiverFaultInjector,
)
from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.application.ingestion import IngestionService
from medihub.application.outbox_worker import OutboxWorker
from medihub.domain import DeliveryStatus, Destination, DestinationProtocol
from medihub.infrastructure.database import Base, create_database_engine
from medihub.infrastructure.event_store import SqlAlchemyEventStore
from medihub.infrastructure.models import (
    DeliveryAttemptRecord,
    DeliveryOutboxRecord,
    EventRecord,
)


class SyntheticAmbiguousDeliveryDemoError(RuntimeError):
    """Safe error code for an incomplete local lost-acknowledgement drill."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class SyntheticAmbiguousDeliveryDemoSummary:
    """Aggregate-only evidence for receiver idempotency after an ACK is lost."""

    events_inserted: int
    simulated_worker_restarts: int
    delivery_attempts: int
    retryable_failures: int
    acknowledged_attempts: int
    final_acknowledged_deliveries: int
    pending_deliveries: int
    receiver_delivery_attempts: int
    receiver_duplicate_attempts: int
    unique_test_receipts: int
    faults_injected: int
    fault_injector_clear: bool
    network_enabled: bool


async def run_synthetic_ambiguous_delivery_demo(
    config: SyntheticDeviceConfig,
) -> SyntheticAmbiguousDeliveryDemoSummary:
    """Lose one synthetic receiver ACK, restart the worker, then retry the same event.

    A disposable file-backed outbox survives the simulated worker restart. The
    in-process receiver remains available as the remote-system stand-in and uses
    the event ID as its idempotency key; no device or network connection is made.
    """

    if config.disconnect_after is not None or config.disconnect_for:
        raise SyntheticAmbiguousDeliveryDemoError("ambiguous_ack_requires_continuous_source")
    if config.device.firmware_version not in config.supported_firmware_versions:
        raise SyntheticAmbiguousDeliveryDemoError("ambiguous_ack_requires_supported_firmware")

    source_config = config.model_copy(update={"event_count": 1, "duplicate_every": 0})
    simulator = SyntheticDeviceAdapter(source_config)
    events = []
    try:
        async for event in simulator.read_events():
            events.append(event)
        health = await simulator.health()
    finally:
        await simulator.close()

    if len(events) != 1 or health.status.value != "healthy":
        raise SyntheticAmbiguousDeliveryDemoError("ambiguous_ack_source_not_ready")

    destination = Destination(
        destination_id="medihub.synthetic-ambiguous-ack-receiver",
        site_id=source_config.site_id,
        name="MediHub in-process synthetic acknowledgement-loss receiver",
        protocol=DestinationProtocol.FHIR_R4,
        contract_version="generic-r4-synthetic-ambiguous-ack-v1",
        connection_ref="in-process",
        enabled=True,
        accepts_synthetic_data=True,
    )
    receiver = SyntheticFhirR4DestinationAdapter(destination, max_seen_event_ids=1)
    fault_injector = SyntheticReceiverFaultInjector(receiver)

    with TemporaryDirectory(prefix="medihub-ambiguous-ack-") as temporary_directory:
        database_path = Path(temporary_directory) / "ambiguous-ack.db"
        database_url = f"sqlite+aiosqlite:///{database_path}"
        engine = create_database_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            ingestion_result = await IngestionService(store).ingest(events[0], [destination])
            if ingestion_result.duplicate or len(ingestion_result.queued_destination_ids) != 1:
                raise SyntheticAmbiguousDeliveryDemoError("ambiguous_ack_event_not_queued")

            first_worker = OutboxWorker(
                store,
                {destination.destination_id: fault_injector},
                base_retry_delay=timedelta(0),
                max_retry_delay=timedelta(0),
            )
            await fault_injector.arm("ack_lost_once")
            first_attempt = await first_worker.dispatch_once()
            if (
                first_attempt is None
                or first_attempt.status is not DeliveryStatus.RETRYABLE_FAILURE
                or first_attempt.error_code != "synthetic_test_ack_lost_after_acceptance"
            ):
                raise SyntheticAmbiguousDeliveryDemoError("ambiguous_ack_fault_not_observed")

            # Close and reopen the file-backed store to exercise retry after restart.
            await engine.dispose()
            engine = create_database_engine(database_url)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            restarted_worker = OutboxWorker(
                store,
                {destination.destination_id: fault_injector},
                base_retry_delay=timedelta(0),
                max_retry_delay=timedelta(0),
            )
            retry_attempt = await restarted_worker.dispatch_once()
            if (
                retry_attempt is None
                or retry_attempt.event_id != events[0].event_id
                or retry_attempt.status is not DeliveryStatus.ACKNOWLEDGED
            ):
                raise SyntheticAmbiguousDeliveryDemoError("ambiguous_ack_retry_not_acknowledged")
            if await restarted_worker.dispatch_once() is not None:
                raise SyntheticAmbiguousDeliveryDemoError("ambiguous_ack_outbox_not_drained")

            fault_status = await fault_injector.status()
            async with sessions() as session:
                event_rows = (await session.scalars(select(EventRecord))).all()
                outbox_rows = (await session.scalars(select(DeliveryOutboxRecord))).all()
                attempt_rows = list(
                    await session.scalars(
                        select(DeliveryAttemptRecord).order_by(DeliveryAttemptRecord.attempt_number)
                    )
                )

            attempt_counts = Counter(record.status for record in attempt_rows)
            outbox_counts = Counter(record.status for record in outbox_rows)
            expected_attempt_statuses = [
                DeliveryStatus.RETRYABLE_FAILURE.value,
                DeliveryStatus.ACKNOWLEDGED.value,
            ]
            if (
                len(event_rows) != 1
                or len(outbox_rows) != 1
                or [record.status for record in attempt_rows] != expected_attempt_statuses
                or outbox_rows[0].status != DeliveryStatus.ACKNOWLEDGED.value
                or receiver.delivery_attempt_count != 2
                or receiver.unique_receipt_count != 1
                or fault_status["last_injected_fault"] != "ack_lost_once"
                or fault_status["last_outcome"] != "receiver_acknowledgement_lost_after_acceptance"
                or fault_status["armed_fault"] is not None
                or fault_status["network_enabled"] is not False
            ):
                raise SyntheticAmbiguousDeliveryDemoError("ambiguous_ack_invariant_failed")

            pending = sum(
                outbox_counts[status.value]
                for status in (
                    DeliveryStatus.QUEUED,
                    DeliveryStatus.SENT,
                    DeliveryStatus.RETRYABLE_FAILURE,
                )
            )
            return SyntheticAmbiguousDeliveryDemoSummary(
                events_inserted=len(event_rows),
                simulated_worker_restarts=1,
                delivery_attempts=len(attempt_rows),
                retryable_failures=attempt_counts[DeliveryStatus.RETRYABLE_FAILURE.value],
                acknowledged_attempts=attempt_counts[DeliveryStatus.ACKNOWLEDGED.value],
                final_acknowledged_deliveries=outbox_counts[DeliveryStatus.ACKNOWLEDGED.value],
                pending_deliveries=pending,
                receiver_delivery_attempts=receiver.delivery_attempt_count,
                receiver_duplicate_attempts=(
                    receiver.delivery_attempt_count - receiver.unique_receipt_count
                ),
                unique_test_receipts=receiver.unique_receipt_count,
                faults_injected=int(fault_status["faults_injected"]),
                fault_injector_clear=fault_status["armed_fault"] is None,
                network_enabled=bool(fault_status["network_enabled"]),
            )
        finally:
            await engine.dispose()


__all__ = [
    "SyntheticAmbiguousDeliveryDemoError",
    "SyntheticAmbiguousDeliveryDemoSummary",
    "run_synthetic_ambiguous_delivery_demo",
]

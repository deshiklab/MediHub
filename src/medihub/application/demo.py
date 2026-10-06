"""Ephemeral end-to-end demonstration using only synthetic data and a local test sink."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from medihub.adapters.destinations.simulator import SyntheticDestinationAdapter
from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.application.ingestion import IngestionService
from medihub.application.outbox_worker import OutboxWorker
from medihub.domain import DeliveryStatus, Destination, DestinationProtocol
from medihub.infrastructure.database import Base, create_database_engine
from medihub.infrastructure.event_store import SqlAlchemyEventStore


@dataclass(frozen=True, slots=True)
class DemoSummary:
    events_read: int
    events_inserted: int
    duplicate_events: int
    blocked_routes: int
    delivery_attempts: int
    acknowledged_deliveries: int
    permanent_failures: int
    unique_test_receipts: int
    source_health: str
    source_health_code: str | None


async def run_synthetic_demo(config: SyntheticDeviceConfig) -> DemoSummary:
    """Run simulator → policy → ephemeral event/outbox store → in-process receiver."""

    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        store = SqlAlchemyEventStore(sessions)
        destination = Destination(
            destination_id="medihub.synthetic-test-receiver",
            site_id=config.site_id,
            name="MediHub in-process synthetic receiver",
            protocol=DestinationProtocol.MEDIHUB_API,
            contract_version="synthetic-test-v1",
            connection_ref="in-process",
            enabled=True,
            accepts_synthetic_data=True,
        )
        receiver = SyntheticDestinationAdapter(destination)
        simulator = SyntheticDeviceAdapter(config)
        ingestion = IngestionService(store)

        events_read = 0
        events_inserted = 0
        duplicate_events = 0
        blocked_routes = 0
        try:
            async for event in simulator.read_events():
                events_read += 1
                result = await ingestion.ingest(event, [destination])
                blocked_routes += len(result.blocked_routes)
                if result.duplicate:
                    duplicate_events += 1
                else:
                    events_inserted += 1
            health = await simulator.health()
        finally:
            await simulator.close()

        worker = OutboxWorker(store, {destination.destination_id: receiver})
        delivery_attempts = 0
        acknowledged_deliveries = 0
        permanent_failures = 0
        while (attempt := await worker.dispatch_once()) is not None:
            delivery_attempts += 1
            if attempt.status is DeliveryStatus.ACKNOWLEDGED:
                acknowledged_deliveries += 1
            if attempt.status is DeliveryStatus.PERMANENT_FAILURE:
                permanent_failures += 1

        return DemoSummary(
            events_read=events_read,
            events_inserted=events_inserted,
            duplicate_events=duplicate_events,
            blocked_routes=blocked_routes,
            delivery_attempts=delivery_attempts,
            acknowledged_deliveries=acknowledged_deliveries,
            permanent_failures=permanent_failures,
            unique_test_receipts=receiver.unique_receipt_count,
            source_health=health.status.value,
            source_health_code=health.detail_code,
        )
    finally:
        await engine.dispose()

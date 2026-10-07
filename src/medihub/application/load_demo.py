"""Bounded synthetic throughput drill for the in-process event/outbox path."""

import math
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.ext.asyncio import async_sessionmaker

from medihub.adapters.destinations.fhir_r4 import SyntheticFhirR4DestinationAdapter
from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.application.ingestion import IngestionService
from medihub.application.outbox_worker import OutboxWorker
from medihub.domain import (
    DeliveryStatus,
    Destination,
    DestinationProtocol,
)
from medihub.infrastructure.database import Base, create_database_engine
from medihub.infrastructure.event_store import SqlAlchemyEventStore

MAX_SYNTHETIC_LOAD_EVENTS = 1_000


@dataclass(frozen=True, slots=True)
class SyntheticLoadDemoSummary:
    events_requested: int
    events_read: int
    events_inserted: int
    duplicate_events: int
    blocked_routes: int
    delivery_attempts: int
    acknowledged_deliveries: int
    rejected_deliveries: int
    retryable_failures: int
    permanent_failures: int
    unique_test_receipts: int
    duration_ms: float
    events_per_second: float
    acknowledgements_per_second: float
    acknowledgement_latency_ms_p50: float
    acknowledgement_latency_ms_p95: float
    source_health: str
    source_health_code: str | None
    data_mode: str = "synthetic_only"
    storage: str = "in_memory_sqlite"
    transport: str = "in_process"
    network_enabled: bool = False
    production_benchmark: bool = False


async def run_synthetic_load_demo(
    config: SyntheticDeviceConfig,
) -> SyntheticLoadDemoSummary:
    """Process a bounded synthetic batch and report local pipeline measurements.

    Measurements include in-memory SQLite writes and the local FHIR-shaped test
    receiver. They are useful for functional profiling only, not production
    sizing, site SLOs, network performance, or clinical readiness.
    """

    if not 1 <= config.event_count <= MAX_SYNTHETIC_LOAD_EVENTS:
        raise ValueError("synthetic_load_event_limit_exceeded")

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
            protocol=DestinationProtocol.FHIR_R4,
            contract_version="generic-r4-synthetic-observation-v1",
            connection_ref="in-process",
            enabled=True,
            accepts_synthetic_data=True,
        )
        receiver = SyntheticFhirR4DestinationAdapter(
            destination,
            max_seen_event_ids=config.event_count,
        )
        ingestion = IngestionService(store)
        simulator = SyntheticDeviceAdapter(config)
        event_ingested_at: dict[str, float] = {}
        events_read = 0
        events_inserted = 0
        duplicate_events = 0
        blocked_routes = 0
        delivery_attempts = 0
        acknowledged_deliveries = 0
        rejected_deliveries = 0
        retryable_failures = 0
        permanent_failures = 0
        acknowledgement_latencies_ms: list[float] = []

        try:
            source_start = perf_counter()
            async for event in simulator.read_events():
                events_read += 1
                inserted_at = perf_counter()
                result = await ingestion.ingest(event, [destination])
                blocked_routes += len(result.blocked_routes)
                if result.duplicate:
                    duplicate_events += 1
                else:
                    events_inserted += 1
                    event_ingested_at[str(event.event_id)] = inserted_at
            source_health = await simulator.health()

            worker = OutboxWorker(store, {destination.destination_id: receiver})
            while (attempt := await worker.dispatch_once()) is not None:
                delivery_attempts += 1
                if attempt.status is DeliveryStatus.ACKNOWLEDGED:
                    acknowledged_deliveries += 1
                    start_time = event_ingested_at.get(str(attempt.event_id))
                    if start_time is not None:
                        acknowledgement_latencies_ms.append((perf_counter() - start_time) * 1_000)
                elif attempt.status is DeliveryStatus.REJECTED:
                    rejected_deliveries += 1
                elif attempt.status is DeliveryStatus.RETRYABLE_FAILURE:
                    retryable_failures += 1
                elif attempt.status is DeliveryStatus.PERMANENT_FAILURE:
                    permanent_failures += 1
            duration_seconds = max(perf_counter() - source_start, 1e-9)
        finally:
            await simulator.close()

        return SyntheticLoadDemoSummary(
            events_requested=config.event_count,
            events_read=events_read,
            events_inserted=events_inserted,
            duplicate_events=duplicate_events,
            blocked_routes=blocked_routes,
            delivery_attempts=delivery_attempts,
            acknowledged_deliveries=acknowledged_deliveries,
            rejected_deliveries=rejected_deliveries,
            retryable_failures=retryable_failures,
            permanent_failures=permanent_failures,
            unique_test_receipts=receiver.unique_receipt_count,
            duration_ms=round(duration_seconds * 1_000, 3),
            events_per_second=round(events_inserted / duration_seconds, 3),
            acknowledgements_per_second=round(acknowledged_deliveries / duration_seconds, 3),
            acknowledgement_latency_ms_p50=round(
                _nearest_rank_percentile(acknowledgement_latencies_ms, 0.50),
                3,
            ),
            acknowledgement_latency_ms_p95=round(
                _nearest_rank_percentile(acknowledgement_latencies_ms, 0.95),
                3,
            ),
            source_health=source_health.status.value,
            source_health_code=source_health.detail_code,
        )
    finally:
        await engine.dispose()


def _nearest_rank_percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


__all__ = [
    "MAX_SYNTHETIC_LOAD_EVENTS",
    "SyntheticLoadDemoSummary",
    "run_synthetic_load_demo",
]

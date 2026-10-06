import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from medihub.application.ingestion import IngestionService
from medihub.domain import (
    Coding,
    Destination,
    DestinationProtocol,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    SourceProvenance,
    TimeQuality,
)
from medihub.infrastructure.database import Base, create_database_engine
from medihub.infrastructure.event_store import EventIdentityConflictError, SqlAlchemyEventStore
from medihub.infrastructure.models import DeliveryOutboxRecord, EventRecord

OBSERVED_AT = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)
DATABASE_URLS = ["sqlite+aiosqlite:///:memory:"]
DATABASE_IDS = ["sqlite"]
if os.environ.get("MEDIHUB_TEST_DATABASE_URL"):
    DATABASE_URLS.append(os.environ["MEDIHUB_TEST_DATABASE_URL"])
    DATABASE_IDS.append("postgres")


def make_event() -> ObservationEvent:
    return ObservationEvent(
        event_id=uuid4(),
        site_id="synthetic-site",
        device=DeviceReference(
            device_id="sim-device-001",
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
        ),
        metric=Coding(
            system="https://example.invalid/medihub/synthetic-metrics",
            code="simulated-scalar-reading",
        ),
        value=42.5,
        source_unit=Coding(system="http://unitsofmeasure.org", code="1"),
        observed_at=OBSERVED_AT,
        received_at=OBSERVED_AT,
        time_quality=TimeQuality.DEVICE_SYNCHRONIZED,
        provenance=SourceProvenance(adapter_id="test-adapter", adapter_version="0.1.0"),
        origin=EventOrigin.SYNTHETIC,
    )


def make_destination(
    destination_id: str,
    *,
    accepts_synthetic_data: bool = False,
) -> Destination:
    return Destination(
        destination_id=destination_id,
        site_id="synthetic-site",
        name="synthetic test destination",
        protocol=DestinationProtocol.FHIR_R4,
        contract_version="test-contract-1",
        connection_ref="test-connection",
        accepts_synthetic_data=accepts_synthetic_data,
    )


async def initialize_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_event_and_outbox_are_durable_and_idempotent(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            event = make_event()
            destination = make_destination("test-fhir", accepts_synthetic_data=True)

            assert await store.append_with_outbox(event, [destination]) is True
            assert await store.append_with_outbox(event, [destination]) is False

            async with sessions() as session:
                event_count = await session.scalar(select(func.count()).select_from(EventRecord))
                outbox_count = await session.scalar(
                    select(func.count()).select_from(DeliveryOutboxRecord)
                )
                saved_event = await session.get(EventRecord, event.event_id)
                saved_intent = await session.scalar(select(DeliveryOutboxRecord))

            assert event_count == 1
            assert outbox_count == 1
            assert saved_event is not None
            assert saved_event.payload["origin"] == "synthetic"
            assert saved_intent is not None
            assert saved_intent.destination_id == "test-fhir"
            assert saved_intent.status == "queued"
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_event_id_reuse_with_different_content_fails_closed(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            event = make_event()
            destination = make_destination("test-fhir", accepts_synthetic_data=True)
            await store.append_with_outbox(event, [destination])
            changed_event = event.model_copy(update={"value": event.value + 1})

            with pytest.raises(EventIdentityConflictError, match="different canonical content"):
                await store.append_with_outbox(changed_event, [destination])

            async with sessions() as session:
                saved_event = await session.get(EventRecord, event.event_id)
                outbox_count = await session.scalar(
                    select(func.count()).select_from(DeliveryOutboxRecord)
                )
            assert saved_event is not None
            assert saved_event.payload["value"] == event.value
            assert outbox_count == 1
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_route_failures_are_isolated_before_outbox_creation(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            service = IngestionService(SqlAlchemyEventStore(sessions))
            event = make_event()
            production = make_destination("production-fhir")
            test_destination = make_destination("synthetic-fhir", accepts_synthetic_data=True)

            result = await service.ingest(event, [production, test_destination])

            assert result.duplicate is False
            assert result.queued_destination_ids == ("synthetic-fhir",)
            assert [
                (route.destination_id, route.reason_code) for route in result.blocked_routes
            ] == [("production-fhir", "synthetic_not_accepted")]
            async with sessions() as session:
                outbox_rows = list(await session.scalars(select(DeliveryOutboxRecord)))
            assert [row.destination_id for row in outbox_rows] == ["synthetic-fhir"]
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_duplicate_destination_configuration_does_not_persist_event(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            event = make_event()
            destination = make_destination("synthetic-fhir", accepts_synthetic_data=True)

            with pytest.raises(ValueError, match="duplicate destination IDs"):
                await store.append_with_outbox(event, [destination, destination])

            async with sessions() as session:
                event_count = await session.scalar(select(func.count()).select_from(EventRecord))
                outbox_count = await session.scalar(
                    select(func.count()).select_from(DeliveryOutboxRecord)
                )
            assert event_count == 0
            assert outbox_count == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())

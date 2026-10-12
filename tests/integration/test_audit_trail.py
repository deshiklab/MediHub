import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from medihub.domain import (
    AuditAction,
    BlockedRoute,
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
from medihub.infrastructure.event_store import SqlAlchemyEventStore
from medihub.infrastructure.models import (
    AuditEventRecord,
    DeliveryOutboxRecord,
    EventRecord,
    RoutingHoldRecord,
)

AUDIT_CANARY = "SYNTHETIC-NOT-FOR-AUDIT-CANARY"
OBSERVED_AT = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


def make_event() -> ObservationEvent:
    return ObservationEvent(
        event_id=uuid4(),
        site_id="synthetic-site",
        device=DeviceReference(
            device_id="sim-device-001",
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
        ),
        metric=Coding(system="https://example.invalid/metrics", code="synthetic-scalar"),
        value=42.5,
        source_unit=Coding(system="http://unitsofmeasure.org", code="1"),
        observed_at=OBSERVED_AT,
        received_at=OBSERVED_AT,
        time_quality=TimeQuality.DEVICE_SYNCHRONIZED,
        provenance=SourceProvenance(
            adapter_id="synthetic-test-adapter",
            adapter_version="0.1.0",
            source_message_id=AUDIT_CANARY,
        ),
        origin=EventOrigin.SYNTHETIC,
    )


def make_destination(site_id: str) -> Destination:
    return Destination(
        destination_id="synthetic-destination",
        site_id=site_id,
        name="synthetic receiver",
        protocol=DestinationProtocol.FHIR_R4,
        contract_version="synthetic-contract-v1",
        connection_ref="in-process",
        accepts_synthetic_data=True,
    )


def test_ingestion_audit_is_atomic_idempotent_and_payload_free() -> None:
    async def exercise() -> None:
        engine = create_database_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            event = make_event()
            accepted_destination = make_destination(event.site_id)
            blocked_route = BlockedRoute(
                destination_id="blocked-destination",
                reason_code="synthetic_not_accepted",
            )

            assert await store.append_with_outbox(
                event,
                [accepted_destination],
                blocked_routes=[blocked_route],
            )
            assert not await store.append_with_outbox(
                event,
                [accepted_destination],
                blocked_routes=[blocked_route],
            )

            async with sessions() as session:
                records = list(
                    await session.scalars(
                        select(AuditEventRecord).order_by(AuditEventRecord.action)
                    )
                )
            assert {record.action for record in records} == {
                AuditAction.EVENT_STORED.value,
                AuditAction.DELIVERY_INTENT_CREATED.value,
                AuditAction.ROUTE_HELD.value,
            }
            assert len(records) == 3
            assert all(record.site_id == event.site_id for record in records)
            assert all(record.actor_id == "system:ingestion" for record in records)
            assert all(record.correlation_id == str(event.event_id) for record in records)
            assert (
                next(
                    record.reason_code
                    for record in records
                    if record.action == AuditAction.ROUTE_HELD.value
                )
                == "synthetic_not_accepted"
            )

            serialized = json.dumps(
                [
                    {
                        "site_id": record.site_id,
                        "actor_id": record.actor_id,
                        "action": record.action,
                        "resource_type": record.resource_type,
                        "resource_id": record.resource_id,
                        "correlation_id": record.correlation_id,
                        "reason_code": record.reason_code,
                    }
                    for record in records
                ],
                sort_keys=True,
            )
            assert AUDIT_CANARY not in serialized
            assert "source_message_id" not in serialized
            assert "payload" not in serialized

            recent = await store.recent_audit_events(site_id=event.site_id, limit=2)
            assert len(recent) == 2
            assert all(item.site_id == event.site_id for item in recent)
            assert all(item.occurred_at.tzinfo is not None for item in recent)
            assert await store.recent_audit_events(site_id="other-site") == ()
            with pytest.raises(ValueError, match="limit must be between"):
                await store.recent_audit_events(site_id=event.site_id, limit=0)
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_audit_write_failure_rolls_back_event_routing_and_outbox() -> None:
    async def exercise() -> None:
        engine = create_database_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
                await connection.exec_driver_sql(
                    "CREATE TRIGGER reject_audit_insert BEFORE INSERT ON audit_event "
                    "BEGIN SELECT RAISE(ABORT, 'synthetic test failure'); END"
                )
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            event = make_event()

            with pytest.raises(IntegrityError):
                await store.append_with_outbox(
                    event,
                    [make_destination(event.site_id)],
                    blocked_routes=[
                        BlockedRoute(
                            destination_id="blocked-destination",
                            reason_code="synthetic_not_accepted",
                        )
                    ],
                )

            async with sessions() as session:
                event_count = await session.scalar(select(func.count()).select_from(EventRecord))
                outbox_count = await session.scalar(
                    select(func.count()).select_from(DeliveryOutboxRecord)
                )
                hold_count = await session.scalar(
                    select(func.count()).select_from(RoutingHoldRecord)
                )
                audit_count = await session.scalar(
                    select(func.count()).select_from(AuditEventRecord)
                )
            assert (event_count, outbox_count, hold_count, audit_count) == (0, 0, 0, 0)
        finally:
            await engine.dispose()

    asyncio.run(exercise())

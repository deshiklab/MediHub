import asyncio
import os
from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from medihub.application.ingestion import IngestionService
from medihub.application.outbox_worker import OutboxWorker
from medihub.domain import (
    AuditAction,
    Coding,
    DeliveryAttempt,
    DeliveryStatus,
    Destination,
    DestinationProtocol,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    SourceProvenance,
    TimeQuality,
)
from medihub.infrastructure.database import Base, create_database_engine
from medihub.infrastructure.event_store import (
    OutboxLeaseLostError,
    SqlAlchemyEventStore,
)
from medihub.infrastructure.models import (
    AuditEventRecord,
    DeliveryAttemptRecord,
    DeliveryOutboxRecord,
)
from medihub.ports import DestinationAdapter

OBSERVED_AT = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)
DATABASE_URLS = ["sqlite+aiosqlite:///:memory:"]
DATABASE_IDS = ["sqlite"]
if os.environ.get("MEDIHUB_TEST_DATABASE_URL"):
    DATABASE_URLS.append(os.environ["MEDIHUB_TEST_DATABASE_URL"])
    DATABASE_IDS.append("postgres")


class FakeClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current

    def advance(self, amount: timedelta) -> None:
        self.current += amount


class FakeDestinationAdapter(DestinationAdapter):
    def __init__(
        self,
        destination: Destination,
        clock: FakeClock,
        outcomes: list[DeliveryStatus] | None = None,
        *,
        raises: bool = False,
    ) -> None:
        self._destination = destination
        self._clock = clock
        self._outcomes = deque(outcomes or [])
        self._raises = raises
        self.calls = 0

    @property
    def destination(self) -> Destination:
        return self._destination

    async def send(self, delivery) -> DeliveryAttempt:
        self.calls += 1
        if self._raises:
            raise RuntimeError("synthetic patient identifier must not escape to storage")

        status = self._outcomes.popleft() if self._outcomes else DeliveryStatus.ACKNOWLEDGED
        codes = {
            DeliveryStatus.REJECTED: "receiver_rejected",
            DeliveryStatus.RETRYABLE_FAILURE: "receiver_timeout",
            DeliveryStatus.PERMANENT_FAILURE: "receiver_permanent",
        }
        return DeliveryAttempt(
            attempt_id=delivery.attempt_id,
            event_id=delivery.event.event_id,
            destination_id=delivery.destination_id,
            attempt_number=delivery.attempt_number,
            status=status,
            started_at=delivery.started_at,
            completed_at=max(self._clock(), delivery.started_at),
            acknowledgement_id=f"synthetic-ack-{self.calls}"
            if status is DeliveryStatus.ACKNOWLEDGED
            else None,
            error_code=codes.get(status),
        )


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
        provenance=SourceProvenance(adapter_id="worker-test", adapter_version="0.1.0"),
        origin=EventOrigin.SYNTHETIC,
    )


def make_destination(*, accepts_synthetic_data: bool = True) -> Destination:
    return Destination(
        destination_id="synthetic-receiver",
        site_id="synthetic-site",
        name="synthetic test receiver",
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
def test_worker_records_acknowledgement_and_stops_redelivery(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            event = make_event()
            destination = make_destination()
            await IngestionService(store).ingest(event, [destination])
            clock = FakeClock(OBSERVED_AT + timedelta(minutes=1))
            adapter = FakeDestinationAdapter(destination, clock)
            worker = OutboxWorker(store, {destination.destination_id: adapter}, clock=clock)

            result = await worker.dispatch_once()

            assert result is not None
            assert result.status is DeliveryStatus.ACKNOWLEDGED
            assert result.attempt_number == 1
            assert await worker.dispatch_once() is None
            async with sessions() as session:
                outbox = await session.scalar(select(DeliveryOutboxRecord))
                attempts = list(await session.scalars(select(DeliveryAttemptRecord)))
                audit_rows = list(await session.scalars(select(AuditEventRecord)))
            assert outbox is not None
            assert outbox.status == DeliveryStatus.ACKNOWLEDGED.value
            assert outbox.acknowledgement_id == "synthetic-ack-1"
            assert outbox.lease_token is None
            assert len(attempts) == 1
            assert attempts[0].status == DeliveryStatus.ACKNOWLEDGED.value
            assert {row.action for row in audit_rows} == {
                AuditAction.EVENT_STORED.value,
                AuditAction.DELIVERY_INTENT_CREATED.value,
                AuditAction.DELIVERY_ATTEMPT_STARTED.value,
                AuditAction.DELIVERY_ACKNOWLEDGED.value,
            }
            assert len(audit_rows) == 4
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_worker_retries_with_backoff_then_acknowledges(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            destination = make_destination()
            await IngestionService(store).ingest(make_event(), [destination])
            clock = FakeClock(OBSERVED_AT + timedelta(minutes=1))
            adapter = FakeDestinationAdapter(
                destination,
                clock,
                [DeliveryStatus.RETRYABLE_FAILURE, DeliveryStatus.ACKNOWLEDGED],
            )
            worker = OutboxWorker(store, {destination.destination_id: adapter}, clock=clock)

            first = await worker.dispatch_once()
            assert first is not None
            assert first.status is DeliveryStatus.RETRYABLE_FAILURE
            assert first.error_code == "receiver_timeout"
            clock.advance(timedelta(seconds=1))
            assert await worker.dispatch_once() is None
            clock.advance(timedelta(seconds=1))
            second = await worker.dispatch_once()

            assert second is not None
            assert second.status is DeliveryStatus.ACKNOWLEDGED
            assert second.attempt_number == 2
            async with sessions() as session:
                outbox = await session.scalar(select(DeliveryOutboxRecord))
                attempts = list(
                    await session.scalars(
                        select(DeliveryAttemptRecord).order_by(DeliveryAttemptRecord.attempt_number)
                    )
                )
                audit_rows = list(await session.scalars(select(AuditEventRecord)))
            assert outbox is not None
            assert outbox.status == DeliveryStatus.ACKNOWLEDGED.value
            assert [item.status for item in attempts] == [
                DeliveryStatus.RETRYABLE_FAILURE.value,
                DeliveryStatus.ACKNOWLEDGED.value,
            ]
            actions = [row.action for row in audit_rows]
            assert actions.count(AuditAction.DELIVERY_ATTEMPT_STARTED.value) == 2
            assert AuditAction.DELIVERY_RETRY_SCHEDULED.value in actions
            assert AuditAction.DELIVERY_ACKNOWLEDGED.value in actions
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_worker_sanitizes_adapter_exceptions(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            destination = make_destination()
            await IngestionService(store).ingest(make_event(), [destination])
            clock = FakeClock(OBSERVED_AT + timedelta(minutes=1))
            adapter = FakeDestinationAdapter(destination, clock, raises=True)
            worker = OutboxWorker(store, {destination.destination_id: adapter}, clock=clock)

            result = await worker.dispatch_once()

            assert result is not None
            assert result.status is DeliveryStatus.RETRYABLE_FAILURE
            assert result.error_code == "adapter_exception"
            assert result.error_summary is None
            async with sessions() as session:
                stored_attempt = await session.scalar(select(DeliveryAttemptRecord))
            assert stored_attempt is not None
            assert stored_attempt.error_code == "adapter_exception"
            assert not hasattr(stored_attempt, "error_summary")
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_expired_lease_recovers_and_rejects_stale_completion(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            event = make_event()
            destination = make_destination()
            await IngestionService(store).ingest(event, [destination])
            start = OBSERVED_AT + timedelta(minutes=1)
            first_claim = await store.claim_next(
                destination_ids=[destination.destination_id],
                now=start,
                lease_for=timedelta(seconds=10),
            )
            second_claim = await store.claim_next(
                destination_ids=[destination.destination_id],
                now=start + timedelta(seconds=11),
                lease_for=timedelta(seconds=10),
            )

            assert first_claim is not None
            assert second_claim is not None
            assert second_claim.outbox_id == first_claim.outbox_id
            assert second_claim.attempt_number == 2
            stale_ack = DeliveryAttempt(
                attempt_id=first_claim.attempt_id,
                event_id=event.event_id,
                destination_id=destination.destination_id,
                attempt_number=first_claim.attempt_number,
                status=DeliveryStatus.ACKNOWLEDGED,
                started_at=first_claim.started_at,
                completed_at=start + timedelta(seconds=12),
                acknowledgement_id="stale-ack",
            )
            with pytest.raises(OutboxLeaseLostError, match="lost or superseded"):
                await store.complete(first_claim, stale_ack, retry_at=None)

            async with sessions() as session:
                attempts = list(
                    await session.scalars(
                        select(DeliveryAttemptRecord).order_by(DeliveryAttemptRecord.attempt_number)
                    )
                )
                audit_rows = list(await session.scalars(select(AuditEventRecord)))
            assert attempts[0].status == DeliveryStatus.RETRYABLE_FAILURE.value
            assert attempts[0].error_code == "lease_expired"
            assert attempts[1].status == DeliveryStatus.SENT.value
            lease_events = [
                row for row in audit_rows if row.action == AuditAction.DELIVERY_LEASE_EXPIRED.value
            ]
            assert len(lease_events) == 1
            assert lease_events[0].reason_code == "lease_expired"
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_retry_limit_moves_outbox_to_permanent_failure(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            destination = make_destination()
            await IngestionService(store).ingest(make_event(), [destination])
            clock = FakeClock(OBSERVED_AT + timedelta(minutes=1))
            adapter = FakeDestinationAdapter(
                destination,
                clock,
                [DeliveryStatus.RETRYABLE_FAILURE],
            )
            worker = OutboxWorker(
                store,
                {destination.destination_id: adapter},
                max_attempts=1,
                clock=clock,
            )

            result = await worker.dispatch_once()

            assert result is not None
            assert result.status is DeliveryStatus.RETRYABLE_FAILURE
            async with sessions() as session:
                outbox = await session.scalar(select(DeliveryOutboxRecord))
                audit_rows = list(await session.scalars(select(AuditEventRecord)))
            assert outbox is not None
            assert outbox.status == DeliveryStatus.PERMANENT_FAILURE.value
            assert outbox.last_error_code == "receiver_timeout"
            exhausted = [
                row
                for row in audit_rows
                if row.action == AuditAction.DELIVERY_RETRY_EXHAUSTED.value
            ]
            assert len(exhausted) == 1
            assert exhausted[0].reason_code == "receiver_timeout"
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.parametrize("database_url", DATABASE_URLS, ids=DATABASE_IDS)
def test_worker_rechecks_synthetic_data_destination_boundary(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            event = make_event()
            production_destination = make_destination(accepts_synthetic_data=False)
            # Deliberately bypass ingestion policy to verify the final sending boundary.
            await store.append_with_outbox(event, [production_destination])
            clock = FakeClock(OBSERVED_AT + timedelta(minutes=1))
            adapter = FakeDestinationAdapter(production_destination, clock)
            worker = OutboxWorker(
                store,
                {production_destination.destination_id: adapter},
                clock=clock,
            )

            result = await worker.dispatch_once()

            assert result is not None
            assert result.status is DeliveryStatus.PERMANENT_FAILURE
            assert result.error_code == "synthetic_not_accepted"
            assert adapter.calls == 0
        finally:
            await engine.dispose()

    asyncio.run(exercise())


@pytest.mark.skipif(
    not os.environ.get("MEDIHUB_TEST_DATABASE_URL", "").startswith("postgresql+"),
    reason="PostgreSQL row-lock behavior is verified by the CI database service",
)
def test_postgres_workers_claim_different_outbox_rows_concurrently() -> None:
    database_url = os.environ["MEDIHUB_TEST_DATABASE_URL"]

    async def exercise() -> None:
        engine = create_database_engine(database_url)
        try:
            await initialize_schema(engine)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            store = SqlAlchemyEventStore(sessions)
            destination = make_destination()
            ingest = IngestionService(store)
            await ingest.ingest(make_event(), [destination])
            await ingest.ingest(make_event(), [destination])
            now = OBSERVED_AT + timedelta(minutes=1)

            claims = await asyncio.gather(
                store.claim_next(
                    destination_ids=[destination.destination_id],
                    now=now,
                    lease_for=timedelta(seconds=30),
                ),
                store.claim_next(
                    destination_ids=[destination.destination_id],
                    now=now,
                    lease_for=timedelta(seconds=30),
                ),
            )

            assert all(claim is not None for claim in claims)
            assert len({claim.outbox_id for claim in claims if claim is not None}) == 2
        finally:
            await engine.dispose()

    asyncio.run(exercise())

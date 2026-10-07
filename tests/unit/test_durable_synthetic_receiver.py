"""Durable idempotency guarantees of the offline synthetic FHIR test receiver."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from medihub.adapters.destinations.durable_synthetic_receiver import (
    SyntheticDurableFhirR4TestReceiver,
)
from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.domain import (
    ClaimedDelivery,
    DeliveryAttempt,
    DeliveryStatus,
    Destination,
    DestinationProtocol,
)


def test_durable_receiver_reuses_persisted_acknowledgement_after_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "receiver-inbox.sqlite3"

    async def exercise_receiver_restart() -> None:
        simulator = SyntheticDeviceAdapter(
            SyntheticDeviceConfig(
                event_count=1,
                seed=31,
                start_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
            )
        )
        try:
            events = [event async for event in simulator.read_events()]
        finally:
            await simulator.close()
        if len(events) != 1:
            raise AssertionError("simulator did not emit exactly one event")
        event = events[0]

        destination = Destination(
            destination_id="medihub.synthetic-durable-receiver-test",
            site_id=event.site_id,
            name="Synthetic durable receiver test",
            protocol=DestinationProtocol.FHIR_R4,
            contract_version="synthetic-test-v1",
            connection_ref="in-process",
            accepts_synthetic_data=True,
        )

        async def send(
            receiver: SyntheticDurableFhirR4TestReceiver,
            attempt_number: int,
        ) -> DeliveryAttempt:
            started_at = datetime.now(UTC)
            return await receiver.send(
                ClaimedDelivery(
                    outbox_id=uuid4(),
                    attempt_id=uuid4(),
                    attempt_number=attempt_number,
                    destination_id=destination.destination_id,
                    lease_token=uuid4(),
                    lease_expires_at=started_at + timedelta(minutes=1),
                    started_at=started_at,
                    event=event,
                )
            )

        first_receiver = await SyntheticDurableFhirR4TestReceiver.open(
            destination,
            database_path,
        )
        try:
            first_attempt = await send(first_receiver, 1)
            assert first_attempt.status is DeliveryStatus.ACKNOWLEDGED
            assert first_attempt.acknowledgement_id is not None
            assert first_receiver.unique_receipt_count == 1
        finally:
            await first_receiver.close()

        restarted_receiver = await SyntheticDurableFhirR4TestReceiver.open(
            destination,
            database_path,
        )
        try:
            assert restarted_receiver.unique_receipt_count == 1
            retry_attempt = await send(restarted_receiver, 2)
            assert retry_attempt.status is DeliveryStatus.ACKNOWLEDGED
            assert retry_attempt.acknowledgement_id == first_attempt.acknowledgement_id
            assert restarted_receiver.delivery_attempt_count == 1
            assert restarted_receiver.unique_receipt_count == 1
        finally:
            await restarted_receiver.close()

    asyncio.run(exercise_receiver_restart())

    with sqlite3.connect(database_path) as connection:
        columns = connection.execute("PRAGMA table_info(synthetic_receiver_inbox)").fetchall()
        receipt_count = connection.execute(
            "SELECT COUNT(*) FROM synthetic_receiver_inbox"
        ).fetchone()[0]

    assert [column[1] for column in columns] == ["event_id", "acknowledgement_id"]
    assert receipt_count == 1

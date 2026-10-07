"""File-backed, test-only FHIR receiver with a durable synthetic event-ID inbox."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, uuid5

from medihub.adapters.destinations.fhir_r4 import (
    FhirR4MappingError,
    SyntheticFhirR4DestinationAdapter,
    build_synthetic_observation,
)
from medihub.application.routing import RouteBlockedError, assert_route_eligible
from medihub.domain import ClaimedDelivery, DeliveryAttempt, DeliveryStatus, Destination

if TYPE_CHECKING:
    import aiosqlite


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SyntheticDurableFhirR4TestReceiver(SyntheticFhirR4DestinationAdapter):
    """Synthetic-only receiver that persists just event IDs and stable ACK IDs.

    This test adapter has no network transport and is not a production receiver.
    Its small SQLite inbox lets local resilience tests simulate the receiver
    process restarting while preserving its idempotency state.
    """

    def __init__(
        self,
        destination: Destination,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        super().__init__(destination, clock=clock)
        self._database_path = Path(database_path)
        self._ledger: aiosqlite.Connection | None = None
        self._ledger_lock = asyncio.Lock()

    @classmethod
    async def open(
        cls,
        destination: Destination,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> SyntheticDurableFhirR4TestReceiver:
        """Open or create a local idempotency ledger, reloading its receipt count."""

        receiver = cls(destination, database_path, clock=clock)
        await receiver._open_ledger()
        return receiver

    async def _open_ledger(self) -> None:
        if self._ledger is not None:
            raise RuntimeError("synthetic_receiver_already_open")
        import aiosqlite

        ledger = await aiosqlite.connect(str(self._database_path))
        try:
            await ledger.execute(
                """
                CREATE TABLE IF NOT EXISTS synthetic_receiver_inbox (
                    event_id TEXT PRIMARY KEY,
                    acknowledgement_id TEXT NOT NULL
                )
                """
            )
            await ledger.commit()
            cursor = await ledger.execute("SELECT COUNT(*) FROM synthetic_receiver_inbox")
            row = await cursor.fetchone()
            await cursor.close()
            self._unique_receipt_count = int(row[0]) if row else 0
        except Exception:
            await ledger.close()
            raise
        self._ledger = ledger

    async def close(self) -> None:
        """Close the local ledger connection; repeated closes are safe."""

        async with self._ledger_lock:
            ledger = self._ledger
            self._ledger = None
            if ledger is not None:
                await ledger.close()

    async def send(self, delivery: ClaimedDelivery) -> DeliveryAttempt:
        """Validate and durably deduplicate one synthetic event before ACKing."""

        if self._ledger is None:
            raise RuntimeError("synthetic_receiver_closed")
        try:
            assert_route_eligible(delivery.event, self.destination)
            build_synthetic_observation(delivery.event)
        except (RouteBlockedError, FhirR4MappingError):
            # Preserve the base adapter's stable safe failure behavior.
            return await super().send(delivery)

        event_id = delivery.event.event_id
        candidate_acknowledgement_uuid = uuid5(
            NAMESPACE_URL,
            f"medihub-fhir-r4-synthetic-ack:{self.destination.destination_id}:{event_id}",
        )
        candidate_acknowledgement_id = f"synthetic-fhir-ack-{candidate_acknowledgement_uuid.hex}"
        self._delivery_attempt_count += 1
        async with self._ledger_lock:
            ledger = self._ledger
            if ledger is None:
                raise RuntimeError("synthetic_receiver_closed")
            cursor = await ledger.execute(
                """
                INSERT INTO synthetic_receiver_inbox (event_id, acknowledgement_id)
                VALUES (?, ?)
                ON CONFLICT(event_id) DO NOTHING
                """,
                (str(event_id), candidate_acknowledgement_id),
            )
            inserted = cursor.rowcount == 1
            await cursor.close()
            await ledger.commit()
            if inserted:
                self._unique_receipt_count += 1
                acknowledgement_id = candidate_acknowledgement_id
            else:
                cursor = await ledger.execute(
                    "SELECT acknowledgement_id FROM synthetic_receiver_inbox WHERE event_id = ?",
                    (str(event_id),),
                )
                row = await cursor.fetchone()
                await cursor.close()
                if row is None:
                    raise RuntimeError("synthetic_receiver_inbox_receipt_missing")
                acknowledgement_id = str(row[0])

        return DeliveryAttempt(
            attempt_id=delivery.attempt_id,
            event_id=event_id,
            destination_id=delivery.destination_id,
            attempt_number=delivery.attempt_number,
            status=DeliveryStatus.ACKNOWLEDGED,
            started_at=delivery.started_at,
            completed_at=max(self._clock(), delivery.started_at),
            acknowledgement_id=acknowledgement_id,
        )


__all__ = ["SyntheticDurableFhirR4TestReceiver"]

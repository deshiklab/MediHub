"""Ports between the domain and transport, persistence, and receiver adapters."""

from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from medihub.domain import (
    AdapterHealth,
    ClaimedDelivery,
    DeliveryAttempt,
    Destination,
    ObservationEvent,
)


@runtime_checkable
class DeviceAdapter(Protocol):
    """Read-only device adapter that yields normalized events, never EHR messages."""

    @property
    def adapter_id(self) -> str: ...

    @property
    def adapter_version(self) -> str: ...

    async def read_events(self) -> AsyncIterator[ObservationEvent]: ...

    async def health(self) -> AdapterHealth: ...

    async def close(self) -> None: ...


@runtime_checkable
class EventStore(Protocol):
    """Atomically persist a new event and its eligible delivery intents."""

    async def append_with_outbox(
        self,
        event: ObservationEvent,
        destinations: Sequence[Destination],
    ) -> bool:
        """Return True if inserted; an exact duplicate is a no-op returning False."""
        ...


@runtime_checkable
class OutboxStore(Protocol):
    """Lease eligible intents and atomically record each final delivery outcome."""

    async def claim_next(
        self,
        *,
        destination_ids: Sequence[str],
        now: datetime,
        lease_for: timedelta,
    ) -> ClaimedDelivery | None: ...

    async def complete(
        self,
        delivery: ClaimedDelivery,
        attempt: DeliveryAttempt,
        *,
        retry_at: datetime | None,
    ) -> None: ...


@runtime_checkable
class DestinationAdapter(Protocol):
    """Destination-specific sender that returns a completed, correlated attempt."""

    @property
    def destination(self) -> Destination: ...

    async def send(self, delivery: ClaimedDelivery) -> DeliveryAttempt: ...

"""One-shot, in-process delivery faults for the synthetic operations demo only."""

import asyncio
from datetime import UTC, datetime
from typing import Literal

from medihub.adapters.destinations.fhir_r4 import SyntheticFhirR4DestinationAdapter
from medihub.domain import ClaimedDelivery, DeliveryAttempt, DeliveryStatus, EventOrigin
from medihub.domain.delivery import Destination

SyntheticFaultMode = Literal["retry_once", "reject_once"]


class SyntheticFaultInjectorError(ValueError):
    """Safe control error for the bounded synthetic receiver fault injector."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SyntheticReceiverFaultInjector:
    """Wrap the local FHIR test sink with a single pending synthetic failure.

    This wrapper cannot construct a network connection. It only injects one
    deterministic outcome into the in-process receiver path, then delegates all
    later attempts to the wrapped synthetic receiver.
    """

    def __init__(self, receiver: SyntheticFhirR4DestinationAdapter) -> None:
        if not receiver.destination.accepts_synthetic_data:
            raise ValueError("fault injection requires a synthetic-only destination")
        self._receiver = receiver
        self._lock = asyncio.Lock()
        self._armed_fault: SyntheticFaultMode | None = None
        self._last_injected_fault: SyntheticFaultMode | None = None
        self._last_outcome: str | None = None
        self._faults_injected = 0

    @property
    def destination(self) -> Destination:
        return self._receiver.destination

    async def arm(self, mode: SyntheticFaultMode) -> dict[str, object]:
        async with self._lock:
            if self._armed_fault is not None:
                raise SyntheticFaultInjectorError("synthetic_fault_already_armed")
            self._armed_fault = mode
            return self._snapshot_unlocked()

    async def clear(self) -> dict[str, object]:
        async with self._lock:
            self._armed_fault = None
            return self._snapshot_unlocked()

    async def status(self) -> dict[str, object]:
        async with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> dict[str, object]:
        return {
            "mode": "synthetic_test_only",
            "armed_fault": self._armed_fault,
            "last_injected_fault": self._last_injected_fault,
            "last_outcome": self._last_outcome,
            "faults_injected": self._faults_injected,
            "network_enabled": False,
        }

    async def send(self, delivery: ClaimedDelivery) -> DeliveryAttempt:
        if delivery.event.origin is not EventOrigin.SYNTHETIC:
            return await self._receiver.send(delivery)
        async with self._lock:
            fault = self._armed_fault
            if fault is not None:
                self._armed_fault = None
                self._last_injected_fault = fault
                self._faults_injected += 1
                if fault == "retry_once":
                    status = DeliveryStatus.RETRYABLE_FAILURE
                    error_code = "synthetic_test_retryable_failure"
                else:
                    status = DeliveryStatus.REJECTED
                    error_code = "synthetic_test_receiver_rejected"
                self._last_outcome = status.value

        if fault is None:
            return await self._receiver.send(delivery)

        completed_at = max(datetime.now(UTC), delivery.started_at)
        return DeliveryAttempt(
            attempt_id=delivery.attempt_id,
            event_id=delivery.event.event_id,
            destination_id=delivery.destination_id,
            attempt_number=delivery.attempt_number,
            status=status,
            started_at=delivery.started_at,
            completed_at=completed_at,
            error_code=error_code,
        )


__all__ = [
    "SyntheticFaultInjectorError",
    "SyntheticFaultMode",
    "SyntheticReceiverFaultInjector",
]

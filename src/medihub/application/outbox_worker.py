"""Single-item outbox dispatcher with leases, bounded retries, and safe failures."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from medihub.domain import (
    ClaimedDelivery,
    DeliveryAttempt,
    DeliveryStatus,
    EventOrigin,
)
from medihub.ports import DestinationAdapter, OutboxStore

from .routing import RouteBlockedError, assert_route_eligible


class DestinationAdapterContractError(ValueError):
    """A destination adapter returned an uncorrelated or incomplete outcome."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class OutboxWorker:
    """Dispatch one eligible intent per call; delivery semantics are at-least-once.

    Destination implementations must use the canonical event ID as their receiver
    idempotency key where the receiver supports it. A crash after a remote send but
    before local acknowledgement persistence can otherwise lead to a repeated send.
    """

    def __init__(
        self,
        outbox: OutboxStore,
        adapters: Mapping[str, DestinationAdapter],
        *,
        max_attempts: int = 5,
        lease_duration: timedelta = timedelta(seconds=60),
        base_retry_delay: timedelta = timedelta(seconds=2),
        max_retry_delay: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        if base_retry_delay < timedelta(0):
            raise ValueError("base_retry_delay must not be negative")
        if max_retry_delay < base_retry_delay:
            raise ValueError("max_retry_delay must be at least base_retry_delay")
        for destination_id, adapter in adapters.items():
            if destination_id != adapter.destination.destination_id:
                raise ValueError("adapter mapping key must match its destination_id")

        self._outbox = outbox
        self._adapters = dict(adapters)
        self._enabled_destination_ids = tuple(
            destination_id
            for destination_id, adapter in self._adapters.items()
            if adapter.destination.enabled
        )
        self._max_attempts = max_attempts
        self._lease_duration = lease_duration
        self._base_retry_delay = base_retry_delay
        self._max_retry_delay = max_retry_delay
        self._clock = clock

    async def dispatch_once(self) -> DeliveryAttempt | None:
        """Claim, send, and record one outcome; return None when nothing is due."""

        if not self._enabled_destination_ids:
            return None
        now = self._aware_now()
        delivery = await self._outbox.claim_next(
            destination_ids=self._enabled_destination_ids,
            now=now,
            lease_for=self._lease_duration,
        )
        if delivery is None:
            return None

        adapter = self._adapters[delivery.destination_id]
        destination = adapter.destination
        if delivery.event.origin is EventOrigin.SYNTHETIC:
            try:
                assert_route_eligible(delivery.event, destination)
            except RouteBlockedError as error:
                attempt = self._failure(
                    delivery,
                    DeliveryStatus.PERMANENT_FAILURE,
                    error.code,
                )
                await self._outbox.complete(delivery, attempt, retry_at=None)
                return attempt
        elif delivery.event.site_id != destination.site_id:
            attempt = self._failure(
                delivery,
                DeliveryStatus.PERMANENT_FAILURE,
                "site_mismatch",
            )
            await self._outbox.complete(delivery, attempt, retry_at=None)
            return attempt

        if delivery.attempt_number > self._max_attempts:
            attempt = self._failure(
                delivery,
                DeliveryStatus.PERMANENT_FAILURE,
                "retry_limit_exceeded",
            )
        else:
            try:
                attempt = await adapter.send(delivery)
                self._validate_adapter_attempt(delivery, attempt)
            except DestinationAdapterContractError:
                attempt = self._failure(
                    delivery,
                    DeliveryStatus.PERMANENT_FAILURE,
                    "adapter_contract_violation",
                )
            except Exception:
                # Exception text can include source payloads or identifiers; never persist it.
                attempt = self._failure(
                    delivery,
                    DeliveryStatus.RETRYABLE_FAILURE,
                    "adapter_exception",
                )

        retry_at = self._retry_at(delivery, attempt)
        await self._outbox.complete(delivery, attempt, retry_at=retry_at)
        return attempt

    def _aware_now(self) -> datetime:
        moment = self._clock()
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("worker clock must return a timezone-aware datetime")
        return moment.astimezone(UTC)

    def _failure(
        self,
        delivery: ClaimedDelivery,
        status: DeliveryStatus,
        error_code: str,
    ) -> DeliveryAttempt:
        completed_at = max(self._aware_now(), delivery.started_at)
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

    @staticmethod
    def _validate_adapter_attempt(
        delivery: ClaimedDelivery,
        attempt: object,
    ) -> None:
        if not isinstance(attempt, DeliveryAttempt):
            raise DestinationAdapterContractError("adapter result must be a DeliveryAttempt")
        if (
            attempt.attempt_id != delivery.attempt_id
            or attempt.event_id != delivery.event.event_id
            or attempt.destination_id != delivery.destination_id
            or attempt.attempt_number != delivery.attempt_number
            or attempt.started_at != delivery.started_at
        ):
            raise DestinationAdapterContractError("adapter result does not match its claim")
        if attempt.status in {DeliveryStatus.QUEUED, DeliveryStatus.SENT}:
            raise DestinationAdapterContractError("adapter must return a final outcome")

    def _retry_at(
        self,
        delivery: ClaimedDelivery,
        attempt: DeliveryAttempt,
    ) -> datetime | None:
        if (
            attempt.status is not DeliveryStatus.RETRYABLE_FAILURE
            or delivery.attempt_number >= self._max_attempts
        ):
            return None

        exponent = min(delivery.attempt_number - 1, 30)
        delay_seconds = self._base_retry_delay.total_seconds() * (2**exponent)
        delay = min(delay_seconds, self._max_retry_delay.total_seconds())
        return attempt.completed_at + timedelta(seconds=delay)

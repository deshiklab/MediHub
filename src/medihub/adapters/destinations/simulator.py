"""In-process synthetic receiver for end-to-end tests; it opens no network socket."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from medihub.application.routing import RouteBlockedError, assert_route_eligible
from medihub.domain import (
    ClaimedDelivery,
    DeliveryAttempt,
    DeliveryStatus,
    Destination,
    DestinationProtocol,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SyntheticDestinationAdapter:
    """Test sink that ACKs synthetic events and remembers stable event IDs only."""

    def __init__(
        self,
        destination: Destination | None = None,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._destination = destination or Destination(
            destination_id="medihub.synthetic-test-receiver",
            site_id="synthetic-site",
            name="MediHub in-process synthetic receiver",
            protocol=DestinationProtocol.MEDIHUB_API,
            contract_version="synthetic-test-v1",
            connection_ref="in-process",
            enabled=True,
            accepts_synthetic_data=True,
        )
        self._clock = clock
        self._seen_event_ids: set[UUID] = set()
        self._delivery_attempt_count = 0

    @property
    def destination(self) -> Destination:
        return self._destination

    @property
    def unique_receipt_count(self) -> int:
        return len(self._seen_event_ids)

    @property
    def delivery_attempt_count(self) -> int:
        return self._delivery_attempt_count

    async def send(self, delivery: ClaimedDelivery) -> DeliveryAttempt:
        self._delivery_attempt_count += 1
        try:
            assert_route_eligible(delivery.event, self._destination)
        except RouteBlockedError as error:
            return DeliveryAttempt(
                attempt_id=delivery.attempt_id,
                event_id=delivery.event.event_id,
                destination_id=delivery.destination_id,
                attempt_number=delivery.attempt_number,
                status=DeliveryStatus.PERMANENT_FAILURE,
                started_at=delivery.started_at,
                completed_at=max(self._clock(), delivery.started_at),
                error_code=error.code,
            )

        self._seen_event_ids.add(delivery.event.event_id)
        ack_id = uuid5(
            NAMESPACE_URL,
            f"medihub-synthetic-ack:{self._destination.destination_id}:{delivery.event.event_id}",
        )
        return DeliveryAttempt(
            attempt_id=delivery.attempt_id,
            event_id=delivery.event.event_id,
            destination_id=delivery.destination_id,
            attempt_number=delivery.attempt_number,
            status=DeliveryStatus.ACKNOWLEDGED,
            started_at=delivery.started_at,
            completed_at=max(self._clock(), delivery.started_at),
            acknowledgement_id=f"synthetic-ack-{ack_id.hex}",
        )

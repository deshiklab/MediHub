"""Validate routing decisions and atomically persist events with eligible intents."""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from medihub.domain import Destination, ObservationEvent, PatientAssociation
from medihub.ports import EventStore

from .routing import RouteBlockedError, assert_route_eligible


@dataclass(frozen=True, slots=True)
class BlockedRoute:
    """Safe-to-log route rejection with a stable code and no clinical payload."""

    destination_id: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Summary of durable ingestion and destination decisions."""

    event_id: UUID
    duplicate: bool
    queued_destination_ids: tuple[str, ...]
    blocked_routes: tuple[BlockedRoute, ...]


class IngestionService:
    """Keep route failures isolated while persisting one event and valid intents."""

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    async def ingest(
        self,
        event: ObservationEvent,
        destinations: Sequence[Destination],
        *,
        association: PatientAssociation | None = None,
    ) -> IngestionResult:
        """Persist the event and outbox only for routes that pass policy checks.

        A blocked destination does not prevent another eligible destination from
        receiving an intent. The event itself is retained even if every route is
        blocked, so a later reviewed workflow can decide what happens next.
        """

        destination_ids = [destination.destination_id for destination in destinations]
        if len(destination_ids) != len(set(destination_ids)):
            raise ValueError("destination list contains duplicate destination IDs")

        eligible: list[Destination] = []
        blocked: list[BlockedRoute] = []
        for destination in destinations:
            try:
                assert_route_eligible(event, destination, association=association)
            except RouteBlockedError as error:
                blocked.append(
                    BlockedRoute(
                        destination_id=destination.destination_id,
                        reason_code=error.code,
                    )
                )
            else:
                eligible.append(destination)

        inserted = await self._event_store.append_with_outbox(event, eligible)
        queued_ids = (
            tuple(destination.destination_id for destination in eligible) if inserted else ()
        )
        return IngestionResult(
            event_id=event.event_id,
            duplicate=not inserted,
            queued_destination_ids=queued_ids,
            blocked_routes=tuple(blocked),
        )

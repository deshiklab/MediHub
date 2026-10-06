"""Safe NDJSON loading and idempotent replay for synthetic observation fixtures."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from medihub.domain import EventOrigin, ObservationEvent
from medihub.ports import EventStore

from .ingestion import IngestionService

MAX_REPLAY_EVENTS = 10_000
MAX_REPLAY_FILE_BYTES = 50 * 1024 * 1024
MAX_REPLAY_LINE_BYTES = 64 * 1024


class ReplayInputError(ValueError):
    """A synthetic replay file is invalid or exceeds safe local limits."""


@dataclass(frozen=True, slots=True)
class ReplaySummary:
    events_read: int
    events_inserted: int
    duplicate_events: int


def load_synthetic_events(path: Path) -> tuple[ObservationEvent, ...]:
    """Read a bounded NDJSON file and reject live or patient-associated events."""

    try:
        file_size = path.stat().st_size
        if file_size > MAX_REPLAY_FILE_BYTES:
            raise ReplayInputError("replay file exceeds the 50 MiB limit")
        events: list[ObservationEvent] = []
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if len(line.encode("utf-8")) > MAX_REPLAY_LINE_BYTES:
                    raise ReplayInputError(f"line {line_number} exceeds the 64 KiB limit")
                if not line.strip():
                    continue
                if len(events) >= MAX_REPLAY_EVENTS:
                    raise ReplayInputError("replay file exceeds the 10000 event limit")
                try:
                    event = ObservationEvent.model_validate_json(line)
                except ValidationError:
                    raise ReplayInputError(f"line {line_number} failed event validation") from None
                if event.origin is not EventOrigin.SYNTHETIC:
                    raise ReplayInputError(f"line {line_number} is not marked synthetic")
                if event.patient is not None:
                    raise ReplayInputError(f"line {line_number} contains patient context")
                events.append(event)
    except ReplayInputError:
        raise
    except (OSError, UnicodeError):
        raise ReplayInputError("replay file could not be read as UTF-8") from None
    return tuple(events)


async def replay_synthetic_events(
    events: Sequence[ObservationEvent],
    event_store: EventStore,
) -> ReplaySummary:
    """Persist events individually; re-running the same fixture is idempotent."""

    ingestion = IngestionService(event_store)
    inserted = 0
    duplicates = 0
    for event in events:
        if event.origin is not EventOrigin.SYNTHETIC or event.patient is not None:
            raise ReplayInputError("replay accepts only synthetic events without patient context")
        result = await ingestion.ingest(event, ())
        if result.duplicate:
            duplicates += 1
        else:
            inserted += 1
    return ReplaySummary(
        events_read=len(events),
        events_inserted=inserted,
        duplicate_events=duplicates,
    )

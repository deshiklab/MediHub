"""Offline loading/execution for the permanently synthetic-only mapping workbench."""

import tomllib
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from medihub.domain import (
    ObservationEvent,
    SyntheticMappingError,
    SyntheticMappingResult,
    SyntheticMappingSet,
)

MAX_SYNTHETIC_MAPPING_SIZE_BYTES = 64 * 1024


class SyntheticMappingConfigError(ValueError):
    """A local synthetic mapping file failed safe parsing or schema validation."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SyntheticMappingBatchError(ValueError):
    """One or more synthetic events could not be mapped; no partial output is emitted."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def load_synthetic_mapping(path: Path) -> SyntheticMappingSet:
    """Load a bounded, strict TOML mapping set without exposing file values."""

    try:
        with path.open("rb") as mapping_file:
            content = mapping_file.read(MAX_SYNTHETIC_MAPPING_SIZE_BYTES + 1)
    except OSError:
        raise SyntheticMappingConfigError("mapping_file_unreadable") from None
    if len(content) > MAX_SYNTHETIC_MAPPING_SIZE_BYTES:
        raise SyntheticMappingConfigError("mapping_file_too_large")

    try:
        parsed = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise SyntheticMappingConfigError("invalid_mapping_toml") from None

    try:
        return SyntheticMappingSet.model_validate(parsed)
    except ValidationError:
        raise SyntheticMappingConfigError("invalid_mapping_schema") from None


def map_synthetic_events(
    events: Sequence[ObservationEvent],
    mapping_set: SyntheticMappingSet,
) -> tuple[SyntheticMappingResult, ...]:
    """Map a bounded synthetic batch atomically in memory; never return partial results."""

    if not events:
        raise SyntheticMappingBatchError("mapping_input_empty")

    mapped: list[SyntheticMappingResult] = []
    try:
        for event in events:
            mapped.append(mapping_set.map_event(event))
    except SyntheticMappingError as error:
        raise SyntheticMappingBatchError(error.code) from None
    return tuple(mapped)

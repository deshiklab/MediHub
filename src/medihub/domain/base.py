"""Shared validation primitives for MediHub domain models."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


def _require_timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone or UTC offset")
    return value


AwareDateTime = Annotated[datetime, AfterValidator(_require_timezone_aware)]
NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]


class DomainModel(BaseModel):
    """Immutable, strict-about-shape base for persisted domain contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

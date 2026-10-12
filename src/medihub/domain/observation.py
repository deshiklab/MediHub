"""Canonical device observation event contracts.

The model intentionally omits names, raw payloads, and national identifiers. Any
patient reference added by an approved context workflow is still sensitive data
and must be access-controlled and excluded from ordinary logs.
"""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import AwareDateTime, DomainModel, NonEmptyText
from .device import DeviceReference


class EventOrigin(StrEnum):
    DEVICE = "device"
    SYNTHETIC = "synthetic"
    MANUAL = "manual"


class TimeQuality(StrEnum):
    DEVICE_SYNCHRONIZED = "device_synchronized"
    DEVICE_UNSYNCHRONIZED = "device_unsynchronized"
    GATEWAY_ONLY = "gateway_only"
    UNKNOWN = "unknown"


class QualityFlag(StrEnum):
    DEVICE_WARNING = "device_warning"
    CLOCK_UNSYNCED = "clock_unsynced"
    REQUIRES_REVIEW = "requires_review"
    SOURCE_VALUE_UNCERTAIN = "source_value_uncertain"


class Coding(DomainModel):
    """A source or normalized code without lossy display-name matching."""

    system: NonEmptyText
    code: NonEmptyText
    display: NonEmptyText | None = None


class PatientReference(DomainModel):
    """Reference to a target/facility patient record; value is deliberately hidden in repr."""

    assigning_authority: NonEmptyText
    value: NonEmptyText = Field(repr=False)


class SourceProvenance(DomainModel):
    """Traceability metadata only; raw source frames are stored separately if approved."""

    adapter_id: NonEmptyText
    adapter_version: NonEmptyText
    source_message_id: NonEmptyText | None = Field(default=None, repr=False)
    source_sequence: int | None = Field(default=None, ge=0)
    payload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")


class ObservationEvent(DomainModel):
    """One immutable scalar reading, with source meaning and timing preserved."""

    schema_version: Literal["1.0"] = "1.0"
    event_id: UUID
    site_id: NonEmptyText
    device: DeviceReference
    metric: Coding
    value: float = Field(allow_inf_nan=False)
    source_unit: Coding
    normalized_metric: Coding | None = None
    normalized_unit: Coding | None = None
    patient: PatientReference | None = None
    encounter_reference: NonEmptyText | None = None
    observed_at: AwareDateTime | None = None
    received_at: AwareDateTime
    time_quality: TimeQuality
    quality_flags: tuple[QualityFlag, ...] = ()
    provenance: SourceProvenance
    origin: EventOrigin = EventOrigin.DEVICE

    @field_validator("value", mode="before")
    @classmethod
    def value_must_be_numeric(cls, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("observation value must be a numeric scalar")
        return float(value)

    @model_validator(mode="after")
    def validate_time_quality(self) -> "ObservationEvent":
        if self.observed_at is None and self.time_quality is not TimeQuality.GATEWAY_ONLY:
            raise ValueError("missing observed_at requires gateway_only time quality")
        if self.observed_at is not None and self.time_quality is TimeQuality.GATEWAY_ONLY:
            raise ValueError("gateway_only time quality cannot claim an observed_at")
        return self

"""Versioned mapping contracts for offline synthetic validation only."""

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .base import AwareDateTime, DomainModel, NonEmptyText
from .observation import Coding, EventOrigin, ObservationEvent

MAX_MAPPING_FACTOR = Decimal("1000000000000")
MAX_MAPPED_VALUE = Decimal("1000000000000000000")


class SyntheticMetricMapping(DomainModel):
    """Exact source metric/unit signature mapped to a synthetic canonical target."""

    source_metric: Coding
    source_unit: Coding
    normalized_metric: Coding
    normalized_unit: Coding
    operation: Literal["identity", "linear"] = "identity"
    scale: Decimal = Decimal("1")
    offset: Decimal = Decimal("0")
    decimal_places: int = Field(default=2, ge=0, le=9)

    @model_validator(mode="after")
    def validate_transform(self) -> "SyntheticMetricMapping":
        if not self.scale.is_finite() or not self.offset.is_finite():
            raise ValueError("mapping parameters must be finite decimals")
        if abs(self.scale) > MAX_MAPPING_FACTOR or abs(self.offset) > MAX_MAPPING_FACTOR:
            raise ValueError("mapping parameters exceed the synthetic safety bound")
        if self.operation == "identity" and (self.scale != 1 or self.offset != 0):
            raise ValueError("identity mapping requires neutral scale and offset")
        if self.operation == "linear" and self.scale == 0:
            raise ValueError("linear mapping scale must be nonzero")
        return self


class SyntheticMappingSet(DomainModel):
    """A firmware- and adapter-scoped catalog that is permanently synthetic-only."""

    scope: Literal["synthetic_only"]
    mapping_set_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    manufacturer: NonEmptyText
    model: NonEmptyText
    firmware_versions: tuple[NonEmptyText, ...] = Field(min_length=1, max_length=100)
    adapter_id: NonEmptyText
    adapter_version: NonEmptyText
    entries: tuple[SyntheticMetricMapping, ...] = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_unique_source_signatures(self) -> "SyntheticMappingSet":
        signatures = [
            (
                entry.source_metric.system,
                entry.source_metric.code,
                entry.source_unit.system,
                entry.source_unit.code,
            )
            for entry in self.entries
        ]
        if len(signatures) != len(set(signatures)):
            raise ValueError("mapping set contains duplicate source metric/unit signatures")
        return self

    def map_event(self, event: ObservationEvent) -> "SyntheticMappingResult":
        """Map one exact-scope, patient-free synthetic event or fail closed."""

        if event.origin is not EventOrigin.SYNTHETIC:
            raise SyntheticMappingError("mapping_synthetic_only")
        if event.patient is not None or event.encounter_reference is not None:
            raise SyntheticMappingError("mapping_patient_context_forbidden")
        if (
            event.device.manufacturer != self.manufacturer
            or event.device.model != self.model
            or event.device.firmware_version not in self.firmware_versions
            or event.provenance.adapter_id != self.adapter_id
            or event.provenance.adapter_version != self.adapter_version
        ):
            raise SyntheticMappingError("mapping_source_scope_mismatch")

        mapping = next(
            (
                entry
                for entry in self.entries
                if entry.source_metric.system == event.metric.system
                and entry.source_metric.code == event.metric.code
                and entry.source_unit.system == event.source_unit.system
                and entry.source_unit.code == event.source_unit.code
            ),
            None,
        )
        if mapping is None:
            raise SyntheticMappingError("mapping_entry_not_found")

        source_value = Decimal(str(event.value))
        try:
            if mapping.operation == "identity":
                normalized_value = source_value
            else:
                normalized_value = source_value * mapping.scale + mapping.offset
            quantum = Decimal(1).scaleb(-mapping.decimal_places)
            normalized_value = normalized_value.quantize(quantum, rounding=ROUND_HALF_EVEN)
        except ArithmeticError:
            raise SyntheticMappingError("mapping_numeric_transform_failed") from None

        if not normalized_value.is_finite() or abs(normalized_value) > MAX_MAPPED_VALUE:
            raise SyntheticMappingError("mapping_numeric_result_out_of_range")

        return SyntheticMappingResult(
            event_id=event.event_id,
            mapping_set_id=self.mapping_set_id,
            mapping_version=self.version,
            device_id=event.device.device_id,
            source_metric=event.metric,
            source_value=source_value,
            source_unit=event.source_unit,
            normalized_metric=mapping.normalized_metric,
            normalized_value=normalized_value,
            normalized_unit=mapping.normalized_unit,
            received_at=event.received_at,
        )


class SyntheticMappingError(ValueError):
    """Safe mapping error carrying a stable code and no input values."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SyntheticMappingResult(DomainModel):
    """Curated output of the offline mapper; deliberately has no patient fields."""

    origin: Literal["synthetic"] = "synthetic"
    event_id: UUID
    mapping_set_id: NonEmptyText
    mapping_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    device_id: NonEmptyText
    source_metric: Coding
    source_value: Decimal
    source_unit: Coding
    normalized_metric: Coding
    normalized_value: Decimal
    normalized_unit: Coding
    received_at: AwareDateTime


__all__ = [
    "MAX_MAPPED_VALUE",
    "MAX_MAPPING_FACTOR",
    "SyntheticMappingError",
    "SyntheticMappingResult",
    "SyntheticMappingSet",
    "SyntheticMetricMapping",
]

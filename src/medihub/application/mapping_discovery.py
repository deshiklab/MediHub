"""Strict, local-only source-to-canonical-to-destination worksheet preflight."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from medihub.application.discovery import EvidenceGate, EvidenceStatus
from medihub.domain.base import DomainModel, NonEmptyText

MAX_WORKSHEET_SIZE_BYTES = 64 * 1024


class MappingSourceDiscovery(DomainModel):
    manufacturer: NonEmptyText | None = None
    model: NonEmptyText | None = None
    firmware_versions: tuple[NonEmptyText, ...] = ()
    adapter_id: NonEmptyText | None = None
    adapter_version: NonEmptyText | None = None
    protocol_version: NonEmptyText | None = None
    vendor_authorization: EvidenceGate = Field(default_factory=EvidenceGate)
    technical_specification: EvidenceGate = Field(default_factory=EvidenceGate)
    sample_messages: EvidenceGate = Field(default_factory=EvidenceGate)


class MappingDestinationDiscovery(DomainModel):
    product: NonEmptyText | None = None
    protocol: NonEmptyText | None = None
    interface_version: NonEmptyText | None = None
    contract: EvidenceGate = Field(default_factory=EvidenceGate)


class MappingWorksheetEntry(DomainModel):
    """One proposed mapping row; values document intent and are never executed."""

    entry_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    source_element: NonEmptyText | None = None
    source_state: NonEmptyText | None = None
    source_metric_system: NonEmptyText | None = None
    source_metric_code: NonEmptyText | None = None
    source_unit_system: NonEmptyText | None = None
    source_unit_code: NonEmptyText | None = None
    canonical_element: NonEmptyText | None = None
    canonical_state: NonEmptyText | None = None
    canonical_metric_system: NonEmptyText | None = None
    canonical_metric_code: NonEmptyText | None = None
    canonical_unit_system: NonEmptyText | None = None
    canonical_unit_code: NonEmptyText | None = None
    destination_element: NonEmptyText | None = None
    destination_state: NonEmptyText | None = None
    destination_profile: NonEmptyText | None = None
    destination_code_system: NonEmptyText | None = None
    destination_code: NonEmptyText | None = None
    destination_unit_system: NonEmptyText | None = None
    destination_unit_code: NonEmptyText | None = None
    transformation_rule: NonEmptyText | None = None
    approval: EvidenceGate = Field(default_factory=EvidenceGate)


class MappingWorksheet(DomainModel):
    """Discovery worksheet, not a mapping catalog or runtime transformation."""

    schema_version: Literal["1.0"] = "1.0"
    worksheet_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    discovery_profile_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    country_code: str = Field(default="BD", pattern=r"^[A-Z]{2}$")
    facility: NonEmptyText | None = None
    source: MappingSourceDiscovery = Field(default_factory=MappingSourceDiscovery)
    destination: MappingDestinationDiscovery = Field(default_factory=MappingDestinationDiscovery)
    entries: tuple[MappingWorksheetEntry, ...] = ()
    worksheet_approval: EvidenceGate = Field(default_factory=EvidenceGate)
    synthetic_test_vectors: EvidenceGate = Field(default_factory=EvidenceGate)

    def readiness_blockers(self) -> tuple[str, ...]:
        """Return stable blocker codes without exposing worksheet values."""

        blockers: set[str] = set()
        if not _is_resolved(self.facility):
            blockers.add("pilot_facility_missing")
        if self.country_code != "BD":
            blockers.add("bangladesh_mapping_target_missing")

        if not _is_resolved(self.source.manufacturer) or not _is_resolved(self.source.model):
            blockers.add("source_device_identity_missing")
        if not self.source.firmware_versions or any(
            not _is_resolved(version) for version in self.source.firmware_versions
        ):
            blockers.add("source_firmware_scope_missing")
        if (
            not _is_resolved(self.source.adapter_id)
            or not _is_resolved(self.source.adapter_version)
            or not _is_resolved(self.source.protocol_version)
        ):
            blockers.add("source_interface_details_missing")
        _require_gate(blockers, "vendor_authorization", self.source.vendor_authorization)
        _require_gate(
            blockers, "source_technical_specification", self.source.technical_specification
        )
        _require_gate(blockers, "source_sample_messages", self.source.sample_messages)

        if (
            not _is_resolved(self.destination.product)
            or not _is_resolved(self.destination.protocol)
            or not _is_resolved(self.destination.interface_version)
        ):
            blockers.add("destination_interface_details_missing")
        _require_gate(blockers, "destination_contract", self.destination.contract)

        if not self.entries:
            blockers.add("mapping_entries_missing")
        source_signatures: set[tuple[str, str, str, str]] = set()
        entry_ids: set[str] = set()
        for entry in self.entries:
            if entry.entry_id in entry_ids:
                blockers.add("duplicate_mapping_entry_id")
            entry_ids.add(entry.entry_id)

            source_values = (
                entry.source_metric_system,
                entry.source_metric_code,
                entry.source_unit_system,
                entry.source_unit_code,
            )
            if any(not _is_resolved(value) for value in source_values):
                blockers.add("mapping_source_code_or_unit_missing")
            if not _is_resolved(entry.source_element) or not _is_resolved(entry.source_state):
                blockers.add("mapping_source_field_or_state_missing")
            source_identity = (entry.source_element, entry.source_state, *source_values)
            if all(_is_resolved(value) for value in source_identity):
                signature = tuple(value.strip() for value in source_identity if value is not None)
                if signature in source_signatures:
                    blockers.add("duplicate_source_mapping_key")
                source_signatures.add(signature)

            canonical_values = (
                entry.canonical_metric_system,
                entry.canonical_metric_code,
                entry.canonical_unit_system,
                entry.canonical_unit_code,
            )
            if any(not _is_resolved(value) for value in canonical_values):
                blockers.add("mapping_canonical_code_or_unit_missing")
            if not _is_resolved(entry.canonical_element) or not _is_resolved(entry.canonical_state):
                blockers.add("mapping_canonical_field_or_state_missing")

            destination_values = (
                entry.destination_element,
                entry.destination_state,
                entry.destination_profile,
                entry.destination_code_system,
                entry.destination_code,
                entry.destination_unit_system,
                entry.destination_unit_code,
            )
            if any(not _is_resolved(value) for value in destination_values):
                blockers.add("mapping_destination_field_or_code_missing")
            if not _is_resolved(entry.transformation_rule):
                blockers.add("mapping_transformation_rule_missing")
            _require_approved_gate(blockers, "mapping_entry_approval", entry.approval)

        _require_approved_gate(blockers, "mapping_worksheet_approval", self.worksheet_approval)
        _require_approved_gate(
            blockers,
            "synthetic_mapping_test_vectors",
            self.synthetic_test_vectors,
        )
        return tuple(sorted(blockers))


def _is_resolved(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().casefold()
    placeholders = ("tbd", "unknown", "pending", "not_selected", "not selected")
    return not any(
        normalized == placeholder
        or normalized.startswith(f"{placeholder}:")
        or normalized.startswith(f"{placeholder} ")
        for placeholder in placeholders
    )


def _require_gate(blockers: set[str], name: str, gate: EvidenceGate) -> None:
    if not (
        gate.status in {EvidenceStatus.APPROVED, EvidenceStatus.NOT_APPLICABLE}
        and gate.reference is not None
    ):
        blockers.add(f"{name}_evidence_incomplete")


def _require_approved_gate(blockers: set[str], name: str, gate: EvidenceGate) -> None:
    if gate.status is not EvidenceStatus.APPROVED or gate.reference is None:
        blockers.add(f"{name}_evidence_incomplete")


@dataclass(frozen=True, slots=True)
class MappingWorksheetCheckReport:
    """Sanitized result for a local mapping worksheet preflight."""

    schema_valid: bool
    readiness: str
    blockers: tuple[str, ...]
    errors: tuple[dict[str, str], ...]
    mapping_activation_enabled: Literal[False] = False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_valid": self.schema_valid,
            "readiness": self.readiness,
            "blockers": list(self.blockers),
            "errors": list(self.errors),
            "mapping_activation_enabled": self.mapping_activation_enabled,
        }

    @property
    def exit_code(self) -> int:
        if not self.schema_valid:
            return 2
        return 0 if self.readiness == "worksheet_complete" else 1


def validate_mapping_worksheet_file(path: Path) -> MappingWorksheetCheckReport:
    """Validate local TOML structure and review gates without executing mappings."""

    try:
        with path.open("rb") as worksheet_file:
            content = worksheet_file.read(MAX_WORKSHEET_SIZE_BYTES + 1)
    except OSError:
        return _invalid_worksheet("worksheet_file_unreadable")
    if len(content) > MAX_WORKSHEET_SIZE_BYTES:
        return _invalid_worksheet("worksheet_file_too_large")

    try:
        parsed = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return _invalid_worksheet("invalid_toml")

    try:
        worksheet = MappingWorksheet.model_validate(parsed)
    except ValidationError as error:
        return MappingWorksheetCheckReport(
            schema_valid=False,
            readiness="invalid_worksheet",
            blockers=(),
            errors=_safe_validation_errors(error),
        )

    blockers = worksheet.readiness_blockers()
    return MappingWorksheetCheckReport(
        schema_valid=True,
        readiness="worksheet_complete" if not blockers else "not_ready",
        blockers=blockers,
        errors=(),
    )


def _invalid_worksheet(code: str) -> MappingWorksheetCheckReport:
    return MappingWorksheetCheckReport(
        schema_valid=False,
        readiness="invalid_worksheet",
        blockers=(),
        errors=({"field": "worksheet", "code": code},),
    )


_SAFE_FIELD_NAMES = {
    "schema_version",
    "worksheet_id",
    "discovery_profile_id",
    "country_code",
    "facility",
    "source",
    "manufacturer",
    "model",
    "firmware_versions",
    "adapter_id",
    "adapter_version",
    "protocol_version",
    "vendor_authorization",
    "technical_specification",
    "sample_messages",
    "destination",
    "product",
    "protocol",
    "interface_version",
    "contract",
    "entries",
    "entry_id",
    "source_element",
    "source_state",
    "source_metric_system",
    "source_metric_code",
    "source_unit_system",
    "source_unit_code",
    "canonical_element",
    "canonical_state",
    "canonical_metric_system",
    "canonical_metric_code",
    "canonical_unit_system",
    "canonical_unit_code",
    "destination_element",
    "destination_state",
    "destination_profile",
    "destination_code_system",
    "destination_code",
    "destination_unit_system",
    "destination_unit_code",
    "transformation_rule",
    "approval",
    "worksheet_approval",
    "synthetic_test_vectors",
    "status",
    "reference",
}


def _safe_validation_errors(error: ValidationError) -> tuple[dict[str, str], ...]:
    sanitized: set[tuple[str, str]] = set()
    for issue in error.errors():
        field_path = ".".join(
            str(part)
            for part in issue["loc"]
            if isinstance(part, str) and part in _SAFE_FIELD_NAMES
        )
        sanitized.add((field_path or "worksheet", issue["type"]))
    return tuple({"field": field, "code": code} for field, code in sorted(sanitized))

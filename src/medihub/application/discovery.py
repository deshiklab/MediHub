"""Contract-first integration discovery profile and privacy-safe preflight report."""

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from medihub.domain.base import DomainModel, NonEmptyText

MAX_PROFILE_SIZE_BYTES = 64 * 1024


class EvidenceStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class CrossBorderDecision(StrEnum):
    UNDECIDED = "undecided"
    LOCAL_ONLY = "local_only"
    APPROVED = "approved"
    PROHIBITED = "prohibited"


class EvidenceGate(DomainModel):
    """A governance/technical decision tracked by status and opaque evidence ID."""

    status: EvidenceStatus = EvidenceStatus.OPEN
    reference: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )

    @model_validator(mode="after")
    def approved_or_not_applicable_requires_reference(self) -> "EvidenceGate":
        if self.status in {EvidenceStatus.APPROVED, EvidenceStatus.NOT_APPLICABLE}:
            if self.reference is None:
                raise ValueError("completed decisions require an evidence reference")
        return self

    @property
    def is_complete(self) -> bool:
        return (
            self.status in {EvidenceStatus.APPROVED, EvidenceStatus.NOT_APPLICABLE}
            and self.reference is not None
        )


class UseCaseDiscovery(DomainModel):
    statement: NonEmptyText | None = None
    approval: EvidenceGate = Field(default_factory=EvidenceGate)


class DeviceDiscovery(DomainModel):
    manufacturer: NonEmptyText | None = None
    model: NonEmptyText | None = None
    firmware_versions: tuple[NonEmptyText, ...] = ()
    transport: NonEmptyText | None = None
    protocol_version: NonEmptyText | None = None
    vendor_authorization: EvidenceGate = Field(default_factory=EvidenceGate)
    technical_specification: EvidenceGate = Field(default_factory=EvidenceGate)
    test_assets: EvidenceGate = Field(default_factory=EvidenceGate)


class DestinationDiscovery(DomainModel):
    product: NonEmptyText | None = None
    protocol: NonEmptyText | None = None
    interface_version: NonEmptyText | None = None
    contract: EvidenceGate = Field(default_factory=EvidenceGate)
    protocol_mapping_worksheet: EvidenceGate = Field(default_factory=EvidenceGate)
    synthetic_test_receiver: EvidenceGate = Field(default_factory=EvidenceGate)


class AssociationDiscovery(DomainModel):
    authority: NonEmptyText | None = None
    workflow: EvidenceGate = Field(default_factory=EvidenceGate)
    clinical_owner: EvidenceGate = Field(default_factory=EvidenceGate)


class DeploymentDiscovery(DomainModel):
    facility: NonEmptyText | None = None
    country_code: str = Field(default="BD", pattern=r"^[A-Z]{2}$")
    site_owners: EvidenceGate = Field(default_factory=EvidenceGate)
    approved_network_flow: EvidenceGate = Field(default_factory=EvidenceGate)
    hosting_location: NonEmptyText | None = None
    cross_border_decision: CrossBorderDecision = CrossBorderDecision.UNDECIDED
    privacy_legal_review: EvidenceGate = Field(default_factory=EvidenceGate)
    regulatory_review: EvidenceGate = Field(default_factory=EvidenceGate)
    synthetic_test_plan: EvidenceGate = Field(default_factory=EvidenceGate)


class IntegrationDiscoveryProfile(DomainModel):
    """Structured discovery only; it contains no connection or credential fields."""

    schema_version: Literal["1.0"] = "1.0"
    profile_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    use_case: UseCaseDiscovery = Field(default_factory=UseCaseDiscovery)
    device: DeviceDiscovery = Field(default_factory=DeviceDiscovery)
    destination: DestinationDiscovery = Field(default_factory=DestinationDiscovery)
    patient_association: AssociationDiscovery = Field(default_factory=AssociationDiscovery)
    deployment: DeploymentDiscovery = Field(default_factory=DeploymentDiscovery)

    def readiness_blockers(self) -> tuple[str, ...]:
        """Return stable codes for unresolved discovery gates, never raw profile data."""

        blockers: set[str] = set()
        if not _is_resolved(self.use_case.statement):
            blockers.add("intended_use_missing")
        _require_gate(blockers, "intended_use_approval", self.use_case.approval)

        if not _is_resolved(self.device.manufacturer) or not _is_resolved(self.device.model):
            blockers.add("device_identity_missing")
        if not self.device.firmware_versions or any(
            not _is_resolved(version) for version in self.device.firmware_versions
        ):
            blockers.add("device_firmware_support_missing")
        if not _is_resolved(self.device.transport) or not _is_resolved(
            self.device.protocol_version
        ):
            blockers.add("device_protocol_details_missing")
        _require_gate(blockers, "device_authorization", self.device.vendor_authorization)
        _require_gate(blockers, "device_specification", self.device.technical_specification)
        _require_gate(blockers, "device_test_assets", self.device.test_assets)

        if (
            not _is_resolved(self.destination.product)
            or not _is_resolved(self.destination.protocol)
            or not _is_resolved(self.destination.interface_version)
        ):
            blockers.add("destination_contract_details_missing")
        _require_gate(blockers, "destination_contract", self.destination.contract)
        _require_gate(
            blockers,
            "protocol_mapping_worksheet",
            self.destination.protocol_mapping_worksheet,
        )
        _require_gate(
            blockers,
            "synthetic_destination_test",
            self.destination.synthetic_test_receiver,
        )

        if not _is_resolved(self.patient_association.authority):
            blockers.add("patient_association_authority_missing")
        _require_gate(blockers, "patient_association_workflow", self.patient_association.workflow)
        _require_gate(blockers, "clinical_owner", self.patient_association.clinical_owner)

        if not _is_resolved(self.deployment.facility):
            blockers.add("pilot_facility_missing")
        if self.deployment.country_code != "BD":
            blockers.add("bangladesh_deployment_target_missing")
        _require_gate(blockers, "site_owners", self.deployment.site_owners)
        _require_gate(
            blockers,
            "approved_network_flow",
            self.deployment.approved_network_flow,
        )
        if not _is_resolved(self.deployment.hosting_location):
            blockers.add("hosting_location_missing")
        if self.deployment.cross_border_decision is CrossBorderDecision.UNDECIDED:
            blockers.add("cross_border_decision_missing")
        _require_gate(blockers, "privacy_legal_review", self.deployment.privacy_legal_review)
        _require_gate(blockers, "regulatory_review", self.deployment.regulatory_review)
        _require_gate(blockers, "synthetic_test_plan", self.deployment.synthetic_test_plan)
        return tuple(sorted(blockers))


def _require_gate(blockers: set[str], name: str, gate: EvidenceGate) -> None:
    if not gate.is_complete:
        blockers.add(f"{name}_evidence_incomplete")


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


@dataclass(frozen=True, slots=True)
class ProfileCheckReport:
    """Sanitized discovery report that never echoes configuration values."""

    schema_valid: bool
    readiness: str
    blockers: tuple[str, ...]
    errors: tuple[dict[str, str], ...]
    connectivity_enabled: Literal[False] = False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_valid": self.schema_valid,
            "readiness": self.readiness,
            "blockers": list(self.blockers),
            "errors": list(self.errors),
            "connectivity_enabled": self.connectivity_enabled,
        }

    @property
    def exit_code(self) -> int:
        if not self.schema_valid:
            return 2
        return 0 if self.readiness == "discovery_complete" else 1


def validate_profile_file(path: Path) -> ProfileCheckReport:
    """Parse and evaluate a local TOML discovery profile without exposing its values."""

    try:
        with path.open("rb") as profile_file:
            content = profile_file.read(MAX_PROFILE_SIZE_BYTES + 1)
    except OSError:
        return _invalid_profile("profile_file_unreadable")
    if len(content) > MAX_PROFILE_SIZE_BYTES:
        return _invalid_profile("profile_file_too_large")

    try:
        parsed = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return _invalid_profile("invalid_toml")

    try:
        profile = IntegrationDiscoveryProfile.model_validate(parsed)
    except ValidationError as error:
        return ProfileCheckReport(
            schema_valid=False,
            readiness="invalid_profile",
            blockers=(),
            errors=_safe_validation_errors(error),
        )

    blockers = profile.readiness_blockers()
    return ProfileCheckReport(
        schema_valid=True,
        readiness="discovery_complete" if not blockers else "not_ready",
        blockers=blockers,
        errors=(),
    )


def _invalid_profile(code: str) -> ProfileCheckReport:
    return ProfileCheckReport(
        schema_valid=False,
        readiness="invalid_profile",
        blockers=(),
        errors=({"field": "profile", "code": code},),
    )


_SAFE_FIELD_NAMES = {
    "schema_version",
    "profile_id",
    "use_case",
    "statement",
    "approval",
    "device",
    "manufacturer",
    "model",
    "firmware_versions",
    "transport",
    "protocol_version",
    "vendor_authorization",
    "technical_specification",
    "test_assets",
    "destination",
    "product",
    "protocol",
    "interface_version",
    "contract",
    "protocol_mapping_worksheet",
    "synthetic_test_receiver",
    "patient_association",
    "authority",
    "workflow",
    "clinical_owner",
    "deployment",
    "facility",
    "country_code",
    "site_owners",
    "approved_network_flow",
    "hosting_location",
    "cross_border_decision",
    "privacy_legal_review",
    "regulatory_review",
    "synthetic_test_plan",
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
        sanitized.add((field_path or "profile", issue["type"]))
    return tuple({"field": field, "code": code} for field, code in sorted(sanitized))

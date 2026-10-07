"""Strict, local-only receiver contract worksheet and privacy-safe preflight."""

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, ValidationError, model_validator

from medihub.application.discovery import EvidenceGate, EvidenceStatus
from medihub.domain.base import DomainModel, NonEmptyText

MAX_RECEIVER_CONTRACT_SIZE_BYTES = 64 * 1024
ReceiverContractCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=48,
        pattern=r"^[a-z][a-z0-9_.:-]*$",
    ),
]


class ReceiverProtocol(StrEnum):
    """Supported contract families; this is not a network connector selector."""

    FHIR_R4 = "fhir_r4"
    HL7_V2 = "hl7_v2"


class AcknowledgementLevel(StrEnum):
    APPLICATION = "application"
    TRANSPORT_ONLY = "transport_only"
    UNKNOWN = "unknown"


class AcknowledgementMeaning(StrEnum):
    ACCEPTED = "accepted"
    DURABLY_STORED = "durably_stored"
    QUEUED = "queued"
    PROCESSED = "processed"
    UNKNOWN = "unknown"


class IdempotencyKeyKind(StrEnum):
    STABLE_EVENT_ID = "stable_event_id"
    FHIR_IDENTIFIER = "fhir_identifier"
    HL7_MSH10 = "hl7_msh10"
    FACILITY_DEFINED = "facility_defined"
    NONE = "none"
    UNKNOWN = "unknown"


class DuplicateOutcome(StrEnum):
    SAME_ACKNOWLEDGEMENT = "same_acknowledgement"
    ACKNOWLEDGED_AS_DUPLICATE = "acknowledged_as_duplicate"
    CONFLICT = "conflict"
    CREATES_DUPLICATE = "creates_duplicate"
    UNKNOWN = "unknown"


class IdempotencyRetention(StrEnum):
    BOUNDED = "bounded"
    INDEFINITE = "indefinite"
    UNKNOWN = "unknown"


class ContractLimitStatus(StrEnum):
    SPECIFIED = "specified"
    UNLIMITED = "unlimited"
    UNKNOWN = "unknown"


class RetryHintBehavior(StrEnum):
    HONORED = "honored"
    IGNORED = "ignored"
    NOT_SUPPORTED = "not_supported"
    UNKNOWN = "unknown"


class ReceiverAcknowledgement(DomainModel):
    """Documented receiver ACK semantics, not proof that the receiver behaves so."""

    level: AcknowledgementLevel = AcknowledgementLevel.UNKNOWN
    meaning: AcknowledgementMeaning = AcknowledgementMeaning.UNKNOWN
    success_codes: tuple[ReceiverContractCode, ...] = ()


class ReceiverIdempotency(DomainModel):
    """Receiver deduplication key and retention behavior from the approved contract."""

    key_kind: IdempotencyKeyKind = IdempotencyKeyKind.UNKNOWN
    key_location: ReceiverContractCode | None = None
    duplicate_outcome: DuplicateOutcome = DuplicateOutcome.UNKNOWN
    retention: IdempotencyRetention = IdempotencyRetention.UNKNOWN
    retention_seconds: int | None = Field(default=None, gt=0)
    survives_receiver_restart: bool | None = None

    @model_validator(mode="after")
    def validate_retention_shape(self) -> "ReceiverIdempotency":
        if (
            self.retention is not IdempotencyRetention.BOUNDED
            and self.retention_seconds is not None
        ):
            raise ValueError("retention_seconds requires bounded retention")
        return self


class ReceiverLimit(DomainModel):
    """A numeric limit, an explicit unlimited declaration, or an unresolved value."""

    status: ContractLimitStatus = ContractLimitStatus.UNKNOWN
    value: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_limit_shape(self) -> "ReceiverLimit":
        if self.status is not ContractLimitStatus.SPECIFIED and self.value is not None:
            raise ValueError("a value is only valid for a specified limit")
        return self

    @property
    def is_resolved(self) -> bool:
        return self.status is ContractLimitStatus.UNLIMITED or (
            self.status is ContractLimitStatus.SPECIFIED and self.value is not None
        )


class ReceiverLimits(DomainModel):
    request_timeout_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    requests_per_minute: ReceiverLimit = Field(default_factory=ReceiverLimit)
    events_per_request: ReceiverLimit = Field(default_factory=ReceiverLimit)
    request_bytes: ReceiverLimit = Field(default_factory=ReceiverLimit)


class ReceiverFailureHandling(DomainModel):
    retryable_codes: tuple[ReceiverContractCode, ...] = ()
    permanent_codes: tuple[ReceiverContractCode, ...] = ()
    retry_hint_behavior: RetryHintBehavior = RetryHintBehavior.UNKNOWN


class ReceiverContract(DomainModel):
    """Versioned destination behavior worksheet; it never carries transport secrets."""

    schema_version: Literal["1.0"] = "1.0"
    contract_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    discovery_profile_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    receiver_name: NonEmptyText | None = None
    protocol: ReceiverProtocol | None = None
    interface_version: NonEmptyText | None = None
    contract_evidence: EvidenceGate = Field(default_factory=EvidenceGate)
    acknowledgement: ReceiverAcknowledgement = Field(default_factory=ReceiverAcknowledgement)
    idempotency: ReceiverIdempotency = Field(default_factory=ReceiverIdempotency)
    failure_handling: ReceiverFailureHandling = Field(default_factory=ReceiverFailureHandling)
    limits: ReceiverLimits = Field(default_factory=ReceiverLimits)

    @model_validator(mode="after")
    def validate_code_sets(self) -> "ReceiverContract":
        retryable = set(self.failure_handling.retryable_codes)
        permanent = set(self.failure_handling.permanent_codes)
        success = set(self.acknowledgement.success_codes)
        if retryable & permanent:
            raise ValueError("response code cannot be both retryable and permanent")
        if success & (retryable | permanent):
            raise ValueError("success response code cannot be classified as a failure")
        if (
            len(retryable) != len(self.failure_handling.retryable_codes)
            or len(permanent) != len(self.failure_handling.permanent_codes)
            or len(success) != len(self.acknowledgement.success_codes)
        ):
            raise ValueError("response code lists must not contain duplicates")

        if self.protocol is not None:
            if (
                self.protocol is ReceiverProtocol.FHIR_R4
                and self.idempotency.key_kind is IdempotencyKeyKind.HL7_MSH10
            ) or (
                self.protocol is ReceiverProtocol.HL7_V2
                and self.idempotency.key_kind is IdempotencyKeyKind.FHIR_IDENTIFIER
            ):
                raise ValueError("idempotency key kind does not match receiver protocol")
            expected_prefix = "http_" if self.protocol is ReceiverProtocol.FHIR_R4 else "msa_"
            if any(not code.startswith(expected_prefix) for code in success):
                raise ValueError("success response code does not match receiver protocol")
            transport_codes = {
                "transport_reset",
                "transport_timeout",
                "transport_unavailable",
            }
            if any(
                not code.startswith(expected_prefix) and code not in transport_codes
                for code in retryable | permanent
            ):
                raise ValueError("failure response code does not match receiver protocol")
        return self

    def readiness_blockers(self) -> tuple[str, ...]:
        """Return stable codes for missing or unsafe contract facts without raw values."""

        blockers: set[str] = set()
        if not _is_resolved(self.receiver_name):
            blockers.add("receiver_identity_missing")
        if self.protocol is None:
            blockers.add("receiver_protocol_missing")
        if not _is_resolved(self.interface_version):
            blockers.add("receiver_interface_version_missing")
        if self.contract_evidence.status is not EvidenceStatus.APPROVED:
            blockers.add("receiver_contract_evidence_not_approved")
        elif self.contract_evidence.reference is None:
            blockers.add("receiver_contract_evidence_reference_missing")

        acknowledgement = self.acknowledgement
        if acknowledgement.level is AcknowledgementLevel.UNKNOWN:
            blockers.add("receiver_acknowledgement_level_unknown")
        elif acknowledgement.level is AcknowledgementLevel.TRANSPORT_ONLY:
            blockers.add("receiver_acknowledgement_not_application_level")
        if acknowledgement.meaning is AcknowledgementMeaning.UNKNOWN:
            blockers.add("receiver_acknowledgement_meaning_unknown")
        if not acknowledgement.success_codes:
            blockers.add("receiver_success_response_codes_missing")

        idempotency = self.idempotency
        if idempotency.key_kind is IdempotencyKeyKind.UNKNOWN:
            blockers.add("receiver_idempotency_key_unknown")
        elif idempotency.key_kind is IdempotencyKeyKind.NONE:
            blockers.add("receiver_idempotency_key_unsupported")
        elif not _is_resolved(idempotency.key_location):
            blockers.add("receiver_idempotency_key_location_missing")
        if idempotency.duplicate_outcome is DuplicateOutcome.UNKNOWN:
            blockers.add("receiver_duplicate_outcome_unknown")
        elif idempotency.duplicate_outcome is DuplicateOutcome.CREATES_DUPLICATE:
            blockers.add("receiver_duplicate_outcome_unsafe")
        elif idempotency.duplicate_outcome is DuplicateOutcome.CONFLICT:
            blockers.add("receiver_duplicate_conflict_semantics_need_review")
        if idempotency.retention is IdempotencyRetention.UNKNOWN:
            blockers.add("receiver_idempotency_retention_unknown")
        elif (
            idempotency.retention is IdempotencyRetention.BOUNDED
            and idempotency.retention_seconds is None
        ):
            blockers.add("receiver_idempotency_retention_duration_missing")
        if idempotency.survives_receiver_restart is None:
            blockers.add("receiver_restart_idempotency_unverified")
        elif not idempotency.survives_receiver_restart:
            blockers.add("receiver_idempotency_not_restart_durable")

        failure_handling = self.failure_handling
        if not failure_handling.retryable_codes:
            blockers.add("receiver_retryable_outcomes_missing")
        if not failure_handling.permanent_codes:
            blockers.add("receiver_permanent_outcomes_missing")
        if failure_handling.retry_hint_behavior is RetryHintBehavior.UNKNOWN:
            blockers.add("receiver_retry_hint_behavior_unknown")

        limits = self.limits
        if limits.request_timeout_seconds is None:
            blockers.add("receiver_request_timeout_missing")
        _require_limit(blockers, "receiver_rate_limit", limits.requests_per_minute)
        _require_limit(blockers, "receiver_batch_limit", limits.events_per_request)
        _require_limit(blockers, "receiver_request_size_limit", limits.request_bytes)
        return tuple(sorted(blockers))


@dataclass(frozen=True, slots=True)
class ReceiverContractCheckReport:
    """Sanitized contract check result; it never echoes receiver or profile values."""

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
        return 0 if self.readiness == "contract_documented" else 1


def validate_receiver_contract_file(path: Path) -> ReceiverContractCheckReport:
    """Validate local TOML contract structure and readiness; never open a connection."""

    try:
        with path.open("rb") as contract_file:
            content = contract_file.read(MAX_RECEIVER_CONTRACT_SIZE_BYTES + 1)
    except OSError:
        return _invalid_contract("contract_file_unreadable")
    if len(content) > MAX_RECEIVER_CONTRACT_SIZE_BYTES:
        return _invalid_contract("contract_file_too_large")

    try:
        parsed = tomllib.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return _invalid_contract("invalid_toml")

    try:
        contract = ReceiverContract.model_validate(parsed)
    except ValidationError as error:
        return ReceiverContractCheckReport(
            schema_valid=False,
            readiness="invalid_contract",
            blockers=(),
            errors=_safe_validation_errors(error),
        )

    blockers = contract.readiness_blockers()
    return ReceiverContractCheckReport(
        schema_valid=True,
        readiness="contract_documented" if not blockers else "not_ready",
        blockers=blockers,
        errors=(),
    )


def _require_limit(blockers: set[str], name: str, limit: ReceiverLimit) -> None:
    if limit.is_resolved:
        return
    if limit.status is ContractLimitStatus.UNKNOWN:
        blockers.add(f"{name}_unknown")
    else:
        blockers.add(f"{name}_value_missing")


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


_SAFE_FIELD_NAMES = {
    "schema_version",
    "contract_id",
    "discovery_profile_id",
    "receiver_name",
    "protocol",
    "interface_version",
    "contract_evidence",
    "status",
    "reference",
    "acknowledgement",
    "level",
    "meaning",
    "success_codes",
    "idempotency",
    "key_kind",
    "key_location",
    "duplicate_outcome",
    "retention",
    "retention_seconds",
    "survives_receiver_restart",
    "failure_handling",
    "retryable_codes",
    "permanent_codes",
    "retry_hint_behavior",
    "limits",
    "request_timeout_seconds",
    "requests_per_minute",
    "events_per_request",
    "request_bytes",
    "value",
}


def _safe_validation_errors(error: ValidationError) -> tuple[dict[str, str], ...]:
    sanitized: set[tuple[str, str]] = set()
    for issue in error.errors():
        field_path = ".".join(
            str(part)
            for part in issue["loc"]
            if isinstance(part, str) and part in _SAFE_FIELD_NAMES
        )
        sanitized.add((field_path or "contract", issue["type"]))
    return tuple({"field": field, "code": code} for field, code in sorted(sanitized))


def _invalid_contract(code: str) -> ReceiverContractCheckReport:
    return ReceiverContractCheckReport(
        schema_valid=False,
        readiness="invalid_contract",
        blockers=(),
        errors=({"field": "contract", "code": code},),
    )


__all__ = [
    "MAX_RECEIVER_CONTRACT_SIZE_BYTES",
    "AcknowledgementLevel",
    "AcknowledgementMeaning",
    "ContractLimitStatus",
    "DuplicateOutcome",
    "IdempotencyKeyKind",
    "IdempotencyRetention",
    "ReceiverAcknowledgement",
    "ReceiverContract",
    "ReceiverContractCheckReport",
    "ReceiverFailureHandling",
    "ReceiverIdempotency",
    "ReceiverLimit",
    "ReceiverLimits",
    "ReceiverProtocol",
    "RetryHintBehavior",
    "validate_receiver_contract_file",
]

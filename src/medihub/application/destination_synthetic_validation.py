"""Offline synthetic validation against MediHub's versioned FHIR shape fixture."""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import Field

from medihub.adapters.destinations.fhir_r4 import (
    FhirR4MappingError,
    FhirR4Observation,
    build_synthetic_observation,
)
from medihub.domain import (
    Coding,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    SourceProvenance,
    TimeQuality,
)
from medihub.domain.base import AwareDateTime, DomainModel

FHIR_SYNTHETIC_FIXTURE_VERSION = "medihub-fhir-r4-synthetic-observation-v1"
FIXTURE_OBSERVED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
FIXTURE_EVENT_ID = uuid5(NAMESPACE_URL, FHIR_SYNTHETIC_FIXTURE_VERSION)
FIXTURE_EXPECTED_RESOURCE = {
    "resourceType": "Observation",
    "id": FIXTURE_EVENT_ID.hex,
    "identifier": [
        {
            "system": "urn:ietf:rfc:3986",
            "value": f"urn:uuid:{FIXTURE_EVENT_ID}",
        }
    ],
    "meta": {
        "tag": [
            {
                "system": "urn:medihub:data-origin",
                "code": "synthetic",
                "display": "Synthetic demonstration data",
            }
        ]
    },
    "status": "preliminary",
    "code": {
        "coding": [
            {
                "system": "https://example.invalid/medihub/synthetic-metrics",
                "code": "fixture-scalar-reading",
            }
        ]
    },
    "effectiveDateTime": "2026-01-01T12:00:00Z",
    "issued": "2026-01-01T12:00:00Z",
    "valueQuantity": {
        "value": 42.5,
        "unit": "1",
        "system": "http://unitsofmeasure.org",
        "code": "1",
    },
    "device": {"display": "sim-validation-device"},
}
FIXTURE_FORBIDDEN_RESOURCE_FIELDS = frozenset({"subject", "encounter"})
PROFILE_FINGERPRINT_FIELDS = (
    "target_id",
    "receiver_product",
    "receiver_version",
    "interface_version_profile",
    "controlled_interface_contract_reference",
    "resource_message_profile_reference",
    "patient_association_policy_reference",
    "results_only_technician_review_confirmed",
    "results_only_review_reference",
    "acknowledgement_idempotency_retry_reference",
    "security_transport_authorization_reference",
    "vendor_authorization_status",
    "vendor_authorization_reference",
    "facility_authorization_status",
    "facility_authorization_reference",
    "authorized_synthetic_sandbox_reference",
)


class DestinationSyntheticValidationCheck(DomainModel):
    """Fixed-code outcome for one offline fixture assertion; contains no payload values."""

    check_id: Literal[
        "synthetic_event_origin",
        "patient_context_omitted",
        "fixture_output_matches",
        "fhir_r4_model_validation",
        "preliminary_status",
    ]
    status: Literal["passed", "failed"]
    code: Literal[
        "synthetic_event_confirmed",
        "synthetic_event_required",
        "patient_context_absent",
        "patient_context_present",
        "fixture_output_matches",
        "fixture_output_mismatch",
        "fhir_r4_model_validation_passed",
        "fhir_r4_model_validation_failed",
        "preliminary_status_confirmed",
        "preliminary_status_mismatch",
    ]


class DestinationSyntheticValidationRecord(DomainModel):
    """Persistable latest local fixture result; never a target-conformance assertion."""

    target_id: Literal["emr_fhir_r4"] = "emr_fhir_r4"
    validation_id: UUID
    fixture_version: str = Field(
        default=FHIR_SYNTHETIC_FIXTURE_VERSION,
        min_length=40,
        max_length=80,
        pattern=r"^medihub-fhir-r4-synthetic-observation-v[0-9]+$",
    )
    status: Literal["local_fixture_passed", "local_fixture_failed"]
    profile_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    ran_at: AwareDateTime
    checks: list[DestinationSyntheticValidationCheck]
    scope: Literal["local_fixture_only"] = "local_fixture_only"
    network_enabled: Literal[False] = False
    sent: Literal[False] = False
    external_connection_enabled: Literal[False] = False
    target_contract_validated: Literal[False] = False
    target_conformance_claimed: Literal[False] = False
    site_approval_changed: Literal[False] = False


def destination_profile_fingerprint(profile: Mapping[str, object] | None) -> str | None:
    """Hash only fixed non-secret worksheet fields for stale-result detection."""

    if profile is None:
        return None
    allowlisted = {field: profile.get(field) for field in PROFILE_FINGERPRINT_FIELDS}
    encoded = json.dumps(
        allowlisted,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def destination_validation_readiness_status(
    record: DestinationSyntheticValidationRecord | None,
    profile: Mapping[str, object] | None,
) -> str:
    """Return current local-fixture status without promoting it to target validation."""

    if record is None:
        return "not_run"
    if (
        record.fixture_version != FHIR_SYNTHETIC_FIXTURE_VERSION
        or record.profile_fingerprint != destination_profile_fingerprint(profile)
    ):
        return "stale"
    return record.status


def _fixture_event() -> ObservationEvent:
    return ObservationEvent(
        event_id=FIXTURE_EVENT_ID,
        site_id="synthetic-validation-fixture",
        device=DeviceReference(
            device_id="sim-validation-device",
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
            firmware_version="1.0",
        ),
        metric=Coding(
            system="https://example.invalid/medihub/synthetic-metrics",
            code="fixture-scalar-reading",
        ),
        value=42.5,
        source_unit=Coding(system="http://unitsofmeasure.org", code="1"),
        observed_at=FIXTURE_OBSERVED_AT,
        received_at=FIXTURE_OBSERVED_AT,
        time_quality=TimeQuality.DEVICE_SYNCHRONIZED,
        provenance=SourceProvenance(
            adapter_id="medihub.synthetic-device",
            adapter_version="fixture-v1",
        ),
        origin=EventOrigin.SYNTHETIC,
    )


def run_offline_fhir_synthetic_validation(
    *,
    profile_fingerprint: str | None,
    ran_at: datetime | None = None,
) -> DestinationSyntheticValidationRecord:
    """Run a deterministic patient-free FHIR shape check; never send or open a socket."""

    event = _fixture_event()
    checks: list[DestinationSyntheticValidationCheck] = []

    is_synthetic = event.origin is EventOrigin.SYNTHETIC
    checks.append(
        DestinationSyntheticValidationCheck(
            check_id="synthetic_event_origin",
            status="passed" if is_synthetic else "failed",
            code="synthetic_event_confirmed" if is_synthetic else "synthetic_event_required",
        )
    )

    has_patient_context = event.patient is not None or event.encounter_reference is not None
    checks.append(
        DestinationSyntheticValidationCheck(
            check_id="patient_context_omitted",
            status="failed" if has_patient_context else "passed",
            code="patient_context_present" if has_patient_context else "patient_context_absent",
        )
    )

    resource_payload: dict[str, object] = {}
    mapping_succeeded = False
    try:
        resource = build_synthetic_observation(event)
        resource_payload = resource.model_dump(mode="json", by_alias=True, exclude_none=True)
        mapping_succeeded = True
    except (FhirR4MappingError, ValueError, TypeError):
        pass

    actual_fields = frozenset(resource_payload)
    fixture_matches = (
        mapping_succeeded
        and actual_fields == frozenset(FIXTURE_EXPECTED_RESOURCE)
        and not (FIXTURE_FORBIDDEN_RESOURCE_FIELDS & actual_fields)
        and resource_payload == FIXTURE_EXPECTED_RESOURCE
    )
    checks.append(
        DestinationSyntheticValidationCheck(
            check_id="fixture_output_matches",
            status="passed" if fixture_matches else "failed",
            code="fixture_output_matches" if fixture_matches else "fixture_output_mismatch",
        )
    )

    model_valid = False
    try:
        FhirR4Observation.model_validate(resource_payload)
        model_valid = mapping_succeeded
    except (ValueError, TypeError):
        pass
    checks.append(
        DestinationSyntheticValidationCheck(
            check_id="fhir_r4_model_validation",
            status="passed" if model_valid else "failed",
            code=(
                "fhir_r4_model_validation_passed"
                if model_valid
                else "fhir_r4_model_validation_failed"
            ),
        )
    )

    preliminary_status = (
        resource_payload.get("resourceType") == "Observation"
        and resource_payload.get("status") == "preliminary"
    )
    checks.append(
        DestinationSyntheticValidationCheck(
            check_id="preliminary_status",
            status="passed" if preliminary_status else "failed",
            code=(
                "preliminary_status_confirmed"
                if preliminary_status
                else "preliminary_status_mismatch"
            ),
        )
    )

    passed = all(check.status == "passed" for check in checks)
    return DestinationSyntheticValidationRecord(
        validation_id=uuid4(),
        status="local_fixture_passed" if passed else "local_fixture_failed",
        profile_fingerprint=profile_fingerprint,
        ran_at=ran_at or datetime.now(UTC),
        checks=checks,
    )

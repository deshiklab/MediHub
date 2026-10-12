"""Generic FHIR R4 shape checks for synthetic observations."""

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from medihub.adapters.destinations.fhir_r4 import (
    FhirR4MappingError,
    FhirR4Observation,
    build_synthetic_observation,
)
from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.domain import EventOrigin, PatientReference


def sample_event():
    async def create_event():
        adapter = SyntheticDeviceAdapter(
            SyntheticDeviceConfig(
                event_count=1,
                seed=31,
                start_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
            )
        )
        try:
            async for event in adapter.read_events():
                return event
        finally:
            await adapter.close()
        raise AssertionError("simulator did not emit an event")

    return asyncio.run(create_event())


def test_generic_fhir_r4_observation_preserves_synthetic_values_without_subject() -> None:
    event = sample_event()
    resource = build_synthetic_observation(event)
    payload = resource.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert payload["resourceType"] == "Observation"
    assert payload["id"] == event.event_id.hex
    assert payload["identifier"] == [
        {
            "system": "urn:ietf:rfc:3986",
            "value": f"urn:uuid:{event.event_id}",
        }
    ]
    assert payload["status"] == "preliminary"
    assert payload["code"]["coding"][0]["system"] == event.metric.system
    assert payload["code"]["coding"][0]["code"] == event.metric.code
    assert payload["effectiveDateTime"] == event.observed_at.isoformat().replace("+00:00", "Z")
    assert payload["issued"] == event.received_at.isoformat().replace("+00:00", "Z")
    assert payload["valueQuantity"]["value"] == event.value
    assert payload["valueQuantity"]["system"] == event.source_unit.system
    assert payload["valueQuantity"]["code"] == event.source_unit.code
    assert payload["meta"]["tag"][0]["code"] == "synthetic"
    assert "subject" not in payload
    assert "patient" not in payload
    assert "encounter" not in payload


def test_fhir_mapper_rejects_live_or_patient_associated_events() -> None:
    event = sample_event()
    with pytest.raises(FhirR4MappingError, match="only synthetic"):
        build_synthetic_observation(event.model_copy(update={"origin": EventOrigin.DEVICE}))

    patient_event = event.model_copy(
        update={
            "patient": PatientReference(
                assigning_authority="synthetic-test-authority",
                value="synthetic-test-subject",
            )
        }
    )
    with pytest.raises(FhirR4MappingError, match="cannot contain patient context"):
        build_synthetic_observation(patient_event)


def test_fhir_mapper_requires_observation_time_and_forbids_unreviewed_fields() -> None:
    event = sample_event()
    with pytest.raises(FhirR4MappingError, match="effectiveDateTime"):
        build_synthetic_observation(event.model_copy(update={"observed_at": None}))

    payload = build_synthetic_observation(event).model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )
    with pytest.raises(ValidationError):
        FhirR4Observation.model_validate({**payload, "subject": {"reference": "Patient/1"}})

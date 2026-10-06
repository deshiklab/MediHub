from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from medihub.domain import (
    Coding,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    SourceProvenance,
    TimeQuality,
)


def make_event(**overrides: object) -> ObservationEvent:
    data: dict[str, object] = {
        "event_id": uuid4(),
        "site_id": "test-site",
        "device": DeviceReference(
            device_id="test-device",
            manufacturer="test-manufacturer",
            model="test-model",
        ),
        "metric": Coding(system="https://example.invalid/codes", code="test-reading"),
        "value": 12.5,
        "source_unit": Coding(system="http://unitsofmeasure.org", code="1"),
        "observed_at": datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
        "received_at": datetime(2026, 10, 7, 8, 0, 1, tzinfo=UTC),
        "time_quality": TimeQuality.DEVICE_SYNCHRONIZED,
        "provenance": SourceProvenance(
            adapter_id="test-adapter",
            adapter_version="0.1.0",
        ),
    }
    data.update(overrides)
    return ObservationEvent.model_validate(data)


def test_event_accepts_timezone_aware_times_and_preserves_origin() -> None:
    event = make_event(origin=EventOrigin.SYNTHETIC)

    assert event.received_at.utcoffset().total_seconds() == 0
    assert event.origin is EventOrigin.SYNTHETIC
    assert event.patient is None


def test_event_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        make_event(received_at=datetime(2026, 10, 7, 8, 0, 1))


def test_missing_observation_time_must_be_marked_gateway_only() -> None:
    with pytest.raises(ValidationError, match="gateway_only"):
        make_event(observed_at=None)

    event = make_event(observed_at=None, time_quality=TimeQuality.GATEWAY_ONLY)
    assert event.observed_at is None


def test_non_finite_or_non_numeric_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_event(value=float("nan"))
    with pytest.raises(ValidationError, match="numeric scalar"):
        make_event(value="12.5")


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        make_event(unreviewed_patient_match="someone")


def test_patient_identifier_is_not_in_default_model_repr() -> None:
    event = make_event(
        patient={"assigning_authority": "synthetic-authority", "value": "synthetic-patient-1"}
    )

    assert "synthetic-patient-1" not in repr(event)

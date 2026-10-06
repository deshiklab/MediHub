from datetime import UTC, datetime
from uuid import uuid4

import pytest

from medihub.application.replay import ReplayInputError, load_synthetic_events
from medihub.domain import (
    Coding,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    PatientReference,
    SourceProvenance,
    TimeQuality,
)


def make_event(
    *,
    origin: EventOrigin = EventOrigin.SYNTHETIC,
    patient: PatientReference | None = None,
) -> ObservationEvent:
    observed_at = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)
    return ObservationEvent(
        event_id=uuid4(),
        site_id="synthetic-site",
        device=DeviceReference(
            device_id="sim-device-001",
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
        ),
        metric=Coding(
            system="https://example.invalid/medihub/synthetic-metrics",
            code="simulated-scalar-reading",
        ),
        value=12.5,
        source_unit=Coding(system="http://unitsofmeasure.org", code="1"),
        patient=patient,
        observed_at=observed_at,
        received_at=observed_at,
        time_quality=TimeQuality.DEVICE_SYNCHRONIZED,
        provenance=SourceProvenance(adapter_id="test-adapter", adapter_version="0.1.0"),
        origin=origin,
    )


def test_loader_accepts_only_valid_synthetic_json_lines(tmp_path) -> None:
    first = make_event()
    second = make_event()
    fixture = tmp_path / "events.ndjson"
    fixture.write_text(f"{first.model_dump_json()}\n\n{second.model_dump_json()}\n")

    events = load_synthetic_events(fixture)

    assert [event.event_id for event in events] == [first.event_id, second.event_id]
    assert all(event.origin is EventOrigin.SYNTHETIC for event in events)


def test_loader_rejects_malformed_data_without_echoing_the_line(tmp_path) -> None:
    sentinel = "SYNTHETIC-DO-NOT-PRINT"
    fixture = tmp_path / "invalid.ndjson"
    fixture.write_text(f'{{"site_id":"{sentinel}"\n')

    with pytest.raises(ReplayInputError, match="line 1 failed event validation") as error:
        load_synthetic_events(fixture)

    assert sentinel not in str(error.value)


def test_loader_rejects_live_event_origin(tmp_path) -> None:
    fixture = tmp_path / "live.ndjson"
    fixture.write_text(make_event(origin=EventOrigin.DEVICE).model_dump_json() + "\n")

    with pytest.raises(ReplayInputError, match="not marked synthetic"):
        load_synthetic_events(fixture)


def test_loader_rejects_patient_context_even_when_origin_is_synthetic(tmp_path) -> None:
    patient = PatientReference(
        assigning_authority="test-authority",
        value="SYNTHETIC-TEST-0001",
    )
    fixture = tmp_path / "patient-context.ndjson"
    fixture.write_text(make_event(patient=patient).model_dump_json() + "\n")

    with pytest.raises(ReplayInputError, match="contains patient context"):
        load_synthetic_events(fixture)

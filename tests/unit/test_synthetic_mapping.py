from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal, localcontext
from uuid import uuid4

import pytest
from pydantic import ValidationError

from medihub.domain import (
    Coding,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    PatientReference,
    SourceProvenance,
    SyntheticMappingError,
    SyntheticMappingSet,
    TimeQuality,
)

OBSERVED_AT = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


def make_event(
    *,
    value: float = 42.5,
    origin: EventOrigin = EventOrigin.SYNTHETIC,
) -> ObservationEvent:
    return ObservationEvent(
        event_id=uuid4(),
        site_id="synthetic-site",
        device=DeviceReference(
            device_id="sim-device-001",
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
            firmware_version="1.0",
        ),
        metric=Coding(
            system="https://example.invalid/medihub/synthetic-metrics",
            code="simulated-scalar-reading",
            display="display text deliberately not used as a key",
        ),
        value=value,
        source_unit=Coding(
            system="http://unitsofmeasure.org",
            code="1",
            display="source unit label",
        ),
        observed_at=OBSERVED_AT,
        received_at=OBSERVED_AT,
        time_quality=TimeQuality.DEVICE_SYNCHRONIZED,
        provenance=SourceProvenance(
            adapter_id="medihub.synthetic-device",
            adapter_version="0.2.0",
        ),
        origin=origin,
    )


def make_mapping_set(**entry_updates: object) -> SyntheticMappingSet:
    entry: dict[str, object] = {
        "source_metric": {
            "system": "https://example.invalid/medihub/synthetic-metrics",
            "code": "simulated-scalar-reading",
        },
        "source_unit": {"system": "http://unitsofmeasure.org", "code": "1"},
        "normalized_metric": {
            "system": "https://example.invalid/medihub/canonical-synthetic",
            "code": "mapped-synthetic-scalar",
        },
        "normalized_unit": {"system": "http://unitsofmeasure.org", "code": "1"},
    }
    entry.update(entry_updates)
    return SyntheticMappingSet.model_validate(
        {
            "scope": "synthetic_only",
            "mapping_set_id": "synthetic-scalar-demo",
            "version": "1.0.0",
            "manufacturer": "MediHub Synthetic",
            "model": "scalar-simulator-v1",
            "firmware_versions": ["1.0"],
            "adapter_id": "medihub.synthetic-device",
            "adapter_version": "0.2.0",
            "entries": [entry],
        }
    )


def test_mapping_requires_exact_codes_and_preserves_source_semantics() -> None:
    result = make_mapping_set().map_event(make_event())

    assert result.origin == "synthetic"
    assert result.normalized_metric.code == "mapped-synthetic-scalar"
    assert result.normalized_value == Decimal("42.50")
    assert result.source_metric.code == "simulated-scalar-reading"
    assert result.source_unit.display == "source unit label"
    assert result.mapping_set_id == "synthetic-scalar-demo"
    assert result.mapping_version == "1.0.0"


def test_linear_transform_uses_bounded_decimal_half_even_rounding() -> None:
    mapping_set = make_mapping_set(
        operation="linear",
        scale="1",
        offset="0",
        decimal_places=2,
    )

    with localcontext() as decimal_context:
        decimal_context.rounding = ROUND_DOWN
        result = mapping_set.map_event(make_event(value=3.155))

    assert result.normalized_value == Decimal("3.16")


def test_mapping_fails_closed_for_live_context_scope_and_unknown_keys() -> None:
    mapping_set = make_mapping_set()

    with pytest.raises(SyntheticMappingError, match="mapping_synthetic_only"):
        mapping_set.map_event(make_event(origin=EventOrigin.DEVICE))

    patient_event = make_event().model_copy(
        update={
            "patient": PatientReference(
                assigning_authority="urn:synthetic:fixture",
                value="synthetic-fixture-only",
            )
        }
    )
    with pytest.raises(SyntheticMappingError, match="mapping_patient_context_forbidden"):
        mapping_set.map_event(patient_event)

    wrong_metric_event = make_event().model_copy(
        update={"metric": Coding(system="urn:example:synthetic", code="unmapped")}
    )
    with pytest.raises(SyntheticMappingError, match="mapping_entry_not_found"):
        mapping_set.map_event(wrong_metric_event)

    wrong_device_event = make_event().model_copy(
        update={
            "device": DeviceReference(
                device_id="sim-device-001",
                manufacturer="Unknown Synthetic Vendor",
                model="scalar-simulator-v1",
                firmware_version="1.0",
            )
        }
    )
    with pytest.raises(SyntheticMappingError, match="mapping_source_scope_mismatch"):
        mapping_set.map_event(wrong_device_event)

    with pytest.raises(ValidationError):
        make_mapping_set(unknown_property="must be rejected")

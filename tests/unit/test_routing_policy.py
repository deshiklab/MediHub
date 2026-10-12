from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from medihub.application.routing import RouteBlockedError, assert_route_eligible
from medihub.domain import (
    AssociationSource,
    AssociationStatus,
    Coding,
    Destination,
    DestinationProtocol,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    PatientAssociation,
    PatientReference,
    SourceProvenance,
    TimeQuality,
)

OBSERVED_AT = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)
TEST_PATIENT = PatientReference(
    assigning_authority="test-authority",
    value="SYNTHETIC-TEST-0001",
)


def make_event(
    *,
    site_id: str = "site-a",
    origin: EventOrigin = EventOrigin.SYNTHETIC,
    device_id: str = "device-a",
    patient: PatientReference | None = None,
    time_quality: TimeQuality = TimeQuality.DEVICE_SYNCHRONIZED,
) -> ObservationEvent:
    return ObservationEvent(
        event_id=uuid4(),
        site_id=site_id,
        device=DeviceReference(
            device_id=device_id,
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
        ),
        metric=Coding(
            system="https://example.invalid/medihub/synthetic-metrics",
            code="simulated-scalar-reading",
        ),
        value=12.0,
        source_unit=Coding(system="http://unitsofmeasure.org", code="1"),
        patient=patient,
        observed_at=OBSERVED_AT,
        received_at=OBSERVED_AT + timedelta(milliseconds=25),
        time_quality=time_quality,
        provenance=SourceProvenance(adapter_id="test-adapter", adapter_version="0.1.0"),
        origin=origin,
    )


def make_association(
    *,
    site_id: str = "site-a",
    device_id: str = "device-a",
    status: AssociationStatus = AssociationStatus.CONFIRMED,
    patient: PatientReference | None = TEST_PATIENT,
    valid_from: datetime = OBSERVED_AT - timedelta(minutes=5),
) -> PatientAssociation:
    return PatientAssociation(
        association_id=uuid4(),
        site_id=site_id,
        device_id=device_id,
        status=status,
        patient=patient,
        valid_from=valid_from,
        source=AssociationSource.ADT,
    )


def make_destination(
    *,
    site_id: str = "site-a",
    enabled: bool = True,
    accepts_synthetic_data: bool = False,
) -> Destination:
    return Destination(
        destination_id="test-destination",
        site_id=site_id,
        name="test destination",
        protocol=DestinationProtocol.FHIR_R4,
        contract_version="test-contract-1",
        connection_ref="test-connection",
        enabled=enabled,
        accepts_synthetic_data=accepts_synthetic_data,
    )


def test_synthetic_event_cannot_route_to_production_destination() -> None:
    with pytest.raises(RouteBlockedError, match="synthetic"):
        assert_route_eligible(make_event(), make_destination())


def test_synthetic_event_can_route_to_explicit_test_destination() -> None:
    assert_route_eligible(
        make_event(),
        make_destination(accepts_synthetic_data=True),
    )


def test_synthetic_event_cannot_carry_patient_context() -> None:
    with pytest.raises(RouteBlockedError, match="patient context"):
        assert_route_eligible(
            make_event(patient=TEST_PATIENT),
            make_destination(accepts_synthetic_data=True),
        )


def test_cross_site_route_is_blocked() -> None:
    with pytest.raises(RouteBlockedError, match="different sites"):
        assert_route_eligible(make_event(), make_destination(site_id="site-b"))


def test_disabled_destination_is_blocked() -> None:
    with pytest.raises(RouteBlockedError, match="disabled"):
        assert_route_eligible(make_event(), make_destination(enabled=False))


def test_live_event_requires_a_confirmed_patient_association() -> None:
    event = make_event(origin=EventOrigin.DEVICE, patient=TEST_PATIENT)
    with pytest.raises(RouteBlockedError, match="confirmed patient/device association"):
        assert_route_eligible(event, make_destination())


def test_live_event_with_matching_active_association_can_route() -> None:
    event = make_event(origin=EventOrigin.DEVICE, patient=TEST_PATIENT)
    association = make_association()

    assert_route_eligible(event, make_destination(), association=association)


def test_unresolved_association_cannot_route() -> None:
    event = make_event(origin=EventOrigin.DEVICE, patient=TEST_PATIENT)
    association = make_association(status=AssociationStatus.UNRESOLVED, patient=None)

    with pytest.raises(RouteBlockedError, match="confirmed patient/device association"):
        assert_route_eligible(event, make_destination(), association=association)


def test_association_must_match_event_site_and_device() -> None:
    event = make_event(origin=EventOrigin.DEVICE, patient=TEST_PATIENT)
    association = make_association(device_id="another-device")

    with pytest.raises(RouteBlockedError, match="does not match the event"):
        assert_route_eligible(event, make_destination(), association=association)


def test_association_must_be_active_at_observation_time() -> None:
    event = make_event(origin=EventOrigin.DEVICE, patient=TEST_PATIENT)
    association = make_association(valid_from=OBSERVED_AT + timedelta(seconds=1))

    with pytest.raises(RouteBlockedError, match="not active"):
        assert_route_eligible(event, make_destination(), association=association)


def test_event_patient_must_match_association() -> None:
    another_patient = PatientReference(
        assigning_authority="test-authority",
        value="SYNTHETIC-TEST-0002",
    )
    event = make_event(origin=EventOrigin.DEVICE, patient=another_patient)

    with pytest.raises(RouteBlockedError, match="does not match the confirmed association"):
        assert_route_eligible(event, make_destination(), association=make_association())


def test_association_requires_synchronized_observation_time() -> None:
    event = make_event(
        origin=EventOrigin.DEVICE,
        patient=TEST_PATIENT,
        time_quality=TimeQuality.DEVICE_UNSYNCHRONIZED,
    )

    with pytest.raises(RouteBlockedError, match="synchronized observation time"):
        assert_route_eligible(event, make_destination(), association=make_association())

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from medihub.domain import (
    AssociationSource,
    AssociationStatus,
    PatientAssociation,
    PatientReference,
)

BASE_TIME = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


def test_confirmed_association_is_time_bounded() -> None:
    association = PatientAssociation(
        association_id=uuid4(),
        site_id="test-site",
        device_id="test-device",
        status=AssociationStatus.CONFIRMED,
        patient=PatientReference(assigning_authority="test-facility", value="synthetic-patient-1"),
        valid_from=BASE_TIME,
        valid_to=BASE_TIME + timedelta(minutes=30),
        source=AssociationSource.ADT,
    )

    assert association.is_confirmed_at(BASE_TIME)
    assert association.is_confirmed_at(BASE_TIME + timedelta(minutes=29))
    assert not association.is_confirmed_at(BASE_TIME + timedelta(minutes=30))


def test_unresolved_and_conflicting_states_never_choose_a_patient() -> None:
    with pytest.raises(ValidationError, match="must not select a patient"):
        PatientAssociation(
            association_id=uuid4(),
            site_id="test-site",
            device_id="test-device",
            status=AssociationStatus.CONFLICT,
            patient=PatientReference(
                assigning_authority="test-facility",
                value="synthetic-patient-1",
            ),
            valid_from=BASE_TIME,
            source=AssociationSource.ADT,
            candidate_count=2,
        )


def test_conflict_requires_multiple_candidates() -> None:
    with pytest.raises(ValidationError, match="at least two"):
        PatientAssociation(
            association_id=uuid4(),
            site_id="test-site",
            device_id="test-device",
            status=AssociationStatus.CONFLICT,
            valid_from=BASE_TIME,
            source=AssociationSource.ADT,
            candidate_count=1,
        )


def test_operator_association_requires_auditable_actor() -> None:
    with pytest.raises(ValidationError, match="actor_id"):
        PatientAssociation(
            association_id=uuid4(),
            site_id="test-site",
            device_id="test-device",
            status=AssociationStatus.UNRESOLVED,
            valid_from=BASE_TIME,
            source=AssociationSource.OPERATOR,
        )


def test_naive_lookup_time_is_rejected() -> None:
    association = PatientAssociation(
        association_id=uuid4(),
        site_id="test-site",
        device_id="test-device",
        status=AssociationStatus.UNRESOLVED,
        valid_from=BASE_TIME,
        source=AssociationSource.ADT,
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        association.is_confirmed_at(datetime(2026, 10, 7, 8, 0))

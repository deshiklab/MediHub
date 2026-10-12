"""Patient/device association contracts with explicit unresolved and conflict states."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from .base import AwareDateTime, DomainModel, NonEmptyText
from .observation import PatientReference


class AssociationStatus(StrEnum):
    CONFIRMED = "confirmed"
    UNRESOLVED = "unresolved"
    CONFLICT = "conflict"


class AssociationSource(StrEnum):
    ADT = "adt"
    EHR = "ehr"
    SHR = "shr"
    DEVICE = "device"
    OPERATOR = "operator"


class PatientAssociation(DomainModel):
    """Time-bounded association; this contract does not perform identity matching."""

    association_id: UUID
    site_id: NonEmptyText
    device_id: NonEmptyText
    status: AssociationStatus
    patient: PatientReference | None = None
    valid_from: AwareDateTime
    valid_to: AwareDateTime | None = None
    source: AssociationSource
    actor_id: NonEmptyText | None = None
    candidate_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_association_state(self) -> "PatientAssociation":
        if self.status is AssociationStatus.CONFIRMED and self.patient is None:
            raise ValueError("confirmed association requires a patient reference")
        if self.status is not AssociationStatus.CONFIRMED and self.patient is not None:
            raise ValueError("unresolved/conflicting association must not select a patient")
        if self.status is AssociationStatus.CONFLICT and self.candidate_count < 2:
            raise ValueError("conflict state requires at least two candidate matches")
        if self.source is AssociationSource.OPERATOR and self.actor_id is None:
            raise ValueError("operator-created association requires an actor_id")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be later than valid_from")
        return self

    def is_confirmed_at(self, moment: datetime) -> bool:
        """Return whether this confirmed association is active at an aware instant."""

        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("moment must be timezone-aware")
        return (
            self.status is AssociationStatus.CONFIRMED
            and self.valid_from <= moment
            and (self.valid_to is None or moment < self.valid_to)
        )

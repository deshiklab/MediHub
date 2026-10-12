"""Destination, delivery, and validation contracts."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from .base import AwareDateTime, DomainModel, NonEmptyText
from .observation import ObservationEvent


class DestinationProtocol(StrEnum):
    FHIR_R4 = "fhir_r4"
    HL7_V2 = "hl7_v2"
    MEDIHUB_API = "medihub_api"


class DeliveryStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"


class ValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


SafeErrorCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.-]+$",
    ),
]


class Destination(DomainModel):
    """Destination metadata, not credentials or a transport connection."""

    destination_id: NonEmptyText
    site_id: NonEmptyText
    name: NonEmptyText
    protocol: DestinationProtocol
    contract_version: NonEmptyText
    connection_ref: NonEmptyText
    enabled: bool = True
    accepts_synthetic_data: bool = False


class ClaimedDelivery(DomainModel):
    """A leased outbox item; the stable event ID is the receiver idempotency key."""

    outbox_id: UUID
    attempt_id: UUID
    attempt_number: int = Field(ge=1)
    destination_id: NonEmptyText
    lease_token: UUID = Field(repr=False)
    lease_expires_at: AwareDateTime
    started_at: AwareDateTime
    event: ObservationEvent = Field(repr=False)


class DeliveryAttempt(DomainModel):
    """One durable attempt record; acknowledgment meaning is receiver-specific."""

    attempt_id: UUID
    event_id: UUID
    destination_id: NonEmptyText
    attempt_number: int = Field(ge=1)
    status: DeliveryStatus
    started_at: AwareDateTime
    completed_at: AwareDateTime | None = None
    acknowledgement_id: NonEmptyText | None = None
    error_code: SafeErrorCode | None = None
    error_summary: NonEmptyText | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def validate_attempt(self) -> "DeliveryAttempt":
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not be earlier than started_at")
        terminal_statuses = {
            DeliveryStatus.ACKNOWLEDGED,
            DeliveryStatus.REJECTED,
            DeliveryStatus.RETRYABLE_FAILURE,
            DeliveryStatus.PERMANENT_FAILURE,
        }
        if self.status in terminal_statuses and self.completed_at is None:
            raise ValueError("a completed delivery outcome requires completed_at")
        if (
            self.status
            in {
                DeliveryStatus.REJECTED,
                DeliveryStatus.RETRYABLE_FAILURE,
                DeliveryStatus.PERMANENT_FAILURE,
            }
            and self.error_code is None
        ):
            raise ValueError("a failed delivery outcome requires an error_code")
        return self


class ValidationIssue(DomainModel):
    """A safe-to-log validation result; message must not echo PHI/raw frames."""

    code: NonEmptyText
    severity: ValidationSeverity
    path: NonEmptyText | None = None
    message: NonEmptyText

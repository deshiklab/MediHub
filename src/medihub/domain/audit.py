"""Audit metadata. Event payloads and patient identifiers do not belong here."""

from enum import StrEnum
from uuid import UUID

from .base import AwareDateTime, DomainModel, NonEmptyText


class AuditAction(StrEnum):
    DEVICE_REGISTERED = "device_registered"
    ASSOCIATION_CREATED = "association_created"
    ASSOCIATION_CHANGED = "association_changed"
    DELIVERY_REPLAYED = "delivery_replayed"
    CONFIGURATION_CHANGED = "configuration_changed"
    PHI_READ = "phi_read"
    PHI_WRITTEN = "phi_written"


class AuditEvent(DomainModel):
    event_id: UUID
    site_id: NonEmptyText
    actor_id: NonEmptyText
    action: AuditAction
    resource_type: NonEmptyText
    resource_id: NonEmptyText
    occurred_at: AwareDateTime
    correlation_id: NonEmptyText | None = None

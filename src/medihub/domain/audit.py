"""Audit metadata. Event payloads and patient identifiers do not belong here."""

from enum import StrEnum
from uuid import UUID

from .base import AwareDateTime, DomainModel, NonEmptyText
from .delivery import SafeErrorCode


class AuditAction(StrEnum):
    DEVICE_REGISTERED = "device_registered"
    ASSOCIATION_CREATED = "association_created"
    ASSOCIATION_CHANGED = "association_changed"
    DELIVERY_REPLAYED = "delivery_replayed"
    CONFIGURATION_CHANGED = "configuration_changed"
    PHI_READ = "phi_read"
    PHI_WRITTEN = "phi_written"
    EVENT_STORED = "event_stored"
    ROUTE_HELD = "route_held"
    DELIVERY_INTENT_CREATED = "delivery_intent_created"
    DELIVERY_ATTEMPT_STARTED = "delivery_attempt_started"
    DELIVERY_LEASE_EXPIRED = "delivery_lease_expired"
    DELIVERY_ACKNOWLEDGED = "delivery_acknowledged"
    DELIVERY_REJECTED = "delivery_rejected"
    DELIVERY_RETRY_SCHEDULED = "delivery_retry_scheduled"
    DELIVERY_RETRY_EXHAUSTED = "delivery_retry_exhausted"
    DELIVERY_PERMANENT_FAILURE = "delivery_permanent_failure"


class AuditEvent(DomainModel):
    event_id: UUID
    site_id: NonEmptyText
    actor_id: NonEmptyText
    action: AuditAction
    resource_type: NonEmptyText
    resource_id: NonEmptyText
    occurred_at: AwareDateTime
    correlation_id: NonEmptyText | None = None
    reason_code: SafeErrorCode | None = None

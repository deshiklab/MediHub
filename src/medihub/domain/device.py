"""Device identity and adapter health contracts."""

from enum import StrEnum

from .base import AwareDateTime, DomainModel, NonEmptyText


class AdapterHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


class DeviceReference(DomainModel):
    """Facility-scoped device identity; never infer identity from an IP address."""

    device_id: NonEmptyText
    manufacturer: NonEmptyText
    model: NonEmptyText
    firmware_version: NonEmptyText | None = None


class DeviceRegistration(DomainModel):
    """Site inventory record for an explicitly supported device/interface."""

    device: DeviceReference
    site_id: NonEmptyText
    location_id: NonEmptyText | None = None
    registered_at: AwareDateTime
    enabled: bool = True
    capabilities: tuple[NonEmptyText, ...] = ()


class AdapterHealth(DomainModel):
    """Operational health only; detail codes must not contain patient data."""

    adapter_id: NonEmptyText
    status: AdapterHealthStatus
    checked_at: AwareDateTime
    detail_code: NonEmptyText | None = None

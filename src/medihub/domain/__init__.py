"""Versioned domain contracts for device observations and routing."""

from .association import AssociationSource, AssociationStatus, PatientAssociation
from .audit import AuditAction, AuditEvent
from .delivery import (
    ClaimedDelivery,
    DeliveryAttempt,
    DeliveryStatus,
    Destination,
    DestinationProtocol,
    ValidationIssue,
    ValidationSeverity,
)
from .device import AdapterHealth, AdapterHealthStatus, DeviceReference, DeviceRegistration
from .mapping import (
    SyntheticMappingError,
    SyntheticMappingResult,
    SyntheticMappingSet,
    SyntheticMetricMapping,
)
from .observation import (
    Coding,
    EventOrigin,
    ObservationEvent,
    PatientReference,
    QualityFlag,
    SourceProvenance,
    TimeQuality,
)
from .routing import BlockedRoute

__all__ = [
    "AdapterHealth",
    "AdapterHealthStatus",
    "AssociationSource",
    "AssociationStatus",
    "AuditAction",
    "BlockedRoute",
    "AuditEvent",
    "Coding",
    "ClaimedDelivery",
    "DeliveryAttempt",
    "DeliveryStatus",
    "Destination",
    "DestinationProtocol",
    "DeviceReference",
    "DeviceRegistration",
    "EventOrigin",
    "ObservationEvent",
    "PatientAssociation",
    "PatientReference",
    "QualityFlag",
    "SourceProvenance",
    "SyntheticMappingError",
    "SyntheticMappingResult",
    "SyntheticMappingSet",
    "SyntheticMetricMapping",
    "TimeQuality",
    "ValidationIssue",
    "ValidationSeverity",
]

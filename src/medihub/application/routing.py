"""Pre-route checks shared by all destination adapters.

The initial live-data policy fails closed: a patient-bearing event must match
an active, confirmed device association at a synchronized observation time.
Facility-specific policies may become more permissive only after review.
"""

from medihub.domain import (
    AssociationStatus,
    Destination,
    EventOrigin,
    ObservationEvent,
    PatientAssociation,
    TimeQuality,
)


class RouteBlockedError(ValueError):
    """Raised when a route violates a site, origin, or patient-context policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def assert_route_eligible(
    event: ObservationEvent,
    destination: Destination,
    *,
    association: PatientAssociation | None = None,
) -> None:
    """Block unsafe routing before any destination adapter sends an event."""

    if not destination.enabled:
        raise RouteBlockedError("destination_disabled", "destination is disabled")
    if event.site_id != destination.site_id:
        raise RouteBlockedError("site_mismatch", "event and destination belong to different sites")

    if event.origin is EventOrigin.SYNTHETIC:
        if event.patient is not None or association is not None:
            raise RouteBlockedError(
                "synthetic_patient_context",
                "synthetic events must not carry patient context",
            )
        if not destination.accepts_synthetic_data:
            raise RouteBlockedError(
                "synthetic_not_accepted",
                "synthetic events are not accepted by this destination",
            )
        return

    if association is None or association.status is not AssociationStatus.CONFIRMED:
        raise RouteBlockedError(
            "association_not_confirmed",
            "a confirmed patient/device association is required",
        )
    if association.site_id != event.site_id or association.device_id != event.device.device_id:
        raise RouteBlockedError(
            "association_binding_mismatch",
            "patient association does not match the event site and device",
        )
    if event.patient is None or event.patient != association.patient:
        raise RouteBlockedError(
            "patient_reference_mismatch",
            "event patient does not match the confirmed association",
        )
    if event.observed_at is None or event.time_quality is not TimeQuality.DEVICE_SYNCHRONIZED:
        raise RouteBlockedError(
            "observation_time_unreliable",
            "a synchronized observation time is required for association",
        )
    if not association.is_confirmed_at(event.observed_at):
        raise RouteBlockedError(
            "association_inactive",
            "patient association was not active at observation time",
        )

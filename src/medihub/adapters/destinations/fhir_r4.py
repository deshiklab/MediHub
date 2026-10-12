"""Synthetic-only FHIR R4 Observation mapping and in-process test receiver.

This is a deliberately small generic R4 resource shape. It is not a validator for
Bangladesh Core FHIR profiles or a facility's receiver contract, and it opens no
network connection.
"""

from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from medihub.application.routing import RouteBlockedError, assert_route_eligible
from medihub.domain import (
    ClaimedDelivery,
    DeliveryAttempt,
    DeliveryStatus,
    Destination,
    DestinationProtocol,
    EventOrigin,
    ObservationEvent,
)
from medihub.domain.base import AwareDateTime


def _utc_now() -> datetime:
    return datetime.now(UTC)


class FhirR4MappingError(ValueError):
    """A synthetic event cannot be safely represented by this limited R4 mapper."""


class FhirCoding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    display: str | None = None


class FhirCodeableConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coding: list[FhirCoding] = Field(min_length=1)
    text: str | None = None


class FhirIdentifier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str = Field(min_length=1)
    value: str = Field(min_length=1)


class FhirMetaTag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    display: str | None = None


class FhirMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: list[FhirMetaTag] = Field(min_length=1)


class FhirQuantity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str = Field(min_length=1)
    system: str = Field(min_length=1)
    code: str = Field(min_length=1)


class FhirReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display: str = Field(min_length=1)


class FhirR4Observation(BaseModel):
    """Minimal FHIR R4 Observation subset used by this synthetic preview only."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    resource_type: Literal["Observation"] = Field(alias="resourceType")
    id: str = Field(pattern=r"^[A-Za-z0-9.\-]{1,64}$")
    identifier: list[FhirIdentifier] = Field(min_length=1)
    meta: FhirMeta
    status: Literal["preliminary"]
    code: FhirCodeableConcept
    effective_date_time: AwareDateTime = Field(alias="effectiveDateTime")
    issued: AwareDateTime
    value_quantity: FhirQuantity = Field(alias="valueQuantity")
    device: FhirReference


def build_synthetic_observation(event: ObservationEvent) -> FhirR4Observation:
    """Map a patient-free synthetic event to a small generic R4 Observation.

    The output deliberately omits ``subject`` and any encounter or patient link.
    A site must supply and validate its own profile and association policy before
    any live-event mapper or destination can be enabled.
    """

    if event.origin is not EventOrigin.SYNTHETIC:
        raise FhirR4MappingError("only synthetic events can use the demo FHIR mapper")
    if event.patient is not None or event.encounter_reference is not None:
        raise FhirR4MappingError("synthetic FHIR observations cannot contain patient context")
    if event.observed_at is None:
        raise FhirR4MappingError("FHIR effectiveDateTime requires an observation timestamp")

    try:
        return FhirR4Observation.model_validate(
            {
                "resourceType": "Observation",
                "id": event.event_id.hex,
                "identifier": [
                    {
                        "system": "urn:ietf:rfc:3986",
                        "value": f"urn:uuid:{event.event_id}",
                    }
                ],
                "meta": {
                    "tag": [
                        {
                            "system": "urn:medihub:data-origin",
                            "code": "synthetic",
                            "display": "Synthetic demonstration data",
                        }
                    ]
                },
                "status": "preliminary",
                "code": {
                    "coding": [
                        {
                            "system": event.metric.system,
                            "code": event.metric.code,
                            "display": event.metric.display,
                        }
                    ]
                },
                "effectiveDateTime": event.observed_at,
                "issued": event.received_at,
                "valueQuantity": {
                    "value": event.value,
                    "unit": event.source_unit.display or event.source_unit.code,
                    "system": event.source_unit.system,
                    "code": event.source_unit.code,
                },
                "device": {"display": event.device.device_id},
            }
        )
    except ValidationError:
        raise FhirR4MappingError("synthetic event failed the limited FHIR R4 shape check") from None


class SyntheticFhirR4DestinationAdapter:
    """Validate FHIR-shaped synthetic resources and ACK them in-process only."""

    def __init__(
        self,
        destination: Destination,
        *,
        clock: Callable[[], datetime] = _utc_now,
        max_seen_event_ids: int | None = None,
    ) -> None:
        if destination.protocol is not DestinationProtocol.FHIR_R4:
            raise ValueError("FHIR R4 receiver requires a fhir_r4 destination")
        if not destination.accepts_synthetic_data:
            raise ValueError("synthetic FHIR receiver must explicitly accept synthetic data")
        if max_seen_event_ids is not None and max_seen_event_ids < 1:
            raise ValueError("max_seen_event_ids must be positive")
        self._destination = destination
        self._clock = clock
        self._max_seen_event_ids = max_seen_event_ids
        self._seen_event_ids: OrderedDict[UUID, None] = OrderedDict()
        self._unique_receipt_count = 0
        self._delivery_attempt_count = 0

    @property
    def destination(self) -> Destination:
        return self._destination

    @property
    def unique_receipt_count(self) -> int:
        return self._unique_receipt_count

    @property
    def delivery_attempt_count(self) -> int:
        return self._delivery_attempt_count

    async def send(self, delivery: ClaimedDelivery) -> DeliveryAttempt:
        self._delivery_attempt_count += 1
        try:
            assert_route_eligible(delivery.event, self._destination)
            build_synthetic_observation(delivery.event)
        except RouteBlockedError as error:
            return self._failure(delivery, error.code)
        except FhirR4MappingError:
            return self._failure(delivery, "fhir_r4_synthetic_mapping_failed")

        event_id = delivery.event.event_id
        if event_id not in self._seen_event_ids:
            self._seen_event_ids[event_id] = None
            self._unique_receipt_count += 1
            if (
                self._max_seen_event_ids is not None
                and len(self._seen_event_ids) > self._max_seen_event_ids
            ):
                self._seen_event_ids.popitem(last=False)

        acknowledgement_id = uuid5(
            NAMESPACE_URL,
            f"medihub-fhir-r4-synthetic-ack:{self._destination.destination_id}:{event_id}",
        )
        return DeliveryAttempt(
            attempt_id=delivery.attempt_id,
            event_id=event_id,
            destination_id=delivery.destination_id,
            attempt_number=delivery.attempt_number,
            status=DeliveryStatus.ACKNOWLEDGED,
            started_at=delivery.started_at,
            completed_at=max(self._clock(), delivery.started_at),
            acknowledgement_id=f"synthetic-fhir-ack-{acknowledgement_id.hex}",
        )

    def _failure(self, delivery: ClaimedDelivery, error_code: str) -> DeliveryAttempt:
        return DeliveryAttempt(
            attempt_id=delivery.attempt_id,
            event_id=delivery.event.event_id,
            destination_id=delivery.destination_id,
            attempt_number=delivery.attempt_number,
            status=DeliveryStatus.PERMANENT_FAILURE,
            started_at=delivery.started_at,
            completed_at=max(self._clock(), delivery.started_at),
            error_code=error_code,
        )

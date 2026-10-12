"""Deterministic synthetic source with configurable transport/time faults.

The simulator emits only synthetic events with a non-routable example.invalid
metric system. It does not represent a real device or clinical measurement.
"""

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from medihub.domain import (
    AdapterHealth,
    AdapterHealthStatus,
    Coding,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    QualityFlag,
    SourceProvenance,
    TimeQuality,
)
from medihub.domain.base import AwareDateTime, DomainModel, NonEmptyText


class SyntheticDeviceConfig(DomainModel):
    site_id: NonEmptyText = "synthetic-site"
    device: DeviceReference = Field(
        default_factory=lambda: DeviceReference(
            device_id="sim-device-001",
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
            firmware_version="1.0",
        )
    )
    event_count: int = Field(default=5, ge=1, le=10_000)
    seed: int = 7
    start_at: AwareDateTime | None = None
    interval_ms: int = Field(default=1_000, ge=1, le=86_400_000)
    duplicate_every: int = Field(default=0, ge=0, le=10_000)
    reverse_adjacent_pairs: bool = False
    clock_drift_ms_per_sample: int = Field(default=0, ge=-60_000, le=60_000)
    disconnect_after: int | None = Field(default=None, ge=0, le=9_999)
    disconnect_for: int = Field(default=0, ge=0, le=10_000)
    supported_firmware_versions: tuple[NonEmptyText, ...] = ("1.0",)

    @model_validator(mode="after")
    def validate_scenario(self) -> "SyntheticDeviceConfig":
        if self.interval_ms + self.clock_drift_ms_per_sample <= 0:
            raise ValueError("clock drift must leave observation times increasing")
        if self.disconnect_after is None and self.disconnect_for > 0:
            raise ValueError("disconnect_for requires disconnect_after")
        if self.disconnect_after is not None:
            if self.disconnect_for == 0:
                raise ValueError("disconnect_after requires a positive disconnect_for")
            if self.disconnect_after >= self.event_count:
                raise ValueError("disconnect_after must be less than event_count")
        return self


class SyntheticDeviceAdapter:
    """Finite async adapter for local tests; never connects to a real device."""

    adapter_id = "medihub.synthetic-device"
    adapter_version = "0.2.0"

    def __init__(self, config: SyntheticDeviceConfig | None = None) -> None:
        self.config = config or SyntheticDeviceConfig()
        self._closed = False
        self._disconnected = False

    async def read_events(self) -> AsyncIterator[ObservationEvent]:
        if self._closed or not self._firmware_supported:
            return
        start = self.config.start_at or datetime.now(UTC)
        sequences = list(range(self.config.event_count))
        if self.config.reverse_adjacent_pairs:
            for index in range(0, len(sequences) - 1, 2):
                sequences[index], sequences[index + 1] = (
                    sequences[index + 1],
                    sequences[index],
                )

        for arrival_index, sequence in enumerate(sequences):
            if self._closed:
                return
            if self._is_disconnected_sequence(sequence):
                self._disconnected = True
                await asyncio.sleep(0)
                continue
            self._disconnected = False
            event = self._build_event(sequence, arrival_index, start)
            yield event
            if self.config.duplicate_every and (sequence + 1) % self.config.duplicate_every == 0:
                # Re-yield the exact same envelope so event-ID deduplication is testable.
                yield event
            await asyncio.sleep(0)

    async def health(self) -> AdapterHealth:
        if self._closed:
            status = AdapterHealthStatus.DISCONNECTED
            detail_code = "simulator_closed"
        elif self._disconnected:
            status = AdapterHealthStatus.DISCONNECTED
            detail_code = "simulated_disconnect"
        elif not self._firmware_supported:
            status = AdapterHealthStatus.DEGRADED
            detail_code = "unsupported_firmware"
        else:
            status = AdapterHealthStatus.HEALTHY
            detail_code = "synthetic_source_ready"
        return AdapterHealth(
            adapter_id=self.adapter_id,
            status=status,
            checked_at=datetime.now(UTC),
            detail_code=detail_code,
        )

    async def close(self) -> None:
        self._closed = True

    @property
    def _firmware_supported(self) -> bool:
        return self.config.device.firmware_version in self.config.supported_firmware_versions

    def _is_disconnected_sequence(self, sequence: int) -> bool:
        disconnect_after = self.config.disconnect_after
        return (
            disconnect_after is not None
            and disconnect_after <= sequence < disconnect_after + self.config.disconnect_for
        )

    def _build_event(
        self,
        sequence: int,
        arrival_index: int,
        start: datetime,
    ) -> ObservationEvent:
        nominal_observed_at = start + timedelta(milliseconds=self.config.interval_ms * sequence)
        observed_at = nominal_observed_at + timedelta(
            milliseconds=self.config.clock_drift_ms_per_sample * sequence
        )
        received_at = start + timedelta(milliseconds=self.config.interval_ms * arrival_index + 25)
        scenario_id = ":".join(
            (
                str(self.config.seed),
                start.isoformat(),
                str(self.config.interval_ms),
                str(self.config.clock_drift_ms_per_sample),
                str(self.config.reverse_adjacent_pairs),
                str(self.config.duplicate_every),
                str(self.config.disconnect_after),
                str(self.config.disconnect_for),
                self.config.device.manufacturer,
                self.config.device.model,
                self.config.device.firmware_version or "unknown-firmware",
            )
        )
        event_id = uuid5(
            NAMESPACE_URL,
            f"medihub-simulator:{self.config.site_id}:{self.config.device.device_id}:"
            f"{scenario_id}:{sequence}",
        )
        time_quality = (
            TimeQuality.DEVICE_UNSYNCHRONIZED
            if self.config.clock_drift_ms_per_sample
            else TimeQuality.DEVICE_SYNCHRONIZED
        )
        quality_flags = (
            (QualityFlag.CLOCK_UNSYNCED,)
            if time_quality is TimeQuality.DEVICE_UNSYNCHRONIZED
            else ()
        )
        rng = random.Random(self.config.seed + sequence)
        return ObservationEvent(
            event_id=event_id,
            site_id=self.config.site_id,
            device=self.config.device,
            metric=Coding(
                system="https://example.invalid/medihub/synthetic-metrics",
                code="simulated-scalar-reading",
                display="Synthetic scalar measurement",
            ),
            value=round(rng.uniform(0.0, 100.0), 2),
            source_unit=Coding(
                system="http://unitsofmeasure.org",
                code="1",
                display="dimensionless",
            ),
            observed_at=observed_at,
            received_at=received_at,
            time_quality=time_quality,
            quality_flags=quality_flags,
            provenance=SourceProvenance(
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                source_message_id=f"synthetic-{self.config.seed}-{sequence}",
                source_sequence=sequence,
            ),
            origin=EventOrigin.SYNTHETIC,
        )

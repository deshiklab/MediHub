import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.domain import (
    AdapterHealthStatus,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    QualityFlag,
    TimeQuality,
)


async def collect_events(adapter: SyntheticDeviceAdapter) -> list[ObservationEvent]:
    return [event async for event in adapter.read_events()]


def test_simulator_is_reproducible_and_marks_data_synthetic() -> None:
    config = SyntheticDeviceConfig(
        event_count=3,
        seed=42,
        start_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
    )
    first = asyncio.run(collect_events(SyntheticDeviceAdapter(config)))
    second = asyncio.run(collect_events(SyntheticDeviceAdapter(config)))

    assert len(first) == 3
    assert [event.event_id for event in first] == [event.event_id for event in second]
    assert [event.value for event in first] == [event.value for event in second]
    assert all(event.origin is EventOrigin.SYNTHETIC for event in first)
    assert all(event.patient is None for event in first)
    assert all("example.invalid" in event.metric.system for event in first)


def test_simulator_uses_monotonic_source_sequences_and_ordered_times() -> None:
    config = SyntheticDeviceConfig(
        event_count=4,
        start_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
        interval_ms=250,
    )
    events = asyncio.run(collect_events(SyntheticDeviceAdapter(config)))

    assert [event.provenance.source_sequence for event in events] == [0, 1, 2, 3]
    assert [event.observed_at for event in events] == sorted(event.observed_at for event in events)
    assert events[1].observed_at - events[0].observed_at == timedelta(milliseconds=250)


def test_duplicate_and_out_of_order_faults_are_deterministic() -> None:
    config = SyntheticDeviceConfig(
        event_count=4,
        seed=11,
        start_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
        duplicate_every=2,
        reverse_adjacent_pairs=True,
    )
    first = asyncio.run(collect_events(SyntheticDeviceAdapter(config)))
    second = asyncio.run(collect_events(SyntheticDeviceAdapter(config)))

    assert [event.provenance.source_sequence for event in first] == [1, 1, 0, 3, 3, 2]
    assert first[0] == first[1]
    assert first[3] == first[4]
    assert [event.event_id for event in first] == [event.event_id for event in second]
    assert [event.value for event in first] == [event.value for event in second]
    assert [event.received_at for event in first] == sorted(event.received_at for event in first)


def test_clock_drift_is_cumulative_and_marked_unsynchronized() -> None:
    config = SyntheticDeviceConfig(
        event_count=3,
        start_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
        interval_ms=1_000,
        clock_drift_ms_per_sample=100,
    )
    events = asyncio.run(collect_events(SyntheticDeviceAdapter(config)))

    assert events[1].observed_at - events[0].observed_at == timedelta(milliseconds=1_100)
    assert all(event.time_quality is TimeQuality.DEVICE_UNSYNCHRONIZED for event in events)
    assert all(QualityFlag.CLOCK_UNSYNCED in event.quality_flags for event in events)


def test_simulator_disconnect_skips_readings_and_health_recovers() -> None:
    async def exercise() -> tuple[
        list[ObservationEvent],
        list[AdapterHealthStatus],
        AdapterHealthStatus,
    ]:
        adapter = SyntheticDeviceAdapter(
            SyntheticDeviceConfig(
                event_count=6,
                disconnect_after=2,
                disconnect_for=2,
                start_at=datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
            )
        )
        stop = asyncio.Event()
        observed_health: list[AdapterHealthStatus] = []

        async def poll_health() -> None:
            while not stop.is_set():
                observed_health.append((await adapter.health()).status)
                await asyncio.sleep(0)

        polling = asyncio.create_task(poll_health())
        try:
            events = await collect_events(adapter)
        finally:
            stop.set()
            await polling
        final_health = (await adapter.health()).status
        return events, observed_health, final_health

    events, observed_health, final_health = asyncio.run(exercise())

    assert [event.provenance.source_sequence for event in events] == [0, 1, 4, 5]
    assert AdapterHealthStatus.DISCONNECTED in observed_health
    assert final_health is AdapterHealthStatus.HEALTHY


def test_unsupported_firmware_is_degraded_and_emits_no_observations() -> None:
    async def exercise() -> tuple[list[ObservationEvent], AdapterHealthStatus, str | None]:
        adapter = SyntheticDeviceAdapter(
            SyntheticDeviceConfig(
                device=DeviceReference(
                    device_id="sim-device-unsupported",
                    manufacturer="MediHub Synthetic",
                    model="scalar-simulator-v1",
                    firmware_version="9.9-test",
                ),
                event_count=2,
            )
        )
        events = await collect_events(adapter)
        health = await adapter.health()
        await adapter.close()
        return events, health.status, health.detail_code

    events, status, detail_code = asyncio.run(exercise())

    assert events == []
    assert status is AdapterHealthStatus.DEGRADED
    assert detail_code == "unsupported_firmware"


def test_invalid_clock_and_disconnect_scenarios_are_rejected() -> None:
    with pytest.raises(ValidationError, match="leave observation times increasing"):
        SyntheticDeviceConfig(interval_ms=1_000, clock_drift_ms_per_sample=-1_000)
    with pytest.raises(ValidationError, match="disconnect_for requires disconnect_after"):
        SyntheticDeviceConfig(disconnect_for=1)

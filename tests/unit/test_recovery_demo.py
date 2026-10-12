import asyncio
from datetime import UTC, datetime

import pytest

from medihub.adapters.devices.simulator import SyntheticDeviceConfig
from medihub.application.recovery_demo import (
    SyntheticRecoveryDemoError,
    run_synthetic_recovery_demo,
)

START_AT = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


def test_recovery_demo_recovers_a_lease_retries_then_drains_durable_outbox() -> None:
    summary = asyncio.run(
        run_synthetic_recovery_demo(
            SyntheticDeviceConfig(
                event_count=2,
                duplicate_every=2,
                start_at=START_AT,
            )
        )
    )

    assert summary.events_read == 3
    assert summary.events_inserted == 2
    assert summary.duplicate_events == 1
    assert summary.simulated_process_restarts == 1
    assert summary.expired_leases_recovered == 1
    assert summary.retryable_failures == 2
    assert summary.delivery_attempts == 4
    assert summary.acknowledged_deliveries == 2
    assert summary.pending_deliveries == 0
    assert summary.unique_test_receipts == 2


def test_recovery_demo_refuses_a_disconnected_source_scenario() -> None:
    config = SyntheticDeviceConfig(
        event_count=3,
        disconnect_after=0,
        disconnect_for=1,
        start_at=START_AT,
    )

    with pytest.raises(
        SyntheticRecoveryDemoError,
        match="recovery_demo_requires_continuous_source",
    ):
        asyncio.run(run_synthetic_recovery_demo(config))

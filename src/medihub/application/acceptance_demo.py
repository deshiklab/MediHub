"""Offline synthetic acceptance and resilience checks for the existing MediHub pipeline."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from medihub.adapters.destinations.fhir_r4 import SyntheticFhirR4DestinationAdapter
from medihub.adapters.destinations.synthetic_fault_injector import (
    SyntheticReceiverFaultInjector,
)
from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.application.ambiguous_delivery_demo import (
    SyntheticAmbiguousDeliveryDemoError,
    SyntheticAmbiguousDeliveryDemoSummary,
    run_synthetic_ambiguous_delivery_demo,
)
from medihub.application.demo import DemoSummary, run_synthetic_demo
from medihub.application.ingestion import IngestionService
from medihub.application.load_demo import (
    MAX_SYNTHETIC_LOAD_EVENTS,
    SyntheticLoadDemoSummary,
    run_synthetic_load_demo,
)
from medihub.application.outbox_worker import OutboxWorker
from medihub.application.recovery_demo import (
    MAX_RECOVERY_DEMO_EVENTS,
    SyntheticRecoveryDemoError,
    SyntheticRecoveryDemoSummary,
    run_synthetic_recovery_demo,
)
from medihub.application.synthetic_mapping import (
    SyntheticMappingBatchError,
    map_synthetic_events,
)
from medihub.domain import (
    Coding,
    DeliveryStatus,
    Destination,
    DestinationProtocol,
    SyntheticMappingSet,
    SyntheticMetricMapping,
)
from medihub.infrastructure.database import Base, create_database_engine
from medihub.infrastructure.event_store import SqlAlchemyEventStore
from medihub.infrastructure.models import (
    DeliveryAttemptRecord,
    DeliveryOutboxRecord,
    RoutingHoldRecord,
)

MIN_SYNTHETIC_ACCEPTANCE_EVENTS = 2
MAX_SYNTHETIC_ACCEPTANCE_EVENTS = min(
    MAX_RECOVERY_DEMO_EVENTS,
    MAX_SYNTHETIC_LOAD_EVENTS,
    100,
)


class SyntheticAcceptanceDemoError(ValueError):
    """Safe error code for an incomplete synthetic acceptance run."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class SyntheticAcceptanceCheck:
    """One aggregate-only acceptance assertion; never includes event identifiers."""

    check_id: str
    passed: bool
    observed: int | bool | str
    expected: int | bool | str


@dataclass(frozen=True, slots=True)
class SyntheticAcceptanceMappingSummary:
    """Aggregate result from the built-in, patient-free simulator mapping exercise."""

    mapped_events: int
    unmapped_events: int
    mapping_set_id: str
    mapping_version: str
    synthetic_only: bool
    partial_output: bool
    source_health: str
    network_enabled: bool = False


@dataclass(frozen=True, slots=True)
class SyntheticAcceptanceFaultSummary:
    """Aggregate result from one retry → rejection → explicit replay sequence."""

    delivery_attempts: int
    retryable_failures: int
    terminal_rejections: int
    acknowledged_attempts: int
    manual_replays: int
    final_acknowledged_deliveries: int
    pending_deliveries: int
    routing_policy_holds: int
    unique_test_receipts: int
    faults_injected: int
    fault_injector_clear: bool
    network_enabled: bool


@dataclass(frozen=True, slots=True)
class SyntheticAcceptanceDemoSummary:
    """Combined status and aggregate evidence from all local synthetic stages."""

    status: str
    events_requested: int
    duplicate_every: int
    duplicate_events_expected: int
    pipeline: DemoSummary
    mapping: SyntheticAcceptanceMappingSummary
    fault_drill: SyntheticAcceptanceFaultSummary
    ambiguous_ack_drill: SyntheticAmbiguousDeliveryDemoSummary
    restart_recovery: SyntheticRecoveryDemoSummary
    bounded_load: SyntheticLoadDemoSummary
    checks: tuple[SyntheticAcceptanceCheck, ...]
    data_mode: str = "synthetic_only"
    transport: str = "in_process"
    network_enabled: bool = False
    facility_qualification: str = "not_performed"


def _expected_duplicates(config: SyntheticDeviceConfig) -> int:
    if config.duplicate_every == 0:
        return 0
    return config.event_count // config.duplicate_every


def _check(
    check_id: str,
    observed: int | bool | str,
    expected: int | bool | str,
) -> SyntheticAcceptanceCheck:
    return SyntheticAcceptanceCheck(
        check_id=check_id,
        passed=observed == expected,
        observed=observed,
        expected=expected,
    )


def _acceptance_mapping(config: SyntheticDeviceConfig) -> SyntheticMappingSet:
    """Construct the same deliberately non-clinical mapping used by the example."""

    if config.device.firmware_version is None:
        raise SyntheticAcceptanceDemoError("acceptance_requires_versioned_synthetic_firmware")

    return SyntheticMappingSet(
        scope="synthetic_only",
        mapping_set_id="synthetic-acceptance-scalar",
        version="1.0.0",
        manufacturer=config.device.manufacturer,
        model=config.device.model,
        firmware_versions=(config.device.firmware_version,),
        adapter_id=SyntheticDeviceAdapter.adapter_id,
        adapter_version=SyntheticDeviceAdapter.adapter_version,
        entries=(
            SyntheticMetricMapping(
                source_metric=Coding(
                    system="https://example.invalid/medihub/synthetic-metrics",
                    code="simulated-scalar-reading",
                    display="Synthetic scalar measurement",
                ),
                source_unit=Coding(
                    system="http://unitsofmeasure.org",
                    code="1",
                    display="dimensionless",
                ),
                normalized_metric=Coding(
                    system="https://example.invalid/medihub/canonical-synthetic",
                    code="mapped-synthetic-scalar",
                    display="Mapped synthetic scalar",
                ),
                normalized_unit=Coding(
                    system="http://unitsofmeasure.org",
                    code="1",
                    display="dimensionless",
                ),
                operation="identity",
            ),
        ),
    )


async def _run_mapping_stage(
    config: SyntheticDeviceConfig,
) -> SyntheticAcceptanceMappingSummary:
    simulator = SyntheticDeviceAdapter(config)
    unique_events = {}
    try:
        async for event in simulator.read_events():
            unique_events.setdefault(event.event_id, event)
        source_health = await simulator.health()
    finally:
        await simulator.close()

    if len(unique_events) != config.event_count:
        raise SyntheticAcceptanceDemoError("acceptance_mapping_source_count_mismatch")

    mapping_set = _acceptance_mapping(config)
    try:
        mapped = map_synthetic_events(tuple(unique_events.values()), mapping_set)
    except SyntheticMappingBatchError as error:
        raise SyntheticAcceptanceDemoError(f"acceptance_{error.code}") from None

    return SyntheticAcceptanceMappingSummary(
        mapped_events=len(mapped),
        unmapped_events=config.event_count - len(mapped),
        mapping_set_id=mapping_set.mapping_set_id,
        mapping_version=mapping_set.version,
        synthetic_only=all(result.origin == "synthetic" for result in mapped),
        partial_output=False,
        source_health=source_health.status.value,
    )


async def _run_fault_drill(config: SyntheticDeviceConfig) -> SyntheticAcceptanceFaultSummary:
    """Exercise durable retry and terminal replay with a single synthetic event."""

    fault_config = config.model_copy(update={"event_count": 1, "duplicate_every": 0})
    simulator = SyntheticDeviceAdapter(fault_config)
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        sessions = async_sessionmaker(engine, expire_on_commit=False)
        store = SqlAlchemyEventStore(sessions)
        destination = Destination(
            destination_id="medihub.synthetic-acceptance-receiver",
            site_id=fault_config.site_id,
            name="MediHub in-process synthetic acceptance receiver",
            protocol=DestinationProtocol.FHIR_R4,
            contract_version="generic-r4-synthetic-acceptance-v1",
            connection_ref="in-process",
            enabled=True,
            accepts_synthetic_data=True,
        )
        held_destination = Destination(
            destination_id="medihub.synthetic-acceptance-policy-hold",
            site_id=fault_config.site_id,
            name="MediHub synthetic policy hold",
            protocol=DestinationProtocol.FHIR_R4,
            contract_version="synthetic-policy-test-v1",
            connection_ref="in-process",
            enabled=True,
            accepts_synthetic_data=False,
        )
        receiver = SyntheticFhirR4DestinationAdapter(destination, max_seen_event_ids=1)
        fault_injector = SyntheticReceiverFaultInjector(receiver)
        ingestion = IngestionService(store)

        events_read = 0
        events_inserted = 0
        policy_holds = 0
        try:
            async for event in simulator.read_events():
                events_read += 1
                result = await ingestion.ingest(event, [destination, held_destination])
                if not result.duplicate:
                    events_inserted += 1
                    policy_holds += len(result.blocked_routes)
            source_health = await simulator.health()
        finally:
            await simulator.close()

        if events_read != 1 or events_inserted != 1:
            raise SyntheticAcceptanceDemoError("acceptance_fault_source_count_mismatch")
        if source_health.status.value != "healthy":
            raise SyntheticAcceptanceDemoError("acceptance_fault_source_unhealthy")

        worker = OutboxWorker(
            store,
            {destination.destination_id: fault_injector},
            max_attempts=5,
            base_retry_delay=timedelta(0),
            max_retry_delay=timedelta(0),
        )
        await fault_injector.arm("retry_once")
        retry_attempt = await worker.dispatch_once()
        if retry_attempt is None or retry_attempt.status is not DeliveryStatus.RETRYABLE_FAILURE:
            raise SyntheticAcceptanceDemoError("acceptance_retry_fault_not_observed")

        await fault_injector.arm("reject_once")
        rejection_attempt = await worker.dispatch_once()
        if rejection_attempt is None or rejection_attempt.status is not DeliveryStatus.REJECTED:
            raise SyntheticAcceptanceDemoError("acceptance_terminal_rejection_not_observed")

        await store.requeue_terminal_synthetic_delivery(
            rejection_attempt.event_id,
            destination.destination_id,
            now=datetime.now(UTC),
            max_attempts=5,
        )
        manual_replays = 1
        replay_attempt = await worker.dispatch_once()
        if (
            replay_attempt is None
            or replay_attempt.event_id != rejection_attempt.event_id
            or replay_attempt.status is not DeliveryStatus.ACKNOWLEDGED
        ):
            raise SyntheticAcceptanceDemoError("acceptance_terminal_replay_not_acknowledged")

        fault_status = await fault_injector.status()
        async with sessions() as session:
            outbox_rows = (await session.scalars(select(DeliveryOutboxRecord))).all()
            attempt_rows = (await session.scalars(select(DeliveryAttemptRecord))).all()
            hold_rows = (await session.scalars(select(RoutingHoldRecord))).all()

        attempt_counts = Counter(row.status for row in attempt_rows)
        outbox_counts = Counter(row.status for row in outbox_rows)
        return SyntheticAcceptanceFaultSummary(
            delivery_attempts=len(attempt_rows),
            retryable_failures=attempt_counts[DeliveryStatus.RETRYABLE_FAILURE.value],
            terminal_rejections=attempt_counts[DeliveryStatus.REJECTED.value],
            acknowledged_attempts=attempt_counts[DeliveryStatus.ACKNOWLEDGED.value],
            manual_replays=manual_replays,
            final_acknowledged_deliveries=outbox_counts[DeliveryStatus.ACKNOWLEDGED.value],
            pending_deliveries=sum(
                outbox_counts[status.value]
                for status in (
                    DeliveryStatus.QUEUED,
                    DeliveryStatus.SENT,
                    DeliveryStatus.RETRYABLE_FAILURE,
                )
            ),
            routing_policy_holds=len(hold_rows),
            unique_test_receipts=receiver.unique_receipt_count,
            faults_injected=int(fault_status["faults_injected"]),
            fault_injector_clear=fault_status["armed_fault"] is None,
            network_enabled=bool(fault_status["network_enabled"]),
        )
    finally:
        await engine.dispose()


async def run_synthetic_acceptance_demo(
    config: SyntheticDeviceConfig,
) -> SyntheticAcceptanceDemoSummary:
    """Run pipeline, mapping, fault/replay, ACK-loss, recovery, and load stages offline.

    The run uses synthetic simulator events, in-memory SQLite for pipeline, fault,
    and load stages, separate temporary file-backed SQLite stores for ACK-loss and
    recovery drills, and in-process test receivers. It never reads
    ``MEDIHUB_DATABASE_URL`` or opens a device/network connection.
    """

    if not MIN_SYNTHETIC_ACCEPTANCE_EVENTS <= config.event_count <= MAX_SYNTHETIC_ACCEPTANCE_EVENTS:
        raise SyntheticAcceptanceDemoError("synthetic_acceptance_event_limit_exceeded")
    if config.disconnect_after is not None or config.disconnect_for:
        raise SyntheticAcceptanceDemoError("synthetic_acceptance_requires_continuous_source")
    if config.device.firmware_version not in config.supported_firmware_versions:
        raise SyntheticAcceptanceDemoError("synthetic_acceptance_requires_supported_firmware")

    duplicates_expected = _expected_duplicates(config)
    pipeline = await run_synthetic_demo(config)
    mapping = await _run_mapping_stage(config)
    fault_drill = await _run_fault_drill(config)
    try:
        ambiguous_ack_drill = await run_synthetic_ambiguous_delivery_demo(config)
    except SyntheticAmbiguousDeliveryDemoError as error:
        raise SyntheticAcceptanceDemoError(f"acceptance_{error.code}") from None
    try:
        recovery = await run_synthetic_recovery_demo(config)
    except SyntheticRecoveryDemoError as error:
        raise SyntheticAcceptanceDemoError(f"acceptance_{error.code}") from None
    load = await run_synthetic_load_demo(config)

    checks = (
        _check("pipeline_unique_events_inserted", pipeline.events_inserted, config.event_count),
        _check(
            "pipeline_duplicate_events_detected", pipeline.duplicate_events, duplicates_expected
        ),
        _check(
            "pipeline_deliveries_acknowledged", pipeline.acknowledged_deliveries, config.event_count
        ),
        _check(
            "pipeline_test_receiver_receipts", pipeline.unique_test_receipts, config.event_count
        ),
        _check("pipeline_no_blocked_routes", pipeline.blocked_routes, 0),
        _check("pipeline_source_healthy", pipeline.source_health, "healthy"),
        _check("mapping_results_complete", mapping.mapped_events, config.event_count),
        _check("mapping_no_unmapped_events", mapping.unmapped_events, 0),
        _check("mapping_synthetic_only", mapping.synthetic_only, True),
        _check("mapping_no_partial_output", mapping.partial_output, False),
        _check("mapping_source_healthy", mapping.source_health, "healthy"),
        _check("fault_retry_injected_once", fault_drill.retryable_failures, 1),
        _check("fault_terminal_rejection_injected_once", fault_drill.terminal_rejections, 1),
        _check("fault_manual_replay_performed", fault_drill.manual_replays, 1),
        _check("fault_replay_acknowledged", fault_drill.final_acknowledged_deliveries, 1),
        _check("fault_attempt_history_complete", fault_drill.delivery_attempts, 3),
        _check("fault_acknowledged_attempt_count", fault_drill.acknowledged_attempts, 1),
        _check("fault_policy_hold_persisted", fault_drill.routing_policy_holds, 1),
        _check("fault_pending_deliveries_drained", fault_drill.pending_deliveries, 0),
        _check("fault_test_receiver_receipt", fault_drill.unique_test_receipts, 1),
        _check("fault_count", fault_drill.faults_injected, 2),
        _check("fault_injector_cleared", fault_drill.fault_injector_clear, True),
        _check("fault_network_disabled", fault_drill.network_enabled, False),
        _check("ambiguous_ack_one_event_inserted", ambiguous_ack_drill.events_inserted, 1),
        _check("ambiguous_ack_worker_restarted", ambiguous_ack_drill.simulated_worker_restarts, 1),
        _check(
            "ambiguous_ack_receiver_restarted", ambiguous_ack_drill.simulated_receiver_restarts, 1
        ),
        _check("ambiguous_ack_attempt_history", ambiguous_ack_drill.delivery_attempts, 2),
        _check("ambiguous_ack_lost_once", ambiguous_ack_drill.retryable_failures, 1),
        _check("ambiguous_ack_retry_acknowledged", ambiguous_ack_drill.acknowledged_attempts, 1),
        _check(
            "ambiguous_ack_final_outbox_acknowledged",
            ambiguous_ack_drill.final_acknowledged_deliveries,
            1,
        ),
        _check("ambiguous_ack_queue_drained", ambiguous_ack_drill.pending_deliveries, 0),
        _check("ambiguous_ack_receiver_sends", ambiguous_ack_drill.receiver_delivery_attempts, 2),
        _check(
            "ambiguous_ack_duplicate_delivery", ambiguous_ack_drill.receiver_duplicate_attempts, 1
        ),
        _check(
            "ambiguous_ack_unique_receiver_receipt", ambiguous_ack_drill.unique_test_receipts, 1
        ),
        _check("ambiguous_ack_fault_injected_once", ambiguous_ack_drill.faults_injected, 1),
        _check(
            "ambiguous_ack_fault_injector_clear", ambiguous_ack_drill.fault_injector_clear, True
        ),
        _check("ambiguous_ack_network_disabled", ambiguous_ack_drill.network_enabled, False),
        _check("recovery_events_inserted", recovery.events_inserted, config.event_count),
        _check("recovery_duplicates_detected", recovery.duplicate_events, duplicates_expected),
        _check(
            "recovery_deliveries_acknowledged", recovery.acknowledged_deliveries, config.event_count
        ),
        _check(
            "recovery_attempt_history_complete", recovery.delivery_attempts, config.event_count + 2
        ),
        _check("recovery_restart_simulated", recovery.simulated_process_restarts, 1),
        _check("recovery_expired_lease_recovered", recovery.expired_leases_recovered, 1),
        _check("recovery_queue_drained", recovery.pending_deliveries, 0),
        _check("recovery_receiver_receipts", recovery.unique_test_receipts, config.event_count),
        _check("load_events_read", load.events_read, config.event_count + duplicates_expected),
        _check("load_unique_events_inserted", load.events_inserted, config.event_count),
        _check("load_duplicate_events_detected", load.duplicate_events, duplicates_expected),
        _check("load_deliveries_acknowledged", load.acknowledged_deliveries, config.event_count),
        _check("load_no_blocked_routes", load.blocked_routes, 0),
        _check("load_no_rejections", load.rejected_deliveries, 0),
        _check("load_no_retryable_failures", load.retryable_failures, 0),
        _check("load_no_permanent_failures", load.permanent_failures, 0),
        _check("load_test_receiver_receipts", load.unique_test_receipts, config.event_count),
        _check("load_network_disabled", load.network_enabled, False),
        _check("load_not_a_production_benchmark", load.production_benchmark, False),
    )
    passed = all(check.passed for check in checks)

    return SyntheticAcceptanceDemoSummary(
        status="passed" if passed else "failed",
        events_requested=config.event_count,
        duplicate_every=config.duplicate_every,
        duplicate_events_expected=duplicates_expected,
        pipeline=pipeline,
        mapping=mapping,
        fault_drill=fault_drill,
        ambiguous_ack_drill=ambiguous_ack_drill,
        restart_recovery=recovery,
        bounded_load=load,
        checks=checks,
    )


__all__ = [
    "MAX_SYNTHETIC_ACCEPTANCE_EVENTS",
    "MIN_SYNTHETIC_ACCEPTANCE_EVENTS",
    "SyntheticAcceptanceCheck",
    "SyntheticAcceptanceDemoError",
    "SyntheticAcceptanceDemoSummary",
    "SyntheticAcceptanceFaultSummary",
    "SyntheticAcceptanceMappingSummary",
    "run_synthetic_acceptance_demo",
]

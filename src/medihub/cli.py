"""Command-line entry points for synthetic simulation and local replay workflows."""

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import uvicorn
from sqlalchemy.ext.asyncio import async_sessionmaker

from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.application.acceptance_demo import (
    MAX_SYNTHETIC_ACCEPTANCE_EVENTS,
    MIN_SYNTHETIC_ACCEPTANCE_EVENTS,
    SyntheticAcceptanceDemoError,
    run_synthetic_acceptance_demo,
)
from medihub.application.demo import DemoSummary, run_synthetic_demo
from medihub.application.discovery import validate_profile_file
from medihub.application.load_demo import (
    MAX_SYNTHETIC_LOAD_EVENTS,
    run_synthetic_load_demo,
)
from medihub.application.mapping_discovery import validate_mapping_worksheet_file
from medihub.application.operations import SyntheticOperationsDashboard
from medihub.application.recovery_demo import (
    SyntheticRecoveryDemoError,
    run_synthetic_recovery_demo,
)
from medihub.application.replay import (
    ReplayInputError,
    ReplaySummary,
    load_synthetic_events,
    replay_synthetic_events,
)
from medihub.application.synthetic_mapping import (
    SyntheticMappingBatchError,
    SyntheticMappingConfigError,
    load_synthetic_mapping,
    map_synthetic_events,
)
from medihub.dashboard import create_dashboard_app
from medihub.domain import DeviceReference, ObservationEvent
from medihub.infrastructure.database import create_database_engine
from medihub.infrastructure.event_store import SqlAlchemyEventStore

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./medihub-local.db"


def _parse_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError("use an ISO-8601 timestamp") from error


def _add_simulation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--site-id", default="synthetic-site")
    parser.add_argument("--device-id", default="sim-device-001")
    parser.add_argument("--start-at", type=_parse_datetime)
    parser.add_argument("--interval-ms", type=int, default=1_000)
    parser.add_argument("--duplicate-every", type=int, default=0)
    parser.add_argument(
        "--reverse-adjacent-pairs",
        action="store_true",
        help="emit neighboring source sequences in reverse order",
    )
    parser.add_argument("--clock-drift-ms-per-sample", type=int, default=0)
    parser.add_argument("--disconnect-after", type=int)
    parser.add_argument("--disconnect-for", type=int, default=0)
    parser.add_argument("--firmware-version", default="1.0")


def _simulator_config_from_args(args: argparse.Namespace) -> SyntheticDeviceConfig:
    return SyntheticDeviceConfig(
        site_id=args.site_id,
        device=DeviceReference(
            device_id=args.device_id,
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
            firmware_version=args.firmware_version,
        ),
        event_count=args.count,
        seed=args.seed,
        start_at=args.start_at,
        interval_ms=args.interval_ms,
        duplicate_every=args.duplicate_every,
        reverse_adjacent_pairs=args.reverse_adjacent_pairs,
        clock_drift_ms_per_sample=args.clock_drift_ms_per_sample,
        disconnect_after=args.disconnect_after,
        disconnect_for=args.disconnect_for,
    )


def _recovery_config_from_args(args: argparse.Namespace) -> SyntheticDeviceConfig:
    return SyntheticDeviceConfig(
        site_id=args.site_id,
        device=DeviceReference(
            device_id=args.device_id,
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
            firmware_version="1.0",
        ),
        event_count=args.count,
        seed=args.seed,
        start_at=args.start_at,
        duplicate_every=args.duplicate_every,
    )


def _load_demo_config_from_args(args: argparse.Namespace) -> SyntheticDeviceConfig:
    return SyntheticDeviceConfig(
        site_id=args.site_id,
        device=DeviceReference(
            device_id=args.device_id,
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
            firmware_version="1.0",
        ),
        event_count=args.count,
        seed=args.seed,
        start_at=args.start_at,
        interval_ms=args.interval_ms,
        duplicate_every=args.duplicate_every,
    )


def _acceptance_config_from_args(args: argparse.Namespace) -> SyntheticDeviceConfig:
    return SyntheticDeviceConfig(
        site_id=args.site_id,
        device=DeviceReference(
            device_id=args.device_id,
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
            firmware_version="1.0",
        ),
        event_count=args.count,
        seed=args.seed,
        start_at=args.start_at,
        duplicate_every=args.duplicate_every,
    )


async def _write_synthetic_events(config: SyntheticDeviceConfig) -> None:
    adapter = SyntheticDeviceAdapter(config)
    try:
        async for event in adapter.read_events():
            print(event.model_dump_json())
    finally:
        await adapter.close()


async def _persist_replay(events: tuple[ObservationEvent, ...]) -> ReplaySummary:
    database_url = os.environ.get("MEDIHUB_DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_database_engine(database_url)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        return await replay_synthetic_events(events, SqlAlchemyEventStore(sessions))
    finally:
        await engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medihub")
    commands = parser.add_subparsers(dest="command", required=True)
    simulate = commands.add_parser(
        "simulate",
        help="emit synthetic observation events as NDJSON",
    )
    _add_simulation_arguments(simulate)

    demo = commands.add_parser(
        "demo",
        help="run a synthetic event through the in-process test receiver",
    )
    _add_simulation_arguments(demo)

    acceptance_demo = commands.add_parser(
        "acceptance-demo",
        help="run combined synthetic-only pipeline, mapping, recovery, and bounded-load checks",
    )
    acceptance_demo.add_argument(
        "--count",
        type=int,
        default=10,
        help=(
            "unique synthetic events for the bounded stages "
            f"({MIN_SYNTHETIC_ACCEPTANCE_EVENTS}–{MAX_SYNTHETIC_ACCEPTANCE_EVENTS})"
        ),
    )
    acceptance_demo.add_argument("--seed", type=int, default=7)
    acceptance_demo.add_argument("--site-id", default="synthetic-site")
    acceptance_demo.add_argument("--device-id", default="sim-device-001")
    acceptance_demo.add_argument("--start-at", type=_parse_datetime)
    acceptance_demo.add_argument(
        "--duplicate-every",
        type=int,
        default=2,
        help="redeliver every Nth event to exercise deduplication; 0 disables",
    )

    recovery_demo = commands.add_parser(
        "recovery-demo",
        help="exercise synthetic outbox recovery after a simulated gateway restart",
    )
    recovery_demo.add_argument("--count", type=int, default=3, help="synthetic events (1–100)")
    recovery_demo.add_argument("--seed", type=int, default=7)
    recovery_demo.add_argument("--site-id", default="synthetic-site")
    recovery_demo.add_argument("--device-id", default="sim-device-001")
    recovery_demo.add_argument("--start-at", type=_parse_datetime)
    recovery_demo.add_argument(
        "--duplicate-every",
        type=int,
        default=0,
        help="redeliver every Nth synthetic event to exercise event-ID deduplication",
    )

    load_demo = commands.add_parser(
        "load-demo",
        help="profile a bounded synthetic batch through the in-process outbox and receiver",
    )
    load_demo.add_argument(
        "--count",
        type=int,
        default=100,
        help=f"unique synthetic events (1–{MAX_SYNTHETIC_LOAD_EVENTS})",
    )
    load_demo.add_argument("--seed", type=int, default=7)
    load_demo.add_argument("--site-id", default="synthetic-site")
    load_demo.add_argument("--device-id", default="sim-device-001")
    load_demo.add_argument("--start-at", type=_parse_datetime)
    load_demo.add_argument("--interval-ms", type=int, default=1_000)
    load_demo.add_argument(
        "--duplicate-every",
        type=int,
        default=0,
        help="redeliver every Nth synthetic event to exercise idempotency",
    )

    dashboard = commands.add_parser(
        "dashboard",
        help="serve a read-only, synthetic-only operations dashboard",
    )
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8000)
    dashboard.add_argument("--refresh-interval-seconds", type=float, default=2.0)
    dashboard.add_argument(
        "--duplicate-every",
        type=int,
        default=4,
        help="redeliver every Nth synthetic event to demonstrate deduplication; 0 disables",
    )

    replay = commands.add_parser(
        "replay",
        help="validate and idempotently store a synthetic NDJSON fixture",
    )
    replay.add_argument("input", type=Path, help="path to a synthetic NDJSON event fixture")

    validate_profile = commands.add_parser(
        "validate-profile",
        help="check a local TOML integration-discovery profile; never enables connectivity",
    )
    validate_profile.add_argument(
        "profile",
        type=Path,
        help="path to a local integration-discovery TOML profile",
    )

    validate_mapping = commands.add_parser(
        "validate-mapping",
        help="check a local TOML field-mapping worksheet; never activates mappings",
    )
    validate_mapping.add_argument(
        "worksheet",
        type=Path,
        help="path to a local source-to-canonical-to-destination worksheet",
    )

    map_synthetic = commands.add_parser(
        "map-synthetic",
        help="dry-run synthetic NDJSON through a synthetic-only mapping; no storage or receiver",
    )
    map_synthetic.add_argument("input", type=Path, help="path to a synthetic NDJSON fixture")
    map_synthetic.add_argument(
        "--mapping",
        required=True,
        type=Path,
        help="path to a synthetic-only TOML mapping set",
    )
    return parser


def _write_demo_summary(summary: DemoSummary) -> None:
    print(json.dumps(asdict(summary), sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "acceptance-demo":
        if not MIN_SYNTHETIC_ACCEPTANCE_EVENTS <= args.count <= MAX_SYNTHETIC_ACCEPTANCE_EVENTS:
            parser.error("synthetic_acceptance_event_limit_exceeded")
        try:
            config = _acceptance_config_from_args(args)
        except ValueError as error:
            parser.error(f"invalid synthetic acceptance options ({type(error).__name__})")
        try:
            summary = asyncio.run(run_synthetic_acceptance_demo(config))
        except SyntheticAcceptanceDemoError as error:
            parser.error(f"synthetic acceptance demo stopped ({error.code})")
        except Exception as error:
            parser.error(f"synthetic acceptance demo failed ({type(error).__name__})")
        print(json.dumps(asdict(summary), sort_keys=True))
        return 0 if summary.status == "passed" else 1

    if args.command == "dashboard":
        if not 1 <= args.port <= 65_535:
            parser.error("--port must be between 1 and 65535")
        try:
            runtime = SyntheticOperationsDashboard(
                refresh_interval_seconds=args.refresh_interval_seconds,
                duplicate_every=args.duplicate_every,
            )
        except ValueError as error:
            parser.error(str(error))
        try:
            uvicorn.run(
                create_dashboard_app(runtime),
                host=args.host,
                port=args.port,
                access_log=False,
                log_level="info",
            )
        except Exception as error:
            parser.error(f"dashboard failed ({type(error).__name__})")
        return 0

    if args.command == "recovery-demo":
        try:
            config = _recovery_config_from_args(args)
        except ValueError as error:
            parser.error(f"invalid recovery demo options ({type(error).__name__})")
        try:
            summary = asyncio.run(run_synthetic_recovery_demo(config))
        except SyntheticRecoveryDemoError as error:
            parser.error(f"synthetic recovery demo stopped ({error.code})")
        except Exception as error:
            parser.error(f"synthetic recovery demo failed ({type(error).__name__})")
        print(json.dumps(asdict(summary), sort_keys=True))
        return 0

    if args.command == "load-demo":
        if not 1 <= args.count <= MAX_SYNTHETIC_LOAD_EVENTS:
            parser.error("synthetic_load_event_limit_exceeded")
        try:
            config = _load_demo_config_from_args(args)
        except ValueError as error:
            parser.error(f"invalid synthetic load options ({type(error).__name__})")
        try:
            summary = asyncio.run(run_synthetic_load_demo(config))
        except Exception as error:
            parser.error(f"synthetic load demo failed ({type(error).__name__})")
        print(json.dumps(asdict(summary), sort_keys=True))
        return 0

    if args.command in {"simulate", "demo"}:
        try:
            config = _simulator_config_from_args(args)
        except ValueError as error:
            parser.error(str(error))
        if args.command == "simulate":
            asyncio.run(_write_synthetic_events(config))
            return 0
        try:
            summary = asyncio.run(run_synthetic_demo(config))
        except Exception as error:
            parser.error(f"synthetic demo failed ({type(error).__name__})")
        _write_demo_summary(summary)
        return 0

    if args.command == "validate-profile":
        report = validate_profile_file(args.profile)
        print(json.dumps(report.to_dict(), sort_keys=True))
        return report.exit_code

    if args.command == "validate-mapping":
        report = validate_mapping_worksheet_file(args.worksheet)
        print(json.dumps(report.to_dict(), sort_keys=True))
        return report.exit_code

    if args.command == "map-synthetic":
        try:
            events = load_synthetic_events(args.input)
        except ReplayInputError as error:
            parser.error(str(error))
        try:
            mapping_set = load_synthetic_mapping(args.mapping)
        except SyntheticMappingConfigError as error:
            parser.error(f"synthetic mapping config rejected ({error.code})")
        try:
            mapped_events = map_synthetic_events(events, mapping_set)
        except SyntheticMappingBatchError as error:
            parser.error(f"synthetic mapping stopped ({error.code})")
        for mapped_event in mapped_events:
            print(mapped_event.model_dump_json())
        return 0

    if args.command == "replay":
        try:
            events = load_synthetic_events(args.input)
        except ReplayInputError as error:
            parser.error(str(error))
        try:
            summary = asyncio.run(_persist_replay(events))
        except Exception as error:
            parser.error(
                "replay failed; verify MEDIHUB_DATABASE_URL and run `alembic upgrade head` "
                f"({type(error).__name__})"
            )
        print(
            json.dumps(
                {
                    "events_read": summary.events_read,
                    "events_inserted": summary.events_inserted,
                    "duplicate_events": summary.duplicate_events,
                },
                sort_keys=True,
            )
        )
        return 0

    parser.error("unsupported command")
    return 2

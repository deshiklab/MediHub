"""Command-line entry points for synthetic simulation and local replay workflows."""

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from medihub.adapters.devices.simulator import SyntheticDeviceAdapter, SyntheticDeviceConfig
from medihub.application.demo import DemoSummary, run_synthetic_demo
from medihub.application.replay import (
    ReplayInputError,
    ReplaySummary,
    load_synthetic_events,
    replay_synthetic_events,
)
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

    replay = commands.add_parser(
        "replay",
        help="validate and idempotently store a synthetic NDJSON fixture",
    )
    replay.add_argument("input", type=Path, help="path to a synthetic NDJSON event fixture")
    return parser


def _write_demo_summary(summary: DemoSummary) -> None:
    print(json.dumps(asdict(summary), sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
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

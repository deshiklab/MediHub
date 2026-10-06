import json
import subprocess
import sys
from pathlib import Path


def run_demo(repository_root: Path, *arguments: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "medihub", "demo", *arguments],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_demo_runs_synthetic_events_through_persisted_outbox_to_test_receiver() -> None:
    repository_root = Path(__file__).resolve().parents[2]

    summary = run_demo(
        repository_root,
        "--count",
        "4",
        "--seed",
        "13",
        "--start-at",
        "2026-10-07T08:00:00Z",
        "--duplicate-every",
        "2",
    )

    assert summary == {
        "acknowledged_deliveries": 4,
        "blocked_routes": 0,
        "delivery_attempts": 4,
        "duplicate_events": 2,
        "events_inserted": 4,
        "events_read": 6,
        "permanent_failures": 0,
        "source_health": "healthy",
        "source_health_code": "synthetic_source_ready",
        "unique_test_receipts": 4,
    }


def test_demo_reports_unsupported_firmware_without_emitting_events() -> None:
    repository_root = Path(__file__).resolve().parents[2]

    summary = run_demo(repository_root, "--count", "3", "--firmware-version", "9.9-test")

    assert summary["events_read"] == 0
    assert summary["events_inserted"] == 0
    assert summary["delivery_attempts"] == 0
    assert summary["source_health"] == "degraded"
    assert summary["source_health_code"] == "unsupported_firmware"

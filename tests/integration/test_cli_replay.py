import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_simulate_then_replay_cli_is_idempotent(tmp_path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    fixture_path = tmp_path / "synthetic-events.ndjson"
    database_path = tmp_path / "replay-test.db"
    env = os.environ.copy()
    env["MEDIHUB_DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    generated = subprocess.run(
        [
            sys.executable,
            "-m",
            "medihub",
            "simulate",
            "--count",
            "3",
            "--seed",
            "19",
            "--start-at",
            "2026-10-07T08:00:00Z",
            "--duplicate-every",
            "2",
            "--reverse-adjacent-pairs",
            "--clock-drift-ms-per-sample",
            "10",
            "--disconnect-after",
            "2",
            "--disconnect-for",
            "1",
        ],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    fixture_path.write_text(generated.stdout, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=repository_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    command = [sys.executable, "-m", "medihub", "replay", str(fixture_path)]
    first_replay = subprocess.run(
        command,
        cwd=repository_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    second_replay = subprocess.run(
        command,
        cwd=repository_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(first_replay.stdout) == {
        "duplicate_events": 1,
        "events_inserted": 2,
        "events_read": 3,
    }
    assert json.loads(second_replay.stdout) == {
        "duplicate_events": 3,
        "events_inserted": 0,
        "events_read": 3,
    }
    with sqlite3.connect(database_path) as connection:
        event_count = connection.execute("SELECT COUNT(*) FROM event_store").fetchone()[0]
        outbox_count = connection.execute("SELECT COUNT(*) FROM delivery_outbox").fetchone()[0]
    assert event_count == 2
    assert outbox_count == 0

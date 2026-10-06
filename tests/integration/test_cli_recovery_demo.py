import json

import pytest

from medihub.cli import main


def test_recovery_demo_cli_reports_aggregate_synthetic_results(capsys, monkeypatch) -> None:
    monkeypatch.setenv("MEDIHUB_DATABASE_URL", "not-a-database-url")
    exit_code = main(
        [
            "recovery-demo",
            "--count",
            "2",
            "--duplicate-every",
            "2",
            "--start-at",
            "2026-10-07T08:00:00Z",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result == {
        "acknowledged_deliveries": 2,
        "delivery_attempts": 4,
        "duplicate_events": 1,
        "events_inserted": 2,
        "events_read": 3,
        "expired_leases_recovered": 1,
        "pending_deliveries": 0,
        "retryable_failures": 2,
        "simulated_process_restarts": 1,
        "unique_test_receipts": 2,
    }
    assert "patient" not in str(result).lower()
    assert "event_id" not in result


def test_recovery_demo_cli_rejects_counts_above_the_local_safety_limit(capsys) -> None:
    with pytest.raises(SystemExit) as error:
        main(["recovery-demo", "--count", "101"])

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert captured.out == ""
    assert "recovery_demo_event_limit_exceeded" in captured.err

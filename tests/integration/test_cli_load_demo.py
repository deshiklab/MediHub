import json

import pytest

from medihub.cli import main


def test_load_demo_reports_bounded_synthetic_pipeline_metrics(capsys, monkeypatch) -> None:
    monkeypatch.setenv("MEDIHUB_DATABASE_URL", "not-a-database-url")
    exit_code = main(
        [
            "load-demo",
            "--count",
            "10",
            "--seed",
            "17",
            "--start-at",
            "2026-10-07T08:00:00Z",
            "--interval-ms",
            "5",
            "--duplicate-every",
            "3",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["events_requested"] == 10
    assert summary["events_read"] == 13
    assert summary["events_inserted"] == 10
    assert summary["duplicate_events"] == 3
    assert summary["blocked_routes"] == 0
    assert summary["delivery_attempts"] == 10
    assert summary["acknowledged_deliveries"] == 10
    assert summary["rejected_deliveries"] == 0
    assert summary["retryable_failures"] == 0
    assert summary["permanent_failures"] == 0
    assert summary["unique_test_receipts"] == 10
    assert summary["source_health"] == "healthy"
    assert summary["data_mode"] == "synthetic_only"
    assert summary["storage"] == "in_memory_sqlite"
    assert summary["transport"] == "in_process"
    assert summary["network_enabled"] is False
    assert summary["production_benchmark"] is False
    assert summary["duration_ms"] > 0
    assert summary["events_per_second"] > 0
    assert summary["acknowledgements_per_second"] > 0
    assert summary["acknowledgement_latency_ms_p95"] >= (summary["acknowledgement_latency_ms_p50"])
    assert "patient" not in str(summary).lower()
    assert "payload" not in str(summary).lower()
    assert "event_id" not in summary


def test_load_demo_rejects_zero_or_oversized_counts(capsys) -> None:
    with pytest.raises(SystemExit) as error:
        main(["load-demo", "--count", "1001"])

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert captured.out == ""
    assert "synthetic_load_event_limit_exceeded" in captured.err

    with pytest.raises(SystemExit) as error:
        main(["load-demo", "--count", "0"])

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert captured.out == ""
    assert "synthetic_load_event_limit_exceeded" in captured.err

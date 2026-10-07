import json

import pytest

from medihub.cli import main


def test_acceptance_demo_runs_all_synthetic_stages_and_emits_only_aggregate_results(
    capsys, monkeypatch
) -> None:
    monkeypatch.setenv("MEDIHUB_DATABASE_URL", "not-a-database-url")

    exit_code = main(
        [
            "acceptance-demo",
            "--count",
            "3",
            "--seed",
            "13",
            "--start-at",
            "2026-10-07T08:00:00Z",
            "--duplicate-every",
            "2",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["status"] == "passed"
    assert summary["events_requested"] == 3
    assert summary["duplicate_events_expected"] == 1
    assert summary["pipeline"]["events_read"] == 4
    assert summary["pipeline"]["events_inserted"] == 3
    assert summary["pipeline"]["duplicate_events"] == 1
    assert summary["pipeline"]["acknowledged_deliveries"] == 3
    assert summary["mapping"]["mapped_events"] == 3
    assert summary["mapping"]["unmapped_events"] == 0
    assert summary["mapping"]["synthetic_only"] is True
    assert summary["mapping"]["partial_output"] is False
    assert summary["fault_drill"]["delivery_attempts"] == 3
    assert summary["fault_drill"]["retryable_failures"] == 1
    assert summary["fault_drill"]["terminal_rejections"] == 1
    assert summary["fault_drill"]["manual_replays"] == 1
    assert summary["fault_drill"]["final_acknowledged_deliveries"] == 1
    assert summary["fault_drill"]["routing_policy_holds"] == 1
    assert summary["restart_recovery"]["simulated_process_restarts"] == 1
    assert summary["restart_recovery"]["expired_leases_recovered"] == 1
    assert summary["restart_recovery"]["pending_deliveries"] == 0
    assert summary["bounded_load"]["events_requested"] == 3
    assert summary["bounded_load"]["acknowledged_deliveries"] == 3
    assert summary["bounded_load"]["production_benchmark"] is False
    assert summary["network_enabled"] is False
    assert summary["facility_qualification"] == "not_performed"
    assert all(check["passed"] for check in summary["checks"])
    assert "patient" not in json.dumps(summary).lower()
    assert "event_id" not in json.dumps(summary).lower()


def test_acceptance_demo_rejects_counts_outside_its_bounded_range(capsys) -> None:
    for count in (1, 101):
        with pytest.raises(SystemExit) as error:
            main(["acceptance-demo", "--count", str(count)])

        captured = capsys.readouterr()
        assert error.value.code == 2
        assert captured.out == ""
        assert "synthetic_acceptance_event_limit_exceeded" in captured.err

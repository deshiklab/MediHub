"""Decision-table tests for the local-only receiver contract acceptance harness."""

import json
from pathlib import Path

from medihub.application.contract_acceptance import run_contract_acceptance
from medihub.application.receiver_contract import load_receiver_contract_file
from medihub.cli import main

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPLETE_CONTRACT_PATH = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "receiver-contract.synthetic-complete.toml"
)
EXAMPLE_CONTRACT_PATH = REPOSITORY_ROOT / "config" / "receiver-contract.example.toml"
EXPECTED_SCENARIOS = (
    "application_ack",
    "duplicate_delivery",
    "lost_ack_retry",
    "receiver_restart",
    "permanent_rejection",
    "transport_timeout",
    "idempotency_retention_horizon",
    "interface_version_drift",
)


def test_complete_contract_passes_all_offline_acceptance_scenarios() -> None:
    result = load_receiver_contract_file(COMPLETE_CONTRACT_PATH)

    summary = run_contract_acceptance(result)
    serialized = json.dumps(summary.to_dict(), sort_keys=True)

    assert summary.status == "passed"
    assert summary.exit_code == 0
    assert tuple(check.check_id for check in summary.checks) == EXPECTED_SCENARIOS
    assert all(check.passed for check in summary.checks)
    assert summary.blockers == ()
    assert summary.network_enabled is False
    assert summary.connectivity_enabled is False
    assert summary.real_receiver_tested is False
    assert summary.test_target == "local_synthetic_contract_model"
    assert "In-process synthetic test receiver" not in serialized
    assert "synthetic-contract-test-event-001" not in serialized
    assert "event_id" not in serialized


def test_bounded_retention_requires_a_redelivery_horizon(tmp_path: Path) -> None:
    contract_path = tmp_path / "bounded-retention.toml"
    contract_path.write_text(
        COMPLETE_CONTRACT_PATH.read_text(encoding="utf-8").replace(
            'retention = "indefinite"',
            'retention = "bounded"\nretention_seconds = 3600',
        ),
        encoding="utf-8",
    )
    result = load_receiver_contract_file(contract_path)

    summary = run_contract_acceptance(result)

    assert summary.status == "blocked"
    assert summary.exit_code == 2
    assert summary.checks == ()
    assert summary.blockers == ("required_idempotency_horizon_missing",)
    assert summary.connectivity_enabled is False


def test_bounded_retention_must_exceed_the_required_redelivery_horizon(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "short-retention.toml"
    contract_path.write_text(
        COMPLETE_CONTRACT_PATH.read_text(encoding="utf-8").replace(
            'retention = "indefinite"',
            'retention = "bounded"\nretention_seconds = 3600',
        ),
        encoding="utf-8",
    )
    result = load_receiver_contract_file(contract_path)

    summary = run_contract_acceptance(
        result,
        required_idempotency_horizon_seconds=3600,
    )
    retention_check = next(
        check for check in summary.checks if check.check_id == "idempotency_retention_horizon"
    )

    assert summary.status == "failed"
    assert summary.exit_code == 1
    assert not retention_check.passed
    assert retention_check.result_code == "idempotency_retention_below_required_horizon"
    assert summary.network_enabled is False


def test_bounded_retention_longer_than_the_horizon_passes(tmp_path: Path) -> None:
    contract_path = tmp_path / "sufficient-retention.toml"
    contract_path.write_text(
        COMPLETE_CONTRACT_PATH.read_text(encoding="utf-8").replace(
            'retention = "indefinite"',
            'retention = "bounded"\nretention_seconds = 7201',
        ),
        encoding="utf-8",
    )
    result = load_receiver_contract_file(contract_path)

    summary = run_contract_acceptance(
        result,
        required_idempotency_horizon_seconds=7200,
    )

    assert summary.status == "passed"
    assert all(check.passed for check in summary.checks)


def test_invalid_redelivery_horizon_is_blocked() -> None:
    result = load_receiver_contract_file(COMPLETE_CONTRACT_PATH)

    summary = run_contract_acceptance(result, required_idempotency_horizon_seconds=0)

    assert summary.status == "blocked"
    assert summary.checks == ()
    assert summary.blockers == ("required_idempotency_horizon_invalid",)


def test_incomplete_contract_is_blocked_without_running_scenarios() -> None:
    result = load_receiver_contract_file(EXAMPLE_CONTRACT_PATH)

    summary = run_contract_acceptance(result)

    assert summary.status == "blocked"
    assert summary.checks == ()
    assert "receiver_acknowledgement_level_unknown" in summary.blockers
    assert summary.network_enabled is False
    assert summary.real_receiver_tested is False


def test_cli_runs_offline_harness_and_reports_no_real_receiver_test(capsys) -> None:
    exit_code = main(["contract-test", str(COMPLETE_CONTRACT_PATH)])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 0
    assert report["status"] == "passed"
    assert report["passed_checks"] == len(EXPECTED_SCENARIOS)
    assert report["network_enabled"] is False
    assert report["connectivity_enabled"] is False
    assert report["real_receiver_tested"] is False
    assert report["test_target"] == "local_synthetic_contract_model"
    assert str(COMPLETE_CONTRACT_PATH) not in output
    assert "In-process synthetic test receiver" not in output


def test_cli_blocks_bounded_retention_without_declared_policy_horizon(
    capsys, tmp_path: Path
) -> None:
    contract_path = tmp_path / "bounded-retention.toml"
    contract_path.write_text(
        COMPLETE_CONTRACT_PATH.read_text(encoding="utf-8").replace(
            'retention = "indefinite"',
            'retention = "bounded"\nretention_seconds = 3600',
        ),
        encoding="utf-8",
    )

    exit_code = main(["contract-test", str(contract_path)])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 2
    assert report["status"] == "blocked"
    assert report["blockers"] == ["required_idempotency_horizon_missing"]
    assert report["checks"] == []
    assert report["connectivity_enabled"] is False

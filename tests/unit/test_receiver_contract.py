"""Local-only receiver contract schema, readiness, and privacy-safe CLI checks."""

import json
from pathlib import Path

from medihub.application.receiver_contract import (
    MAX_RECEIVER_CONTRACT_SIZE_BYTES,
    validate_receiver_contract_file,
)
from medihub.cli import main

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONTRACT = REPOSITORY_ROOT / "config" / "receiver-contract.example.toml"

COMPLETE_CONTRACT = """\
schema_version = "1.0"
contract_id = "synthetic-receiver-contract"
discovery_profile_id = "synthetic-contract-check"
receiver_name = "In-process synthetic test receiver"
protocol = "fhir_r4"
interface_version = "FHIR R4 synthetic fixture v1"

[contract_evidence]
status = "approved"
reference = "SYNTH-RECEIVER-CONTRACT-001"

[acknowledgement]
level = "application"
meaning = "durably_stored"
success_codes = ["http_201"]

[idempotency]
key_kind = "fhir_identifier"
key_location = "observation_identifier"
duplicate_outcome = "same_acknowledgement"
retention = "indefinite"
survives_receiver_restart = true

[failure_handling]
retryable_codes = ["http_429", "http_503", "transport_timeout"]
permanent_codes = ["http_400", "http_422"]
retry_hint_behavior = "not_supported"

[limits]
request_timeout_seconds = 10.0

[limits.requests_per_minute]
status = "specified"
value = 60

[limits.events_per_request]
status = "specified"
value = 1

[limits.request_bytes]
status = "specified"
value = 1048576
"""


def test_example_contract_is_valid_but_reports_unresolved_receiver_facts() -> None:
    report = validate_receiver_contract_file(EXAMPLE_CONTRACT)

    assert report.schema_valid is True
    assert report.readiness == "not_ready"
    assert report.exit_code == 1
    assert report.connectivity_enabled is False
    assert report.errors == ()
    assert "receiver_identity_missing" in report.blockers
    assert "receiver_contract_evidence_not_approved" in report.blockers
    assert "receiver_acknowledgement_level_unknown" in report.blockers
    assert "receiver_idempotency_key_unknown" in report.blockers
    assert "receiver_restart_idempotency_unverified" in report.blockers
    assert "receiver_request_timeout_missing" in report.blockers
    assert "receiver_rate_limit_unknown" in report.blockers


def test_complete_contract_is_documented_but_never_enables_connectivity(tmp_path: Path) -> None:
    contract_path = tmp_path / "complete-local-contract.toml"
    contract_path.write_text(COMPLETE_CONTRACT, encoding="utf-8")

    report = validate_receiver_contract_file(contract_path)

    assert report.to_dict() == {
        "schema_valid": True,
        "readiness": "contract_documented",
        "blockers": [],
        "errors": [],
        "connectivity_enabled": False,
    }
    assert report.exit_code == 0


def test_complete_hl7_contract_uses_protocol_specific_ack_and_idempotency_fields(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "complete-hl7-contract.toml"
    hl7_contract = (
        COMPLETE_CONTRACT.replace('protocol = "fhir_r4"', 'protocol = "hl7_v2"')
        .replace('success_codes = ["http_201"]', 'success_codes = ["msa_aa"]')
        .replace('key_kind = "fhir_identifier"', 'key_kind = "hl7_msh10"')
        .replace('key_location = "observation_identifier"', 'key_location = "msh_10"')
        .replace(
            'retryable_codes = ["http_429", "http_503", "transport_timeout"]',
            'retryable_codes = ["msa_ae", "transport_timeout"]',
        )
        .replace(
            'permanent_codes = ["http_400", "http_422"]',
            'permanent_codes = ["msa_ar"]',
        )
    )
    contract_path.write_text(hl7_contract, encoding="utf-8")

    report = validate_receiver_contract_file(contract_path)

    assert report.schema_valid is True
    assert report.readiness == "contract_documented"
    assert report.blockers == ()
    assert report.connectivity_enabled is False


def test_contract_documents_idempotency_blockers_without_promoting_them_to_ready(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "unsafe-receiver.toml"
    contract_path.write_text(
        COMPLETE_CONTRACT.replace(
            'duplicate_outcome = "same_acknowledgement"',
            'duplicate_outcome = "creates_duplicate"',
        ).replace("survives_receiver_restart = true", "survives_receiver_restart = false"),
        encoding="utf-8",
    )

    report = validate_receiver_contract_file(contract_path)

    assert report.schema_valid is True
    assert report.readiness == "not_ready"
    assert "receiver_duplicate_outcome_unsafe" in report.blockers
    assert "receiver_idempotency_not_restart_durable" in report.blockers
    assert report.connectivity_enabled is False


def test_conflict_duplicate_outcome_requires_review(tmp_path: Path) -> None:
    contract_path = tmp_path / "conflicting-duplicate-outcome.toml"
    contract_path.write_text(
        COMPLETE_CONTRACT.replace(
            'duplicate_outcome = "same_acknowledgement"', 'duplicate_outcome = "conflict"'
        ),
        encoding="utf-8",
    )

    report = validate_receiver_contract_file(contract_path)

    assert report.schema_valid is True
    assert report.readiness == "not_ready"
    assert "receiver_duplicate_conflict_semantics_need_review" in report.blockers


def test_transport_ack_is_not_treated_as_application_acceptance(tmp_path: Path) -> None:
    contract_path = tmp_path / "transport-ack-only.toml"
    contract_path.write_text(
        COMPLETE_CONTRACT.replace('level = "application"', 'level = "transport_only"'),
        encoding="utf-8",
    )

    report = validate_receiver_contract_file(contract_path)

    assert report.schema_valid is True
    assert report.readiness == "not_ready"
    assert "receiver_acknowledgement_not_application_level" in report.blockers
    assert report.connectivity_enabled is False


def test_protocol_mismatched_response_code_is_rejected_without_echoing_values(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "mismatched-protocol.toml"
    contract_path.write_text(
        COMPLETE_CONTRACT.replace('protocol = "fhir_r4"', 'protocol = "hl7_v2"')
        .replace('key_kind = "fhir_identifier"', 'key_kind = "hl7_msh10"')
        .replace('key_location = "observation_identifier"', 'key_location = "msh_10"'),
        encoding="utf-8",
    )

    report = validate_receiver_contract_file(contract_path)
    serialized = json.dumps(report.to_dict(), sort_keys=True)

    assert report.schema_valid is False
    assert report.readiness == "invalid_contract"
    assert report.exit_code == 2
    assert report.errors == ({"field": "contract", "code": "value_error"},)
    assert "http_201" not in serialized
    assert "hl7_v2" not in serialized
    assert report.connectivity_enabled is False


def test_unknown_fields_and_sensitive_values_are_not_echoed(tmp_path: Path) -> None:
    secret = "do-not-print-this-token"
    contract_path = tmp_path / "unknown-contract-field.toml"
    contract_path.write_text(f'api_token = "{secret}"\n' + COMPLETE_CONTRACT, encoding="utf-8")

    report = validate_receiver_contract_file(contract_path)
    serialized = json.dumps(report.to_dict(), sort_keys=True)

    assert report.schema_valid is False
    assert report.readiness == "invalid_contract"
    assert {"field": "contract", "code": "extra_forbidden"} in report.errors
    assert secret not in serialized
    assert "api_token" not in serialized
    assert str(contract_path) not in serialized
    assert report.connectivity_enabled is False


def test_cli_prints_only_safe_blocker_codes(tmp_path: Path, capsys) -> None:
    contract_path = tmp_path / "local-contract.toml"
    contract_path.write_text(EXAMPLE_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")

    exit_code = main(["validate-contract", str(contract_path)])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 1
    assert report["schema_valid"] is True
    assert report["readiness"] == "not_ready"
    assert report["connectivity_enabled"] is False
    assert "receiver_acknowledgement_level_unknown" in report["blockers"]
    assert "TBD" not in output
    assert str(contract_path) not in output


def test_malformed_and_missing_contracts_return_safe_errors(tmp_path: Path) -> None:
    malformed_path = tmp_path / "malformed-contract.toml"
    malformed_path.write_text("[acknowledgement\nlevel = 'private-value'", encoding="utf-8")

    malformed_report = validate_receiver_contract_file(malformed_path)
    missing_report = validate_receiver_contract_file(tmp_path / "missing-contract.toml")

    assert malformed_report.to_dict()["errors"] == [{"field": "contract", "code": "invalid_toml"}]
    assert missing_report.to_dict()["errors"] == [
        {"field": "contract", "code": "contract_file_unreadable"}
    ]
    assert "private-value" not in json.dumps(malformed_report.to_dict())


def test_oversized_contract_is_rejected_with_a_safe_error(tmp_path: Path) -> None:
    oversized_path = tmp_path / "oversized-contract.toml"
    oversized_path.write_bytes(b"#" * (MAX_RECEIVER_CONTRACT_SIZE_BYTES + 1))

    report = validate_receiver_contract_file(oversized_path)

    assert report.schema_valid is False
    assert report.to_dict()["errors"] == [{"field": "contract", "code": "contract_file_too_large"}]

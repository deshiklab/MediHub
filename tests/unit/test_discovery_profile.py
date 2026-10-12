import json
from pathlib import Path

from medihub.application.discovery import validate_profile_file
from medihub.cli import main

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PROFILE = REPOSITORY_ROOT / "config" / "integration-profile.example.toml"

COMPLETE_PROFILE = """\
schema_version = "1.0"
profile_id = "synthetic-contract-check"

[use_case]
statement = "Synthetic contract and mapping verification only."

[use_case.approval]
status = "approved"
reference = "SYNTH-USE-001"

[device]
manufacturer = "Synthetic Test Vendor"
model = "Recorded Protocol Fixture"
firmware_versions = ["1.0-test"]
transport = "recorded synthetic fixture"
protocol_version = "test-v1"

[device.vendor_authorization]
status = "not_applicable"
reference = "SYNTH-DEVICE-AUTH-001"

[device.technical_specification]
status = "approved"
reference = "SYNTH-DEVICE-SPEC-001"

[device.test_assets]
status = "not_applicable"
reference = "SYNTH-DEVICE-ASSETS-001"

[destination]
product = "In-process test receiver"
protocol = "FHIR R4 test shape"
interface_version = "R4 test-only"

[destination.contract]
status = "approved"
reference = "SYNTH-DEST-CONTRACT-001"

[destination.protocol_mapping_worksheet]
status = "approved"
reference = "SYNTH-MAPPING-001"

[destination.synthetic_test_receiver]
status = "approved"
reference = "SYNTH-DEST-TEST-001"

[patient_association]
authority = "No patient association is used in this synthetic-only test."

[patient_association.workflow]
status = "not_applicable"
reference = "SYNTH-ASSOCIATION-001"

[patient_association.clinical_owner]
status = "not_applicable"
reference = "SYNTH-CLINICAL-OWNER-001"

[deployment]
facility = "Synthetic validation environment"
country_code = "BD"
hosting_location = "local test process"
cross_border_decision = "local_only"

[deployment.site_owners]
status = "not_applicable"
reference = "SYNTH-OWNERS-001"

[deployment.approved_network_flow]
status = "not_applicable"
reference = "SYNTH-NETWORK-FLOW-001"

[deployment.privacy_legal_review]
status = "not_applicable"
reference = "SYNTH-PRIVACY-001"

[deployment.regulatory_review]
status = "not_applicable"
reference = "SYNTH-REGULATORY-001"

[deployment.synthetic_test_plan]
status = "approved"
reference = "SYNTH-TEST-PLAN-001"
"""


def test_example_profile_is_valid_but_reports_unresolved_discovery_gates() -> None:
    report = validate_profile_file(EXAMPLE_PROFILE)

    assert report.schema_valid is True
    assert report.readiness == "not_ready"
    assert report.exit_code == 1
    assert report.connectivity_enabled is False
    assert report.errors == ()
    assert "device_identity_missing" in report.blockers
    assert "device_test_assets_evidence_incomplete" in report.blockers
    assert "destination_contract_details_missing" in report.blockers
    assert "patient_association_authority_missing" in report.blockers
    assert "protocol_mapping_worksheet_evidence_incomplete" in report.blockers
    assert "approved_network_flow_evidence_incomplete" in report.blockers
    assert "cross_border_decision_missing" in report.blockers


def test_complete_profile_only_marks_discovery_complete_and_never_enables_connectivity(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "complete-local-profile.toml"
    profile_path.write_text(COMPLETE_PROFILE, encoding="utf-8")

    report = validate_profile_file(profile_path)

    assert report.to_dict() == {
        "schema_valid": True,
        "readiness": "discovery_complete",
        "blockers": [],
        "errors": [],
        "connectivity_enabled": False,
    }
    assert report.exit_code == 0


def test_tbd_destination_protocol_is_reported_as_unresolved(tmp_path: Path) -> None:
    profile_path = tmp_path / "unresolved-destination.toml"
    profile_path.write_text(
        COMPLETE_PROFILE.replace(
            'protocol = "FHIR R4 test shape"', 'protocol = "TBD: exact contract"'
        ),
        encoding="utf-8",
    )

    report = validate_profile_file(profile_path)

    assert report.schema_valid is True
    assert "destination_contract_details_missing" in report.blockers
    assert report.connectivity_enabled is False


def test_non_bangladesh_deployment_is_blocked(tmp_path: Path) -> None:
    profile_path = tmp_path / "non-bd-profile.toml"
    profile_path.write_text(
        COMPLETE_PROFILE.replace('country_code = "BD"', 'country_code = "US"'), encoding="utf-8"
    )

    report = validate_profile_file(profile_path)

    assert "bangladesh_deployment_target_missing" in report.blockers
    assert report.connectivity_enabled is False


def test_approved_gate_requires_an_evidence_reference(tmp_path: Path) -> None:
    profile_path = tmp_path / "approval-without-evidence.toml"
    profile_path.write_text(
        EXAMPLE_PROFILE.read_text(encoding="utf-8").replace(
            '[use_case.approval]\nstatus = "open"',
            '[use_case.approval]\nstatus = "approved"',
        ),
        encoding="utf-8",
    )

    report = validate_profile_file(profile_path)

    assert report.schema_valid is False
    assert report.readiness == "invalid_profile"
    assert report.connectivity_enabled is False
    assert report.errors
    assert all("msg" not in error for error in report.errors)


def test_unknown_secret_field_is_rejected_without_echoing_values(tmp_path: Path) -> None:
    secret = "do-not-print-this-token"
    profile_path = tmp_path / "unknown-field.toml"
    profile_path.write_text(f'api_token = "{secret}"\n' + COMPLETE_PROFILE, encoding="utf-8")

    report = validate_profile_file(profile_path)
    serialized = json.dumps(report.to_dict(), sort_keys=True)

    assert report.schema_valid is False
    assert report.readiness == "invalid_profile"
    assert report.exit_code == 2
    assert {"field": "profile", "code": "extra_forbidden"} in report.errors
    assert secret not in serialized
    assert "api_token" not in serialized
    assert report.connectivity_enabled is False


def test_cli_prints_only_safe_blocker_codes(tmp_path: Path, capsys) -> None:
    profile_path = tmp_path / "local-profile.toml"
    profile_path.write_text(EXAMPLE_PROFILE.read_text(encoding="utf-8"), encoding="utf-8")

    exit_code = main(["validate-profile", str(profile_path)])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 1
    assert report["schema_valid"] is True
    assert report["readiness"] == "not_ready"
    assert report["connectivity_enabled"] is False
    assert "device_identity_missing" in report["blockers"]
    assert "TBD" not in output
    assert str(profile_path) not in output


def test_invalid_toml_and_missing_file_return_safe_errors(tmp_path: Path) -> None:
    malformed_path = tmp_path / "malformed.toml"
    malformed_path.write_text("[device\nmodel = 'secret-value'", encoding="utf-8")

    malformed_report = validate_profile_file(malformed_path)
    missing_report = validate_profile_file(tmp_path / "missing.toml")

    assert malformed_report.to_dict()["errors"] == [{"field": "profile", "code": "invalid_toml"}]
    assert missing_report.to_dict()["errors"] == [
        {"field": "profile", "code": "profile_file_unreadable"}
    ]
    assert "secret-value" not in json.dumps(malformed_report.to_dict())

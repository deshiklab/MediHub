import json
import tomllib
from pathlib import Path

from medihub.application.mapping_discovery import (
    MappingWorksheet,
    validate_mapping_worksheet_file,
)
from medihub.cli import main

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_WORKSHEET = REPOSITORY_ROOT / "config" / "device-mapping.example.toml"

COMPLETE_WORKSHEET = """\
schema_version = "1.0"
worksheet_id = "synthetic-mapping-check"
discovery_profile_id = "bd-first-site"
country_code = "BD"
facility = "Synthetic test environment"

[source]
manufacturer = "Synthetic test source"
model = "Recorded fixture"
firmware_versions = ["1.0-test"]
adapter_id = "synthetic-fixture-adapter"
adapter_version = "0.1.0-test"
protocol_version = "synthetic-v1"

[source.vendor_authorization]
status = "not_applicable"
reference = "SYNTH-VENDOR-001"

[source.technical_specification]
status = "approved"
reference = "SYNTH-SPEC-001"

[source.sample_messages]
status = "approved"
reference = "SYNTH-MESSAGES-001"

[destination]
product = "In-process test sink"
protocol = "synthetic-only"
interface_version = "test-v1"

[destination.contract]
status = "approved"
reference = "SYNTH-CONTRACT-001"

[[entries]]
entry_id = "synthetic-scalar-001"
source_element = "synthetic.frame.value"
source_state = "not_applicable"
source_metric_system = "urn:example:synthetic-metrics"
source_metric_code = "scalar-a"
source_unit_system = "urn:example:synthetic-units"
source_unit_code = "one"
canonical_element = "synthetic.measurement"
canonical_state = "not_applicable"
canonical_metric_system = "urn:example:canonical-synthetic"
canonical_metric_code = "scalar-a"
canonical_unit_system = "urn:example:canonical-synthetic-units"
canonical_unit_code = "one"
destination_element = "synthetic-only.receiver.value"
destination_state = "not_applicable"
destination_profile = "synthetic-shape-v1"
destination_code_system = "urn:example:synthetic-metrics"
destination_code = "scalar-a"
destination_unit_system = "urn:example:synthetic-units"
destination_unit_code = "one"
transformation_rule = "identity; no clinical equivalence is asserted"

[entries.approval]
status = "approved"
reference = "SYNTH-MAP-ROW-001"

[worksheet_approval]
status = "approved"
reference = "SYNTH-MAP-REVIEW-001"

[synthetic_test_vectors]
status = "approved"
reference = "SYNTH-MAP-TESTS-001"
"""


def test_example_worksheet_is_valid_but_all_safety_gates_remain_open() -> None:
    report = validate_mapping_worksheet_file(EXAMPLE_WORKSHEET)

    assert report.schema_valid is True
    assert report.readiness == "not_ready"
    assert report.exit_code == 1
    assert report.mapping_activation_enabled is False
    assert "source_device_identity_missing" in report.blockers
    assert "destination_interface_details_missing" in report.blockers
    assert "mapping_source_code_or_unit_missing" in report.blockers
    assert "mapping_source_field_or_state_missing" in report.blockers
    assert "mapping_canonical_field_or_state_missing" in report.blockers
    assert "mapping_destination_field_or_code_missing" in report.blockers
    assert "mapping_entry_approval_evidence_incomplete" in report.blockers


def test_complete_synthetic_worksheet_does_not_activate_runtime_mappings(tmp_path: Path) -> None:
    worksheet_path = tmp_path / "complete-synthetic-mapping.toml"
    worksheet_path.write_text(COMPLETE_WORKSHEET, encoding="utf-8")

    report = validate_mapping_worksheet_file(worksheet_path)

    assert report.to_dict() == {
        "schema_valid": True,
        "readiness": "worksheet_complete",
        "blockers": [],
        "errors": [],
        "mapping_activation_enabled": False,
    }
    assert report.exit_code == 0


def test_duplicate_source_metric_and_unit_signature_is_blocked() -> None:
    parsed = tomllib.loads(COMPLETE_WORKSHEET)
    duplicate = dict(parsed["entries"][0])
    duplicate["entry_id"] = "synthetic-scalar-002"
    parsed["entries"].append(duplicate)

    worksheet = MappingWorksheet.model_validate(parsed)

    assert "duplicate_source_mapping_key" in worksheet.readiness_blockers()


def test_unknown_secret_field_is_rejected_without_echoing_its_name_or_value(
    tmp_path: Path,
) -> None:
    secret = "synthetic-not-a-real-credential"
    worksheet_path = tmp_path / "unknown-key.toml"
    worksheet_path.write_text(
        f'api_token = "{secret}"\n' + COMPLETE_WORKSHEET,
        encoding="utf-8",
    )

    report = validate_mapping_worksheet_file(worksheet_path)
    output = json.dumps(report.to_dict(), sort_keys=True)

    assert report.schema_valid is False
    assert report.exit_code == 2
    assert {"field": "worksheet", "code": "extra_forbidden"} in report.errors
    assert "api_token" not in output
    assert secret not in output
    assert report.mapping_activation_enabled is False


def test_cli_reports_safe_mapping_blockers_only(capsys) -> None:
    exit_code = main(["validate-mapping", str(EXAMPLE_WORKSHEET)])
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 1
    assert report["readiness"] == "not_ready"
    assert report["mapping_activation_enabled"] is False
    assert "mapping_source_code_or_unit_missing" in report["blockers"]
    assert "TBD" not in output
    assert str(EXAMPLE_WORKSHEET) not in output

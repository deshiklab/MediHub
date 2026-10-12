"""Versioned local FHIR fixture checks, freshness, and data minimization."""

import json
from datetime import UTC, datetime

from medihub.adapters.destinations.fhir_r4 import build_synthetic_observation
from medihub.application import destination_synthetic_validation as validation


def test_offline_runner_checks_exact_versioned_fixture_and_returns_safe_codes() -> None:
    ran_at = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
    report = validation.run_offline_fhir_synthetic_validation(
        profile_fingerprint="a" * 64,
        ran_at=ran_at,
    )

    assert report.target_id == "emr_fhir_r4"
    assert report.fixture_version == validation.FHIR_SYNTHETIC_FIXTURE_VERSION
    assert report.status == "local_fixture_passed"
    assert report.ran_at == ran_at
    assert report.scope == "local_fixture_only"
    assert report.network_enabled is False
    assert report.sent is False
    assert report.external_connection_enabled is False
    assert report.target_contract_validated is False
    assert report.target_conformance_claimed is False
    assert report.site_approval_changed is False
    assert [check.check_id for check in report.checks] == [
        "synthetic_event_origin",
        "patient_context_omitted",
        "fixture_output_matches",
        "fhir_r4_model_validation",
        "preliminary_status",
    ]
    assert all(check.status == "passed" for check in report.checks)

    safe_json = json.dumps(report.model_dump(mode="json"), sort_keys=True)
    assert "42.5" not in safe_json
    assert "urn:uuid" not in safe_json
    assert "subject" not in safe_json
    assert "encounter" not in safe_json
    assert "sim-validation-device" not in safe_json


def test_worksheet_fingerprint_controls_stale_status_and_ignores_unpersisted_fields() -> None:
    profile = {
        "target_id": "emr_fhir_r4",
        "receiver_product": "Authorized test receiver",
        "receiver_version": "4.0.1",
        "interface_version_profile": "FHIR R4",
        "controlled_interface_contract_reference": "CONTRACT-001",
    }
    original_fingerprint = validation.destination_profile_fingerprint(profile)
    assert original_fingerprint is not None
    report = validation.run_offline_fhir_synthetic_validation(
        profile_fingerprint=original_fingerprint,
        ran_at=datetime(2026, 10, 12, 7, 0, tzinfo=UTC),
    )

    assert validation.destination_validation_readiness_status(report, profile) == (
        "local_fixture_passed"
    )
    previous_fixture_report = validation.DestinationSyntheticValidationRecord.model_validate(
        {
            **report.model_dump(mode="python"),
            "fixture_version": "medihub-fhir-r4-synthetic-observation-v0",
        }
    )
    assert (
        validation.destination_validation_readiness_status(previous_fixture_report, profile)
        == "stale"
    )
    changed_profile = {**profile, "receiver_version": "4.0.2"}
    assert validation.destination_validation_readiness_status(report, changed_profile) == "stale"
    assert validation.destination_validation_readiness_status(report, None) == "stale"

    with_non_profile_keys = {
        **profile,
        "endpoint": "https://must-not-be-used.example",
        "credential": "must-not-be-persisted",
    }
    assert validation.destination_profile_fingerprint(with_non_profile_keys) == original_fingerprint


def test_runner_marks_fixture_or_model_mismatch_without_exposing_payload(monkeypatch) -> None:
    original_builder = build_synthetic_observation
    monkeypatch.setattr(
        validation,
        "build_synthetic_observation",
        lambda event: original_builder(event).model_copy(update={"status": "final"}),
    )

    report = validation.run_offline_fhir_synthetic_validation(profile_fingerprint=None)

    assert report.status == "local_fixture_failed"
    checks = {check.check_id: check for check in report.checks}
    assert checks["fixture_output_matches"].status == "failed"
    assert checks["fhir_r4_model_validation"].status == "failed"
    safe_json = json.dumps(report.model_dump(mode="json"), sort_keys=True)
    assert "42.5" not in safe_json
    assert "final" not in safe_json

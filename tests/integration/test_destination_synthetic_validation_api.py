"""Offline synthetic destination validation remains disconnected and non-conformant."""

import asyncio

from httpx import ASGITransport, AsyncClient

from medihub.application.operations import SyntheticOperationsDashboard
from medihub.dashboard import create_dashboard_app


def test_fhir_offline_validation_keeps_target_and_hl7_gates_unapproved() -> None:
    app = create_dashboard_app(
        SyntheticOperationsDashboard(refresh_interval_seconds=60, duplicate_every=0)
    )

    async def exercise() -> None:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                before = (await client.get("/api/management/destinations")).json()
                fhir_before = next(
                    target
                    for target in before["api_targets"]
                    if target["target_id"] == "emr_fhir_r4"
                )
                assert (
                    next(
                        check["status"]
                        for check in fhir_before["checks"]
                        if check["id"] == "synthetic_validation"
                    )
                    == "not_run"
                )

                response = await client.post(
                    "/api/management/destinations/fhir-synthetic-validation"
                )
                assert response.status_code == 200
                report = response.json()
                assert report["mode"] == "synthetic_only"
                assert report["target_id"] == "emr_fhir_r4"
                assert report["status"] == "local_fixture_passed"
                assert report["fixture_version"] == "medihub-fhir-r4-synthetic-observation-v1"
                assert report["scope"] == "local_fixture_only"
                assert report["persistent"] is False
                assert report["network_enabled"] is False
                assert report["sent"] is False
                assert report["external_connection_enabled"] is False
                assert report["target_contract_validated"] is False
                assert report["target_conformance_claimed"] is False
                assert report["site_approval_changed"] is False
                assert len(report["checks"]) == 5
                assert all(check["status"] == "passed" for check in report["checks"])
                assert "42.5" not in response.text
                assert "subject" not in response.text
                assert "encounter" not in response.text
                assert "endpoint" not in response.text
                assert "credential" not in response.text

                after = (await client.get("/api/management/destinations")).json()
                assert after["external_connections_enabled"] is False
                assert after["target_conformance_claimed"] is False
                fhir_after = next(
                    target
                    for target in after["api_targets"]
                    if target["target_id"] == "emr_fhir_r4"
                )
                fhir_checks = {check["id"]: check["status"] for check in fhir_after["checks"]}
                assert fhir_checks["synthetic_validation"] == "local_fixture_passed"
                assert fhir_checks["site_approval"] == "not_approved"
                assert fhir_after["status"] == "contract_required"
                assert fhir_after["synthetic_validation_scope"] == "local_fixture_only"
                assert (
                    fhir_after["synthetic_validation_report"]["target_conformance_claimed"] is False
                )

                hl7_after = next(
                    target
                    for target in after["api_targets"]
                    if target["target_id"] == "facility_hl7_v2"
                )
                assert hl7_after["status"] == "contract_required"
                hl7_validation = next(
                    check for check in hl7_after["checks"] if check["id"] == "synthetic_validation"
                )
                assert hl7_validation["status"] == "not_run"
                assert hl7_validation["scope"] == "blocked_pending_exact_receiver_contract"
                assert hl7_after["external_connection_enabled"] is False
                assert hl7_after["activation_enabled"] is False

                assert (
                    await client.post("/api/management/destinations/hl7-synthetic-validation")
                ).status_code == 404

                unconfirmed_hl7_profile = await client.post(
                    "/api/management/destination-profiles",
                    json={
                        "target_id": "facility_hl7_v2",
                        "receiver_product": "Unconfirmed receiver draft",
                        "receiver_version": "2.5.1",
                        "interface_version_profile": "HL7 v2.5.1 ORU R01",
                        "controlled_interface_contract_reference": "DRAFT-CONTRACT-1",
                        "resource_message_profile_reference": "DRAFT-ORU-1",
                        "patient_association_policy_reference": "DRAFT-PATIENT-1",
                        "results_only_technician_review_confirmed": True,
                        "results_only_review_reference": "DRAFT-REVIEW-1",
                        "acknowledgement_idempotency_retry_reference": "DRAFT-ACK-1",
                        "security_transport_authorization_reference": "DRAFT-SECURITY-1",
                        "vendor_authorization_status": "approved",
                        "vendor_authorization_reference": "DRAFT-VENDOR-1",
                        "facility_authorization_status": "approved",
                        "facility_authorization_reference": "DRAFT-FACILITY-1",
                        "authorized_synthetic_sandbox_reference": "DRAFT-SANDBOX-1",
                    },
                )
                assert unconfirmed_hl7_profile.status_code == 201
                readiness_with_hl7_notes = (await client.get("/api/management/destinations")).json()
                hl7_with_notes = next(
                    target
                    for target in readiness_with_hl7_notes["api_targets"]
                    if target["target_id"] == "facility_hl7_v2"
                )
                assert hl7_with_notes["status"] == "contract_required"
                assert (
                    next(
                        check["status"]
                        for check in hl7_with_notes["checks"]
                        if check["id"] == "synthetic_validation"
                    )
                    == "not_run"
                )

    asyncio.run(exercise())

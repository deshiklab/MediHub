"""Durability and safety for non-secret EMR/EMS worksheets."""

import asyncio

from httpx import ASGITransport, AsyncClient

from medihub.application.operations import SyntheticOperationsDashboard
from medihub.dashboard import create_dashboard_app


def test_destination_api_worksheets_survive_dashboard_restart(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'profile-store.db').as_posix()}"
    draft = {
        "target_id": "emr_fhir_r4",
        "receiver_product": "Authorized Test Receiver",
        "receiver_version": "4.0.1",
        "interface_version_profile": "FHIR R4",
        "controlled_interface_contract_reference": "CONTRACT-001",
        "resource_message_profile_reference": "OBS-PROFILE-001",
        "patient_association_policy_reference": "ASSOCIATION-001",
        "results_only_technician_review_confirmed": True,
        "results_only_review_reference": "REVIEW-001",
        "acknowledgement_idempotency_retry_reference": "ACK-001",
        "security_transport_authorization_reference": "SECURITY-001",
        "vendor_authorization_status": "approved",
        "vendor_authorization_reference": "VENDOR-001",
        "facility_authorization_status": "approved",
        "facility_authorization_reference": "FACILITY-001",
        "authorized_synthetic_sandbox_reference": "SANDBOX-001",
    }

    async def exercise() -> None:
        first_app = create_dashboard_app(
            SyntheticOperationsDashboard(refresh_interval_seconds=60, duplicate_every=0),
            destination_api_profile_database_url=database_url,
        )
        async with first_app.router.lifespan_context(first_app):
            async with AsyncClient(
                transport=ASGITransport(app=first_app),
                base_url="http://testserver",
            ) as client:
                empty = await client.get("/api/management/destination-profiles")
                assert empty.status_code == 200
                assert empty.json()["persistent"] is True
                assert empty.json()["profiles"] == []

                destinations = (await client.get("/api/management/destinations")).json()
                assert destinations["destination_profiles_persistent"] is True
                assert destinations["external_connections_enabled"] is False

                saved = await client.post("/api/management/destination-profiles", json=draft)
                assert saved.status_code == 201
                assert saved.json()["persistent"] is True
                assert saved.json()["external_connection_enabled"] is False
                assert saved.json()["endpoint_fields_supported"] is False
                assert saved.json()["credential_fields_supported"] is False
                original_profile = saved.json()["profile"]
                assert original_profile["receiver_product"] == draft["receiver_product"]
                assert "endpoint" not in str(original_profile).lower()
                assert "credential" not in str(original_profile).lower()

        second_app = create_dashboard_app(
            SyntheticOperationsDashboard(refresh_interval_seconds=60, duplicate_every=0),
            destination_api_profile_database_url=database_url,
        )
        async with second_app.router.lifespan_context(second_app):
            async with AsyncClient(
                transport=ASGITransport(app=second_app),
                base_url="http://testserver",
            ) as client:
                restored = await client.get("/api/management/destination-profiles")
                assert restored.status_code == 200
                assert restored.json()["persistent"] is True
                assert len(restored.json()["profiles"]) == 1
                restored_profile = restored.json()["profiles"][0]
                assert restored_profile["profile_id"] == original_profile["profile_id"]
                assert restored_profile["created_at"] == original_profile["created_at"]
                assert restored_profile["receiver_version"] == "4.0.1"

                readiness = (await client.get("/api/management/destinations")).json()
                assert readiness["external_connections_enabled"] is False
                fhir_target = next(
                    target
                    for target in readiness["api_targets"]
                    if target["target_id"] == "emr_fhir_r4"
                )
                assert fhir_target["status"] == "discovery_complete_pending_synthetic_validation"
                assert fhir_target["external_connection_enabled"] is False
                assert fhir_target["endpoint_fields_supported"] is False
                assert fhir_target["credential_fields_supported"] is False
                assert fhir_target["activation_enabled"] is False
                checks = {check["id"]: check["status"] for check in fhir_target["checks"]}
                assert checks["synthetic_validation"] == "not_run"
                assert checks["site_approval"] == "not_approved"

                updated = await client.patch(
                    "/api/management/destination-profiles/emr_fhir_r4",
                    json={**draft, "receiver_version": "4.0.2"},
                )
                assert updated.status_code == 200
                assert updated.json()["persistent"] is True
                assert updated.json()["profile"]["profile_id"] == original_profile["profile_id"]
                assert updated.json()["profile"]["receiver_version"] == "4.0.2"

        third_app = create_dashboard_app(
            SyntheticOperationsDashboard(refresh_interval_seconds=60, duplicate_every=0),
            destination_api_profile_database_url=database_url,
        )
        async with third_app.router.lifespan_context(third_app):
            async with AsyncClient(
                transport=ASGITransport(app=third_app),
                base_url="http://testserver",
            ) as client:
                profiles = (await client.get("/api/management/destination-profiles")).json()
                assert profiles["persistent"] is True
                assert profiles["profiles"][0]["receiver_version"] == "4.0.2"

    asyncio.run(exercise())

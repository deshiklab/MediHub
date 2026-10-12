"""Discovery-only device library and non-connectable profile API tests."""

import asyncio

from httpx import ASGITransport, AsyncClient

from medihub.application.operations import SyntheticOperationsDashboard
from medihub.dashboard import create_dashboard_app


def test_device_library_separates_market_leads_from_actual_adapters() -> None:
    async def exercise() -> None:
        app = create_dashboard_app(
            SyntheticOperationsDashboard(refresh_interval_seconds=60, duplicate_every=0)
        )
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get("/api/management/device-library")
                assert response.status_code == 200
                payload = response.json()
                assert payload["mode"] == "synthetic_only"
                assert payload["country_focus"] == "BD"
                assert payload["installed_base_ranked"] is False
                assert payload["physical_device_connections_enabled"] is False
                assert payload["endpoint_fields_supported"] is False
                assert payload["credential_fields_supported"] is False
                assert {item["adapter_id"] for item in payload["device_adapters"]} == {
                    "medihub.synthetic-device",
                    "offline-astm-e1394-parser-scaffold",
                }
                assert all(
                    not item["connects_to_physical_device"] for item in payload["device_adapters"]
                )
                cl900i = next(
                    candidate
                    for candidate in payload["candidates"]
                    if candidate["candidate_id"] == "mindray-cl900i"
                )
                assert cl900i["status"] == "discovery_only"
                assert cl900i["compatibility_verified"] is False
                assert cl900i["live_adapter_available"] is False
                assert payload["candidate_count"] == len(payload["candidates"])

    asyncio.run(exercise())


def test_device_profiles_are_ephemeral_strict_and_cannot_enable_connections() -> None:
    async def exercise() -> None:
        app = create_dashboard_app(
            SyntheticOperationsDashboard(refresh_interval_seconds=60, duplicate_every=0)
        )
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                initial = await client.get("/api/management/device-profiles")
                assert initial.status_code == 200
                assert initial.json() == {
                    "mode": "synthetic_only",
                    "persistent": False,
                    "physical_device_connections_enabled": False,
                    "endpoint_fields_supported": False,
                    "credential_fields_supported": False,
                    "profiles": [],
                }

                cl900i_draft = {
                    "candidate_id": "mindray-cl900i",
                    "manufacturer": "Mindray",
                    "model": "CL-900i",
                    "device_family": "immunoassay",
                    "firmware_software_scope": "unknown",
                    "transport": "unconfirmed",
                    "protocol": "unconfirmed",
                    "protocol_version": None,
                    "interface_document_reference": None,
                    "vendor_authorization_status": "pending",
                    "vendor_authorization_reference": None,
                    "facility_authorization_status": "pending",
                    "facility_authorization_reference": None,
                    "results_only_confirmed": False,
                    "receiver_contract_reference": None,
                }
                created = await client.post("/api/management/device-profiles", json=cl900i_draft)
                assert created.status_code == 201
                profile = created.json()
                assert profile["manufacturer"] == "Mindray"
                assert profile["model"] == "CL-900i"
                assert profile["readiness"]["status"] == "discovery_only"
                assert "firmware_scope_unconfirmed" in profile["readiness"]["blockers"]
                assert "vendor_authorization_pending" in profile["readiness"]["blockers"]
                assert profile["readiness"]["synthetic_validation_status"] == "not_run"
                assert profile["readiness"]["site_approval_status"] == "not_approved"
                assert profile["readiness"]["hardware_connection_enabled"] is False
                initial_checks = {
                    check["id"]: check["status"] for check in profile["readiness"]["checks"]
                }
                assert initial_checks["exact_device_identity"] == "recorded"
                assert initial_checks["firmware_scope"] == "pending"
                assert initial_checks["synthetic_validation"] == "not_run"
                assert initial_checks["site_approval"] == "not_approved"
                for forbidden in ("host", "port", "password", "api_key", "endpoint", "credentials"):
                    assert forbidden not in profile

                listed = await client.get("/api/management/device-profiles")
                assert listed.status_code == 200
                assert listed.json()["persistent"] is False
                assert listed.json()["physical_device_connections_enabled"] is False
                assert len(listed.json()["profiles"]) == 1

                rejected_secret_fields = await client.post(
                    "/api/management/device-profiles",
                    json={**cl900i_draft, "api_key": "synthetic-secret-must-not-echo"},
                )
                assert rejected_secret_fields.status_code == 422
                assert "synthetic-secret-must-not-echo" not in rejected_secret_fields.text
                assert "api_key" not in rejected_secret_fields.text

                rejected_approval = await client.post(
                    "/api/management/device-profiles",
                    json={
                        **cl900i_draft,
                        "vendor_authorization_status": "approved",
                        "vendor_authorization_reference": None,
                    },
                )
                assert rejected_approval.status_code == 422
                assert "vendor_approval_reference_required" not in rejected_approval.text

                fixture_profile = {
                    "candidate_id": None,
                    "manufacturer": "Synthetic Lab",
                    "model": "Fixture Analyzer 1",
                    "device_family": "other",
                    "firmware_software_scope": "fixture-1",
                    "transport": "file_feed",
                    "protocol": "vendor_defined",
                    "protocol_version": "fixture-v1",
                    "interface_document_reference": "synthetic-fixture-doc-v1",
                    "vendor_authorization_status": "approved",
                    "vendor_authorization_reference": "synthetic-vendor-approval",
                    "facility_authorization_status": "approved",
                    "facility_authorization_reference": "synthetic-facility-approval",
                    "results_only_confirmed": True,
                    "receiver_contract_reference": "synthetic-receiver-contract",
                }
                fixture = await client.post(
                    "/api/management/device-profiles",
                    json=fixture_profile,
                )
                assert fixture.status_code == 201
                ready_for_synthetic = fixture.json()
                assert (
                    ready_for_synthetic["readiness"]["status"]
                    == "discovery_complete_pending_synthetic_validation"
                )
                assert ready_for_synthetic["readiness"]["blockers"] == []
                assert ready_for_synthetic["readiness"]["synthetic_validation_status"] == "not_run"
                assert ready_for_synthetic["readiness"]["site_approval_status"] == "not_approved"
                assert ready_for_synthetic["readiness"]["hardware_connection_enabled"] is False
                ready_checks = {
                    check["id"]: check["status"]
                    for check in ready_for_synthetic["readiness"]["checks"]
                }
                assert sum(status == "recorded" for status in ready_checks.values()) == 9
                assert ready_checks["synthetic_validation"] == "not_run"
                assert ready_checks["site_approval"] == "not_approved"

                updated = await client.patch(
                    f"/api/management/device-profiles/{profile['profile_id']}",
                    json={**cl900i_draft, "firmware_software_scope": "unknown-site-version"},
                )
                assert updated.status_code == 200
                assert updated.json()["profile_id"] == profile["profile_id"]
                assert updated.json()["updated_at"] >= profile["updated_at"]
                assert updated.json()["readiness"]["hardware_connection_enabled"] is False

                missing_profile = await client.patch(
                    "/api/management/device-profiles/00000000-0000-0000-0000-000000000001",
                    json=cl900i_draft,
                )
                assert missing_profile.status_code == 404
                assert missing_profile.json() == {"error": "device_profile_not_found"}

    asyncio.run(exercise())

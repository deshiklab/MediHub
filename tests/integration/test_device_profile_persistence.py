"""Durability and safety for non-secret device discovery profiles."""

import asyncio

from httpx import ASGITransport, AsyncClient

from medihub.application.operations import SyntheticOperationsDashboard
from medihub.dashboard import create_dashboard_app


def test_device_discovery_profiles_survive_dashboard_restart(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'device-profile-store.db').as_posix()}"
    draft = {
        "candidate_id": "mindray-cl900i",
        "manufacturer": "Mindray",
        "model": "CL-900i",
        "device_family": "immunoassay",
        "firmware_software_scope": "CL900i-software-1",
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
                empty = await client.get("/api/management/device-profiles")
                assert empty.status_code == 200
                assert empty.json()["persistent"] is True
                assert empty.json()["profiles"] == []
                assert empty.json()["physical_device_connections_enabled"] is False

                created = await client.post("/api/management/device-profiles", json=draft)
                assert created.status_code == 201
                profile = created.json()
                assert profile["model"] == "CL-900i"
                assert profile["readiness"]["status"] == "discovery_only"
                assert profile["readiness"]["hardware_connection_enabled"] is False
                assert not any(
                    forbidden in profile
                    for forbidden in ("host", "port", "endpoint", "password", "credentials")
                )

        second_app = create_dashboard_app(
            SyntheticOperationsDashboard(refresh_interval_seconds=60, duplicate_every=0),
            destination_api_profile_database_url=database_url,
        )
        async with second_app.router.lifespan_context(second_app):
            async with AsyncClient(
                transport=ASGITransport(app=second_app),
                base_url="http://testserver",
            ) as client:
                restored = await client.get("/api/management/device-profiles")
                assert restored.status_code == 200
                assert restored.json()["persistent"] is True
                assert restored.json()["physical_device_connections_enabled"] is False
                assert restored.json()["endpoint_fields_supported"] is False
                assert restored.json()["credential_fields_supported"] is False
                assert len(restored.json()["profiles"]) == 1
                restored_profile = restored.json()["profiles"][0]
                assert restored_profile["profile_id"] == profile["profile_id"]
                assert restored_profile["created_at"] == profile["created_at"]
                assert restored_profile["firmware_software_scope"] == "CL900i-software-1"

                updated = await client.patch(
                    f"/api/management/device-profiles/{profile['profile_id']}",
                    json={**draft, "firmware_software_scope": "CL900i-software-2"},
                )
                assert updated.status_code == 200
                assert updated.json()["profile_id"] == profile["profile_id"]
                assert updated.json()["updated_at"] >= profile["updated_at"]
                assert updated.json()["readiness"]["hardware_connection_enabled"] is False

        third_app = create_dashboard_app(
            SyntheticOperationsDashboard(refresh_interval_seconds=60, duplicate_every=0),
            destination_api_profile_database_url=database_url,
        )
        async with third_app.router.lifespan_context(third_app):
            async with AsyncClient(
                transport=ASGITransport(app=third_app),
                base_url="http://testserver",
            ) as client:
                restored = await client.get("/api/management/device-profiles")
                assert restored.status_code == 200
                assert restored.json()["persistent"] is True
                assert restored.json()["profiles"][0]["firmware_software_scope"] == (
                    "CL900i-software-2"
                )
                assert (
                    restored.json()["profiles"][0]["readiness"]["hardware_connection_enabled"]
                    is False
                )

    asyncio.run(exercise())

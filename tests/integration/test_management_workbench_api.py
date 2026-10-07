import asyncio

from httpx import ASGITransport, AsyncClient

from medihub.application.operations import SyntheticOperationsDashboard
from medihub.dashboard import create_dashboard_app


async def _request_workbench():
    runtime = SyntheticOperationsDashboard(
        refresh_interval_seconds=60,
        duplicate_every=0,
    )
    app = create_dashboard_app(runtime)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            devices = await client.get("/api/management/devices")
            assert devices.status_code == 200
            assert devices.json()["physical_device_connections_enabled"] is False
            assert devices.json()["persistent"] is False
            assert devices.json()["devices"][0]["device_id"] == "sim-device-001"

            registered = await client.post("/api/management/devices")
            assert registered.status_code == 201
            assert registered.json()["device_id"] == "sim-device-002"
            assert registered.json()["model"] == "scalar-simulator-v1"

            disabled = await client.patch(
                "/api/management/devices/sim-device-002",
                json={"enabled": False},
            )
            assert disabled.status_code == 200
            assert disabled.json()["enabled"] is False
            rejected_sample = await client.post("/api/management/devices/sim-device-002/emit")
            assert rejected_sample.status_code == 409
            assert rejected_sample.json() == {"error": "simulator_device_disabled"}

            reenabled = await client.patch(
                "/api/management/devices/sim-device-002",
                json={"enabled": True},
            )
            assert reenabled.status_code == 200
            sample = await client.post("/api/management/devices/sim-device-002/emit")
            assert sample.status_code == 200
            assert sample.json()["status"] == "passed"
            assert sample.json()["network_enabled"] is False

            mappings = (await client.get("/api/management/mappings")).json()
            assert mappings["mapping_activation_enabled"] is False
            assert mappings["mapping_set"]["scope"] == "synthetic_only"
            assert len(mappings["mapping_set"]["entries"]) == 1
            initial_history = (await client.get("/api/management/mappings/revisions")).json()
            assert initial_history["current_version"] == "1.0.0"
            assert initial_history["revision_count"] == 1
            assert initial_history["revisions"][0]["change_type"] == "initial"
            initial_revision = await client.get("/api/management/mappings/revisions/1.0.0")
            assert initial_revision.status_code == 200
            assert initial_revision.json()["revision"]["mapping_set"]["version"] == "1.0.0"
            initial_vectors = (await client.get("/api/management/mapping-tests")).json()
            assert initial_vectors["status"] == "not_run"
            assert len(initial_vectors["vectors"]) == 1
            initial_test = await client.post("/api/management/mapping-tests/run")
            assert initial_test.status_code == 200
            assert initial_test.json()["status"] == "passed"
            assert initial_test.json()["passed"] == 1
            assert initial_test.json()["activation_enabled"] is False

            draft = await client.post(
                "/api/management/mappings/entries",
                json={
                    "source_metric_code": "simulated-test-input",
                    "source_unit_code": "1",
                    "normalized_metric_code": "mapped-test-output",
                    "normalized_unit_code": "1",
                    "operation": "linear",
                    "scale": "2",
                    "offset": "1",
                    "decimal_places": 2,
                },
            )
            assert draft.status_code == 200
            assert draft.json()["mapping_activation_enabled"] is False
            assert draft.json()["mapping_set"]["version"] == "1.0.1"
            comparison = await client.get("/api/management/mappings/revisions/1.0.0/compare/1.0.1")
            assert comparison.status_code == 200
            assert comparison.json()["summary"] == {"added": 1, "removed": 0, "changed": 0}
            assert comparison.json()["activation_enabled"] is False
            current_revision = await client.get("/api/management/mappings/revisions/1.0.1")
            assert current_revision.status_code == 200
            assert current_revision.json()["revision"]["change_type"] == "entry_added"
            assert len(current_revision.json()["revision"]["mapping_set"]["entries"]) == 2
            invalidated_vectors = (await client.get("/api/management/mapping-tests")).json()
            assert invalidated_vectors["status"] == "stale"
            assert invalidated_vectors["last_run_mapping_version"] == "1.0.0"
            assert invalidated_vectors["last_report"]["status"] == "passed"

            vector = await client.post(
                "/api/management/mapping-tests/vectors",
                json={
                    "device_id": "sim-device-001",
                    "source_metric_code": "simulated-test-input",
                    "source_unit_code": "1",
                    "input_value": "3.5",
                    "expected_metric_code": "mapped-test-output",
                    "expected_unit_code": "1",
                    "expected_value": "8.00",
                },
            )
            assert vector.status_code == 200
            test_report = await client.post("/api/management/mapping-tests/run")
            assert test_report.status_code == 200
            assert test_report.json()["status"] == "passed"
            assert test_report.json()["mapping_version"] == "1.0.1"
            assert test_report.json()["vectors_run"] == 2
            assert test_report.json()["passed"] == 2
            assert test_report.json()["failed"] == 0
            assert test_report.json()["activation_enabled"] is False
            await client.post(
                "/api/management/mapping-tests/vectors",
                json={
                    "device_id": "sim-device-001",
                    "source_metric_code": "simulated-test-input",
                    "source_unit_code": "1",
                    "input_value": "3.5",
                    "expected_metric_code": "mapped-test-output",
                    "expected_unit_code": "1",
                    "expected_value": "9.00",
                },
            )
            mismatch_report = await client.post("/api/management/mapping-tests/run")
            assert mismatch_report.json()["status"] == "failed"
            assert mismatch_report.json()["failed"] == 1
            assert mismatch_report.json()["results"][-1]["code"] == (
                "mapping_test_expected_output_mismatch"
            )

            preview = await client.post(
                "/api/management/mappings/preview",
                json={
                    "device_id": "sim-device-001",
                    "source_metric_code": "simulated-test-input",
                    "source_unit_code": "1",
                    "value": 3.5,
                },
            )
            assert preview.status_code == 200
            assert preview.json()["mapping_activation_enabled"] is False
            assert preview.json()["result"]["normalized_value"] == "8.00"
            assert preview.json()["result"]["origin"] == "synthetic"
            assert "patient" not in preview.text.lower()

            rejected = await client.post(
                "/api/management/mappings/entries",
                json={
                    "source_metric_code": "secret-not-allowed",
                    "source_unit_code": "1",
                    "normalized_metric_code": "not-added",
                    "normalized_unit_code": "1",
                    "private_note": "SENSITIVE-DEMO-STRING",
                },
            )
            assert rejected.status_code == 422
            assert "SENSITIVE-DEMO-STRING" not in rejected.text
            assert "private_note" not in rejected.text

            destinations = (await client.get("/api/management/destinations")).json()
            assert destinations["external_connections_enabled"] is False
            assert destinations["destinations"][0]["network_enabled"] is False
            assert destinations["destinations"][0]["endpoint_configurable"] is False
            assert destinations["destinations"][0]["credentials_configurable"] is False
            receiver_test = await client.post("/api/management/destinations/test")
            assert receiver_test.status_code == 200
            assert receiver_test.json()["status"] == "passed"
            assert receiver_test.json()["network_enabled"] is False

            fault_status = await client.get("/api/management/destinations/test-receiver/faults")
            assert fault_status.status_code == 200
            assert fault_status.json()["armed_fault"] is None
            assert fault_status.json()["network_enabled"] is False
            armed_retry = await client.post(
                "/api/management/destinations/test-receiver/faults",
                json={"mode": "retry_once"},
            )
            assert armed_retry.status_code == 200
            assert armed_retry.json()["armed_fault"] == "retry_once"
            duplicate_arm = await client.post(
                "/api/management/destinations/test-receiver/faults",
                json={"mode": "reject_once"},
            )
            assert duplicate_arm.status_code == 409
            assert duplicate_arm.json() == {"error": "synthetic_fault_already_armed"}
            injected_retry = await client.post("/api/management/destinations/test")
            assert injected_retry.json()["status"] == "failed"
            assert injected_retry.json()["network_enabled"] is False
            after_retry_fault = (await client.get("/api/dashboard")).json()
            failed_delivery = next(
                row
                for row in after_retry_fault["recent_deliveries"]
                if row["status"] == "retryable_failure"
            )
            assert failed_delivery["error_code"] == "synthetic_test_retryable_failure"
            await asyncio.sleep(2.1)
            recovered_send = await client.post("/api/management/destinations/test")
            assert recovered_send.json()["status"] == "passed"
            after_recovery = (await client.get("/api/dashboard")).json()
            retried_delivery = next(
                row
                for row in after_recovery["recent_deliveries"]
                if row["event_id"] == failed_delivery["event_id"]
            )
            assert retried_delivery["status"] == "acknowledged"
            assert retried_delivery["attempts"] == 2

            armed_rejection = await client.post(
                "/api/management/destinations/test-receiver/faults",
                json={"mode": "reject_once"},
            )
            assert armed_rejection.json()["armed_fault"] == "reject_once"
            injected_rejection = await client.post("/api/management/destinations/test")
            assert injected_rejection.json()["status"] == "failed"
            rejected_snapshot = (await client.get("/api/dashboard")).json()
            rejected_delivery = next(
                row for row in rejected_snapshot["recent_deliveries"] if row["status"] == "rejected"
            )
            assert rejected_delivery["error_code"] == "synthetic_test_receiver_rejected"
            detail = await client.get(f"/api/management/deliveries/{rejected_delivery['event_id']}")
            assert detail.status_code == 200
            detail_data = detail.json()
            assert detail_data["scope"] == "synthetic_only"
            assert detail_data["network_enabled"] is False
            assert detail_data["event"]["origin"] == "synthetic"
            assert detail_data["delivery"]["status"] == "rejected"
            assert detail_data["delivery"]["retry_allowed"] is True
            assert len(detail_data["attempts"]) == 1
            assert "patient" not in detail.text.lower()
            assert "payload" not in detail.text.lower()
            replay = await client.post(
                f"/api/management/deliveries/{rejected_delivery['event_id']}/retry"
            )
            assert replay.status_code == 200
            assert replay.json()["delivery"]["status"] == "acknowledged"
            assert replay.json()["event"]["event_id"] == rejected_delivery["event_id"]
            assert len(replay.json()["attempts"]) == 2
            assert replay.json()["attempts"][-1]["status"] == "acknowledged"
            after_replay = (await client.get("/api/dashboard")).json()
            assert any(
                entry["action"] == "delivery_replayed" for entry in after_replay["recent_activity"]
            )
            replay_acknowledged = await client.post(
                f"/api/management/deliveries/{rejected_delivery['event_id']}/retry"
            )
            assert replay_acknowledged.status_code == 409
            assert replay_acknowledged.json() == {"error": "synthetic_delivery_not_terminal"}
            fault_status = await client.get("/api/management/destinations/test-receiver/faults")
            assert fault_status.json()["armed_fault"] is None
            assert fault_status.json()["faults_injected"] == 2
            await client.post(
                "/api/management/destinations/test-receiver/faults",
                json={"mode": "retry_once"},
            )
            cleared_fault = await client.delete("/api/management/destinations/test-receiver/faults")
            assert cleared_fault.status_code == 200
            assert cleared_fault.json()["armed_fault"] is None
            assert cleared_fault.json()["faults_injected"] == 2

            current_restore = await client.post("/api/management/mappings/revisions/1.0.1/restore")
            assert current_restore.status_code == 409
            missing_revision = await client.post("/api/management/mappings/revisions/9.9.9/restore")
            assert missing_revision.status_code == 404
            restored = await client.post("/api/management/mappings/revisions/1.0.0/restore")
            assert restored.status_code == 200
            assert restored.json()["restored_from_version"] == "1.0.0"
            assert restored.json()["mapping_set"]["version"] == "1.0.2"
            assert len(restored.json()["mapping_set"]["entries"]) == 1
            restore_comparison = await client.get(
                "/api/management/mappings/revisions/1.0.1/compare/1.0.2"
            )
            assert restore_comparison.json()["summary"] == {
                "added": 0,
                "removed": 1,
                "changed": 0,
            }
            restored_history = (await client.get("/api/management/mappings/revisions")).json()
            assert restored_history["revisions"][0]["change_type"] == "restore"
            assert restored_history["revisions"][0]["restored_from_version"] == "1.0.0"
            stale_after_restore = (await client.get("/api/management/mapping-tests")).json()
            assert stale_after_restore["status"] == "stale"
            assert stale_after_restore["last_run_mapping_version"] == "1.0.1"

            return await client.get("/")


def test_management_workbench_is_strict_synthetic_only_and_operational() -> None:
    page = asyncio.run(_request_workbench())

    assert page.status_code == 200
    assert "Register simulator" in page.text
    assert "Preview mapping" in page.text
    assert "Golden test vectors" in page.text
    assert "Run all mapping tests" in page.text
    assert "Revision history" in page.text
    assert "Restore as new draft" in page.text
    assert "Synthetic delivery fault drill" in page.text
    assert "Inject one retryable failure" in page.text
    assert "Selected synthetic delivery" in page.text
    assert "Retry terminal failure" in page.text
    assert "Endpoint and credential fields are not available" in page.text
    assert "no live connections" in page.text.lower()

"""Real-browser checks for dashboard language switching and localized workflows."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Browser, Page, Route, expect, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from medihub.dashboard import DASHBOARD_HTML

BASE_URL = "http://medihub.test"
PAGE_ROUTES = {
    "/": "operations",
    "/operations": "operations",
    "/devices": "devices",
    "/mappings": "mappings",
    "/api-setup": "api-setup",
    "/help": "help",
}

SNAPSHOT = {
    "mode": "synthetic_demo",
    "ready": True,
    "updated_at": "2026-10-07T04:00:00+00:00",
    "source": {
        "adapter_id": "medihub.synthetic-device",
        "detail_code": "synthetic_source_healthy",
        "status": "healthy",
    },
    "receiver": {"status": "in_process", "detail_code": "synthetic_receiver_ready"},
    "totals": {
        "events_received": 1,
        "events_inserted": 1,
        "duplicate_events": 0,
        "blocked_routes": 0,
        "audit_events": 0,
        "delivery_attempts": 1,
        "acknowledged_deliveries": 1,
        "pending_deliveries": 0,
        "retryable_failures": 0,
        "permanent_failures": 0,
        "rejected_deliveries": 0,
        "unique_test_receipts": 1,
    },
    "recent_events": [
        {
            "event_id": "test-event-0001",
            "device_id": "sim-device-001",
            "received_at": "2026-10-07T04:00:00+00:00",
            "observed_at": "2026-10-07T04:00:00+00:00",
            "label": "Synthetic scalar",
            "value": 72.5,
            "source_sequence": 1,
        }
    ],
    "recent_deliveries": [],
    "recent_holds": [],
    "recent_activity": [],
}


@pytest.fixture
def browser() -> Iterator[Browser]:
    """Launch Chromium installed by the browser-test setup step."""

    with sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch()
        except PlaywrightError as error:
            pytest.skip(
                "Chromium is not installed; run "
                "`python -m playwright install --only-shell chromium`: "
                f"{error}"
            )
        yield instance
        instance.close()


def _json_response(route: Route, payload: object, *, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json; charset=utf-8",
        body=json.dumps(payload),
    )


def _page_html(page_name: str) -> str:
    return DASHBOARD_HTML.replace(
        '<body data-current-page="operations">',
        f'<body data-current-page="{page_name}">',
        1,
    )


@pytest.fixture
def page(browser: Browser) -> Page:
    """Serve the packaged dashboard and deterministic synthetic API responses."""

    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        accept_downloads=True,
    )
    current_device = {"enabled": True}
    device_profiles: list[dict[str, object]] = []
    api_evidence_gate_ids = [
        "receiver_product_version",
        "interface_version_profile",
        "controlled_interface_contract",
        "resource_message_profile",
        "patient_association_policy",
        "results_only_review_workflow",
        "acknowledgement_idempotency_retry",
        "security_transport_authorization",
        "authorized_synthetic_sandbox",
    ]
    api_targets = [
        {
            "target_id": target_id,
            "label": label,
            "protocol": protocol,
            "status": "contract_required",
            "checks": [
                *[{"id": gate, "status": "pending"} for gate in api_evidence_gate_ids],
                {
                    "id": "synthetic_validation",
                    "status": "not_run",
                    "scope": "local_fixture_only"
                    if target_id == "emr_fhir_r4"
                    else "blocked_pending_exact_receiver_contract",
                },
                {"id": "site_approval", "status": "not_approved"},
            ],
            "synthetic_validation_scope": "local_fixture_only"
            if target_id == "emr_fhir_r4"
            else "blocked_pending_exact_receiver_contract",
            "synthetic_validation_report": None,
            "external_connection_enabled": False,
            "endpoint_fields_supported": False,
            "credential_fields_supported": False,
            "activation_enabled": False,
        }
        for target_id, label, protocol in (
            ("emr_fhir_r4", "FHIR R4 / EMR", "fhir_r4"),
            ("facility_hl7_v2", "HL7 v2 / interface engine / EMS", "hl7_v2"),
        )
    ]
    device_candidates = [
        {
            "candidate_id": "mindray-cl900i",
            "manufacturer": "Mindray",
            "model": "CL-900i",
            "device_family": "immunoassay",
            "discovery_basis": "user_selected_target",
            "evidence_note": (
                "User-selected integration target; installed base, firmware, and host "
                "interface are unverified."
            ),
            "source_url": None,
            "evidence_reviewed_on": None,
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
        {
            "candidate_id": "zecen-cia-600",
            "manufacturer": "Zecen",
            "model": "CIA 600",
            "device_family": "immunoassay",
            "discovery_basis": "bangladesh_seller_listing",
            "evidence_note": (
                "Medistore Bangladesh page lists this model; its LIS/networking claims are "
                "unverified and do not identify the installed base or interface profile."
            ),
            "source_url": "https://example.invalid/zecen-cia-600",
            "evidence_reviewed_on": "2026-10-14",
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
        {
            "candidate_id": "zecen-cia-1200",
            "manufacturer": "Zecen",
            "model": "CIA 1200",
            "device_family": "immunoassay",
            "discovery_basis": "bangladesh_seller_listing",
            "evidence_note": (
                "Medistore Bangladesh page lists this model; its LIS/networking claims are "
                "unverified and do not identify the installed base or interface profile."
            ),
            "source_url": "https://example.invalid/zecen-cia-1200",
            "evidence_reviewed_on": "2026-10-14",
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
        {
            "candidate_id": "icubio-imagic-m7",
            "manufacturer": "ICUBIO",
            "model": "iMagic M7",
            "device_family": "clinical_chemistry",
            "discovery_basis": "bangladesh_seller_listing",
            "evidence_note": (
                "Medistore Bangladesh page lists this model and claims RS-232/PC connectivity; "
                "installed prevalence, firmware, and host profile are unverified."
            ),
            "source_url": "https://example.invalid/icubio-imagic-m7",
            "evidence_reviewed_on": "2026-10-14",
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
        {
            "candidate_id": "mindray-bc-20s",
            "manufacturer": "Mindray",
            "model": "BC-20s",
            "device_family": "hematology",
            "discovery_basis": "bangladesh_seller_listing",
            "evidence_note": (
                "Bangladesh seller listing only; not evidence of installed-base "
                "prevalence or connectivity."
            ),
            "source_url": "https://example.invalid/listing",
            "evidence_reviewed_on": "2026-10-11",
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
        {
            "candidate_id": "sysmex-xn-3000",
            "manufacturer": "Sysmex",
            "model": "XN-3000",
            "device_family": "hematology",
            "discovery_basis": "bangladesh_facility_self_report",
            "evidence_note": (
                "Facility page self-reports an installation; not independently verified."
            ),
            "source_url": "https://example.invalid/facility-report",
            "evidence_reviewed_on": "2026-10-13",
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
        {
            "candidate_id": "celltus-cts-3000",
            "manufacturer": "Celltus",
            "model": "CTS-3000",
            "device_family": "hematology",
            "discovery_basis": "bangladesh_seller_listing",
            "evidence_note": (
                "Bangladesh seller product page lists the model; installed base unverified."
            ),
            "source_url": "https://example.invalid/celltus-cts-3000",
            "evidence_reviewed_on": "2026-10-13",
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
        {
            "candidate_id": "celltus-cts-5000",
            "manufacturer": "Celltus",
            "model": "CTS-5000",
            "device_family": "hematology",
            "discovery_basis": "bangladesh_supplier_category",
            "evidence_note": (
                "Bangladesh supplier category lists the model; host interface unverified."
            ),
            "source_url": "https://example.invalid/hematology-category",
            "evidence_reviewed_on": "2026-10-13",
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
        {
            "candidate_id": "dymind-df-51",
            "manufacturer": "Dymind",
            "model": "DF-51",
            "device_family": "hematology",
            "discovery_basis": "bangladesh_seller_listing",
            "evidence_note": (
                "Bangladesh seller product page lists the model; installed base unverified."
            ),
            "source_url": "https://example.invalid/dymind-df-51",
            "evidence_reviewed_on": "2026-10-13",
            "status": "discovery_only",
            "compatibility_verified": False,
            "live_adapter_available": False,
        },
    ]

    def handle_request(route: Route) -> None:
        request = route.request
        parsed = urlsplit(request.url)
        if parsed.netloc != "medihub.test":
            route.abort()
            return

        if request.method == "GET" and parsed.path in PAGE_ROUTES:
            route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=_page_html(PAGE_ROUTES[parsed.path]),
            )
            return

        if parsed.path == "/api/dashboard" and request.method == "GET":
            _json_response(route, SNAPSHOT)
            return

        if parsed.path == "/api/management/devices" and request.method == "GET":
            _json_response(
                route,
                {
                    "scope": "synthetic_only",
                    "devices": [
                        {
                            "device_id": "sim-device-001",
                            "enabled": current_device["enabled"],
                            "model": "Demo scalar simulator",
                            "firmware_version": "1.0",
                            "adapter_id": "medihub.synthetic-device",
                            "adapter_version": "1.0",
                        }
                    ],
                },
            )
            return

        if parsed.path == "/api/management/device-library" and request.method == "GET":
            _json_response(
                route,
                {
                    "mode": "synthetic_only",
                    "country_focus": "BD",
                    "candidate_count": len(device_candidates),
                    "installed_base_ranked": False,
                    "physical_device_connections_enabled": False,
                    "endpoint_fields_supported": False,
                    "credential_fields_supported": False,
                    "device_adapters": [],
                    "candidates": device_candidates,
                },
            )
            return

        if parsed.path == "/api/management/device-profiles" and request.method == "GET":
            _json_response(
                route,
                {
                    "mode": "synthetic_only",
                    "persistent": False,
                    "physical_device_connections_enabled": False,
                    "endpoint_fields_supported": False,
                    "credential_fields_supported": False,
                    "profiles": device_profiles,
                },
            )
            return

        if parsed.path == "/api/management/device-profiles" and request.method == "POST":
            body = json.loads(request.post_data or "{}")
            profile = {
                **body,
                "profile_id": "00000000-0000-0000-0000-000000000001",
                "created_at": "2026-10-11T00:00:00+00:00",
                "updated_at": "2026-10-11T00:00:00+00:00",
                "readiness": {
                    "status": "discovery_only",
                    "blockers": ["firmware_scope_unconfirmed"],
                    "synthetic_validation_status": "not_run",
                    "site_approval_status": "not_approved",
                    "hardware_connection_enabled": False,
                    "checks": [
                        {"id": "exact_device_identity", "status": "recorded"},
                        {"id": "firmware_scope", "status": "pending"},
                        {"id": "documented_transport", "status": "pending"},
                        {"id": "protocol_and_version", "status": "pending"},
                        {"id": "controlled_interface_document", "status": "pending"},
                        {"id": "vendor_authorization", "status": "pending"},
                        {"id": "facility_authorization", "status": "pending"},
                        {"id": "results_only_scope", "status": "pending"},
                        {"id": "receiver_contract", "status": "pending"},
                        {"id": "synthetic_validation", "status": "not_run"},
                        {"id": "site_approval", "status": "not_approved"},
                    ],
                },
            }
            device_profiles.append(profile)
            _json_response(route, profile, status=201)
            return

        if parsed.path.startswith("/api/management/device-profiles/") and request.method == "PATCH":
            body = json.loads(request.post_data or "{}")
            profile = {**device_profiles[0], **body}
            device_profiles[0] = profile
            _json_response(route, profile)
            return

        if parsed.path == "/api/management/devices/sim-device-001" and request.method == "PATCH":
            body = json.loads(request.post_data or "{}")
            current_device["enabled"] = bool(body.get("enabled"))
            _json_response(
                route,
                {"device_id": "sim-device-001", "enabled": current_device["enabled"]},
            )
            return

        if (
            parsed.path == "/api/management/devices/sim-device-001/emit"
            and request.method == "POST"
        ):
            _json_response(
                route,
                {"status": "passed", "unique_test_receipts": 1, "network_enabled": False},
            )
            return

        if parsed.path == "/api/management/mappings" and request.method == "GET":
            _json_response(
                route,
                {
                    "scope": "synthetic_only",
                    "persistent": False,
                    "mapping_activation_enabled": False,
                    "mapping_set": {
                        "mapping_set_id": "synthetic-demo",
                        "version": "1",
                        "entries": [],
                    },
                },
            )
            return

        if parsed.path == "/api/management/mapping-tests" and request.method == "GET":
            _json_response(
                route,
                {
                    "mapping_version": "1",
                    "test_count": 0,
                    "status": "not_run",
                    "last_run_mapping_version": None,
                    "last_report": None,
                    "activation_enabled": False,
                    "vectors": [],
                },
            )
            return

        if parsed.path == "/api/management/mappings/revisions" and request.method == "GET":
            _json_response(
                route,
                {
                    "scope": "synthetic_only",
                    "current_version": "1",
                    "revision_count": 1,
                    "older_revisions_discarded": 0,
                    "revisions": [],
                },
            )
            return

        if parsed.path == "/api/management/destinations" and request.method == "GET":
            _json_response(
                route,
                {
                    "destinations": [
                        {
                            "label": "In-process FHIR R4 test receiver",
                            "status": "ready",
                            "protocol": "FHIR R4",
                            "transport": "in_process",
                            "network_enabled": False,
                        }
                    ],
                    "api_targets": api_targets,
                    "external_connections_enabled": False,
                    "target_conformance_claimed": False,
                    "destination_profiles_persistent": False,
                },
            )
            return

        if (
            parsed.path == "/api/management/destinations/fhir-synthetic-validation"
            and request.method == "POST"
        ):
            report = {
                "target_id": "emr_fhir_r4",
                "validation_id": "00000000-0000-0000-0000-000000000001",
                "fixture_version": "medihub-fhir-r4-synthetic-observation-v1",
                "status": "local_fixture_passed",
                "profile_fingerprint": None,
                "ran_at": "2026-10-12T07:00:00Z",
                "checks": [
                    {
                        "check_id": "synthetic_event_origin",
                        "status": "passed",
                        "code": "synthetic_event_confirmed",
                    },
                    {
                        "check_id": "patient_context_omitted",
                        "status": "passed",
                        "code": "patient_context_absent",
                    },
                    {
                        "check_id": "fixture_output_matches",
                        "status": "passed",
                        "code": "fixture_output_matches",
                    },
                    {
                        "check_id": "fhir_r4_model_validation",
                        "status": "passed",
                        "code": "fhir_r4_model_validation_passed",
                    },
                    {
                        "check_id": "preliminary_status",
                        "status": "passed",
                        "code": "preliminary_status_confirmed",
                    },
                ],
                "scope": "local_fixture_only",
                "network_enabled": False,
                "sent": False,
                "external_connection_enabled": False,
                "target_contract_validated": False,
                "target_conformance_claimed": False,
                "site_approval_changed": False,
            }
            fhir_target = next(
                target for target in api_targets if target["target_id"] == "emr_fhir_r4"
            )
            fhir_target["synthetic_validation_report"] = report
            for check in fhir_target["checks"]:
                if check["id"] == "synthetic_validation":
                    check["status"] = "local_fixture_passed"
            _json_response(
                route,
                {"mode": "synthetic_only", **report, "persistent": False},
            )
            return

        if parsed.path == "/api/management/destinations/fhir-preview" and request.method == "POST":
            _json_response(
                route,
                {
                    "scope": "synthetic_only",
                    "status": "preview_only",
                    "resource_profile": "generic_fhir_r4_observation_subset",
                    "network_enabled": False,
                    "sent": False,
                    "target_contract_validated": False,
                    "patient_context_included": False,
                    "resource": {
                        "resourceType": "Observation",
                        "id": "synthetic-preview-001",
                        "status": "preliminary",
                        "valueQuantity": {
                            "value": 42.5,
                            "unit": "1",
                            "system": "http://unitsofmeasure.org",
                            "code": "1",
                        },
                    },
                },
            )
            return

        if (
            parsed.path == "/api/management/destinations/test-receiver/faults"
            and request.method == "GET"
        ):
            _json_response(
                route,
                {"armed_fault": None, "last_injected_fault": None, "faults_injected": 0},
            )
            return

        _json_response(route, {"error": "not_found"}, status=404)

    page = context.new_page()
    page.route("**/*", handle_request)
    try:
        yield page
    finally:
        context.close()


def test_language_switch_localizes_live_operations_and_persists_across_routes(page: Page) -> None:
    page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
    expect(page.locator("#page-title")).to_have_text("Integration operations")
    expect(page.locator("#events-body .reading")).to_have_text("72.50 · synthetic")

    page.get_by_role("combobox", name="Interface language").select_option("bn")

    expect(page.locator("html")).to_have_attribute("lang", "bn")
    expect(page.locator("#page-title")).to_have_text("ইন্টিগ্রেশন কার্যক্রম")
    expect(page.locator("#source-state")).to_have_text("স্বাভাবিক")
    expect(page.locator("#receiver-state")).to_have_text("সংযুক্ত")
    expect(page.locator("#events-count")).to_have_text("1টি সাম্প্রতিক")
    expect(page.locator("#events-body .reading")).to_have_text("72.50 · সিন্থেটিক")
    expect(page.get_by_role("combobox", name="ইন্টারফেসের ভাষা")).to_be_visible()
    assert page.evaluate("window.localStorage.getItem('medihub-language')") == "bn"

    page.get_by_role("link", name="সহায়তা / ব্যবহারকারী নির্দেশিকা").click()
    expect(page.locator("html")).to_have_attribute("lang", "bn")
    expect(page.locator("#page-title")).to_have_text("সহায়তা ও ব্যবহারকারী নির্দেশিকা")
    expect(page.locator("#help-title")).to_have_text("১. এই প্রিভিউতে MediHub কী করে")
    expect(page.locator(".help-lead")).to_contain_text("গুরুত্বপূর্ণ সীমা")

    page.get_by_role("link", name="ডেটা ম্যাপিং").click()
    expect(page.locator("html")).to_have_attribute("lang", "bn")
    expect(page.locator("#page-title")).to_have_text("ডেটা ম্যাপিং")


def test_device_actions_and_generated_statuses_are_localized(page: Page) -> None:
    page.goto(f"{BASE_URL}/devices", wait_until="domcontentloaded")
    page.locator("#language-select").select_option("bn")

    expect(page.locator("#device-workbench-heading")).to_have_text("ডিভাইস ব্যবস্থাপনা")
    expect(page.locator("#device-catalog .device-catalog-card strong").first).to_have_text(
        "Mindray CL-900i"
    )
    expect(page.locator("#devices-list .device-row small")).to_contain_text("শুধু সিন্থেটিক")
    expect(page.get_by_role("button", name="নিষ্ক্রিয় করুন")).to_be_visible()

    page.get_by_role("button", name="নিষ্ক্রিয় করুন", exact=True).click()
    expect(page.locator("#device-status")).to_contain_text(
        "sim-device-001 এখন শুধু স্থানীয় সিমুলেটরে নিষ্ক্রিয়।"
    )
    page.get_by_role("button", name="সক্রিয় করুন", exact=True).click()
    expect(page.locator("#device-status")).to_contain_text(
        "sim-device-001 এখন শুধু স্থানীয় সিমুলেটরে সক্রিয়।"
    )
    page.get_by_role("button", name="নমুনা পাঠান").click()
    expect(page.locator("#device-status")).to_contain_text(
        "sim-device-001: পাস করেছে · প্রসেসের ভেতরের পরীক্ষামূলক রসিদ 1।"
    )

    page.locator("#language-select").select_option("en")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.locator("#device-status")).to_contain_text(
        "sim-device-001: passed; in-process receipts 1."
    )


def test_blank_bangladesh_inventory_survey_template_is_local_and_bilingual(page: Page) -> None:
    page.goto(f"{BASE_URL}/devices", wait_until="domcontentloaded")

    template_button = page.get_by_role("button", name="Download blank inventory survey CSV")
    expect(template_button).to_be_enabled()
    with page.expect_download() as template_download_info:
        template_button.click()
    download = template_download_info.value
    assert download.suggested_filename == (
        "medihub-bangladesh-device-inventory-survey-template.csv"
    )
    with Path(download.path()).open(encoding="utf-8-sig", newline="") as survey_file:
        rows = list(csv.reader(survey_file))
    expected_columns = [
        "survey_record_ref",
        "site_ref",
        "evidence_class",
        "survey_date",
        "device_family",
        "manufacturer",
        "exact_model",
        "firmware_software_scope",
        "lab_section_ref",
        "installed_count_or_band",
        "usage_band",
        "current_receiver_product_version",
        "current_interface_state",
        "device_transport_protocol_version",
        "vendor_gateway_or_interface_ref",
        "results_only_supported",
        "technician_review_workflow_ref",
        "interface_document_ref_revision",
        "vendor_authorization_status_ref",
        "facility_authorization_status_ref",
        "local_service_support_ref",
        "synthetic_test_environment_ref",
        "open_questions",
    ]
    assert rows == [expected_columns, [""] * len(expected_columns)]
    assert not {
        "serial_number",
        "asset_tag",
        "hostname",
        "ip_address",
        "port",
        "credential",
        "patient_id",
        "raw_message",
    } & set(expected_columns)
    expect(page.locator("#device-inventory-survey-status")).to_have_text(
        "Bangladesh device inventory survey CSV template downloaded. "
        "No facility responses were included or uploaded."
    )

    page.locator("#language-select").select_option("bn")
    expect(page.locator(".device-inventory-survey-copy p")).to_contain_text(
        "এই ব্রাউজারে একটি খালি CSV তৈরি হয়"
    )
    expect(page.locator("#device-inventory-survey-status")).to_have_text(
        "বাংলাদেশি ডিভাইস-তালিকা জরিপের CSV টেমপ্লেট ডাউনলোড হয়েছে। কোনো প্রতিষ্ঠানের উত্তর যোগ বা আপলোড হয়নি।"
    )
    bengali_button = page.get_by_role("button", name="খালি ডিভাইস-তালিকা জরিপ CSV ডাউনলোড করুন")
    expect(bengali_button).to_be_enabled()
    with page.expect_download() as bengali_download_info:
        bengali_button.click()
    assert bengali_download_info.value.suggested_filename == download.suggested_filename
    with Path(bengali_download_info.value.path()).open(
        encoding="utf-8-sig", newline=""
    ) as bengali_survey_file:
        assert list(csv.reader(bengali_survey_file)) == rows
    expect(page.locator("#device-inventory-survey-status")).to_have_text(
        "বাংলাদেশি ডিভাইস-তালিকা জরিপের CSV টেমপ্লেট ডাউনলোড হয়েছে। কোনো প্রতিষ্ঠানের উত্তর যোগ বা আপলোড হয়নি।"
    )


def test_device_catalog_filters_by_family_evidence_date_status_and_search(page: Page) -> None:
    page.goto(f"{BASE_URL}/devices", wait_until="domcontentloaded")

    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 9 of 9 discovery leads."
    )
    expect(page.locator(".device-catalog-export-note")).to_contain_text(
        "Known evidence review dates are appended in the evidence_note column"
    )
    selected_target_card = page.locator("#device-catalog .device-catalog-card").filter(
        has_text="Mindray CL-900i"
    )
    expect(selected_target_card.locator(".device-evidence-reviewed")).to_have_text(
        "Evidence review date not recorded"
    )
    seller_card = page.locator("#device-catalog .device-catalog-card").filter(
        has_text="Mindray BC-20s"
    )
    expect(seller_card.locator(".device-evidence-reviewed")).to_have_text(
        "Evidence reviewed: 2026-10-11"
    )
    expect(seller_card.get_by_role("link")).to_have_text("Seller listing (availability only)")

    date_filter = page.locator("#device-catalog-date-filter")
    date_filter.select_option("recorded")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 8 of 9 discovery leads."
    )
    expect(page.locator("#device-catalog .device-catalog-card")).to_have_count(8)
    date_filter.select_option("unknown")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 1 of 9 discovery leads."
    )
    unknown_date_card = page.locator("#device-catalog .device-catalog-card")
    expect(unknown_date_card.locator("strong")).to_have_text("Mindray CL-900i")
    expect(unknown_date_card.locator(".device-evidence-reviewed")).to_have_text(
        "Evidence review date not recorded"
    )
    with page.expect_download() as unknown_date_download_info:
        page.get_by_role("button", name="Export filtered leads CSV").click()
    unknown_date_file = Path(unknown_date_download_info.value.path())
    with unknown_date_file.open(encoding="utf-8-sig", newline="") as csv_file:
        unknown_date_rows = list(csv.reader(csv_file))
    assert len(unknown_date_rows) == 2
    assert unknown_date_rows[1][0] == "mindray-cl900i"
    assert "evidence reviewed:" not in unknown_date_rows[1][5]
    date_filter.select_option("")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 9 of 9 discovery leads."
    )

    page.locator("#device-catalog-search").fill("cia 600")
    cia600_card = page.locator("#device-catalog .device-catalog-card")
    expect(cia600_card.locator("strong")).to_have_text("Zecen CIA 600")
    expect(cia600_card.get_by_role("link")).to_have_text("Seller listing (availability only)")
    expect(cia600_card.locator("small")).to_contain_text("LIS/networking claims are unverified")
    expect(cia600_card.locator(".device-evidence-reviewed")).to_have_text(
        "Evidence reviewed: 2026-10-14"
    )
    page.locator("#device-catalog-search").fill("cia 1200")
    cia1200_card = page.locator("#device-catalog .device-catalog-card")
    expect(cia1200_card.locator("strong")).to_have_text("Zecen CIA 1200")
    expect(cia1200_card.locator(".catalog-status")).to_have_text("Discovery only")
    page.locator("#device-catalog-search").fill("imagic m7")
    chemistry_card = page.locator("#device-catalog .device-catalog-card")
    expect(chemistry_card.locator("strong")).to_have_text("ICUBIO iMagic M7")
    expect(chemistry_card.locator("small")).to_contain_text("RS-232/PC connectivity")
    expect(chemistry_card.locator(".device-evidence-reviewed")).to_have_text(
        "Evidence reviewed: 2026-10-14"
    )
    page.locator("#device-catalog-search").fill("cts-3000")
    celltus_card = page.locator("#device-catalog .device-catalog-card")
    expect(celltus_card.locator("strong")).to_have_text("Celltus CTS-3000")
    expect(celltus_card.get_by_role("link")).to_have_text("Seller listing (availability only)")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 1 of 9 discovery leads."
    )
    page.locator("#device-catalog-search").fill("cts-5000")
    supplier_category_card = page.locator("#device-catalog .device-catalog-card")
    expect(supplier_category_card.locator("strong")).to_have_text("Celltus CTS-5000")
    expect(supplier_category_card.locator(".device-evidence-tag")).to_have_text(
        "Bangladesh supplier category"
    )
    expect(supplier_category_card.get_by_role("link")).to_have_text(
        "Supplier category (discovery only)"
    )
    page.locator("#device-catalog-search").fill("")
    page.locator("#device-catalog-family-filter").select_option("clinical_chemistry")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 1 of 9 discovery leads."
    )
    expect(page.locator("#device-catalog .device-catalog-card")).to_have_count(1)
    page.locator("#device-catalog-family-filter").select_option("immunoassay")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 3 of 9 discovery leads."
    )
    expect(page.locator("#device-catalog .device-catalog-card")).to_have_count(3)
    page.locator("#device-catalog-family-filter").select_option("hematology")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 5 of 9 discovery leads."
    )
    expect(page.locator("#device-catalog .device-catalog-card")).to_have_count(5)

    page.locator("#device-catalog-evidence-filter").select_option("bangladesh_facility_self_report")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 1 of 9 discovery leads."
    )
    facility_card = page.locator("#device-catalog .device-catalog-card")
    expect(facility_card.locator("strong")).to_have_text("Sysmex XN-3000")
    expect(facility_card.locator(".device-evidence-tag")).to_have_text(
        "Bangladesh facility self-report"
    )
    expect(facility_card.locator(".catalog-status")).to_have_text("Discovery only")
    expect(facility_card.locator(".device-evidence-reviewed")).to_have_text(
        "Evidence reviewed: 2026-10-13"
    )
    expect(facility_card.get_by_role("link")).to_have_text(
        "Facility self-report · not independently verified"
    )
    expect(page.locator("#profile-candidate-id option")).to_have_count(10)

    page.locator("#device-catalog-search").fill("xn-3000")
    expect(page.locator("#device-catalog .device-catalog-card")).to_have_count(1)
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export filtered leads CSV").click()
    download = download_info.value
    assert download.suggested_filename == "medihub-device-discovery-leads.csv"
    with Path(download.path()).open(encoding="utf-8-sig", newline="") as exported_file:
        exported_rows = list(csv.reader(exported_file))
    assert exported_rows[0] == [
        "candidate_id",
        "manufacturer",
        "model",
        "device_family",
        "discovery_basis",
        "evidence_note",
        "source_url",
        "status",
        "compatibility_verified",
        "live_adapter_available",
    ]
    assert len(exported_rows) == 2
    assert exported_rows[1][0:5] == [
        "sysmex-xn-3000",
        "Sysmex",
        "XN-3000",
        "hematology",
        "bangladesh_facility_self_report",
    ]
    assert exported_rows[1][5] == (
        "Facility page self-reports an installation; not independently verified. "
        "[evidence reviewed: 2026-10-13]"
    )
    assert exported_rows[1][6] == "https://example.invalid/facility-report"
    assert exported_rows[1][7:] == ["discovery_only", "false", "false"]
    assert not {"site_ref", "host", "port", "endpoint", "credentials"} & set(exported_rows[0])
    expect(page.locator("#device-catalog-export-status")).to_have_text(
        "Exported 1 filtered discovery leads to CSV. No survey responses were included."
    )
    page.locator("#device-catalog-date-filter").select_option("unknown")
    page.locator("#device-catalog-search").fill("no matching model")
    expect(page.locator("#device-catalog .device-catalog-card")).to_have_count(0)
    expect(page.locator("#device-catalog")).to_contain_text(
        "No discovery leads match the current filters."
    )
    expect(page.get_by_role("button", name="Export filtered leads CSV")).to_be_disabled()

    page.get_by_role("button", name="Clear filters").click()
    expect(page.locator("#device-catalog-search")).to_have_value("")
    expect(page.locator("#device-catalog-family-filter")).to_have_value("")
    expect(page.locator("#device-catalog-evidence-filter")).to_have_value("")
    expect(page.locator("#device-catalog-date-filter")).to_have_value("")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "Showing 9 of 9 discovery leads."
    )
    expect(page.locator("#device-catalog .device-catalog-card")).to_have_count(9)
    expect(page.get_by_role("button", name="Export filtered leads CSV")).to_be_enabled()

    page.locator("#language-select").select_option("bn")
    expect(page.locator(".device-catalog-export-note")).to_contain_text(
        "জানা প্রমাণ-যাচাইয়ের তারিখ evidence_note কলামে যোগ হয়"
    )
    bengali_target_card = page.locator("#device-catalog .device-catalog-card").filter(
        has_text="Mindray CL-900i"
    )
    expect(bengali_target_card.locator(".device-evidence-reviewed")).to_have_text(
        "প্রমাণ যাচাইয়ের তারিখ নথিভুক্ত নয়"
    )
    bengali_dated_card = page.locator("#device-catalog .device-catalog-card").filter(
        has_text="Zecen CIA 600"
    )
    expect(bengali_dated_card.locator(".device-evidence-reviewed")).to_have_text(
        "প্রমাণ যাচাই: 2026-10-14"
    )
    expect(page.locator("#device-catalog-search")).to_have_attribute(
        "placeholder", "যেমন Mindray বা XN-3000"
    )
    expect(page.get_by_role("button", name="ফিল্টার মুছুন")).to_be_visible()
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "মোট ৯টির মধ্যে ৯টি অনুসন্ধান-সূত্র দেখানো হচ্ছে।"
    )
    bengali_date_filter = page.locator("#device-catalog-date-filter")
    expect(bengali_date_filter.locator("option[value='recorded']")).to_have_text(
        "যাচাইয়ের তারিখ নথিভুক্ত"
    )
    expect(bengali_date_filter.locator("option[value='unknown']")).to_have_text(
        "যাচাইয়ের তারিখ নথিভুক্ত নয়"
    )
    bengali_date_filter.select_option("unknown")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "মোট ৯টির মধ্যে ১টি অনুসন্ধান-সূত্র দেখানো হচ্ছে।"
    )
    expect(page.locator("#device-catalog .device-catalog-card strong")).to_have_text(
        "Mindray CL-900i"
    )
    bengali_date_filter.select_option("recorded")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "মোট ৯টির মধ্যে ৮টি অনুসন্ধান-সূত্র দেখানো হচ্ছে।"
    )
    bengali_date_filter.select_option("")
    expect(page.locator("#device-catalog-result-count")).to_have_text(
        "মোট ৯টির মধ্যে ৯টি অনুসন্ধান-সূত্র দেখানো হচ্ছে।"
    )
    with page.expect_download() as bengali_download_info:
        page.get_by_role("button", name="ফিল্টার করা সূত্র CSV রপ্তানি করুন").click()
    assert bengali_download_info.value.suggested_filename == "medihub-device-discovery-leads.csv"
    expect(page.locator("#device-catalog-export-status")).to_have_text(
        "৯টি ফিল্টার করা ডিভাইস-সূত্র CSV-তে রপ্তানি হয়েছে; কোনো প্রতিষ্ঠানের জরিপের উত্তর অন্তর্ভুক্ত হয়নি।"
    )


def test_bangladesh_device_library_saves_non_connectable_cl900i_profile(
    page: Page,
) -> None:
    page.goto(f"{BASE_URL}/devices", wait_until="domcontentloaded")

    cl900i_card = page.locator("#device-catalog .device-catalog-card").filter(
        has_text="Mindray CL-900i"
    )
    expect(cl900i_card.locator("strong")).to_have_text("Mindray CL-900i")
    expect(cl900i_card.locator(".catalog-status")).to_have_text("Discovery only")
    expect(cl900i_card.locator(".device-profile-link-status")).to_have_text(
        "No linked discovery profile."
    )
    cl900i_card.get_by_role("button", name="Use in profile").click()
    expect(page.locator("#profile-manufacturer")).to_have_value("Mindray")
    expect(page.locator("#profile-model")).to_have_value("CL-900i")
    expect(page.locator("#profile-family")).to_have_value("immunoassay")
    expect(page.locator("#profile-transport")).to_have_value("unconfirmed")
    expect(page.locator("#profile-protocol")).to_have_value("unconfirmed")
    page.locator("#profile-document-ref").fill("SYNTH-DOC-REF-001")

    for forbidden_name in ("host", "port", "password", "api_key", "endpoint", "credentials"):
        expect(page.locator(f"#device-profile-form [name='{forbidden_name}']")).to_have_count(0)

    page.get_by_role("button", name="Save discovery profile").click()
    expect(page.locator("#device-profile-status")).to_contain_text(
        "no hardware connection was made"
    )
    expect(page.locator("#device-profile-list")).to_contain_text("Mindray CL-900i · unknown")
    expect(page.locator("#device-profile-list")).to_contain_text("discovery only")
    profile_search = page.locator("#device-profile-search")
    profile_filter = page.locator("#device-profile-evidence-filter")
    expect(page.locator("#device-profile-result-count")).to_have_text(
        "Showing 1 of 1 discovery profiles."
    )
    profile_search.fill("SYNTH-DOC-REF-001")
    expect(page.locator("#device-profile-result-count")).to_have_text(
        "Showing 0 of 1 discovery profiles."
    )
    profile_search.fill("mindray-cl900i")
    expect(page.locator("#device-profile-result-count")).to_have_text(
        "Showing 1 of 1 discovery profiles."
    )
    profile_search.fill("NO-SUCH-PROFILE")
    expect(page.locator("#device-profile-result-count")).to_have_text(
        "Showing 0 of 1 discovery profiles."
    )
    expect(page.locator("#device-profile-list")).to_contain_text(
        "No discovery profiles match the current filters."
    )
    profile_search.fill("")
    profile_filter.select_option("missing")
    expect(page.locator("#device-profile-result-count")).to_have_text(
        "Showing 1 of 1 discovery profiles."
    )
    profile_filter.select_option("recorded")
    expect(page.locator("#device-profile-result-count")).to_have_text(
        "Showing 0 of 1 discovery profiles."
    )
    page.get_by_role("button", name="Clear profile filters").click()
    expect(profile_filter).to_have_value("")
    expect(page.locator("#device-profile-result-count")).to_have_text(
        "Showing 1 of 1 discovery profiles."
    )
    expect(cl900i_card.locator(".device-profile-link-status")).to_have_text(
        "Linked discovery profiles: 1. This is not a support status."
    )
    expect(cl900i_card.get_by_role("button", name="Use in profile")).to_have_count(0)
    cl900i_card.get_by_role("button", name="Edit linked profile").click()
    expect(page.locator("#device-profile-id")).to_have_value("00000000-0000-0000-0000-000000000001")
    expect(page.locator("#save-device-profile")).to_have_text("Update discovery profile")
    expect(page.locator("#device-profile-list details summary")).to_have_text(
        "Readiness checklist (1/9 evidence gates recorded)"
    )
    page.locator("#device-profile-list details summary").click()
    expect(page.locator("#device-profile-list details li")).to_have_count(11)
    expect(page.locator("#device-profile-list details li[data-status='not_run']")).to_contain_text(
        "Synthetic validation"
    )

    page.locator("#language-select").select_option("bn")
    expect(cl900i_card.locator(".device-profile-link-status")).to_have_text(
        "এই অনুসন্ধান-সূত্রের সঙ্গে ১টি প্রোফাইল যুক্ত। এটি ডিভাইস-সমর্থনের অবস্থা নয়।"
    )
    expect(cl900i_card.get_by_role("button", name="যুক্ত প্রোফাইল সম্পাদনা করুন")).to_be_visible()
    expect(
        page.get_by_role("searchbox", name="মডেল, ফার্মওয়্যার, প্রোটোকল বা candidate ID খুঁজুন")
    ).to_be_visible()
    expect(page.get_by_role("combobox", name="প্রমাণ-ধাপ ফিল্টার")).to_be_visible()
    expect(page.locator("#device-profile-result-count")).to_have_text(
        "মোট ১টি অনুসন্ধান প্রোফাইলের মধ্যে ১টি দেখানো হচ্ছে।"
    )
    expect(profile_filter.locator("option[value='recorded']")).to_have_text("নয়টি প্রমাণ-ধাপ নথিভুক্ত")


def test_mapping_api_and_help_pages_remain_readable_on_mobile(page: Page) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE_URL}/mappings", wait_until="domcontentloaded")
    page.locator("#language-select").select_option("bn")

    expect(page.locator("#mapping-workbench-heading")).to_have_text("ডেটা ম্যাপিং")
    expect(page.locator("#reset-mappings")).to_have_text("ডেমো নিয়ম রিসেট করুন")
    expect(page.locator("#mapping-operation option[value='identity']")).to_have_text("অপরিবর্তিত")
    expect(page.locator("#mapping-test-summary")).to_contain_text("চালানো হয়নি")

    page.goto(f"{BASE_URL}/api-setup", wait_until="domcontentloaded")
    expect(page.locator("#page-title")).to_have_text("EMR / EMS API")
    expect(page.locator(".locked-note")).to_contain_text("সংযোগ API-এর নিয়ন্ত্রণগুলো বন্ধ রাখা হয়েছে।")
    expect(page.locator("#destination-api-profile-form")).to_be_visible()
    expect(page.locator("#destination-profile-target")).to_have_value("emr_fhir_r4")
    expect(page.locator("#destinations-list strong")).to_have_text(
        "প্রসেসের ভেতরের FHIR R4 পরীক্ষামূলক রিসিভার · প্রস্তুত"
    )
    expect(page.locator("#destinations-list small")).to_have_text(
        "FHIR R4 · প্রসেসের ভেতরে · নেটওয়ার্ক বন্ধ · এন্ডপয়েন্ট বা পরিচয়-প্রমাণের ক্ষেত্র নেই"
    )
    expect(page.locator("#fhir-api-readiness summary")).to_have_text(
        "API প্রস্তুতি তালিকা (0/11টি প্রমাণ-ধাপ নথিভুক্ত)"
    )
    page.locator("#fhir-api-readiness summary").click()
    expect(page.locator("#fhir-api-readiness li")).to_have_count(13)
    expect(page.locator("#fhir-api-readiness li[data-status='not_run']")).to_contain_text(
        "সিন্থেটিক যাচাই"
    )
    page.locator("#preview-fhir-observation").click()
    expect(page.locator("#fhir-preview-status")).to_have_text(
        "সিন্থেটিক প্রিভিউ স্থানীয়ভাবে তৈরি হয়েছে; পাঠানো হয়নি এবং প্রতিষ্ঠানের চুক্তির বিপরীতে যাচাই হয়নি।"
    )
    expect(page.locator("#fhir-preview-details")).to_be_visible()
    expect(page.locator("#fhir-preview-resource")).to_contain_text('"resourceType": "Observation"')

    page.locator("#run-fhir-synthetic-validation").click()
    expect(page.locator("#fhir-validation-status")).to_contain_text("স্থানীয় fixture পাস করেছে")
    expect(page.locator("#fhir-validation-status")).to_contain_text("সাইট অনুমোদনের দাবি নয়")
    expect(page.locator("#fhir-validation-details")).to_be_visible()
    expect(page.locator("#fhir-validation-report")).to_contain_text("fixture_output_matches")
    expect(
        page.locator("#fhir-api-readiness li[data-status='local_fixture_passed']")
    ).to_contain_text("স্থানীয় fixture পাস করেছে")
    expect(page.locator("#hl7-api-readiness li[data-status='not_run']")).to_contain_text(
        "চালানো হয়নি"
    )

    expect(page.locator("#delivery-fault-status")).to_have_text(
        "কোনো ডেলিভারি ত্রুটি নির্ধারিত নেই। মোট তৈরি: 0। নেটওয়ার্ক বন্ধ।"
    )

    page.goto(f"{BASE_URL}/help", wait_until="domcontentloaded")
    expect(page.locator("#help-title")).to_have_text("১. এই প্রিভিউতে MediHub কী করে")
    expect(page.locator("#help-content")).to_contain_text("বাংলাদেশে ডিপ্লয়মেন্টের বিবেচনা")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

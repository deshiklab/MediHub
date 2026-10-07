"""Real-browser checks for dashboard language switching and localized workflows."""

from __future__ import annotations

import json
from collections.abc import Iterator
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

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    current_device = {"enabled": True}

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
                    ]
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
        "মাল্টিপ্যারামিটার মনিটর"
    )
    expect(page.locator("#devices-list .device-row small")).to_contain_text("শুধু সিন্থেটিক")
    expect(page.get_by_role("button", name="নিষ্ক্রিয় করুন")).to_be_visible()

    page.get_by_role("button", name="নিষ্ক্রিয় করুন").click()
    expect(page.locator("#device-status")).to_contain_text(
        "sim-device-001 এখন শুধু স্থানীয় সিমুলেটরে নিষ্ক্রিয়।"
    )
    page.get_by_role("button", name="সক্রিয় করুন").click()
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
    expect(page.locator("#destinations-list strong")).to_have_text(
        "প্রসেসের ভেতরের FHIR R4 পরীক্ষামূলক রিসিভার · প্রস্তুত"
    )
    expect(page.locator("#destinations-list small")).to_have_text(
        "FHIR R4 · প্রসেসের ভেতরে · নেটওয়ার্ক বন্ধ · এন্ডপয়েন্ট বা পরিচয়-প্রমাণের ক্ষেত্র নেই"
    )
    expect(page.locator("#delivery-fault-status")).to_have_text(
        "কোনো ডেলিভারি ত্রুটি নির্ধারিত নেই। মোট তৈরি: 0। নেটওয়ার্ক বন্ধ।"
    )

    page.goto(f"{BASE_URL}/help", wait_until="domcontentloaded")
    expect(page.locator("#help-title")).to_have_text("১. এই প্রিভিউতে MediHub কী করে")
    expect(page.locator("#help-content")).to_contain_text("বাংলাদেশে ডিপ্লয়মেন্টের বিবেচনা")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

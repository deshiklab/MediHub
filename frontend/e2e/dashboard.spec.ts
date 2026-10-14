import { readFile } from "node:fs/promises";
import { expect, test, type Page, type Route } from "@playwright/test";

const snapshot = {
  mode: "synthetic_demo",
  ready: true,
  updated_at: "2026-10-07T04:00:00+00:00",
  source: {
    adapter_id: "medihub.synthetic-device",
    status: "healthy",
    detail_code: "synthetic_source_healthy",
  },
  receiver: { status: "in_process" },
  totals: {
    events_inserted: 12,
    duplicate_events: 3,
    delivery_attempts: 14,
    acknowledged_deliveries: 10,
    pending_deliveries: 1,
    blocked_routes: 2,
  },
  recent_events: [
    {
      event_id: "test-event-0001",
      device_id: "sim-device-001",
      received_at: "2026-10-07T04:00:00+00:00",
      label: "Synthetic scalar",
      value: 72.5,
    },
  ],
  recent_deliveries: [
    {
      event_id: "test-event-0001",
      status: "acknowledged",
      attempts: 1,
      updated_at: "2026-10-07T04:00:01+00:00",
    },
    {
      event_id: "test-event-0003",
      status: "retryable_failure",
      attempts: 2,
      updated_at: "2026-10-07T04:00:02+00:00",
    },
  ],
  recent_holds: [{ event_id: "test-event-0002", reason_code: "synthetic_not_accepted" }],
};

function discoveryCandidate(candidate: {
  candidate_id: string;
  manufacturer: string;
  model: string;
  device_family: string;
  discovery_basis: string;
  evidence_note: string;
  source_url: string | null;
  evidence_reviewed_on: string | null;
}) {
  return {
    ...candidate,
    status: "discovery_only",
    compatibility_verified: false,
    live_adapter_available: false,
  };
}

const deviceLibrarySnapshot = {
  mode: "synthetic_only",
  country_focus: "BD",
  candidate_count: 5,
  installed_base_ranked: false,
  physical_device_connections_enabled: false,
  endpoint_fields_supported: false,
  credential_fields_supported: false,
  device_adapters: [
    {
      adapter_id: "medihub.synthetic-device",
      label: "Deterministic synthetic simulator",
      status: "available_for_local_demo",
      connects_to_physical_device: false,
    },
    {
      adapter_id: "offline-astm-e1394-parser-scaffold",
      label: "Offline ASTM E1394 record parser scaffold",
      status: "parser_only_no_transport_or_model_profile",
      connects_to_physical_device: false,
    },
  ],
  candidates: [
    discoveryCandidate({
      candidate_id: "mindray-cl900i",
      manufacturer: "Mindray",
      model: "CL-900i",
      device_family: "immunoassay",
      discovery_basis: "user_selected_target",
      evidence_note: "User-selected integration target; installed base, firmware, and host interface are unverified.",
      source_url: null,
      evidence_reviewed_on: null,
    }),
    discoveryCandidate({
      candidate_id: "zecen-cia-600",
      manufacturer: "Zecen",
      model: "CIA 600",
      device_family: "immunoassay",
      discovery_basis: "bangladesh_seller_listing",
      evidence_note: "Seller page lists the model; networking claims and installed base are unverified.",
      source_url: "https://www.medistorebd.com/product/cia-600-automic-chemiluminescence-analyzer/",
      evidence_reviewed_on: "2026-10-14",
    }),
    discoveryCandidate({
      candidate_id: "mindray-bc-20s",
      manufacturer: "Mindray",
      model: "BC-20s",
      device_family: "hematology",
      discovery_basis: "bangladesh_seller_listing",
      evidence_note: "Bangladesh seller listing only; not evidence of installed-base prevalence or connectivity.",
      source_url: "https://www.medistorebd.com/product/hematology-analyzer-bc-20s/",
      evidence_reviewed_on: "2026-10-11",
    }),
    discoveryCandidate({
      candidate_id: "survey-hba1c",
      manufacturer: "To be confirmed",
      model: "HbA1c analyzer to survey",
      device_family: "hba1c",
      discovery_basis: "bangladesh_supplier_category",
      evidence_note: "Supplier-category lead for field survey; no model or installed equipment has been confirmed.",
      source_url: null,
      evidence_reviewed_on: null,
    }),
    discoveryCandidate({
      candidate_id: "sysmex-xn-3000",
      manufacturer: "Sysmex",
      model: "XN-3000",
      device_family: "hematology",
      discovery_basis: "bangladesh_facility_self_report",
      evidence_note: "Facility self-report; model, firmware, interface, and host behavior require confirmation.",
      source_url: null,
      evidence_reviewed_on: "2026-10-09",
    }),
  ],
};

async function installSyntheticApiStub(page: Page) {
  await page.route("**/*", async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/dashboard") {
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify(snapshot),
      });
      return;
    }
    if (url.pathname === "/api/management/device-library") {
      await route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify(deviceLibrarySnapshot),
      });
      return;
    }
    if (url.hostname === "localhost" || url.hostname === "127.0.0.1") {
      await route.continue();
      return;
    }
    await route.abort();
  });
}

test.beforeEach(async ({ page }) => {
  await installSyntheticApiStub(page);
  await page.goto("/");
  // The server-rendered select is actionable before Next.js hydrates its onChange handler.
  // Wait for client-side API fetches before checking hydrated dashboard content.
  await expect(page.locator(".metric-card").first().locator("strong")).toHaveText("12");
  await expect(page.getByTestId("bd-discovery-total")).toHaveText("5");
});

test("renders the live synthetic overview and accessible status", async ({ page }) => {
  await expect(page.getByRole("heading", { level: 1, name: "Integration operations" })).toBeVisible();
  await expect(page.locator(".metric-card").first().locator("strong")).toHaveText("12");
  await expect(page.locator("tbody .reading")).toHaveText("72.50");
  await expect(page.locator(".delivery-copy strong").first()).toHaveText("Acknowledged");
  await expect(page.locator(".delivery-copy strong").nth(1)).toHaveText("Retryable failure");
  await expect(page.getByRole("combobox", { name: "Interface language" })).toBeVisible();
  await expect(page.getByText("This preview uses generated synthetic values only;", { exact: false })).toBeVisible();
});

test("summarizes Bangladesh discovery evidence without implying support", async ({ page }) => {
  await expect(
    page.getByRole("heading", { level: 2, name: "Bangladesh device discovery" }),
  ).toBeVisible();
  await expect(page.getByTestId("bd-discovery-total")).toHaveText("5");
  await expect(page.getByTestId("bd-discovery-user-selected")).toHaveText("1");
  await expect(page.getByTestId("bd-discovery-seller-listings")).toHaveText("2");
  await expect(page.getByTestId("bd-discovery-supplier-categories")).toHaveText("1");
  await expect(page.getByTestId("bd-discovery-facility-reports")).toHaveText("1");
  await expect(page.getByText(
    "These entries are discovery leads only—not installed-base counts, verified compatibility, or supported drivers.",
    { exact: true },
  )).toBeVisible();
  await expect(page.getByText("Physical-device connections remain disabled in this preview.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Browse Bangladesh leads" })).toHaveAttribute("href", "/bangladesh-devices");
});

test("browses Bangladesh discovery leads with local search and safe metadata filters", async ({ page }) => {
  await page.getByRole("link", { name: "Browse Bangladesh leads" }).click();

  await expect(page).toHaveURL(/\/bangladesh-devices$/);
  await expect(page.getByRole("heading", { level: 1, name: "Browse device discovery leads" })).toBeVisible();
  await expect(page.getByTestId("device-result-card")).toHaveCount(5);
  await expect(page.getByTestId("device-results-count")).toHaveText("Showing 5 of 5 discovery leads");
  await expect(page.getByText(
    "These records are not installed-base estimates, verified compatibility, supported drivers, or proof of current market availability.",
    { exact: false },
  )).toBeVisible();

  const search = page.getByRole("searchbox", {
    name: "Search manufacturer, model, family, or evidence note",
  });
  await search.fill("Zecen");
  await expect(page.getByTestId("device-results-count")).toHaveText("Showing 2 of 5 discovery leads");
  await expect(page.getByRole("heading", { level: 3, name: "Zecen CIA 600" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "Zecen CIA 1200" })).toBeVisible();

  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByRole("combobox", { name: "Device family" }).selectOption("hematology");
  await expect(page.getByTestId("device-results-count")).toHaveText("Showing 2 of 5 discovery leads");
  await page.getByRole("combobox", { name: "Evidence basis" }).selectOption("bangladesh_seller_listing");
  await expect(page.getByTestId("device-results-count")).toHaveText("Showing 1 of 5 discovery leads");
  await expect(page.getByRole("heading", { level: 3, name: "Mindray BC-20s" })).toBeVisible();

  await page.getByRole("button", { name: "Clear filters" }).click();
  const catalogDate = page.getByRole("combobox", { name: "Catalog date metadata" });
  await catalogDate.selectOption("recorded");
  await expect(page.getByTestId("device-results-count")).toHaveText("Showing 3 of 5 discovery leads");
  await expect(page.getByText("2026-10-14", { exact: true })).toHaveCount(0);
  await catalogDate.selectOption("not-recorded");
  await expect(page.getByTestId("device-results-count")).toHaveText("Showing 2 of 5 discovery leads");
  await expect(page.getByText(
    "A recorded catalog date is metadata only.",
    { exact: false },
  )).toBeVisible();
  await search.fill("NO-SUCH-DISCOVERY-LEAD");
  await expect(page.getByTestId("device-results-count")).toHaveText("Showing 0 of 5 discovery leads");
  await expect(page.getByRole("button", { name: "Export filtered leads CSV" })).toBeDisabled();
});

test("exports only filtered discovery leads with CSV formula protection and scope metadata", async ({ page }) => {
  await page.route("**/api/management/device-library", async (route) => {
    const exportLibrary = structuredClone(deviceLibrarySnapshot);
    exportLibrary.candidates[0].evidence_note = " =HYPERLINK(\"https://example.invalid\",\"formula\")";
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(exportLibrary),
    });
  });
  await page.goto("/bangladesh-devices");

  const search = page.getByRole("searchbox", {
    name: "Search manufacturer, model, family, or evidence note",
  });
  await search.fill("Mindray");
  await expect(page.getByTestId("device-results-count")).toHaveText("Showing 2 of 5 discovery leads");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export filtered leads CSV" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("medihub-bangladesh-device-discovery-leads.csv");
  const downloadPath = await download.path();
  if (!downloadPath) throw new Error("CSV download path was not created");
  const csv = await readFile(downloadPath, "utf8");

  expect(csv.startsWith("\uFEFF")).toBe(true);
  expect(csv).toContain("catalog_date_metadata_recorded");
  expect(csv).toContain("scope_limit");
  expect(csv).toContain("mindray-cl900i");
  expect(csv).toContain("mindray-bc-20s");
  expect(csv).not.toContain("zecen-cia-600");
  expect(csv).toContain("' =HYPERLINK");
  expect(csv).toContain("compatibility_verified");
  expect(csv).not.toContain("2026-10-14");
  await expect(page.getByText(
    "Exported 2 visible discovery leads to CSV. No exact catalog dates or survey responses were included.",
    { exact: true },
  )).toBeVisible();
});

test("localizes the Bangladesh discovery page and keeps its filters usable on mobile", async ({ page }) => {
  await page.getByRole("link", { name: "Browse Bangladesh leads" }).click();
  await page.getByRole("combobox", { name: "Interface language" }).selectOption("bn");

  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await expect(page.getByRole("heading", { level: 1, name: "ডিভাইস অনুসন্ধানের সূত্র দেখুন" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "ইন্টারফেসের ভাষা" })).toBeVisible();
  await expect(page.getByText("এগুলো শুধু অনুসন্ধানের সূত্র।", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "তথ্যের ভিত্তি" })).toBeVisible();
  await expect(page.getByRole("button", { name: "ফিল্টার করা সূত্রের CSV রপ্তানি করুন" })).toBeVisible();

  await page.getByRole("combobox", { name: "ডিভাইসের ধরন" }).selectOption("hematology");
  await expect(page.getByTestId("device-results-count")).toHaveText("৫টি অনুসন্ধান-সূত্রের মধ্যে ২টি দেখানো হচ্ছে");
  const bengaliDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "ফিল্টার করা সূত্রের CSV রপ্তানি করুন" }).click();
  const bengaliDownload = await bengaliDownloadPromise;
  const bengaliPath = await bengaliDownload.path();
  if (!bengaliPath) throw new Error("Bengali CSV download path was not created");
  const bengaliCsv = await readFile(bengaliPath, "utf8");
  expect(bengaliCsv).toContain("শুধু অনুসন্ধানের সূত্র; স্থাপিত ডিভাইসের প্রচলন");
  for (const width of [320, 360, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(page.getByRole("navigation", { name: "MediHub-এর পৃষ্ঠাগুলো" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("fails closed if discovery data leaves the synthetic-only scope", async ({ page }) => {
  await page.route("**/api/management/device-library", async (route) => {
    const unsafeLibrary = structuredClone(deviceLibrarySnapshot);
    unsafeLibrary.candidates[0].compatibility_verified = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(unsafeLibrary),
    });
  });
  await page.goto("/bangladesh-devices");

  await expect(page.getByRole("alert")).toContainText("outside the approved synthetic-only scope");
  await expect(page.getByTestId("device-result-card")).toHaveCount(0);
});

test("switches language and remembers Bengali after reload", async ({ page }) => {
  await page.getByRole("combobox", { name: "Interface language" }).selectOption("bn");

  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await expect(page.getByRole("heading", { level: 1, name: "ইন্টিগ্রেশন কার্যক্রম" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "ইন্টারফেসের ভাষা" })).toBeVisible();
  await expect(page.getByText("সিন্থেটিক কার্যক্রম", { exact: true })).toBeVisible();
  await expect(page.locator(".delivery-copy strong").first()).toHaveText("রিসিভার গ্রহণ করেছে");
  await expect(page.locator(".delivery-copy strong").nth(1)).toHaveText("ব্যর্থ—আবার চেষ্টা করা যাবে");
  await expect(page.getByText("বাংলাদেশে স্থাপন করাই MediHub-এর লক্ষ্য;", { exact: false })).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 2, name: "বাংলাদেশি ডিভাইস অনুসন্ধান" }),
  ).toBeVisible();
  await expect(page.getByTestId("bd-discovery-total")).toHaveText("৫");
  await expect(page.getByText(
    "এগুলো শুধু অনুসন্ধানের সূত্র—স্থাপিত ডিভাইসের সংখ্যা, যাচাইকৃত সামঞ্জস্য বা সমর্থিত ড্রাইভারের তালিকা নয়।",
    { exact: true },
  )).toBeVisible();

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await expect(page.getByRole("heading", { level: 1, name: "ইন্টিগ্রেশন কার্যক্রম" })).toBeVisible();
});

test("keeps the Bengali page within common mobile widths", async ({ page }) => {
  await page.getByRole("combobox", { name: "Interface language" }).selectOption("bn");
  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  for (const width of [320, 360, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(page.getByRole("navigation", { name: "ড্যাশবোর্ডের পৃষ্ঠা" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("shows synthetic lab results as pending and never verifies or releases them", async ({ page }) => {
  await page.getByRole("link", { name: "Lab review (demo)" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "Synthetic lab-result review" })).toBeVisible();
  await expect(page.getByText("SYNTH-ACC-1001").first()).toBeVisible();
  await expect(page.getByText("Pending technician review").first()).toBeVisible();
  await expect(page.getByText("No patient data is present.", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Open demo details" }).first().click();
  await expect(page.getByText("No reference interval or clinical interpretation is supplied.")).toBeVisible();
  await page.getByRole("button", { name: "Acknowledge demo view" }).click();
  await expect(page.getByText(
    "Viewed in this browser only. The result remains pending and unverified.",
    { exact: true },
  )).toBeVisible();
  await expect(page.getByRole("button", { name: /verify|finalize|release|send/i })).toHaveCount(0);
});

test("filters synthetic review rows using only browser-local view acknowledgement", async ({ page }) => {
  await page.getByRole("link", { name: "Lab review (demo)" }).click();

  const search = page.getByRole("searchbox", {
    name: "Search synthetic accession, assay, or source ID",
  });
  const acknowledgementFilter = page.getByRole("combobox", {
    name: "Local view acknowledgement",
  });

  await expect(page.getByText("Showing 3 of 3 synthetic records.", { exact: true })).toBeVisible();
  await search.fill("demo-assay-b");
  await expect(page.getByText("Showing 1 of 3 synthetic records.", { exact: true })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "SYNTH-ACC-1002" })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "SYNTH-ACC-1001" })).toHaveCount(0);

  await search.fill("NO-SUCH-SYNTHETIC-RECORD");
  await expect(page.getByText("Showing 0 of 3 synthetic records.", { exact: true })).toBeVisible();
  await expect(page.getByText("No synthetic rows match the current search and filter.")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByText("Showing 3 of 3 synthetic records.", { exact: true })).toBeVisible();

  await page.getByRole("row").filter({ hasText: "SYNTH-ACC-1001" })
    .getByRole("button", { name: "Open demo details" }).click();
  await page.getByRole("button", { name: "Acknowledge demo view" }).click();
  await expect(page.getByText("The result remains pending and unverified.", { exact: false })).toBeVisible();

  await acknowledgementFilter.selectOption("viewed");
  await expect(page.getByText("Showing 1 of 3 synthetic records.", { exact: true })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "SYNTH-ACC-1001" })).toBeVisible();
  await acknowledgementFilter.selectOption("not-viewed");
  await expect(page.getByText("Showing 2 of 3 synthetic records.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /verify|finalize|release|send/i })).toHaveCount(0);

  await page.reload();
  await expect(page.getByText("Showing 3 of 3 synthetic records.", { exact: true })).toBeVisible();
  await expect(page.getByText("Pending technician review").first()).toBeVisible();
});

test("supports Bengali lab-review copy and keeps the table within mobile viewport", async ({ page }) => {
  await page.getByRole("link", { name: "Lab review (demo)" }).click();
  await page.getByRole("combobox", { name: "Interface language" }).selectOption("bn");

  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await expect(page.getByRole("heading", { level: 1, name: "সিন্থেটিক ল্যাব ফলাফল পর্যালোচনা" })).toBeVisible();
  await expect(page.getByText("ল্যাব টেকনিশিয়ানের পর্যালোচনার অপেক্ষায়").first()).toBeVisible();
  const search = page.getByRole("searchbox", {
    name: "সিন্থেটিক accession, অ্যাসে বা উৎসের ID খুঁজুন",
  });
  await expect(page.getByRole("combobox", { name: "এই ব্রাউজারে দেখার স্বীকৃতি" })).toBeVisible();
  await search.fill("NO-SUCH-SYNTHETIC-RECORD");
  await expect(page.getByText("মোট ৩টি সিন্থেটিক রেকর্ডের মধ্যে ০টি দেখানো হচ্ছে।", { exact: true })).toBeVisible();
  await expect(page.getByText("বর্তমান অনুসন্ধান ও ফিল্টারে কোনো সিন্থেটিক সারি মেলেনি।")).toBeVisible();
  await page.getByRole("button", { name: "ফিল্টার মুছুন" }).click();
  for (const width of [320, 360, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(page.getByRole("navigation", { name: "ড্যাশবোর্ডের পৃষ্ঠা" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

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

test("switches language and remembers Bengali after reload", async ({ page }) => {
  await page.getByRole("combobox", { name: "Interface language" }).selectOption("bn");

  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await expect(page.getByRole("heading", { level: 1, name: "ইন্টিগ্রেশন কার্যক্রম" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "ইন্টারফেসের ভাষা" })).toBeVisible();
  await expect(page.getByText("সিন্থেটিক কার্যক্রম", { exact: true })).toBeVisible();
  await expect(page.locator(".delivery-copy strong").first()).toHaveText("রিসিভার গ্রহণ করেছে");
  await expect(page.locator(".delivery-copy strong").nth(1)).toHaveText("ব্যর্থ—আবার চেষ্টা করা যাবে");
  await expect(page.getByText("বাংলাদেশে স্থাপন করাই MediHub-এর লক্ষ্য;", { exact: false })).toBeVisible();

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
  await expect(page.getByRole("status")).toContainText("The result remains pending and unverified.");
  await expect(page.getByRole("button", { name: /verify|finalize|release|send/i })).toHaveCount(0);
});

test("supports Bengali lab-review copy and keeps the table within mobile viewport", async ({ page }) => {
  await page.getByRole("link", { name: "Lab review (demo)" }).click();
  await page.getByRole("combobox", { name: "Interface language" }).selectOption("bn");

  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await expect(page.getByRole("heading", { level: 1, name: "সিন্থেটিক ল্যাব ফলাফল পর্যালোচনা" })).toBeVisible();
  await expect(page.getByText("ল্যাব টেকনিশিয়ানের পর্যালোচনার অপেক্ষায়").first()).toBeVisible();
  for (const width of [320, 360, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await expect(page.getByRole("navigation", { name: "ড্যাশবোর্ডের পৃষ্ঠা" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

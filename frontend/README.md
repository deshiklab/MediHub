# MediHub Next.js frontend

This is a companion UI to the Python/FastAPI dashboard, not a replacement. FastAPI remains the source of the synthetic operations API; the Next.js home page reads `/api/dashboard` and shows a Bangladesh discovery-only summary, while `/bangladesh-devices` provides local search and filters for device family, evidence basis, and catalog-date metadata, plus a browser-generated CSV of only the visible leads and shareable links containing only the current search text and allowlisted filter values. The CSV allowlists discovery fields, neutralizes spreadsheet formulas, records date-metadata presence without exporting dates, and carries the discovery-only scope note; nothing is uploaded. Both pages fail closed when catalog data leaves the approved synthetic-only scope and avoid installed-prevalence, compatibility, supported-driver, or freshness claims. Browser code uses same-origin relative URLs and does not connect to localhost or an external receiver.

## Run locally

Start the synthetic FastAPI service in one terminal from the repository root:

```bash
.venv/bin/python -m medihub dashboard --host 127.0.0.1 --port 8000
```

In a second terminal, start the Next.js development server:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. Set `MEDIHUB_BACKEND_URL` if FastAPI is listening somewhere other than `http://127.0.0.1:8000`.

## Checks

From this directory, install the dependencies and headless Chromium shell, then run the production build and browser checks:

```bash
npm ci
npx playwright install --only-shell chromium
npm run build
npm run test:e2e
```

The browser tests stub the operations and device-library APIs with synthetic fixtures, verify summary counts, local discovery filters, formula-safe CSV export, allowlisted share links, fail-closed behavior, Bengali preference/localization, and mobile layout, and block external host requests.

For an Arena preview, keep the backend on port 8000 and expose the Next.js server on port 3000; both processes must run in the same sandbox. The dev config allows the Arena `*.e2b.app` origin and proxies `/api/*` and the existing workbench routes to FastAPI. This unauthenticated preview is synthetic-only and must not be exposed as a production operator console.

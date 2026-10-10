# MediHub Next.js frontend

This is a companion UI to the Python/FastAPI dashboard, not a replacement. FastAPI remains the source of the synthetic operations API; the Next.js home page reads `/api/dashboard` through a server-side rewrite. Browser code uses same-origin relative URLs, and does not connect to localhost or an external receiver.

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

The browser tests stub the dashboard API with synthetic fixtures, verify Bengali preference persistence and mobile layout, and block external host requests.

For an Arena preview, keep the backend on port 8000 and expose the Next.js server on port 3000; both processes must run in the same sandbox. The dev config allows the Arena `*.e2b.app` origin and proxies `/api/*` and the existing workbench routes to FastAPI. This unauthenticated preview is synthetic-only and must not be exposed as a production operator console.

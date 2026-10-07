"""Local synthetic operations dashboard and ephemeral setup workbench."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from medihub.application.management_workbench import (
    ManagementWorkbenchError,
    SyntheticDeviceStateRequest,
    SyntheticManagementWorkbench,
    SyntheticMappingEntryDraft,
    SyntheticMappingPreviewRequest,
    SyntheticMappingTestVectorDraft,
)
from medihub.application.operations import SyntheticOperationsDashboard

DASHBOARD_HTML = files("medihub").joinpath("dashboard.html").read_text(encoding="utf-8")


def create_dashboard_app(
    runtime: SyntheticOperationsDashboard | None = None,
) -> FastAPI:
    """Build the dashboard and demo management API with synthetic data only."""

    operations = runtime or SyntheticOperationsDashboard()
    workbench = SyntheticManagementWorkbench(operations)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await operations.start()
        try:
            yield
        finally:
            await operations.stop()

    app = FastAPI(
        title="MediHub Synthetic Operations Dashboard",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.exception_handler(ManagementWorkbenchError)
    async def management_error_handler(
        _request: Request,
        error: ManagementWorkbenchError,
    ) -> JSONResponse:
        return JSONResponse(
            {"error": error.code},
            status_code=error.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        safe_codes = sorted({issue["type"] for issue in error.errors()})
        return JSONResponse(
            {"errors": [{"code": code} for code in safe_codes]},
            status_code=422,
        )

    @app.middleware("http")
    async def add_safety_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_page() -> HTMLResponse:
        return HTMLResponse(DASHBOARD_HTML)

    @app.get("/healthz", include_in_schema=False)
    async def health_check() -> JSONResponse:
        health = await operations.health()
        code = 200 if health["status"] == "ready" else 503
        return JSONResponse(health, status_code=code)

    @app.get("/api/dashboard", include_in_schema=False)
    async def dashboard_snapshot() -> dict[str, object]:
        return await operations.snapshot()

    @app.get("/api/management/devices", include_in_schema=False)
    async def list_synthetic_devices() -> dict[str, object]:
        return await workbench.devices()

    @app.post("/api/management/devices", status_code=201, include_in_schema=False)
    async def register_synthetic_device() -> dict[str, object]:
        return await workbench.register_simulator()

    @app.patch("/api/management/devices/{device_id}", include_in_schema=False)
    async def set_synthetic_device_state(
        device_id: str,
        request: SyntheticDeviceStateRequest,
    ) -> dict[str, object]:
        return await workbench.set_simulator_enabled(device_id, request)

    @app.post("/api/management/devices/{device_id}/emit", include_in_schema=False)
    async def emit_synthetic_device_sample(device_id: str) -> dict[str, object]:
        return await workbench.emit_simulator_sample(device_id)

    @app.get("/api/management/mappings", include_in_schema=False)
    async def list_synthetic_mappings() -> dict[str, object]:
        return await workbench.mappings()

    @app.post("/api/management/mappings/entries", include_in_schema=False)
    async def add_synthetic_mapping_entry(
        draft: SyntheticMappingEntryDraft,
    ) -> dict[str, object]:
        return await workbench.add_mapping(draft)

    @app.post("/api/management/mappings/preview", include_in_schema=False)
    async def preview_synthetic_mapping(
        request: SyntheticMappingPreviewRequest,
    ) -> dict[str, object]:
        return await workbench.preview_mapping(request)

    @app.post("/api/management/mappings/reset", include_in_schema=False)
    async def reset_synthetic_mappings() -> dict[str, object]:
        return await workbench.reset_mappings()

    @app.get("/api/management/mappings/revisions", include_in_schema=False)
    async def list_synthetic_mapping_revisions() -> dict[str, object]:
        return await workbench.mapping_revisions()

    @app.get(
        "/api/management/mappings/revisions/{from_version}/compare/{to_version}",
        include_in_schema=False,
    )
    async def compare_synthetic_mapping_revisions(
        from_version: str,
        to_version: str,
    ) -> dict[str, object]:
        return await workbench.compare_mapping_revisions(from_version, to_version)

    @app.get("/api/management/mappings/revisions/{version}", include_in_schema=False)
    async def get_synthetic_mapping_revision(version: str) -> dict[str, object]:
        return await workbench.mapping_revision(version)

    @app.post("/api/management/mappings/revisions/{version}/restore", include_in_schema=False)
    async def restore_synthetic_mapping_revision(version: str) -> dict[str, object]:
        return await workbench.restore_mapping_revision(version)

    @app.get("/api/management/mapping-tests", include_in_schema=False)
    async def list_synthetic_mapping_tests() -> dict[str, object]:
        return await workbench.mapping_test_vectors()

    @app.post("/api/management/mapping-tests/vectors", include_in_schema=False)
    async def add_synthetic_mapping_test_vector(
        draft: SyntheticMappingTestVectorDraft,
    ) -> dict[str, object]:
        return await workbench.add_mapping_test_vector(draft)

    @app.post("/api/management/mapping-tests/run", include_in_schema=False)
    async def run_synthetic_mapping_tests() -> dict[str, object]:
        return await workbench.run_mapping_tests()

    @app.get("/api/management/destinations", include_in_schema=False)
    async def list_synthetic_destinations() -> dict[str, object]:
        return await workbench.destinations()

    @app.post("/api/management/destinations/test", include_in_schema=False)
    async def test_synthetic_destination() -> dict[str, object]:
        return await workbench.test_destination()

    return app

"""Local synthetic operations dashboard and ephemeral setup workbench."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.resources import files
from time import perf_counter
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST

from medihub.application.management_workbench import (
    ManagementWorkbenchError,
    SyntheticDeviceStateRequest,
    SyntheticManagementWorkbench,
    SyntheticMappingEntryDraft,
    SyntheticMappingPreviewRequest,
    SyntheticMappingTestVectorDraft,
    SyntheticReceiverFaultRequest,
)
from medihub.application.operations import SyntheticOperationsDashboard
from medihub.observability import MediHubMetrics

DASHBOARD_HTML = files("medihub").joinpath("dashboard.html").read_text(encoding="utf-8")
DashboardPage = Literal["operations", "devices", "mappings", "api-setup", "help"]


def _render_dashboard_page(page: DashboardPage) -> HTMLResponse:
    """Render the shared shell with one route-selected tab active."""

    html = DASHBOARD_HTML.replace(
        '<body data-current-page="operations">',
        f'<body data-current-page="{page}">',
        1,
    )
    return HTMLResponse(html)


def create_dashboard_app(
    runtime: SyntheticOperationsDashboard | None = None,
) -> FastAPI:
    """Build the dashboard and demo management API with synthetic data only."""

    operations = runtime or SyntheticOperationsDashboard()
    workbench = SyntheticManagementWorkbench(operations)
    metrics = MediHubMetrics()

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
        started_at = perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            if request.scope.get("path") != "/metrics":
                route = request.scope.get("route")
                metrics.observe_http_request(
                    method=request.method,
                    route=getattr(route, "path", None),
                    status_code=response.status_code if response is not None else 500,
                    duration_seconds=perf_counter() - started_at,
                )
            if response is not None:
                response.headers["Cache-Control"] = "no-store"
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "no-referrer"
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "script-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
                )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_page() -> HTMLResponse:
        return _render_dashboard_page("operations")

    @app.get("/operations", response_class=HTMLResponse, include_in_schema=False)
    async def operations_page() -> HTMLResponse:
        return _render_dashboard_page("operations")

    @app.get("/devices", response_class=HTMLResponse, include_in_schema=False)
    async def devices_page() -> HTMLResponse:
        return _render_dashboard_page("devices")

    @app.get("/mappings", response_class=HTMLResponse, include_in_schema=False)
    async def mappings_page() -> HTMLResponse:
        return _render_dashboard_page("mappings")

    @app.get("/api-setup", response_class=HTMLResponse, include_in_schema=False)
    async def api_setup_page() -> HTMLResponse:
        return _render_dashboard_page("api-setup")

    @app.get("/help", response_class=HTMLResponse, include_in_schema=False)
    async def help_page() -> HTMLResponse:
        return _render_dashboard_page("help")

    @app.get("/healthz", include_in_schema=False)
    async def health_check() -> JSONResponse:
        health = await operations.health()
        code = 200 if health["status"] == "ready" else 503
        return JSONResponse(health, status_code=code)

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        metrics.set_runtime_snapshot(await operations.metrics_snapshot())
        return Response(
            content=metrics.render(),
            headers={"Content-Type": CONTENT_TYPE_LATEST},
        )

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

    @app.get("/api/management/deliveries/{event_id}", include_in_schema=False)
    async def get_synthetic_delivery_detail(event_id: UUID) -> dict[str, object]:
        return await workbench.synthetic_delivery_detail(event_id)

    @app.post("/api/management/deliveries/{event_id}/retry", include_in_schema=False)
    async def replay_synthetic_delivery(event_id: UUID) -> dict[str, object]:
        return await workbench.replay_synthetic_delivery(event_id)

    @app.get("/api/management/destinations", include_in_schema=False)
    async def list_synthetic_destinations() -> dict[str, object]:
        return await workbench.destinations()

    @app.get("/api/management/destinations/test-receiver/faults", include_in_schema=False)
    async def synthetic_test_receiver_fault_status() -> dict[str, object]:
        return await workbench.test_receiver_fault_status()

    @app.post("/api/management/destinations/test-receiver/faults", include_in_schema=False)
    async def arm_synthetic_test_receiver_fault(
        request: SyntheticReceiverFaultRequest,
    ) -> dict[str, object]:
        return await workbench.arm_test_receiver_fault(request)

    @app.delete("/api/management/destinations/test-receiver/faults", include_in_schema=False)
    async def clear_synthetic_test_receiver_fault() -> dict[str, object]:
        return await workbench.clear_test_receiver_fault()

    @app.post("/api/management/destinations/test", include_in_schema=False)
    async def test_synthetic_destination() -> dict[str, object]:
        return await workbench.test_destination()

    metrics.set_route_templates(
        route.path for route in app.routes if isinstance(getattr(route, "path", None), str)
    )
    return app

"""Ephemeral management API for synthetic devices and mapping experiments only."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, ValidationError

from medihub.adapters.destinations.synthetic_fault_injector import SyntheticFaultInjectorError
from medihub.application.operations import (
    SyntheticOperationsDashboard,
    SyntheticOperationsError,
)
from medihub.domain import (
    Coding,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    SourceProvenance,
    SyntheticMappingError,
    SyntheticMappingResult,
    SyntheticMappingSet,
    SyntheticMetricMapping,
    TimeQuality,
)
from medihub.domain.base import AwareDateTime, DomainModel
from medihub.infrastructure.event_store import SyntheticDeliveryReplayError

SIMULATOR_MANUFACTURER = "MediHub Synthetic"
SIMULATOR_MODEL = "scalar-simulator-v1"
SIMULATOR_FIRMWARE = "1.0"
SIMULATOR_ADAPTER_ID = "medihub.synthetic-device"
SIMULATOR_ADAPTER_VERSION = "0.2.0"
SOURCE_METRIC_SYSTEM = "https://example.invalid/medihub/synthetic-metrics"
NORMALIZED_METRIC_SYSTEM = "https://example.invalid/medihub/canonical-synthetic"
UNIT_SYSTEM = "http://unitsofmeasure.org"
TEST_DESTINATION_ID = "medihub.synthetic-test-receiver"
MAX_SIMULATOR_DEVICES = 20
MAX_MANAGED_MAPPINGS = 50
MAX_MAPPING_TEST_VECTORS = 50
MAX_MAPPING_REVISIONS = 100

SyntheticCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
SyntheticUnitCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9.%*/^_-]*$",
    ),
]


class SyntheticDeviceRecord(DomainModel):
    """Fixed simulator inventory row; it cannot describe a physical device."""

    device_id: str = Field(pattern=r"^sim-device-[0-9]{3}$")
    manufacturer: Literal["MediHub Synthetic"] = SIMULATOR_MANUFACTURER
    model: Literal["scalar-simulator-v1"] = SIMULATOR_MODEL
    firmware_version: Literal["1.0"] = SIMULATOR_FIRMWARE
    adapter_id: Literal["medihub.synthetic-device"] = SIMULATOR_ADAPTER_ID
    adapter_version: Literal["0.2.0"] = SIMULATOR_ADAPTER_VERSION
    enabled: bool = True


class SyntheticDeviceStateRequest(DomainModel):
    enabled: bool


class SyntheticReceiverFaultRequest(DomainModel):
    mode: Literal["retry_once", "reject_once", "ack_lost_once"]


class SyntheticMappingEntryDraft(DomainModel):
    """Synthetic-code mapping input with no free-text displays or live targets."""

    source_metric_code: SyntheticCode
    source_unit_code: SyntheticUnitCode
    normalized_metric_code: SyntheticCode
    normalized_unit_code: SyntheticUnitCode
    operation: Literal["identity", "linear"] = "identity"
    scale: Decimal = Field(default=Decimal("1"), max_digits=24, decimal_places=12)
    offset: Decimal = Field(default=Decimal("0"), max_digits=24, decimal_places=12)
    decimal_places: int = Field(default=2, ge=0, le=9)


class SyntheticMappingPreviewRequest(DomainModel):
    device_id: str = Field(pattern=r"^sim-device-[0-9]{3}$")
    source_metric_code: SyntheticCode
    source_unit_code: SyntheticUnitCode
    value: float = Field(ge=-1e18, le=1e18, allow_inf_nan=False)


class SyntheticMappingTestVectorDraft(DomainModel):
    """One synthetic input and expected normalized result for a mapping test."""

    device_id: str = Field(pattern=r"^sim-device-[0-9]{3}$")
    source_metric_code: SyntheticCode
    source_unit_code: SyntheticUnitCode
    input_value: Decimal = Field(
        ge=Decimal("-1e18"),
        le=Decimal("1e18"),
        max_digits=28,
        decimal_places=9,
    )
    expected_metric_code: SyntheticCode
    expected_unit_code: SyntheticUnitCode
    expected_value: Decimal = Field(
        ge=Decimal("-1e18"),
        le=Decimal("1e18"),
        max_digits=28,
        decimal_places=9,
    )


class SyntheticMappingTestVector(SyntheticMappingTestVectorDraft):
    vector_id: str = Field(pattern=r"^mapping-test-[0-9]{3}$")


class SyntheticMappingRevision(DomainModel):
    """One immutable, ephemeral snapshot of a synthetic mapping revision."""

    mapping_set: SyntheticMappingSet
    changed_at: AwareDateTime
    change_type: Literal["initial", "entry_added", "reset", "restore"]
    restored_from_version: str | None = None


class ManagementWorkbenchError(ValueError):
    """Safe error code/status for synthetic management operations."""

    def __init__(self, code: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class SyntheticManagementWorkbench:
    """In-memory catalogs for simulator devices and synthetic mappings.

    Device records are simulator-only. Mapping entries use fixed example.invalid
    code systems. The only destination is MediHub's in-process test sink; this
    class has no endpoint URL, credential, or live-activation fields.
    """

    def __init__(self, operations: SyntheticOperationsDashboard) -> None:
        self._operations = operations
        self._lock = asyncio.Lock()
        self._devices: dict[str, SyntheticDeviceRecord] = {
            "sim-device-001": SyntheticDeviceRecord(device_id="sim-device-001")
        }
        self._mapping_set = _example_mapping_set()
        self._mapping_revisions: list[SyntheticMappingRevision] = [
            SyntheticMappingRevision(
                mapping_set=self._mapping_set,
                changed_at=datetime.now(UTC),
                change_type="initial",
            )
        ]
        self._discarded_mapping_revisions = 0
        self._test_vectors: list[SyntheticMappingTestVector] = [
            SyntheticMappingTestVector(
                vector_id="mapping-test-001",
                device_id="sim-device-001",
                source_metric_code="simulated-scalar-reading",
                source_unit_code="1",
                input_value=Decimal("42.5"),
                expected_metric_code="mapped-synthetic-scalar",
                expected_unit_code="1",
                expected_value=Decimal("42.50"),
            )
        ]
        self._last_test_report: dict[str, object] | None = None

    async def devices(self) -> dict[str, object]:
        async with self._lock:
            rows = [
                record.model_dump(mode="json")
                for record in sorted(self._devices.values(), key=lambda item: item.device_id)
            ]
        return {
            "mode": "synthetic_only",
            "persistent": False,
            "physical_device_connections_enabled": False,
            "devices": rows,
        }

    async def register_simulator(self) -> dict[str, object]:
        async with self._lock:
            if len(self._devices) >= MAX_SIMULATOR_DEVICES:
                raise ManagementWorkbenchError("simulator_device_limit_reached", 409)
            next_number = 1
            while f"sim-device-{next_number:03d}" in self._devices:
                next_number += 1
            if next_number > MAX_SIMULATOR_DEVICES:
                raise ManagementWorkbenchError("simulator_device_limit_reached", 409)
            record = SyntheticDeviceRecord(device_id=f"sim-device-{next_number:03d}")
            self._devices[record.device_id] = record
            return record.model_dump(mode="json")

    async def set_simulator_enabled(
        self,
        device_id: str,
        request: SyntheticDeviceStateRequest,
    ) -> dict[str, object]:
        async with self._lock:
            current = self._devices.get(device_id)
            if current is None:
                raise ManagementWorkbenchError("simulator_device_not_found", 404)
            updated = current.model_copy(update={"enabled": request.enabled})
            self._devices[device_id] = updated
            return updated.model_dump(mode="json")

    async def emit_simulator_sample(self, device_id: str) -> dict[str, object]:
        async with self._lock:
            record = self._devices.get(device_id)
            if record is None:
                raise ManagementWorkbenchError("simulator_device_not_found", 404)
            if not record.enabled:
                raise ManagementWorkbenchError("simulator_device_disabled", 409)
        return await self._operations.emit_synthetic_sample(device_id)

    async def mappings(self) -> dict[str, object]:
        async with self._lock:
            return {
                "scope": "synthetic_only",
                "persistent": False,
                "mapping_activation_enabled": False,
                "mapping_set": self._mapping_set.model_dump(mode="json"),
            }

    async def add_mapping(
        self,
        draft: SyntheticMappingEntryDraft,
    ) -> dict[str, object]:
        try:
            entry = SyntheticMetricMapping(
                source_metric=Coding(system=SOURCE_METRIC_SYSTEM, code=draft.source_metric_code),
                source_unit=Coding(system=UNIT_SYSTEM, code=draft.source_unit_code),
                normalized_metric=Coding(
                    system=NORMALIZED_METRIC_SYSTEM,
                    code=draft.normalized_metric_code,
                ),
                normalized_unit=Coding(system=UNIT_SYSTEM, code=draft.normalized_unit_code),
                operation=draft.operation,
                scale=draft.scale,
                offset=draft.offset,
                decimal_places=draft.decimal_places,
            )
        except ValidationError:
            raise ManagementWorkbenchError("invalid_synthetic_mapping_entry", 422) from None

        async with self._lock:
            if len(self._mapping_set.entries) >= MAX_MANAGED_MAPPINGS:
                raise ManagementWorkbenchError("synthetic_mapping_limit_reached", 409)
            try:
                updated = SyntheticMappingSet.model_validate(
                    {
                        **self._mapping_set.model_dump(mode="python"),
                        "version": _next_patch_version(self._mapping_set.version),
                        "entries": (*self._mapping_set.entries, entry),
                    }
                )
            except ValidationError:
                raise ManagementWorkbenchError(
                    "duplicate_or_invalid_synthetic_mapping", 409
                ) from None
            self._mapping_set = updated
            self._record_mapping_revision(updated, "entry_added")
            return {
                "scope": "synthetic_only",
                "mapping_activation_enabled": False,
                "mapping_set": updated.model_dump(mode="json"),
            }

    async def reset_mappings(self) -> dict[str, object]:
        async with self._lock:
            version = _next_patch_version(self._mapping_set.version)
            self._mapping_set = _example_mapping_set(version=version)
            self._record_mapping_revision(self._mapping_set, "reset")
            return {
                "scope": "synthetic_only",
                "mapping_activation_enabled": False,
                "mapping_set": self._mapping_set.model_dump(mode="json"),
            }

    def _record_mapping_revision(
        self,
        mapping_set: SyntheticMappingSet,
        change_type: Literal["initial", "entry_added", "reset", "restore"],
        *,
        restored_from_version: str | None = None,
    ) -> None:
        self._mapping_revisions.append(
            SyntheticMappingRevision(
                mapping_set=mapping_set,
                changed_at=datetime.now(UTC),
                change_type=change_type,
                restored_from_version=restored_from_version,
            )
        )
        overflow = len(self._mapping_revisions) - MAX_MAPPING_REVISIONS
        if overflow > 0:
            del self._mapping_revisions[:overflow]
            self._discarded_mapping_revisions += overflow

    async def mapping_revisions(self) -> dict[str, object]:
        async with self._lock:
            current_version = self._mapping_set.version
            revisions = [
                {
                    "version": revision.mapping_set.version,
                    "changed_at": revision.changed_at.isoformat(),
                    "change_type": revision.change_type,
                    "restored_from_version": revision.restored_from_version,
                    "entry_count": len(revision.mapping_set.entries),
                    "is_current": revision.mapping_set.version == current_version,
                }
                for revision in reversed(self._mapping_revisions)
            ]
            return {
                "scope": "synthetic_only",
                "persistent": False,
                "current_version": current_version,
                "revision_count": len(revisions),
                "revision_limit": MAX_MAPPING_REVISIONS,
                "older_revisions_discarded": self._discarded_mapping_revisions,
                "revisions": revisions,
            }

    async def mapping_revision(self, version: str) -> dict[str, object]:
        async with self._lock:
            revision = next(
                (
                    candidate
                    for candidate in self._mapping_revisions
                    if candidate.mapping_set.version == version
                ),
                None,
            )
            if revision is None:
                raise ManagementWorkbenchError("mapping_revision_not_found", 404)
            return {
                "scope": "synthetic_only",
                "persistent": False,
                "is_current": revision.mapping_set.version == self._mapping_set.version,
                "revision": {
                    "version": revision.mapping_set.version,
                    "changed_at": revision.changed_at.isoformat(),
                    "change_type": revision.change_type,
                    "restored_from_version": revision.restored_from_version,
                    "mapping_set": revision.mapping_set.model_dump(mode="json"),
                },
            }

    async def compare_mapping_revisions(
        self,
        from_version: str,
        to_version: str,
    ) -> dict[str, object]:
        async with self._lock:
            revisions = {item.mapping_set.version: item for item in self._mapping_revisions}
            from_revision = revisions.get(from_version)
            to_revision = revisions.get(to_version)
            if from_revision is None or to_revision is None:
                raise ManagementWorkbenchError("mapping_revision_not_found", 404)
            before = _index_mapping_entries(from_revision.mapping_set)
            after = _index_mapping_entries(to_revision.mapping_set)

        def signature_json(signature: tuple[str, str, str, str]) -> dict[str, str]:
            metric_system, metric_code, unit_system, unit_code = signature
            return {
                "metric_system": metric_system,
                "metric_code": metric_code,
                "unit_system": unit_system,
                "unit_code": unit_code,
            }

        added = [
            {
                "source_signature": signature_json(signature),
                "entry": after[signature].model_dump(mode="json"),
            }
            for signature in sorted(after.keys() - before.keys())
        ]
        removed = [
            {
                "source_signature": signature_json(signature),
                "entry": before[signature].model_dump(mode="json"),
            }
            for signature in sorted(before.keys() - after.keys())
        ]
        changed = [
            {
                "source_signature": signature_json(signature),
                "from": before[signature].model_dump(mode="json"),
                "to": after[signature].model_dump(mode="json"),
            }
            for signature in sorted(before.keys() & after.keys())
            if before[signature] != after[signature]
        ]
        return {
            "scope": "synthetic_only",
            "activation_enabled": False,
            "from_version": from_version,
            "to_version": to_version,
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "changed": len(changed),
            },
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    async def restore_mapping_revision(self, version: str) -> dict[str, object]:
        async with self._lock:
            revision = next(
                (
                    candidate
                    for candidate in self._mapping_revisions
                    if candidate.mapping_set.version == version
                ),
                None,
            )
            if revision is None:
                raise ManagementWorkbenchError("mapping_revision_not_found", 404)
            if version == self._mapping_set.version:
                raise ManagementWorkbenchError("mapping_revision_already_current", 409)
            restored = SyntheticMappingSet.model_validate(
                {
                    **revision.mapping_set.model_dump(mode="python"),
                    "version": _next_patch_version(self._mapping_set.version),
                }
            )
            self._mapping_set = restored
            self._record_mapping_revision(
                restored,
                "restore",
                restored_from_version=version,
            )
            return {
                "scope": "synthetic_only",
                "activation_enabled": False,
                "restored_from_version": version,
                "mapping_set": restored.model_dump(mode="json"),
            }

    async def preview_mapping(
        self,
        request: SyntheticMappingPreviewRequest,
    ) -> dict[str, object]:
        async with self._lock:
            device = self._devices.get(request.device_id)
            mapping_set = self._mapping_set
            if device is None:
                raise ManagementWorkbenchError("simulator_device_not_found", 404)
            if not device.enabled:
                raise ManagementWorkbenchError("simulator_device_disabled", 409)

        event = _event_from_synthetic_values(
            device,
            source_metric_code=request.source_metric_code,
            source_unit_code=request.source_unit_code,
            value=Decimal(str(request.value)),
        )
        try:
            result: SyntheticMappingResult = mapping_set.map_event(event)
        except SyntheticMappingError as error:
            raise ManagementWorkbenchError(error.code, 422) from None
        return {
            "mapping_activation_enabled": False,
            "result": result.model_dump(mode="json"),
        }

    async def mapping_test_vectors(self) -> dict[str, object]:
        async with self._lock:
            mapping_version = self._mapping_set.version
            report = self._last_test_report
            report_is_current = report is not None and report["mapping_version"] == mapping_version
            return {
                "mapping_version": mapping_version,
                "test_count": len(self._test_vectors),
                "status": (
                    "not_run"
                    if report is None
                    else report["status"]
                    if report_is_current
                    else "stale"
                ),
                "last_run_mapping_version": (
                    report["mapping_version"] if report is not None else None
                ),
                "last_report": report,
                "activation_enabled": False,
                "vectors": [vector.model_dump(mode="json") for vector in self._test_vectors],
            }

    async def add_mapping_test_vector(
        self,
        draft: SyntheticMappingTestVectorDraft,
    ) -> dict[str, object]:
        async with self._lock:
            if len(self._test_vectors) >= MAX_MAPPING_TEST_VECTORS:
                raise ManagementWorkbenchError("synthetic_mapping_test_limit_reached", 409)
            next_number = 1
            existing_ids = {vector.vector_id for vector in self._test_vectors}
            while f"mapping-test-{next_number:03d}" in existing_ids:
                next_number += 1
            vector = SyntheticMappingTestVector(
                vector_id=f"mapping-test-{next_number:03d}",
                **draft.model_dump(mode="python"),
            )
            self._test_vectors.append(vector)
            self._last_test_report = None
            return {
                "mapping_version": self._mapping_set.version,
                "activation_enabled": False,
                "vector": vector.model_dump(mode="json"),
            }

    async def run_mapping_tests(self) -> dict[str, object]:
        async with self._lock:
            mapping_set = self._mapping_set
            vectors = tuple(self._test_vectors)
            devices = dict(self._devices)

        results: list[dict[str, str]] = []
        for vector in vectors:
            device = devices.get(vector.device_id)
            if device is None:
                results.append(
                    {
                        "vector_id": vector.vector_id,
                        "status": "failed",
                        "code": "simulator_device_not_found",
                    }
                )
                continue
            if not device.enabled:
                results.append(
                    {
                        "vector_id": vector.vector_id,
                        "status": "failed",
                        "code": "simulator_device_disabled",
                    }
                )
                continue
            event = _event_from_synthetic_values(
                device,
                source_metric_code=vector.source_metric_code,
                source_unit_code=vector.source_unit_code,
                value=vector.input_value,
            )
            try:
                mapped = mapping_set.map_event(event)
            except SyntheticMappingError as error:
                results.append(
                    {"vector_id": vector.vector_id, "status": "failed", "code": error.code}
                )
                continue
            output_matches = (
                mapped.normalized_metric.code == vector.expected_metric_code
                and mapped.normalized_unit.code == vector.expected_unit_code
                and mapped.normalized_value == vector.expected_value
            )
            results.append(
                {
                    "vector_id": vector.vector_id,
                    "status": "passed" if output_matches else "failed",
                    "code": "mapping_test_passed"
                    if output_matches
                    else "mapping_test_expected_output_mismatch",
                }
            )

        passed = sum(result["status"] == "passed" for result in results)
        failed = len(results) - passed
        report: dict[str, object] = {
            "mapping_version": mapping_set.version,
            "status": "passed" if failed == 0 else "failed",
            "vectors_run": len(results),
            "passed": passed,
            "failed": failed,
            "activation_enabled": False,
            "results": results,
        }
        async with self._lock:
            if self._mapping_set.version == mapping_set.version:
                self._last_test_report = report
        return report

    async def destinations(self) -> dict[str, object]:
        return {
            "mode": "synthetic_only",
            "external_connections_enabled": False,
            "destinations": [
                {
                    "destination_id": TEST_DESTINATION_ID,
                    "label": "In-process synthetic FHIR R4 test receiver",
                    "protocol": "fhir_r4",
                    "status": "ready",
                    "transport": "in_process",
                    "network_enabled": False,
                    "endpoint_configurable": False,
                    "credentials_configurable": False,
                }
            ],
            "future_protocols": [
                {"protocol": "fhir_r4", "status": "contract_required"},
                {"protocol": "hl7_v2", "status": "contract_required"},
            ],
        }

    async def synthetic_delivery_detail(self, event_id: UUID) -> dict[str, object]:
        try:
            return await self._operations.synthetic_delivery_detail(event_id)
        except SyntheticOperationsError as error:
            raise ManagementWorkbenchError(error.code, error.status_code) from None

    async def replay_synthetic_delivery(self, event_id: UUID) -> dict[str, object]:
        try:
            return await self._operations.replay_synthetic_delivery(event_id)
        except SyntheticDeliveryReplayError as error:
            raise ManagementWorkbenchError(error.code, error.status_code) from None

    async def test_receiver_fault_status(self) -> dict[str, object]:
        try:
            return await self._operations.synthetic_delivery_fault_status()
        except SyntheticFaultInjectorError as error:
            raise ManagementWorkbenchError(error.code, 409) from None

    async def arm_test_receiver_fault(
        self,
        request: SyntheticReceiverFaultRequest,
    ) -> dict[str, object]:
        try:
            return await self._operations.arm_synthetic_delivery_fault(request.mode)
        except SyntheticFaultInjectorError as error:
            raise ManagementWorkbenchError(error.code, 409) from None

    async def clear_test_receiver_fault(self) -> dict[str, object]:
        try:
            return await self._operations.clear_synthetic_delivery_fault()
        except SyntheticFaultInjectorError as error:
            raise ManagementWorkbenchError(error.code, 409) from None

    async def test_destination(self) -> dict[str, object]:
        async with self._lock:
            enabled = next(
                (record for record in self._devices.values() if record.enabled),
                None,
            )
            if enabled is None:
                raise ManagementWorkbenchError("no_enabled_simulator_for_test", 409)
        result = await self._operations.emit_synthetic_sample(enabled.device_id)
        return {
            "destination_id": TEST_DESTINATION_ID,
            "status": result["status"],
            "transport": "in_process",
            "network_enabled": False,
            "unique_test_receipts": result["unique_test_receipts"],
        }


def _index_mapping_entries(
    mapping_set: SyntheticMappingSet,
) -> dict[tuple[str, str, str, str], SyntheticMetricMapping]:
    return {
        (
            entry.source_metric.system,
            entry.source_metric.code,
            entry.source_unit.system,
            entry.source_unit.code,
        ): entry
        for entry in mapping_set.entries
    }


def _event_from_synthetic_values(
    device: SyntheticDeviceRecord,
    *,
    source_metric_code: str,
    source_unit_code: str,
    value: Decimal,
) -> ObservationEvent:
    now = datetime.now(UTC)
    return ObservationEvent(
        event_id=uuid4(),
        site_id="synthetic-workbench",
        device=DeviceReference(
            device_id=device.device_id,
            manufacturer=device.manufacturer,
            model=device.model,
            firmware_version=device.firmware_version,
        ),
        metric=Coding(system=SOURCE_METRIC_SYSTEM, code=source_metric_code),
        value=float(value),
        source_unit=Coding(system=UNIT_SYSTEM, code=source_unit_code),
        observed_at=now,
        received_at=now,
        time_quality=TimeQuality.DEVICE_SYNCHRONIZED,
        provenance=SourceProvenance(
            adapter_id=device.adapter_id,
            adapter_version=device.adapter_version,
        ),
        origin=EventOrigin.SYNTHETIC,
    )


def _example_mapping_set(*, version: str = "1.0.0") -> SyntheticMappingSet:
    return SyntheticMappingSet(
        scope="synthetic_only",
        mapping_set_id="synthetic-console-demo",
        version=version,
        manufacturer=SIMULATOR_MANUFACTURER,
        model=SIMULATOR_MODEL,
        firmware_versions=(SIMULATOR_FIRMWARE,),
        adapter_id=SIMULATOR_ADAPTER_ID,
        adapter_version=SIMULATOR_ADAPTER_VERSION,
        entries=(
            SyntheticMetricMapping(
                source_metric=Coding(
                    system=SOURCE_METRIC_SYSTEM,
                    code="simulated-scalar-reading",
                ),
                source_unit=Coding(system=UNIT_SYSTEM, code="1"),
                normalized_metric=Coding(
                    system=NORMALIZED_METRIC_SYSTEM,
                    code="mapped-synthetic-scalar",
                ),
                normalized_unit=Coding(system=UNIT_SYSTEM, code="1"),
                operation="identity",
                scale=Decimal("1"),
                offset=Decimal("0"),
                decimal_places=2,
            ),
        ),
    )


def _next_patch_version(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


__all__ = [
    "ManagementWorkbenchError",
    "SyntheticDeviceRecord",
    "SyntheticDeviceStateRequest",
    "SyntheticManagementWorkbench",
    "SyntheticMappingEntryDraft",
    "SyntheticMappingPreviewRequest",
    "SyntheticMappingRevision",
    "SyntheticMappingTestVectorDraft",
    "SyntheticReceiverFaultRequest",
]

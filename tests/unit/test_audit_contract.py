from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from medihub.domain import AuditAction, AuditEvent


def make_audit_event(**overrides: object) -> AuditEvent:
    values: dict[str, object] = {
        "event_id": uuid4(),
        "site_id": "synthetic-site",
        "actor_id": "system:ingestion",
        "action": AuditAction.ROUTE_HELD,
        "resource_type": "routing_hold",
        "resource_id": str(uuid4()),
        "occurred_at": datetime(2026, 10, 7, 8, 0, tzinfo=UTC),
        "correlation_id": str(uuid4()),
        "reason_code": "synthetic_not_accepted",
    }
    values.update(overrides)
    return AuditEvent.model_validate(values)


def test_audit_contract_has_only_bounded_metadata_fields() -> None:
    event = make_audit_event()

    assert event.action is AuditAction.ROUTE_HELD
    assert event.reason_code == "synthetic_not_accepted"
    assert "payload" not in AuditEvent.model_fields
    assert "patient" not in AuditEvent.model_fields


def test_audit_contract_rejects_payload_and_free_text_reason() -> None:
    with pytest.raises(ValidationError):
        make_audit_event(payload={"synthetic": "not-for-audit"})

    with pytest.raises(ValidationError):
        make_audit_event(reason_code="receiver error with free text")

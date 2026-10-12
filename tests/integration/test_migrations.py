import asyncio
import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from medihub.infrastructure.destination_api_profile_store import (
    SqlAlchemyDestinationApiProfileStore,
)


def test_migrations_build_event_outbox_routing_hold_and_audit_schema(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MEDIHUB_DATABASE_URL", raising=False)
    database_path = tmp_path / "migration-test.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        outbox_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(delivery_outbox)")
        }
        attempt_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(delivery_attempt)")
        }
        hold_columns = {row[1] for row in connection.execute("PRAGMA table_info(routing_hold)")}
        audit_columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_event)")}
        destination_profile_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(destination_api_profile)")
        }
        foreign_keys = list(connection.execute("PRAGMA foreign_key_list(delivery_outbox)"))
        hold_foreign_keys = list(connection.execute("PRAGMA foreign_key_list(routing_hold)"))
        audit_foreign_keys = list(connection.execute("PRAGMA foreign_key_list(audit_event)"))

    assert {
        "alembic_version",
        "event_store",
        "delivery_outbox",
        "delivery_attempt",
        "routing_hold",
        "audit_event",
        "destination_api_profile",
    } <= tables
    assert {
        "event_id",
        "destination_id",
        "status",
        "attempt_count",
        "lease_token",
        "lease_expires_at",
    } <= outbox_columns
    assert {"attempt_id", "outbox_id", "attempt_number", "error_code"} <= attempt_columns
    assert {"hold_id", "event_id", "destination_id", "reason_code", "created_at"} <= hold_columns
    assert {
        "audit_id",
        "site_id",
        "actor_id",
        "action",
        "resource_type",
        "resource_id",
        "occurred_at",
        "correlation_id",
        "reason_code",
    } <= audit_columns
    assert any(row[2] == "event_store" for row in foreign_keys)
    assert any(row[2] == "event_store" for row in hold_foreign_keys)
    assert audit_foreign_keys == []
    assert {
        "target_id",
        "profile_id",
        "receiver_product",
        "receiver_version",
        "interface_version_profile",
        "controlled_interface_contract_reference",
        "resource_message_profile_reference",
        "patient_association_policy_reference",
        "results_only_technician_review_confirmed",
        "results_only_review_reference",
        "acknowledgement_idempotency_retry_reference",
        "security_transport_authorization_reference",
        "vendor_authorization_status",
        "vendor_authorization_reference",
        "facility_authorization_status",
        "facility_authorization_reference",
        "authorized_synthetic_sandbox_reference",
        "created_at",
        "updated_at",
    } <= destination_profile_columns
    assert not any(
        field in column.lower()
        for column in destination_profile_columns
        for field in ("endpoint", "credential", "password", "secret", "token", "base_url")
    )


def test_migrations_adopt_dashboard_initialized_destination_profile_table(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MEDIHUB_DATABASE_URL", raising=False)
    database_path = tmp_path / "dashboard-before-migration.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    store = SqlAlchemyDestinationApiProfileStore(database_url)

    async def initialize_store() -> None:
        await store.start()
        await store.close()

    asyncio.run(initialize_store())

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert version == "0005_destination_api_profile"
    assert "destination_api_profile" in tables

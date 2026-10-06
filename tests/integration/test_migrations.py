import sqlite3

import pytest
from alembic import command
from alembic.config import Config


def test_initial_migration_builds_event_and_outbox_schema(
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
        foreign_keys = list(connection.execute("PRAGMA foreign_key_list(delivery_outbox)"))

    assert {"alembic_version", "event_store", "delivery_outbox", "delivery_attempt"} <= tables
    assert {
        "event_id",
        "destination_id",
        "status",
        "attempt_count",
        "lease_token",
        "lease_expires_at",
    } <= outbox_columns
    assert {"attempt_id", "outbox_id", "attempt_number", "error_code"} <= attempt_columns
    assert any(row[2] == "event_store" for row in foreign_keys)

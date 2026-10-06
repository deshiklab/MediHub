"""Create the canonical event store and transactional delivery outbox.

Revision ID: 0001_event_outbox
Revises:
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_event_outbox"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_store",
        sa.Column("event_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("site_id", sa.String(length=256), nullable=False),
        sa.Column("device_id", sa.String(length=256), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_content_sha256", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "persisted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_event_store"),
    )
    op.create_index(
        "ix_event_store_site_observed_at",
        "event_store",
        ["site_id", "observed_at"],
        unique=False,
    )

    op.create_table(
        "delivery_outbox",
        sa.Column("outbox_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("destination_id", sa.String(length=256), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("acknowledgement_id", sa.String(length=256), nullable=True),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event_store.event_id"],
            name="fk_delivery_outbox_event_id_event_store",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("outbox_id", name="pk_delivery_outbox"),
        sa.UniqueConstraint(
            "event_id",
            "destination_id",
            name="uq_delivery_outbox_event_destination",
        ),
    )
    op.create_index(
        "ix_delivery_outbox_status_next_attempt",
        "delivery_outbox",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_delivery_outbox_status_next_attempt",
        table_name="delivery_outbox",
    )
    op.drop_table("delivery_outbox")
    op.drop_index("ix_event_store_site_observed_at", table_name="event_store")
    op.drop_table("event_store")

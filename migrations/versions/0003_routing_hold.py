"""Persist fail-closed destination policy holds without clinical free text.

Revision ID: 0003_routing_hold
Revises: 0002_delivery_lifecycle
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_routing_hold"
down_revision: str | None = "0002_delivery_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "routing_hold",
        sa.Column("hold_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("destination_id", sa.String(length=256), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event_store.event_id"],
            name="fk_routing_hold_event_id_event_store",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("hold_id", name="pk_routing_hold"),
        sa.UniqueConstraint(
            "event_id",
            "destination_id",
            name="uq_routing_hold_event_destination",
        ),
    )
    op.create_index("ix_routing_hold_created_at", "routing_hold", ["created_at"])
    op.create_index(
        "ix_routing_hold_destination_created",
        "routing_hold",
        ["destination_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_routing_hold_destination_created", table_name="routing_hold")
    op.drop_index("ix_routing_hold_created_at", table_name="routing_hold")
    op.drop_table("routing_hold")

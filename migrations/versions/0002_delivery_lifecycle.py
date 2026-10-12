"""Add leased delivery attempts and recovery metadata.

Revision ID: 0002_delivery_lifecycle
Revises: 0001_event_outbox
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_delivery_lifecycle"
down_revision: str | None = "0001_event_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("delivery_outbox", sa.Column("lease_token", sa.Uuid(as_uuid=True)))
    op.add_column(
        "delivery_outbox",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "delivery_attempt",
        sa.Column("attempt_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("outbox_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledgement_id", sa.String(length=256), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="attempt_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_id"],
            ["delivery_outbox.outbox_id"],
            name="fk_delivery_attempt_outbox_id_delivery_outbox",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_delivery_attempt"),
        sa.UniqueConstraint(
            "outbox_id",
            "attempt_number",
            name="uq_attempt_outbox_number",
        ),
    )
    op.create_index(
        "ix_delivery_attempt_outbox_started",
        "delivery_attempt",
        ["outbox_id", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_attempt_outbox_started", table_name="delivery_attempt")
    op.drop_table("delivery_attempt")
    op.drop_column("delivery_outbox", "lease_expires_at")
    op.drop_column("delivery_outbox", "lease_token")

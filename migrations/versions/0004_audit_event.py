"""Add privacy-minimized lifecycle audit records.

Revision ID: 0004_audit_event
Revises: 0003_routing_hold
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_audit_event"
down_revision: str | None = "0003_routing_hold"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("audit_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("site_id", sa.String(length=256), nullable=False),
        sa.Column("actor_id", sa.String(length=256), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=256), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=256), nullable=True),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("audit_id", name="pk_audit_event"),
    )
    op.create_index(
        "ix_audit_event_site_occurred",
        "audit_event",
        ["site_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_event_correlation",
        "audit_event",
        ["correlation_id"],
    )
    op.create_index(
        "ix_audit_event_resource",
        "audit_event",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_event_resource", table_name="audit_event")
    op.drop_index("ix_audit_event_correlation", table_name="audit_event")
    op.drop_index("ix_audit_event_site_occurred", table_name="audit_event")
    op.drop_table("audit_event")

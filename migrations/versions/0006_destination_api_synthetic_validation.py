"""Persist the latest offline synthetic FHIR fixture result.

Revision ID: 0006_destination_api_validation
Revises: 0005_destination_api_profile
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0006_destination_api_validation"
down_revision: str | None = "0005_destination_api_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not context.is_offline_mode() and sa.inspect(op.get_bind()).has_table(
        "destination_api_synthetic_validation"
    ):
        return
    op.create_table(
        "destination_api_synthetic_validation",
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("validation_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("fixture_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("profile_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.CheckConstraint("target_id = 'emr_fhir_r4'", name="target_id_allowed"),
        sa.CheckConstraint(
            "status IN ('local_fixture_passed', 'local_fixture_failed')",
            name="status_allowed",
        ),
        sa.PrimaryKeyConstraint("target_id", name="pk_destination_api_synthetic_validation"),
        sa.UniqueConstraint(
            "validation_id",
            name="uq_destination_api_synthetic_validation_validation_id",
        ),
    )


def downgrade() -> None:
    if context.is_offline_mode() or sa.inspect(op.get_bind()).has_table(
        "destination_api_synthetic_validation"
    ):
        op.drop_table("destination_api_synthetic_validation")

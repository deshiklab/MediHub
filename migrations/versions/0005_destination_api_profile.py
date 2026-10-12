"""Persist non-secret destination API worksheets.

Revision ID: 0005_destination_api_profile
Revises: 0004_audit_event
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0005_destination_api_profile"
down_revision: str | None = "0004_audit_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not context.is_offline_mode() and sa.inspect(op.get_bind()).has_table(
        "destination_api_profile"
    ):
        return
    op.create_table(
        "destination_api_profile",
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("profile_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("receiver_product", sa.String(length=80), nullable=True),
        sa.Column("receiver_version", sa.String(length=80), nullable=True),
        sa.Column("interface_version_profile", sa.String(length=80), nullable=True),
        sa.Column("controlled_interface_contract_reference", sa.String(length=64), nullable=True),
        sa.Column("resource_message_profile_reference", sa.String(length=64), nullable=True),
        sa.Column("patient_association_policy_reference", sa.String(length=64), nullable=True),
        sa.Column(
            "results_only_technician_review_confirmed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("results_only_review_reference", sa.String(length=64), nullable=True),
        sa.Column(
            "acknowledgement_idempotency_retry_reference",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "security_transport_authorization_reference",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "vendor_authorization_status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("vendor_authorization_reference", sa.String(length=64), nullable=True),
        sa.Column(
            "facility_authorization_status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("facility_authorization_reference", sa.String(length=64), nullable=True),
        sa.Column("authorized_synthetic_sandbox_reference", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "target_id IN ('emr_fhir_r4', 'facility_hl7_v2')",
            name="target_id_allowed",
        ),
        sa.CheckConstraint(
            "vendor_authorization_status IN ('pending', 'approved')",
            name="vendor_authorization_status_allowed",
        ),
        sa.CheckConstraint(
            "facility_authorization_status IN ('pending', 'approved')",
            name="facility_authorization_status_allowed",
        ),
        sa.PrimaryKeyConstraint("target_id", name="pk_destination_api_profile"),
        sa.UniqueConstraint("profile_id", name="uq_destination_api_profile_profile_id"),
    )


def downgrade() -> None:
    if context.is_offline_mode() or sa.inspect(op.get_bind()).has_table("destination_api_profile"):
        op.drop_table("destination_api_profile")

"""Persist non-secret device discovery profiles.

Revision ID: 0007_device_profile
Revises: 0006_destination_api_validation
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0007_device_profile"
down_revision: str | None = "0006_destination_api_validation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not context.is_offline_mode() and sa.inspect(op.get_bind()).has_table("device_profile"):
        return
    op.create_table(
        "device_profile",
        sa.Column("profile_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=True),
        sa.Column("manufacturer", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("device_family", sa.String(length=32), nullable=False),
        sa.Column("firmware_software_scope", sa.String(length=80), nullable=False),
        sa.Column("transport", sa.String(length=32), nullable=False),
        sa.Column("protocol", sa.String(length=32), nullable=False),
        sa.Column("protocol_version", sa.String(length=80), nullable=True),
        sa.Column("interface_document_reference", sa.String(length=64), nullable=True),
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
        sa.Column(
            "results_only_confirmed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("receiver_contract_reference", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "device_family IN ('immunoassay', 'hematology', 'clinical_chemistry', 'urinalysis', "
            "'electrolyte', 'coagulation', 'hba1c', 'blood_gas', 'point_of_care', 'other')",
            name="device_family_allowed",
        ),
        sa.CheckConstraint(
            "transport IN ('unconfirmed', 'tcp', 'serial', 'file_feed', 'vendor_gateway')",
            name="transport_allowed",
        ),
        sa.CheckConstraint(
            "protocol IN ('unconfirmed', 'astm_e1394', 'hl7_v2', 'vendor_defined', 'other')",
            name="protocol_allowed",
        ),
        sa.CheckConstraint(
            "vendor_authorization_status IN ('pending', 'approved')",
            name="vendor_authorization_status_allowed",
        ),
        sa.CheckConstraint(
            "facility_authorization_status IN ('pending', 'approved')",
            name="facility_authorization_status_allowed",
        ),
        sa.PrimaryKeyConstraint("profile_id", name="pk_device_profile"),
    )


def downgrade() -> None:
    if context.is_offline_mode() or sa.inspect(op.get_bind()).has_table("device_profile"):
        op.drop_table("device_profile")

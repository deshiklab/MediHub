"""Durable store for allowlisted, non-secret destination contract worksheets."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from .database import create_database_engine
from .models import DestinationApiProfileRow

_PROFILE_FIELDS = (
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
)


def _utc_from_storage(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class DestinationApiProfileStoreError(RuntimeError):
    """Safe storage failure without leaking database details or bound values."""

    def __init__(self) -> None:
        super().__init__("destination_api_profile_store_unavailable")


class SqlAlchemyDestinationApiProfileStore:
    """Persist only the fixed, non-secret fields defined by DestinationApiProfileRow."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_database_engine(database_url)
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    async def start(self) -> None:
        """Ensure the worksheet table exists for local dashboard use without migrations."""

        try:
            async with self._engine.begin() as connection:
                await connection.run_sync(
                    lambda sync_connection: DestinationApiProfileRow.__table__.create(
                        sync_connection,
                        checkfirst=True,
                    )
                )
        except SQLAlchemyError:
            raise DestinationApiProfileStoreError() from None

    async def list_profiles(self) -> list[dict[str, Any]]:
        try:
            async with self._sessions() as session:
                rows = await session.scalars(
                    select(DestinationApiProfileRow).order_by(DestinationApiProfileRow.target_id)
                )
                return [self._payload(row) for row in rows]
        except SQLAlchemyError:
            raise DestinationApiProfileStoreError() from None

    async def save_profile(self, profile: dict[str, Any]) -> None:
        try:
            async with self._sessions.begin() as session:
                row = await session.get(DestinationApiProfileRow, profile["target_id"])
                if row is None:
                    session.add(DestinationApiProfileRow(**profile))
                else:
                    for field in _PROFILE_FIELDS:
                        setattr(row, field, profile[field])
        except SQLAlchemyError:
            raise DestinationApiProfileStoreError() from None

    async def close(self) -> None:
        try:
            await self._engine.dispose()
        except SQLAlchemyError:
            raise DestinationApiProfileStoreError() from None

    @staticmethod
    def _payload(row: DestinationApiProfileRow) -> dict[str, Any]:
        payload = {field: getattr(row, field) for field in _PROFILE_FIELDS}
        payload["profile_id"] = UUID(str(payload["profile_id"]))
        payload["created_at"] = _utc_from_storage(payload["created_at"])
        payload["updated_at"] = _utc_from_storage(payload["updated_at"])
        return payload

"""Durable store for allowlisted, non-secret device discovery profiles."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from .database import create_database_engine
from .models import DeviceProfileRow

_DEVICE_PROFILE_FIELDS = (
    "profile_id",
    "candidate_id",
    "manufacturer",
    "model",
    "device_family",
    "firmware_software_scope",
    "transport",
    "protocol",
    "protocol_version",
    "interface_document_reference",
    "vendor_authorization_status",
    "vendor_authorization_reference",
    "facility_authorization_status",
    "facility_authorization_reference",
    "results_only_confirmed",
    "receiver_contract_reference",
    "created_at",
    "updated_at",
)


def _utc_from_storage(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class DeviceProfileStoreError(RuntimeError):
    """Safe storage failure without leaking database details or bound values."""

    def __init__(self) -> None:
        super().__init__("device_profile_store_unavailable")


class SqlAlchemyDeviceProfileStore:
    """Persist only the fixed discovery fields defined by ``DeviceProfileRow``."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_database_engine(database_url)
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    @staticmethod
    def _create_tables(sync_connection: Any) -> None:
        DeviceProfileRow.__table__.create(sync_connection, checkfirst=True)

    async def start(self) -> None:
        """Ensure the non-secret discovery-profile table exists for dashboard use."""

        try:
            async with self._engine.begin() as connection:
                await connection.run_sync(self._create_tables)
        except SQLAlchemyError:
            raise DeviceProfileStoreError() from None

    async def list_profiles(self) -> list[dict[str, Any]]:
        try:
            async with self._sessions() as session:
                rows = await session.scalars(
                    select(DeviceProfileRow).order_by(
                        DeviceProfileRow.created_at,
                        DeviceProfileRow.profile_id,
                    )
                )
                return [self._payload(row) for row in rows]
        except SQLAlchemyError:
            raise DeviceProfileStoreError() from None

    async def save_profile(self, profile: dict[str, Any]) -> None:
        try:
            values = {field: profile[field] for field in _DEVICE_PROFILE_FIELDS}
            async with self._sessions.begin() as session:
                row = await session.get(DeviceProfileRow, profile["profile_id"])
                if row is None:
                    session.add(DeviceProfileRow(**values))
                else:
                    for field, value in values.items():
                        setattr(row, field, value)
        except SQLAlchemyError:
            raise DeviceProfileStoreError() from None

    async def close(self) -> None:
        try:
            await self._engine.dispose()
        except SQLAlchemyError:
            raise DeviceProfileStoreError() from None

    @staticmethod
    def _payload(row: DeviceProfileRow) -> dict[str, Any]:
        payload = {field: getattr(row, field) for field in _DEVICE_PROFILE_FIELDS}
        payload["profile_id"] = UUID(str(payload["profile_id"]))
        payload["created_at"] = _utc_from_storage(payload["created_at"])
        payload["updated_at"] = _utc_from_storage(payload["updated_at"])
        return payload

"""SQLAlchemy database base and explicit async engine construction."""

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase

CONSTRAINT_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared ORM metadata used by Alembic and the event store."""

    metadata = MetaData(naming_convention=CONSTRAINT_NAMING_CONVENTION)


def create_database_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine from an explicitly supplied, secret-safe URL."""

    if not database_url.strip():
        raise ValueError("database_url must not be empty")
    return create_async_engine(
        database_url,
        echo=echo,
        hide_parameters=True,
        pool_pre_ping=True,
    )

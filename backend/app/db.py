from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

# Neon suspends idle compute and drops idle connections: recycle them, and fail fast on connect.
engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5,
                             pool_recycle=240, connect_args={"timeout": 15})
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session():
    async with SessionLocal() as session:
        yield session

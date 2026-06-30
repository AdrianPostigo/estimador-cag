import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

# LLM Configuration
MODEL_NAME: str = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5")
PROVIDER: str = MODEL_NAME.split("/")[0] if "/" in MODEL_NAME else "anthropic"

# Database Configuration (Session 08)
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://estimator:estimator@localhost:5432/estimator",
)

# SQLAlchemy async engine
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

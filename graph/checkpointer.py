"""Postgres checkpointer wiring for the estimation graph (Session 13).

Reuses the project's PostgreSQL (the one with pgvector). The checkpointer creates
its own tables and coexists with the embedding tables — no new infrastructure.
"""

from __future__ import annotations

from app.config import DATABASE_URL


def checkpointer_conn_string() -> str:
    """Return a psycopg-compatible URL derived from the project's database URL.

    The service talks to Postgres through SQLAlchemy + asyncpg
    ("postgresql+asyncpg://..."), but AsyncPostgresSaver uses psycopg, which
    needs a plain "postgresql://..." URL.
    """
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

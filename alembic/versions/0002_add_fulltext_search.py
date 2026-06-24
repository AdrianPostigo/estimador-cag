"""Add full-text search support to chunks table.

Revision ID: 0002
Revises: 0001
Create Date: 2025-06-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add tsvector column for full-text search in Spanish
    op.add_column(
        "chunks",
        sa.Column(
            "content_fts",
            postgresql.TSVECTOR,
            sa.Computed(
                "to_tsvector('spanish', content)",
                persisted=True,
            ),
            nullable=False,
        ),
    )

    # Create GIN index for fast full-text search queries
    op.create_index(
        "ix_chunks_content_fts",
        "chunks",
        ["content_fts"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_content_fts", table_name="chunks")
    op.drop_column("chunks", "content_fts")

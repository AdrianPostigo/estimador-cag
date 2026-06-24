"""Rename metadata columns (reserved keyword in SQLAlchemy).

Revision ID: 0003
Revises: 0002
Create Date: 2025-06-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename metadata column in documents table
    op.alter_column(
        "documents",
        "metadata",
        new_column_name="doc_metadata",
    )

    # Rename metadata column in chunks table
    op.alter_column(
        "chunks",
        "metadata",
        new_column_name="chunk_metadata",
    )


def downgrade() -> None:
    # Rename back doc_metadata to metadata in documents table
    op.alter_column(
        "documents",
        "doc_metadata",
        new_column_name="metadata",
    )

    # Rename back chunk_metadata to metadata in chunks table
    op.alter_column(
        "chunks",
        "chunk_metadata",
        new_column_name="metadata",
    )

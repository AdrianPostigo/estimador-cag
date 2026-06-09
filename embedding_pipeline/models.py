"""SQLAlchemy ORM models for documents and chunks."""

from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Document(Base):
    """Document (presupuesto ingestado)."""

    __tablename__ = "documents"

    id = Column(BigInteger, primary_key=True)
    source_path = Column(Text, nullable=False, unique=True, index=True)
    document_type = Column(String(50), nullable=False)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata = Column(JSONB, server_default="{}", nullable=False)

    # Relationship
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document id={self.id} source_path={self.source_path}>"


class Chunk(Base):
    """Chunk (componente de presupuesto con embedding)."""

    __tablename__ = "chunks"

    id = Column(BigInteger, primary_key=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    metadata = Column(JSONB, server_default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<Chunk id={self.id} document_id={self.document_id} chunk_type={self.chunk_type}>"

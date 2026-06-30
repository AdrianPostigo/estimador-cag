"""Acceptance tests for grounded citation integrity and dangling detection."""

import pytest
from pydantic import ValidationError

from embedding_pipeline.citations import verify_citations
from embedding_pipeline.schemas import (
    EstimateLineItem,
    GroundedEstimateOutput,
    SourceReference,
)


def make_source(chunk_id: str = "1") -> SourceReference:
    return SourceReference(
        chunk_id=chunk_id,
        document_id="BG-2023-001",
        evidence="Component: Payment Processing ... Estimated hours: 80",
    )


def build_estimate(line_items: list[EstimateLineItem]) -> GroundedEstimateOutput:
    total = sum(item.hours for item in line_items)
    return GroundedEstimateOutput(
        project_summary="summary",
        line_items=line_items,
        total_hours=total,
    )


# --- Criterion 1: grounded=True must cite at least one source -----------------

def test_grounded_line_requires_a_source():
    with pytest.raises(ValidationError):
        EstimateLineItem(
            component="Auth", hours=10, rationale="r", grounded=True, sources=[]
        )


def test_grounded_line_with_source_is_valid():
    line = EstimateLineItem(
        component="Auth", hours=10, rationale="r", grounded=True,
        sources=[make_source("1")],
    )
    assert len(line.sources) == 1


def test_verify_marks_grounded_line_with_real_source():
    estimate = build_estimate(
        [EstimateLineItem(
            component="Auth", hours=10, rationale="r", grounded=True,
            sources=[make_source("1")],
        )]
    )
    report = verify_citations(estimate, retrieved_chunk_ids={"1", "2"}, request_id="t")
    assert report.has_dangling_citations is False
    assert report.grounded_lines == 1
    assert report.lines[0].status == "grounded"


# --- Criterion 2: a deliberate dangling citation is detected ------------------

def test_verify_detects_deliberate_dangling_citation():
    estimate = build_estimate(
        [EstimateLineItem(
            component="Auth", hours=10, rationale="r", grounded=True,
            sources=[make_source("99999")],  # id never in retrieved context
        )]
    )
    report = verify_citations(estimate, retrieved_chunk_ids={"1", "2"}, request_id="t")
    assert report.has_dangling_citations is True
    assert report.dangling_lines == 1
    assert report.lines[0].status == "dangling"
    assert "99999" in report.lines[0].dangling_chunk_ids


# --- Criterion 3: unsupported lines marked insufficient, no invented figures --

def test_ungrounded_line_cannot_invent_hours():
    with pytest.raises(ValidationError):
        EstimateLineItem(
            component="AI module", hours=40, rationale="r", grounded=False, sources=[]
        )


def test_ungrounded_line_cannot_cite_sources():
    with pytest.raises(ValidationError):
        EstimateLineItem(
            component="AI module", hours=0, rationale="r", grounded=False,
            sources=[make_source("1")],
        )


def test_ungrounded_line_is_marked_insufficient_data():
    estimate = build_estimate(
        [EstimateLineItem(
            component="AI module", hours=0, rationale="no source", grounded=False,
            sources=[],
        )]
    )
    report = verify_citations(estimate, retrieved_chunk_ids={"1", "2"}, request_id="t")
    assert report.insufficient_data_lines == 1
    assert report.lines[0].status == "insufficient_data"
    assert report.has_dangling_citations is False

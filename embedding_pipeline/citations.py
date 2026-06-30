"""Post-generation citation verification for grounded estimates."""

import structlog

from embedding_pipeline.schemas import (
    CitationReport,
    GroundedEstimateOutput,
    LineCitationStatus,
)

logger = structlog.get_logger()


def verify_citations(
    estimate: GroundedEstimateOutput,
    retrieved_chunk_ids: set[str],
    request_id: str,
) -> CitationReport:
    """
    Flag any line whose cited chunk_id was never in the retrieved context.

    Each line is classified into exactly one status:
      - "grounded":          grounded line whose cited chunk_ids are all present
                             in the retrieved context.
      - "dangling":          grounded line citing at least one chunk_id that was
                             never retrieved (invented / hallucinated source).
      - "insufficient_data": line explicitly marked grounded=False.

    A dangling citation is a quality failure and is logged at error level,
    correlated by request_id.

    Args:
        estimate: The generated grounded estimate to verify.
        retrieved_chunk_ids: Chunk ids that were actually handed to the LLM.
        request_id: Correlation id for structured logging.

    Returns:
        CitationReport with per-line status and aggregate counts.
    """
    line_statuses: list[LineCitationStatus] = []
    grounded_count = 0
    dangling_count = 0
    insufficient_count = 0

    for line in estimate.line_items:
        if not line.grounded:
            insufficient_count += 1
            line_statuses.append(
                LineCitationStatus(
                    component=line.component,
                    status="insufficient_data",
                    cited_chunk_ids=[],
                    dangling_chunk_ids=[],
                )
            )
            continue

        cited_chunk_ids = [source.chunk_id for source in line.sources]
        dangling_chunk_ids = [
            chunk_id
            for chunk_id in cited_chunk_ids
            if chunk_id not in retrieved_chunk_ids
        ]

        if dangling_chunk_ids:
            dangling_count += 1
            status = "dangling"
        else:
            grounded_count += 1
            status = "grounded"

        line_statuses.append(
            LineCitationStatus(
                component=line.component,
                status=status,
                cited_chunk_ids=cited_chunk_ids,
                dangling_chunk_ids=dangling_chunk_ids,
            )
        )

    report = CitationReport(
        total_lines=len(estimate.line_items),
        grounded_lines=grounded_count,
        dangling_lines=dangling_count,
        insufficient_data_lines=insufficient_count,
        has_dangling_citations=dangling_count > 0,
        lines=line_statuses,
    )

    logger.info(
        "citation_verification_completed",
        request_id=request_id,
        total_lines=report.total_lines,
        grounded_lines=report.grounded_lines,
        dangling_lines=report.dangling_lines,
        insufficient_data_lines=report.insufficient_data_lines,
        has_dangling_citations=report.has_dangling_citations,
    )

    if report.has_dangling_citations:
        offenders = [
            {"component": ls.component, "dangling_chunk_ids": ls.dangling_chunk_ids}
            for ls in line_statuses
            if ls.status == "dangling"
        ]
        logger.error(
            "dangling_citations_detected",
            request_id=request_id,
            dangling_lines=report.dangling_lines,
            offenders=offenders,
        )

    return report

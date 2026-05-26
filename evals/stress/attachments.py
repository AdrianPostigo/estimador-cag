"""
Synthetic PDF attachment generation for stress-testing large file handling.

Generates calibrated PDFs of specific sizes to measure:
- Latency impact
- Cost curve
- Content recall in summaries
"""

import io
from typing import Tuple

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


# Sample Lorem Ipsum text to repeat
LOREM_IPSUM = """Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
"""

# Calibration: bytes per page (approximate)
# A single LOREM_IPSUM repetition is ~380 bytes
# Typical PDF overhead: 1KB per page
BYTES_PER_LOREM = len(LOREM_IPSUM.encode('utf-8'))
ESTIMATED_OVERHEAD_PER_PAGE = 1024  # 1KB


def _calculate_repetitions(target_kb: int) -> int:
    """Calculate how many times to repeat LOREM_IPSUM to reach target size."""
    target_bytes = target_kb * 1024
    # Account for PDF overhead (rough estimate)
    content_budget = target_bytes - (ESTIMATED_OVERHEAD_PER_PAGE * 5)  # 5 pages overhead
    repetitions = max(1, content_budget // BYTES_PER_LOREM)
    return repetitions


def generate_pdf_bytes(size_kb: int) -> bytes:
    """
    Generate a synthetic PDF of approximately size_kb kilobytes.

    Uses reportlab if available, otherwise falls back to simple text-based PDF.
    """
    if not HAS_REPORTLAB:
        # Fallback: simple text-based PDF
        repetitions = _calculate_repetitions(size_kb)
        content = LOREM_IPSUM * repetitions
        # Very rough PDF wrapper (won't be valid, but demonstrates size scaling)
        pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length {len(content)} >>
stream
{content}
endstream
endobj
xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000074 00000 n
0000000133 00000 n
0000000281 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
{len(content) + 500}
%%EOF
"""
        return pdf_content.encode('utf-8')[:size_kb * 1024]

    # Use reportlab for proper PDF generation
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=letter)

    repetitions = _calculate_repetitions(size_kb)
    content = LOREM_IPSUM * repetitions

    # Split content into pages
    lines_per_page = 40
    words = content.split()
    current_page_words = []
    page_num = 1
    y_position = 750

    for word in words:
        current_page_words.append(word)

        if len(current_page_words) >= lines_per_page:
            # Render current page
            text = " ".join(current_page_words)
            pdf_canvas.drawString(50, y_position, text[:100])  # Truncate for display

            y_position -= 20

            if y_position < 50:
                # Next page
                pdf_canvas.showPage()
                page_num += 1
                y_position = 750
                current_page_words = []

    # Render remaining content
    if current_page_words:
        text = " ".join(current_page_words)
        pdf_canvas.drawString(50, y_position, text[:100])

    pdf_canvas.save()
    buffer.seek(0)
    pdf_bytes = buffer.read()

    # Pad or truncate to target size
    if len(pdf_bytes) < size_kb * 1024:
        # Pad with zeros
        padding = (size_kb * 1024) - len(pdf_bytes)
        pdf_bytes += b"\x00" * padding
    else:
        # Truncate
        pdf_bytes = pdf_bytes[: size_kb * 1024]

    return pdf_bytes


# ============================================================================
# Attachment Size Calibrations
# ============================================================================

ATTACHMENT_SIZES = {
    "baseline": 0,        # No attachment (baseline)
    "small": 5,           # ~2 pages
    "medium": 20,         # ~8 pages
    "large": 50,          # ~20 pages
    "huge": 100,          # ~40 pages (near cap of 60KB for MAX_ATTACHMENT_CHARS)
}


def get_attachment_pdf(size_label: str, prefer_fixtures: bool = True) -> Tuple[bytes, str]:
    """
    Get synthetic PDF bytes for a size label.

    Args:
        size_label: Key in ATTACHMENT_SIZES dict
        prefer_fixtures: If True, try to load from fixtures/ directory first

    Returns: (pdf_bytes, description)
    """
    if size_label not in ATTACHMENT_SIZES:
        raise ValueError(f"Unknown size label: {size_label}")

    size_kb = ATTACHMENT_SIZES[size_label]

    if size_kb == 0:
        return b"", "no_attachment"

    # Try to load from fixtures if prefer_fixtures=True
    if prefer_fixtures:
        from pathlib import Path
        fixtures_dir = Path(__file__).parent / "fixtures"
        fixture_file = fixtures_dir / f"attach_{size_kb}kb.pdf"

        if fixture_file.exists():
            with open(fixture_file, "rb") as f:
                pdf_bytes = f.read()
            return pdf_bytes, f"fixture_{size_kb}kb"

    # Fall back to dynamic generation
    pdf_bytes = generate_pdf_bytes(size_kb)
    actual_size_kb = len(pdf_bytes) / 1024

    return pdf_bytes, f"synthetic_{size_kb}kb_actual_{actual_size_kb:.1f}kb"

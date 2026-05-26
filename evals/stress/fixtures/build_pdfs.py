#!/usr/bin/env python3
"""
Build deterministic synthetic PDF fixtures for attachment stress testing.

Generates:
- attach_5kb.pdf
- attach_20kb.pdf
- attach_50kb.pdf
- attach_100kb.pdf

These are deterministic: same seed → same output, suitable for version control.
Run this script to regenerate fixtures: python build_pdfs.py
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import evals.stress.attachments
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from evals.stress.attachments import generate_pdf_bytes


def build_fixtures():
    """Generate all PDF fixtures."""
    fixtures_dir = Path(__file__).parent

    sizes = {
        "attach_5kb.pdf": 5,
        "attach_20kb.pdf": 20,
        "attach_50kb.pdf": 50,
        "attach_100kb.pdf": 100,
    }

    for filename, size_kb in sizes.items():
        filepath = fixtures_dir / filename

        print(f"Generating {filename}...", end=" ", flush=True)

        # Generate deterministic PDF bytes
        pdf_bytes = generate_pdf_bytes(size_kb)

        # Write to file
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        actual_size = len(pdf_bytes) / 1024
        print(f"OK ({actual_size:.1f} KB)")

    print("\nAll fixtures generated successfully.")


if __name__ == "__main__":
    build_fixtures()

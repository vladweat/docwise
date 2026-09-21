#!/usr/bin/env python3
"""Write demo PDFs and test DOCX into samples/documents/ (no DB, no Docker)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
EVAL_DIR = REPO_ROOT / "eval"
OUT_DIR = Path(__file__).resolve().parent / "documents"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(EVAL_DIR))

from corpus import DEMO_CATALOG, build_pdf  # noqa: E402
from tests.docx_fixtures import policy_docx_bytes  # noqa: E402
from tests.pdf_fixtures import policy_pdf_bytes  # noqa: E402


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    for spec in DEMO_CATALOG:
        path = OUT_DIR / spec.filename
        path.write_bytes(build_pdf(spec))
        written.append(spec.filename)

    extras = {
        "Parser-Policy-Test.pdf": policy_pdf_bytes(),
        "Travel-Policy-Test.docx": policy_docx_bytes(),
    }
    for name, data in extras.items():
        (OUT_DIR / name).write_bytes(data)
        written.append(name)

    print(f"Wrote {len(written)} files to {OUT_DIR}")
    for name in sorted(written):
        print(f"  {OUT_DIR / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

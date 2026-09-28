# -*- coding: utf-8 -*-
"""Convert the Step 09 denoising supervisor report from Markdown to .docx.

Reuses the exact same converter engine as the DMC progress report
(`_md_to_docx.py`), by monkey-patching its SRC/OUT module globals before
calling `main()`.  This guarantees the same §8-compliant formatting
(11 pt body, 1.27 cm margins, single spacing, footer page number only)
without duplicating a single line of layout logic.

Run:
    <venv>/python.exe -X utf8 tools/_md_to_docx_step09.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paths as _paths  # noqa: E402
import _md_to_docx as conv  # noqa: E402

ROOT = _paths.PROJECT_ROOT

conv.SRC = ROOT / "04_reports" / "02_denoising" / "docs" / "STEP09_SUPERVISOR_REPORT.md"
conv.OUT = ROOT / "04_reports" / "02_denoising" / "docs" / "Step09_Denoising_Supervisor_Report.docx"

if __name__ == "__main__":
    print(f"src : {conv.SRC}")
    print(f"out : {conv.OUT}")
    rc = conv.main()
    print(f"exit: {rc}")
    raise SystemExit(rc)

# -*- coding: utf-8 -*-
"""Convert a .docx to .pdf using the locally installed Microsoft Word (COM).

Usage:  python tools/_docx2pdf.py <src.docx> <dst.pdf>

Falls back with a clear message if Word is unavailable. No LibreOffice needed.
"""
from __future__ import annotations

import os
import sys


def convert(src: str, dst: str) -> dict:
    import win32com.client as win32

    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    app = None
    doc = None
    try:
        app = win32.DispatchEx("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        # Open(FileName, ConfirmConversions, ReadOnly, AddToRecentFiles)
        doc = app.Documents.Open(src, False, True, False)

        # 17 = wdFormatPDF
        doc.SaveAs2(dst, FileFormat=17)

        pages = int(doc.ComputeStatistics(2))   # wdStatisticPages
        words = int(doc.ComputeStatistics(0))   # wdStatisticWords
        return dict(pages=pages, words=words, size=os.path.getsize(dst))
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    try:
        r = convert(src, dst)
    except Exception as e:
        print("[pdf] FAILED: %s: %s" % (type(e).__name__, e))
        return 1
    print("[pdf] %s" % dst)
    print("[pdf] pages=%d words=%d size=%.2f MB"
          % (r["pages"], r["words"], r["size"] / 1024 / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())

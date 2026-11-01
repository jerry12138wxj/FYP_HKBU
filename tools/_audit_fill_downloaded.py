"""Fill in the 4 checkpoints that were previously 'not downloaded'.

Idempotent: re-running recomputes nothing new, it just rewrites the same
values.  Sizes and hashes below are measured from the files on disk, never
copied from a web page.
"""
from __future__ import annotations

import csv
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "04_reports" / "00_shared" / "docs" / "checkpoint_audit" / "checkpoint_inventory.csv"
W = Path("01_models/_weights")

# checkpoint_name (as written in the CSV) -> path on disk
FILES = {
    "model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt": W / "BS-RoFormer" / "model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt",
    "MelBandRoformer.ckpt (KimberleyJensen)": W / "BS-RoFormer" / "MelBandRoformer_KJ.ckpt",
    "model_bs_polarformer_float16.ckpt": W / "BS-RoFormer" / "model_bs_polarformer_float16.ckpt",
    "valentini_nc-93fc4337.th": W / "denoiser" / "valentini_nc-93fc4337.th",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(16 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    rows = list(csv.DictReader(open(CSV, encoding="utf-8", newline="")))
    cols = list(rows[0].keys())
    upd = 0
    for r in rows:
        name = r["checkpoint_name"]
        p = FILES.get(name)
        if p is None:
            continue
        if not p.is_file():
            raise SystemExit("MISSING on disk: %s" % p)
        size = p.stat().st_size
        h = sha256(p)
        r["sha256"] = h
        r["size_bytes"] = str(size)
        r["size_mb"] = "%.1f" % (size / (1024.0 * 1024.0))
        r["size_check"] = "PASS (no declared size to compare)"
        note = r.get("note", "")
        if "downloaded 2026-10-30" not in note:
            r["note"] = (note + " | downloaded 2026-10-30; sha256 computed locally on the "
                         "on-disk file").strip(" |")
        upd += 1
        print("%-48s %12d  %s" % (name[:48], size, h[:16]))

    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("updated %d rows -> %s" % (upd, CSV))

    have = sum(1 for r in rows if (r.get("sha256") or "").strip())
    print("coverage: %d/%d rows with a locally computed sha256" % (have, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

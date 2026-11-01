# -*- coding: utf-8 -*-
"""Collect RPCA run records + audio sanity (dur / peak / clip), write rpca_results.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

RUNS_JSON = _paths.REPORTS / "01_separation" / "data" / "comparison" / "model_runs_run.json"
OUT_DIR = _paths.OUTPUTS / "_test_run" / "RPCA"
DST = Path(r"D:\FYP_HKBU_runs\rerun_20261030_2358")


def main():
    doc = json.loads(RUNS_JSON.read_text(encoding="utf-8"))
    rows = []
    for song, rec in doc["runs"].get("rpca", {}).items():
        audio = OUT_DIR / song / "vocals.flac"
        info = {}
        if audio.exists():
            y, sr = sf.read(str(audio), dtype="float32", always_2d=True)
            peak = float(np.abs(y).max())
            info = {
                "out": str(audio), "out_mb": round(audio.stat().st_size / 2**20, 2),
                "out_sr": sr, "out_ch": int(y.shape[1]),
                "out_dur_s": round(y.shape[0] / sr, 3),
                "peak": round(peak, 4),
                "clip_frac": float(np.mean(np.abs(y) >= 0.999)),
            }
        rows.append({
            "song": song,
            "duration_s": rec.get("duration_s"),
            "infer_s": rec.get("infer_s"),
            "rtf": rec.get("rtf"),
            "cross_stem_si_sdr": {k: v["si_sdr"] for k, v in (rec.get("cross_stem") or {}).get("vocals", {}).items()},
            "best_match": rec.get("best_match", {}).get("vocals", {}),
            "status": rec.get("status"),
            "timestamp": rec.get("timestamp"),
            **info,
        })
    DST.mkdir(parents=True, exist_ok=True)
    out = {"source": str(RUNS_JSON), "model": "RPCA (Inexact-ALM)", "runs": rows}
    (DST / "rpca_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in rows:
        print(r["song"], "| rtf", r["rtf"], "| best", r["best_match"], "| peak", r.get("peak"),
              "| dur", r.get("out_dur_s"), "| clip", r.get("clip_frac"))


if __name__ == "__main__":
    main()

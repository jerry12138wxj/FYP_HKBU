"""Probe A extension: paired clean-passthrough on the SAME clean files as the full eval.

The 6-item version used zero-noise clips whose hf_in median was 0.196, while the
full-manifest hf_clean median is 0.221. That 0.025 gap means those 6 items cannot
rule out a genuine low-pass. This probe takes N>=100 real clean_testset_wav files
and measures the paired dHF on exactly those.

Output: denoiser/data/denoise_probeA_paired.json
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
import torchaudio.functional as AF  # noqa: E402

import _denoise_registry as REG  # noqa: E402

ROOT = _paths.PROJECT_ROOT
OUT = ROOT / "04_reports" / "denoiser" / "data" / "denoise_probeA_paired.json"
VAL_CLEAN = ROOT / "02_databases" / "Valentini" / "clean_testset_wav"
CONTRACT_SR, ANA_SR = 44100, 16000
N = 120


def hf(x):
    X = np.abs(np.fft.rfft(x))
    return float(X[len(X) // 4:].sum() / (X.sum() + 1e-12))


def rms(x):
    return float(np.sqrt((x ** 2).mean() + 1e-12))


def rs(a, fi, fo):
    if fi == fo:
        return np.asarray(a, dtype=np.float32)
    return AF.resample(torch.from_numpy(np.asarray(a, dtype=np.float32))[None], fi, fo)[0].numpy()


def main():
    files = sorted(VAL_CLEAN.glob("*.wav"))[:N]
    print("[data] %d clean files" % len(files))
    out = {"task": "Probe A 配对版：真实 clean 直通", "n": len(files), "models": {}}

    for name in ["denoiser_dns48", "denoiser_master64", "mel_roformer_denoise"]:
        run_fn, _s, _i = REG.REGISTRY[name]["loader"]()
        print("== %s" % name)
        rows = []
        for p in files:
            x, sr = sf.read(str(p), dtype="float32", always_2d=True)
            x = rs(x.mean(1), sr, ANA_SR)
            x44 = rs(x, ANA_SR, CONTRACT_SR)
            y = np.asarray(run_fn(np.ascontiguousarray(np.stack([x44, x44], -1)))["enhanced"])
            y = rs(y.mean(1), CONTRACT_SR, ANA_SR)
            L = min(len(x), len(y))
            rows.append({"id": p.stem,
                         "ratio": rms(y[:L]) / rms(x[:L]),
                         "hf_in": hf(x[:L]), "hf_out": hf(y[:L]),
                         "dhf": hf(y[:L]) - hf(x[:L])})
        out["models"][name] = {
            "n": len(rows), "rows": rows,
            "med_ratio": round(float(np.median([r["ratio"] for r in rows])), 4),
            "med_hf_in": round(float(np.median([r["hf_in"] for r in rows])), 4),
            "med_hf_out": round(float(np.median([r["hf_out"] for r in rows])), 4),
            "med_dhf_paired": round(float(np.median([r["dhf"] for r in rows])), 4),
            "p05_dhf": round(float(np.percentile([r["dhf"] for r in rows], 5)), 4),
            "p95_dhf": round(float(np.percentile([r["dhf"] for r in rows], 95)), 4),
        }
        d = out["models"][name]
        print("   ratio=%.4f  hf %.4f -> %.4f  paired dHF med=%+.4f [p05 %+.4f, p95 %+.4f]"
              % (d["med_ratio"], d["med_hf_in"], d["med_hf_out"],
                 d["med_dhf_paired"], d["p05_dhf"], d["p95_dhf"]))

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n[json] %s" % OUT)


if __name__ == "__main__":
    raise SystemExit(main())

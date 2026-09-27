"""Quantify the 16 kHz double-resample bug's blast radius on valentini."""
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
from pathlib import Path  # noqa: E402

import _denoise_registry as R  # noqa: E402

ROOT = _paths.PROJECT_ROOT
MAN = ROOT / "04_reports" / "02_denoising" / "data" / "denoise_manifest.json"
N = 150


def rms(a):
    return float(np.sqrt((a ** 2).mean() + 1e-12))


def contract(xin, sr_in, fn):
    """Correct path: resample to contract 44.1k, stack stereo, run, come back."""
    xa = AF.resample(torch.from_numpy(xin)[None], sr_in, 44100)[0].numpy()
    y = np.asarray(fn(np.ascontiguousarray(np.stack([xa, xa], -1)))["enhanced"]).mean(1)
    return AF.resample(torch.from_numpy(y)[None], 44100, sr_in)[0].numpy()


man = json.loads(MAN.read_text(encoding="utf-8"))
res = {}
for mdl in ["denoiser_dns48", "denoiser_master64", "mel_roformer_denoise"]:
    fn, _s, _i = R.REGISTRY[mdl]["loader"]()
    res[mdl] = {}
    for sr in (16000, 44100):
        cells = [r for r in man["cells"]
                 if r["subset"] == "valentini" and r["sr"] == sr
                 and r["model"] == mdl and r.get("ok")][:N]
        old = [r.get("level_ratio") for r in cells if r.get("level_ratio") is not None]
        new = []
        for r in cells:
            p = ROOT / "02_databases" / "Valentini" / "noisy_testset_wav" / (r["clip_id"] + ".wav")
            x, s0 = sf.read(str(p), dtype="float32", always_2d=True)
            x = x.mean(1)
            y = contract(x, s0, fn)
            xr = AF.resample(torch.from_numpy(x)[None], s0, sr)[0].numpy()
            yr = AF.resample(torch.from_numpy(y)[None], s0, sr)[0].numpy()
            L = min(len(xr), len(yr))
            new.append(rms(yr[:L]) / rms(xr[:L]))
        res[mdl][sr] = {
            "old_med": round(float(np.median(old)), 4),
            "old_lt02": sum(1 for v in old if v < 0.2), "old_n": len(old),
            "new_med": round(float(np.median(new)), 4),
            "new_lt02": sum(1 for v in new if v < 0.2), "new_n": len(new),
            "clip_ids": [r["clip_id"] for r in cells],
        }
        d = res[mdl][sr]
        print("%-22s sr=%-6d OLD med=%.4f  n<0.2=%3d/%-3d | NEW med=%.4f  n<0.2=%3d/%-3d"
              % (mdl, sr, d["old_med"], d["old_lt02"], d["old_n"],
                 d["new_med"], d["new_lt02"], d["new_n"]))

out = ROOT / "04_reports" / "02_denoising" / "data" / "denoise_sr_bug_audit.json"
out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n[json]", out)

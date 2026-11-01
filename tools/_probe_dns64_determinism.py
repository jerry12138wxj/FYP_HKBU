"""Isolate the dns64 / master64 metric discrepancy seen between the offline
export (all 5 models loaded up-front) and the live server (lazy loading).

Runs one model in a *fresh* process on the same clip and prints dSDR, so we can
tell whether the value depends on how many models were loaded before it.
"""
import sys
from pathlib import Path

ROOT = Path(r"E:\FYP_HKBU")
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402
import paths as _paths  # noqa: E402
_paths.setup_env()

import _denoise_registry as REG  # noqa: E402
from _denoise_eval import load_mono, resample_mono, si_sdr  # noqa: E402

CLIP = "p232_340"
D = ROOT / "03_outputs" / "_denoise_ab" / CLIP

keys = sys.argv[1:] or ["denoiser_dns64"]

noisy16 = load_mono(D / "noisy.wav", 16000)
clean16 = load_mono(D / "clean.wav", 16000)

for key in keys:
    run_fn, load_s, info = REG.REGISTRY[key]["loader"]()
    csr = int(getattr(run_fn, "contract_sr", 44100))
    x = resample_mono(noisy16, 16000, csr)
    stack = np.stack([x, x], axis=-1).astype(np.float32)

    est1 = np.asarray(run_fn(stack)["enhanced"], dtype=np.float32)
    est2 = np.asarray(run_fn(stack)["enhanced"], dtype=np.float32)   # repeat == determinism check

    def dsdr(est):
        e16 = resample_mono(est.mean(1), csr, 16000)
        n = min(len(e16), len(noisy16), len(clean16))
        return si_sdr(clean16[:n], e16[:n]) - si_sdr(clean16[:n], noisy16[:n])

    d1, d2 = dsdr(est1), dsdr(est2)
    same = bool(np.array_equal(est1, est2))
    print("%-24s load %5.1fs | dSDR run1 %+7.4f  run2 %+7.4f  (bitwise identical: %s)"
          % (key, load_s, d1, d2, same))

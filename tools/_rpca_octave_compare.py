# -*- coding: utf-8 -*-
"""Compare numpy vs Octave IALM on the same magnitude matrix + reconstruct audio."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import librosa  # noqa: E402
import numpy as np  # noqa: E402

BASE = Path(r"D:\FYP_HKBU_runs\rerun_20261030_2358\rpca_octave")
EPS = 1e-10


def ialm(M, lam=None, max_iter=120, tol=1e-6):
    m, n = M.shape
    if lam is None:
        lam = 1.0 / np.sqrt(max(m, n))
    nrm = max(np.linalg.norm(M, 2), EPS)
    Y, mu, rho = M / nrm, 1.25 / nrm, 1.5
    L, S = np.zeros_like(M), np.zeros_like(M)
    fM = np.linalg.norm(M, "fro") + EPS
    it = 0
    resid = 0.0
    for it in range(1, max_iter + 1):
        U, sig, Vt = np.linalg.svd(M - S + Y / mu, full_matrices=False)
        L = (U * np.maximum(sig - 1.0 / mu, 0.0)) @ Vt
        T = M - L + Y / mu
        S = np.sign(T) * np.maximum(np.abs(T) - lam / mu, 0.0)
        Z = M - L - S
        Y = Y + mu * Z
        resid = np.linalg.norm(Z, "fro") / fM
        if resid < tol:
            break
        mu *= rho
    return L, S, it, resid


def si_sdr(ref, est):
    n = min(len(ref), len(est))
    ref, est = ref[:n], est[:n]
    a = np.dot(est, ref) / (np.dot(ref, ref) + EPS)
    e = est - a * ref
    return 10 * np.log10((a * a * np.dot(ref, ref) + EPS) / (np.dot(e, e) + EPS))


def main():
    mag = np.load(BASE / "mag.npy")
    mix = np.load(BASE / "mix.npy")
    meta = json.loads((BASE / "meta.json").read_text(encoding="utf-8"))
    Lp, Sp, it_py, resid_py = ialm(mag.astype(np.float64))
    mask_py = np.clip(np.abs(Sp) / (np.abs(Sp) + np.abs(Lp) + EPS), 0, 1)

    Lo = np.fromfile(BASE / "L_f32.bin", dtype=np.float32).reshape(mag.shape)
    So = np.fromfile(BASE / "S_f32.bin", dtype=np.float32).reshape(mag.shape)
    mask_o = np.fromfile(BASE / "mask_f32.bin", dtype=np.float32).reshape(mag.shape)

    st = (BASE / "octave_stats.txt").read_text(encoding="utf-8")
    ostats = dict(l.split("=", 1) for l in st.strip().splitlines())
    it_oc = int(ostats["iters"])

    def rel(a, b):
        return float(np.linalg.norm(a - b) / (np.linalg.norm(a) + EPS))

    cmp = {
        "shape": list(mag.shape),
        "numpy_iters": it_py,
        "octave_iters": it_oc,
        "numpy_final_rel_resid": float(resid_py),
        "octave_final_rel_resid": float(ostats["final_rel_resid"]),
        "octave_elapsed_s": float(ostats["elapsed_s"]),
        "rel_err_L": rel(Lp, Lo),
        "rel_err_S": rel(Sp, So),
        "rel_err_mask": rel(mask_py, mask_o),
        "max_abs_err_L": float(np.abs(Lp - Lo).max()),
        "max_abs_err_S": float(np.abs(Sp - So).max()),
        "max_abs_err_mask": float(np.abs(mask_py - mask_o).max()),
        "corr_mask": float(np.corrcoef(mask_py.ravel(), mask_o.ravel())[0, 1]),
        "mask_mean_py": float(mask_py.mean()),
        "mask_mean_oc": float(mask_o.mean()),
    }

    import librosa as _lb

    X = _lb.stft(mix, n_fft=meta["n_fft"], hop_length=meta["hop"])
    y_py = _lb.istft(mask_py * X, hop_length=meta["hop"], length=len(mix))
    y_oc = _lb.istft(mask_o * X, hop_length=meta["hop"], length=len(mix))
    cmp["waveform_max_abs_diff"] = float(np.abs(y_py - y_oc).max())
    cmp["si_sdr_py_vs_oc"] = float(si_sdr(y_py, y_oc))
    cmp["octave_note"] = "same magnitude matrix; only the IALM loop runs in Octave 11.3.0"

    (BASE / "compare.json").write_text(json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in cmp.items():
        print(f"{k} = {v}")


if __name__ == "__main__":
    main()

"""Probe every board-2 (denoise) model exactly as the live server drives it.

Reports, per model: load time, contract rate, output keys, output shape,
inference time, and any exception -- so "does it actually run?" is answered by
evidence rather than by looking at the UI.

    python tools/_probe_denoise_models.py [model ...]
"""
from __future__ import annotations

import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402

import _denoise_registry as REG  # noqa: E402
from _denoise_eval import list_valentini, load_mono, resample_mono  # noqa: E402

METRIC_SR = 16000
ROOT = _paths.PROJECT_ROOT


def main(argv):
    keys = argv or [
        "denoiser_dns48", "denoiser_dns64", "denoiser_master64",
        "mel_roformer_denoise", "mel_roformer_denoise_aggr",
    ]
    rec = None
    for r in list_valentini():
        if r["clip_id"] == "p232_340":
            rec = r
            break
    if rec is None:
        rec = list_valentini()[0]
    noisy16 = load_mono(rec["noisy_path"], METRIC_SR, max_seconds=60.0)
    print("probe clip: %s  (%.2f s @ %d Hz mono)"
          % (rec["clip_id"], len(noisy16) / METRIC_SR, METRIC_SR))
    print("=" * 78)

    bad = []
    for k in keys:
        print("\n[%s]" % k)
        t0 = time.time()
        try:
            run_fn, load_s, info = REG.REGISTRY[k]["loader"]()
        except Exception as e:                                    # noqa: BLE001
            print("  LOAD FAILED  %s: %s" % (type(e).__name__, e))
            traceback.print_exc()
            bad.append((k, "load", str(e)))
            continue
        print("  load %.2fs | contract_sr=%s | native=%s Hz | %s ch | n_stems=%s"
              % (load_s, getattr(run_fn, "contract_sr", "?"),
                 info.get("sample_rate"), info.get("channels"), info.get("n_stems")))
        print("  params %.2f M | targets=%s | missing=%s unexpected=%s"
              % (info.get("params", 0) / 1e6, info.get("targets"),
                 info.get("n_missing_keys"), info.get("n_unexpected_keys")))

        csr = int(getattr(run_fn, "contract_sr", 44100))
        x = noisy16 if csr == METRIC_SR else resample_mono(noisy16, METRIC_SR, csr)
        stack = np.stack([x, x], axis=-1).astype(np.float32)
        print("  input  (N,2)=%s @ %d Hz" % (stack.shape, csr))
        try:
            t1 = time.time()
            got = run_fn(stack)
            dt = time.time() - t1
        except Exception as e:                                    # noqa: BLE001
            print("  RUN FAILED   %s: %s" % (type(e).__name__, e))
            traceback.print_exc()
            bad.append((k, "run", str(e)))
            continue
        if not isinstance(got, dict):
            print("  RUN FAILED   expected dict, got %s" % type(got).__name__)
            bad.append((k, "run", "non-dict output"))
            continue
        print("  run %.3fs | keys=%s" % (dt, list(got.keys())))
        for kk, vv in got.items():
            a = np.asarray(vv)
            print("    %-10s shape=%s  rms=%.5f  peak=%.4f  finite=%s"
                  % (kk, a.shape, float(np.sqrt(np.mean(a ** 2))),
                     float(np.max(np.abs(a))), bool(np.isfinite(a).all())))
        if "enhanced" not in got:
            print("  ⚠ the live server reads got['enhanced'] -- this model would "
                  "raise KeyError there.")
            bad.append((k, "key", "no 'enhanced' key: %s" % list(got.keys())))

    print("\n" + "=" * 78)
    if bad:
        print("PROBLEMS (%d):" % len(bad))
        for k, where, msg in bad:
            print("  %-28s %-5s %s" % (k, where, msg))
    else:
        print("ALL MODELS OK -- load + run + 'enhanced' key present")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

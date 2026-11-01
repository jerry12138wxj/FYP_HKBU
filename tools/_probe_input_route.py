"""Why does the live server disagree with the offline A/B manifest on exactly
dns64 / master64?

Hypothesis: the two pipelines feed the model *slightly different inputs*.

  offline : Valentini original (48 kHz) --load_mono@16k--> 16 kHz --resample--> 44.1 kHz
  live    : stored noisy.wav  (44.1 kHz) --load_mono@16k--> 16 kHz --resample--> 44.1 kHz

Both routes are run through the same models; dSDR is computed against each
route's own 16 kHz noisy input (never a rate-mismatched reference).
"""
import sys
from pathlib import Path

ROOT = Path(r"E:\FYP_HKBU")
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402
import paths as _paths  # noqa: E402
_paths.setup_env()

import _denoise_registry as REG  # noqa: E402
from _denoise_eval import load_mono, resample_mono, si_sdr, list_valentini  # noqa: E402

CLIP = "p232_340"
AB = ROOT / "03_outputs" / "_denoise_ab" / CLIP

row = next(r for r in list_valentini() if r["clip_id"] == CLIP)

# route A: straight from the dataset (what the offline export used)
a16 = load_mono(row["noisy_path"], 16000)
a44 = resample_mono(a16, 16000, 44100)
a_clean = load_mono(row["clean_path"], 16000)

# route B: re-decode the stored 44.1 kHz wav (what the live server does)
b16 = load_mono(AB / "noisy.wav", 16000)
b44 = resample_mono(b16, 16000, 44100)
b_clean = load_mono(AB / "clean.wav", 16000)

print("route A 16k len %d | route B 16k len %d" % (len(a16), len(b16)))
print("input SI-SDR  A %.4f dB   B %.4f dB"
      % (si_sdr(a_clean[:min(len(a_clean), len(a16))], a16[:min(len(a_clean), len(a16))]),
         si_sdr(b_clean[:min(len(b_clean), len(b16))], b16[:min(len(b_clean), len(b16))])))

keys = ["denoiser_dns48", "denoiser_dns64", "denoiser_master64",
        "mel_roformer_denoise", "mel_roformer_denoise_aggr"]
OFF = {"denoiser_dns48": 21.8492, "denoiser_dns64": 18.8516,
       "denoiser_master64": 19.5380, "mel_roformer_denoise": 0.9638,
       "mel_roformer_denoise_aggr": 21.1674}


def dsdr(run_fn, x44, x16, clean16, csr):
    est = np.asarray(run_fn(np.stack([x44, x44], -1).astype(np.float32))["enhanced"], np.float32)
    e16 = resample_mono(est.mean(1), csr, 16000)
    n = min(len(e16), len(x16), len(clean16))
    return (si_sdr(clean16[:n], e16[:n]) - si_sdr(clean16[:n], x16[:n]))


print("\n%-30s %11s %11s %11s   %s" % ("model", "routeA(48k)", "routeB(44k)", "manifest", "A-manifest"))
for key in keys:
    run_fn, _ls, _info = REG.REGISTRY[key]["loader"]()
    csr = int(getattr(run_fn, "contract_sr", 44100))
    da = dsdr(run_fn, a44, a16, a_clean, csr)
    db = dsdr(run_fn, b44, b16, b_clean, csr)
    print("%-30s %11.4f %11.4f %11.4f   %+.4f"
          % (key, da, db, OFF[key], da - OFF[key]))

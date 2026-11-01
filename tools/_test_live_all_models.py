"""Drive the live server the way the browser does, for every board-2 model.

Two inputs are tested:
  * a short Valentini clip (built-in sample, ~1.4 s)
  * a LONG music excerpt (~30 s) uploaded as a file -- the case the built-in
    samples never exercise, and the one that maxes out the 228 M mel models.

    python tools/_test_live_all_models.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

ROOT = _paths.PROJECT_ROOT
BASE = "http://127.0.0.1:8123"
MODELS = ["denoiser_dns48", "denoiser_dns64", "denoiser_master64",
          "mel_roformer_denoise", "mel_roformer_denoise_aggr"]


def post(path, obj):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d: %s" % (e.code, e.read().decode("utf-8", "ignore")[:300])}


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=900) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d: %s" % (e.code, e.read().decode("utf-8", "ignore")[:300])}


def run_all(sid, tag):
    print("\n--- %s (sid=%s) ---" % (tag, sid))
    fails = 0
    for m in MODELS:
        j = post("/api/run", {"sid": sid, "model": m})
        if j.get("error"):
            print("  %-26s FAILED  %s" % (m, str(j["error"])[:160]))
            fails += 1
        else:
            mt = j.get("metrics") or {}
            print("  %-26s ok  infer %.2fs  %.1f MB  out %s  dSDR %s"
                  % (m, j.get("infer_s", -1), j.get("mb", -1), j.get("out_sr"),
                     mt.get("si_sdr_improve")))
    return fails


def main():
    total_fail = 0

    j = get("/api/sample?id=p232_340")
    if j.get("error"):
        print("sample failed:", j["error"])
        return 1
    total_fail += run_all(j["sid"], "short built-in sample p232_340 (1.4 s)")

    # a ~30 s stereo music excerpt, 44.1 kHz -- the "long upload" case
    mix = ROOT / "02_databases" / "MUSDB18-HQ" / "test" / "PR - Oh No" / "mixture.wav"
    if not mix.is_file():
        print("skipped long-input test: %s missing" % mix)
    else:
        info = sf.info(str(mix))
        want = int(30 * info.samplerate)
        a, sr = sf.read(str(mix), frames=want, always_2d=True)
        tmp = ROOT / "03_outputs" / "_denoise_live" / "_long_30s.wav"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(tmp), a.astype(np.float32), sr, subtype="PCM_16")
        nz = base64.b64encode(tmp.read_bytes()).decode("ascii")
        j = post("/api/session", {"name": "long_30s.wav", "noisy_b64": nz})
        if j.get("error"):
            print("session failed:", j["error"])
            total_fail += 1
        else:
            total_fail += run_all(j["sid"], "long upload 30 s stereo music")

    print("\n" + "=" * 78)
    print("FAILURES: %d" % total_fail)
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())

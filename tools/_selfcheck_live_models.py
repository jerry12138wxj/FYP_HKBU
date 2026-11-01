# -*- coding: utf-8 -*-
"""Self-check: every model the two pages expose must actually RUN.

Writes nothing but its own report.  Covers, against the live server:

  A. denoise   -- all 5 board-2 models, on a built-in 1.4 s sample AND on a
                  30 s stereo music upload (the long case the samples miss).
  B. separation -- all 13 board-1 models on a 30 s MUSDB18-HQ session (with
                  ground truth, so SI-SDR is checked too).  Under the 8 s rule
                  some models are *expected* to be SKIPPED; the run only fails
                  if something reports `failed`.
  C. the upload path  -- POST /api/sep/session with a real file.

Exit code 0 only when there are zero FAILs.

    python tools/_selfcheck_live_models.py                # everything
    python tools/_selfcheck_live_models.py --denoise
    python tools/_selfcheck_live_models.py --sep
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

ROOT = _paths.PROJECT_ROOT
BASE = "http://127.0.0.1:8123"
DENOISE_KEYS = ["denoiser_dns48", "denoiser_dns64", "denoiser_master64",
                "mel_roformer_denoise", "mel_roformer_denoise_aggr"]
SONG = "PR - Oh No"
LONG_SEC = 30


def get(path, timeout=900):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d: %s" % (e.code, e.read().decode("utf-8", "ignore")[:300])}
    except Exception as e:                                     # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, e)}


def post(path, obj, timeout=1800):
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d: %s" % (e.code, e.read().decode("utf-8", "ignore")[:400])}
    except Exception as e:                                     # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, e)}


RESULTS: list = []


def note(section, model, status, detail=""):
    RESULTS.append((section, model, status, detail))
    mark = {"PASS": "ok  ", "SKIP": "skip", "FAIL": "FAIL"}.get(status, "?   ")
    print("  [%s] %-26s %s" % (mark, model, detail))


# ------------------------------------------------------------------ denoise ---
def check_denoise():
    print("\n=== A. denoise (board 2) ===")
    j = get("/api/sample?id=p232_340")
    if j.get("error"):
        note("denoise/short", "session", "FAIL", j["error"])
        return
    for m in DENOISE_KEYS:
        r = post("/api/run", {"sid": j["sid"], "model": m})
        if r.get("error"):
            note("denoise/short", m, "FAIL", str(r["error"])[:160])
        else:
            note("denoise/short", m, "PASS",
                 "infer %.2fs  %s  dSDR %s" % (r.get("infer_s", -1), r.get("src", "")[-24:],
                                               (r.get("metrics") or {}).get("si_sdr_improve")))

    mix = ROOT / "02_databases" / "MUSDB18-HQ" / "test" / SONG / "mixture.wav"
    if not mix.is_file():
        note("denoise/long", "fixture", "FAIL", "missing %s" % mix)
        return
    a, sr = sf.read(str(mix), frames=int(LONG_SEC * 44100), always_2d=True)
    tmp = ROOT / "03_outputs" / "_denoise_live" / "_selfcheck_long.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(tmp), a.astype(np.float32), sr, subtype="PCM_16")
    j = post("/api/session", {"name": "selfcheck_%ds.wav" % LONG_SEC,
                              "noisy_b64": base64.b64encode(tmp.read_bytes()).decode("ascii")})
    if j.get("error"):
        note("denoise/long", "session", "FAIL", j["error"])
        return
    for m in DENOISE_KEYS:
        r = post("/api/run", {"sid": j["sid"], "model": m})
        if r.get("error"):
            note("denoise/long", m, "FAIL", str(r["error"])[:160])
        else:
            note("denoise/long", m, "PASS", "infer %.2fs  %.1f MB" % (r.get("infer_s", -1), r.get("mb", -1)))


# --------------------------------------------------------------- separation ---
def check_sep(with_upload=True):
    print("\n=== B. separation (board 1) ===")
    cat = get("/api/sep/models")
    if cat.get("error"):
        note("sep", "catalogue", "FAIL", cat["error"])
        return
    order = cat["order"]
    budget = cat.get("budget_s", 8)
    print("  models %d | budget %.1f s | input cap %.0f s"
          % (len(order), budget, cat.get("max_sec", 0)))
    meta = {m["key"]: m for m in cat["models"]}

    j = get("/api/sep/sample?id=" + urllib.parse.quote(SONG))
    if j.get("error"):
        note("sep", "sample", "FAIL", j["error"])
        return
    print("  session %s  %s s  has_gt=%s" % (j["sid"], j["dur_s"], j["has_gt"]))
    note("sep", "session(builtin)", "PASS", "%s s, GT=%s" % (j["dur_s"], j["has_gt"]))

    for k in order:
        r = post("/api/sep/run", {"sid": j["sid"], "model": k, "budget_s": budget})
        if r.get("error"):
            note("sep", k, "FAIL", str(r["error"])[:160])
            continue
        if r.get("failed"):
            note("sep", k, "FAIL", str(r.get("error"))[:200])
        elif r.get("skipped"):
            note("sep", k, "SKIP", "load %s s | %s" % (r.get("load_s"), r.get("reason")))
        else:
            sc = r.get("score") or {}
            tgt = ",".join(s["target"] for s in r.get("stems", []))
            note("sep", k, "PASS",
                 "load %s s | infer %.2f s | %d chunk(s) | %s | mean4=%s"
                 % (r.get("load_s"), r.get("infer_s"), r.get("n_chunks"),
                    tgt, sc.get("mean4")))

    # ---- C. upload path (no ground truth) -----------------------------------
    if with_upload:
        check_upload(budget)


def check_upload(budget):
    print("\n=== C. separation via upload (no GT) ===")
    mix = ROOT / "02_databases" / "MUSDB18-HQ" / "test" / SONG / "mixture.wav"
    if not mix.is_file():
        note("sep/upload", "fixture", "FAIL", "missing %s" % mix)
        return
    a, sr = sf.read(str(mix), frames=int(12 * 44100), always_2d=True)
    tmp = ROOT / "03_outputs" / "_sep_live" / "_selfcheck_upload.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(tmp), a.astype(np.float32), sr, subtype="PCM_16")
    up = post("/api/sep/session", {"name": "selfcheck_upload.wav",
                                   "noisy_b64": base64.b64encode(tmp.read_bytes()).decode("ascii")})
    if up.get("error"):
        note("sep/upload", "session", "FAIL", up["error"])
        return
    note("sep/upload", "session", "PASS", "%s s, has_gt=%s" % (up["dur_s"], up["has_gt"]))
    for k in ("demucs", "mdx"):
        r = post("/api/sep/run", {"sid": up["sid"], "model": k, "budget_s": budget})
        if r.get("error") or r.get("failed"):
            note("sep/upload", k, "FAIL", str(r.get("error") or r.get("failed"))[:200])
        elif r.get("skipped"):
            note("sep/upload", k, "SKIP", r.get("reason"))
        else:
            sc = r.get("score") or {}
            ok = (sc.get("has_gt") is False
                  and (sc.get("per_target") or {}) == {}
                  and sc.get("mean4") is None)
            note("sep/upload", k, "PASS" if ok else "FAIL",
                 "infer %.2fs | has_gt=%s mean4=%s (must be False/None)"
                 % (r.get("infer_s"), sc.get("has_gt"), sc.get("mean4")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--denoise", action="store_true")
    ap.add_argument("--sep", action="store_true")
    ap.add_argument("--upload", action="store_true", help="only the upload path (section C)")
    a = ap.parse_args()
    do_all = not (a.denoise or a.sep or a.upload)

    h = get("/api/health", timeout=30)
    if h.get("error"):
        print("server not reachable at %s -> %s" % (BASE, h["error"]))
        return 2
    print("server: device=%s gpu=%s loaded_denoise=%s sep_worker=%s"
          % (h.get("device"), h.get("gpu"), h.get("loaded"), h.get("sep_worker")))

    if a.upload:
        check_upload(h.get("sep_budget_s", 8))
    else:
        if do_all or a.denoise:
            check_denoise()
        if do_all or a.sep:
            check_sep(with_upload=do_all)

    n_pass = sum(1 for r in RESULTS if r[2] == "PASS")
    n_skip = sum(1 for r in RESULTS if r[2] == "SKIP")
    n_fail = sum(1 for r in RESULTS if r[2] == "FAIL")
    print("\n" + "=" * 78)
    print("PASS %d | SKIP %d | FAIL %d" % (n_pass, n_skip, n_fail))
    if n_fail:
        print("\nFAILURES:")
        for sec, m, st, d in RESULTS:
            if st == "FAIL":
                print("  %-14s %-26s %s" % (sec, m, d))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

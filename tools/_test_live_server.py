"""End-to-end test of the live denoise server (upload -> run -> score).

Posts a real Valentini noisy file to /api/session, runs every model through
/api/run, and cross-checks the returned metrics against the offline A/B
manifest for the SAME clip -- the two must agree, because both are supposed to
implement the identical 16 kHz-metric / 44.1 kHz-contract pipeline.
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"E:\FYP_HKBU")
BASE = "http://127.0.0.1:8123"
CLIP = "p232_340"


def post(path, obj, timeout=600):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path, timeout=60):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    print("health:", get("/api/health"))

    # Feed the ORIGINAL dataset file, not the stored 44.1 kHz wav: re-decoding
    # the stored wav adds a 16k round-trip (44.1k->16k->44.1k) and perturbs the
    # model input, which shifts dns64/master64 by up to 2.1 dB.  A real user
    # upload is one decode -- exactly like the offline route.
    src = ROOT / "02_databases" / "Valentini" / "noisy_testset_wav" / (CLIP + ".wav")
    cl = ROOT / "02_databases" / "Valentini" / "clean_testset_wav" / (CLIP + ".wav")
    if not src.is_file():
        src = ROOT / "03_outputs" / "_denoise_ab" / CLIP / "noisy.wav"
        cl = ROOT / "03_outputs" / "_denoise_ab" / CLIP / "clean.wav"
    nz = src
    print("upload:", nz.name, nz.stat().st_size, "bytes")

    t0 = time.time()
    s = post("/api/session", {
        "name": CLIP + ".wav",
        "noisy_b64": base64.b64encode(nz.read_bytes()).decode("ascii"),
        "clean_b64": base64.b64encode(cl.read_bytes()).decode("ascii") if cl.is_file() else None,
    })
    print("session:", s, "(%.2fs)" % (time.time() - t0))
    sid = s["sid"]

    man = json.loads((ROOT / "04_reports" / "02_denoising" / "data"
                      / "denoise_ab_manifest.json").read_text(encoding="utf-8"))
    ref = {m["key"]: m for c in man["clips"] if c["id"] == CLIP for m in c["models"]}

    print("\n%-30s %9s %9s %7s   %s" % ("model", "dSDR(live)", "dSDR(off)", "delta", "peak/level"))
    bad = 0
    for key in ["denoiser_dns48", "denoiser_dns64", "denoiser_master64",
                "mel_roformer_denoise", "mel_roformer_denoise_aggr"]:
        r = post("/api/run", {"sid": sid, "model": key})
        if "error" in r:
            print("  FAILED", key, r["error"])
            bad += 1
            continue
        d_live = r["metrics"]["si_sdr_improve"]
        d_off = ref[key]["metrics"]["si_sdr_improve"]
        delta = None if d_live is None else round(d_live - d_off, 4)
        flag = "" if (delta is not None and abs(delta) < 0.05) else "   <-- MISMATCH"
        if flag:
            bad += 1
        print("%-30s %9.4f %9.4f %7s   L=%.3f  %5.2fs%s"
              % (key, d_live, d_off, delta,
                 r["metrics"]["level_ratio"], r["infer_s"], flag))

    # the produced audio must actually be fetchable
    r = post("/api/run", {"sid": sid, "model": "denoiser_dns48"})
    with urllib.request.urlopen(BASE + r["src"], timeout=30) as rr:
        head = rr.status
        blob = rr.read(200000)
    print("\noutput audio: HTTP %s, %d bytes, RIFF=%s"
          % (head, len(blob), blob[:4] == b"RIFF"))

    print("\nmismatches:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

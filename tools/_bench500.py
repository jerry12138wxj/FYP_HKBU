"""500-segment comparison across every runnable separation model.

Design (fixed, deterministic):
  * 500 segments = 50 MUSDB18-HQ test songs x 10 segments each.
  * Each segment is 4.0 s, stereo, native 44.1 kHz.
  * Offsets are drawn with a fixed seed (42) from a per-song candidate pool
    that keeps only the top 40% of 4 s windows by vocals RMS.  Rationale: the
    first 30 s of a MUSDB track is frequently near-silent / bass-only, and
    hand-picked windows are not trustworthy (already cost us a full re-run on
    2026-10-30).  The pool is energy-gated, the choice inside the pool is
    random, and the seed makes the draw reproducible.
  * Metric is SI-SDR per stem against ground truth, same implementation the
    existing benchmark harness uses (compare_separation_methods.si_sdr).
  * One model per process: 12 models in one process would blow the 8 GiB card.

Modes:
    python tools/_bench500.py build
    python tools/_bench500.py model --model demucs
    python tools/_bench500.py summary
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import paths as _paths  # noqa: E402

_paths.setup_env()

OUT = _paths.PROJECT_ROOT / "baseline" / "bench500"
SEG_S = 4.0
POOL_FRAC = 0.40
N_PER_SONG = 10
SEED = 42


def _load_bm():
    import benchmark_model_universal as bm
    return bm


def _wav(path):
    import soundfile as sf
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return y, sr


def build_segments(limit_songs=0):
    bm = _load_bm()
    root = bm.DATA_ROOT / "test"
    songs = sorted([p.name for p in root.iterdir() if p.is_dir()])
    if limit_songs:
        songs = songs[:limit_songs]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results").mkdir(exist_ok=True)

    rng = np.random.default_rng(SEED)
    rows = []
    for song in songs:
        d = root / song
        voc, sr = _wav(d / "vocals.wav")
        mix, _ = _wav(d / "mixture.wav")
        n_win = len(voc)
        L = int(SEG_S * sr)
        hop = L // 2
        starts = list(range(0, max(1, n_win - L + 1), hop))
        e = np.array([float(np.mean(voc[s:s + L] ** 2)) for s in starts])
        keep = max(1, int(len(starts) * POOL_FRAC))
        order = np.argsort(e)[::-1][:keep]
        pool = np.array([starts[i] for i in sorted(order)])
        pick = rng.choice(pool, size=min(N_PER_SONG, len(pool)), replace=False)
        for s in sorted(pick.tolist()):
            rows.append(dict(song=song, offset_s=round(s / sr, 3),
                             dur_s=SEG_S, seg_id="%s@%.3f" % (song, s / sr),
                             voc_rms=round(float(np.sqrt(np.mean(voc[s:s + L] ** 2))), 6),
                             mix_rms=round(float(np.sqrt(np.mean(mix[s:s + L] ** 2))), 6)))
        print("  %-40s picked %d from %d candidates" % (song[:40], len(pick), len(pool)))

    p = OUT / "segments.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("segments: %d -> %s" % (len(rows), p))
    return len(rows)


def run_model(name, label=None, force=False):
    bm = _load_bm()
    if name not in bm.REGISTRY:
        raise SystemExit("unknown model %s (have: %s)" % (name, ",".join(sorted(bm.REGISTRY))))
    spec = bm.REGISTRY[name]
    label = label or name

    segs = list(csv.DictReader(open(OUT / "segments.csv", encoding="utf-8")))
    outp = OUT / "results" / (label + ".csv")
    done = set()
    if outp.exists() and not force:
        for r in csv.DictReader(open(outp, encoding="utf-8")):
            done.add(r["seg_id"])
        mode = "a"
    else:
        mode = "w"
    print("%s: %d segments, %d already done -> %s" % (label, len(segs), len(done), outp.name))

    t0 = time.time()
    run_fn, load_s, info = spec["loader"]()
    print("  loaded in %.1f s  info=%s" % (time.time() - t0, str(info)[:120]))

    ref_map = spec.get("ref_map", {})
    f = open(outp, mode, newline="", encoding="utf-8")
    cols = ["model", "seg_id", "song", "offset_s", "stem", "si_sdr", "rtf", "infer_s", "note"]
    w = csv.DictWriter(f, fieldnames=cols)
    if mode == "w":
        w.writeheader()

    n = 0
    for sg in segs:
        if sg["seg_id"] in done:
            continue
        mix, gt, sr = bm.load_clip(sg["song"], "test", SEG_S, float(sg["offset_s"]))
        t1 = time.time()
        stems = run_fn(mix)
        dt = time.time() - t1
        rtf = dt / (len(mix) / float(sr))
        for t, y in stems.items():
            est = np.asarray(y)
            if est.ndim > 1:
                est = est.mean(axis=1)
            if t in ref_map:
                if not all(k in gt for k, _ in ref_map[t]):
                    continue
                ref = sum(c * gt[k] for k, c in ref_map[t])
            elif t in gt:
                ref = gt[t]
            else:
                continue
            L = min(len(ref), len(est))
            if L < 1024:
                continue
            v = float(bm.si_sdr(ref[:L], est[:L]))
            w.writerow(dict(model=label, seg_id=sg["seg_id"], song=sg["song"],
                            offset_s=sg["offset_s"], stem=t, si_sdr=round(v, 3),
                            rtf=round(rtf, 4), infer_s=round(dt, 3), note=""))
        f.flush()
        n += 1
        if n % 50 == 0:
            print("  %d/%d  %.1f min" % (n, len(segs) - len(done), (time.time() - t0) / 60.0))
    f.close()
    print("done %s: %d segments in %.1f min -> %s" % (name, n, (time.time() - t0) / 60.0, outp))


def summary():
    files = sorted((OUT / "results").glob("*.csv"))
    if not files:
        raise SystemExit("no results yet")
    per = {}
    rtf = {}
    for p in files:
        m = p.stem
        for r in csv.DictReader(open(p, encoding="utf-8")):
            per.setdefault((m, r["stem"]), []).append(float(r["si_sdr"]))
            rtf.setdefault(m, []).append(float(r["rtf"]))
    stems = ["vocals", "drums", "bass", "other"]
    models = sorted({m for m, _ in per})
    rows = []
    for m in models:
        rec = dict(model=m, n_seg=len(per.get((m, "vocals"), [])) or None)
        vals = []
        for s in stems:
            v = per.get((m, s), [])
            rec[s] = round(float(np.median(v)), 3) if v else ""
            if v:
                vals.extend(v)
        rec["avg4_median"] = round(float(np.median(vals)), 3) if vals else ""
        rec["rtf_median"] = round(float(np.median(rtf[m])), 4) if rtf.get(m) else ""
        rows.append(rec)
    p = OUT / "summary.csv"
    cols = ["model", "n_seg"] + stems + ["avg4_median", "rtf_median"]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda x: (-(x["avg4_median"] if x["avg4_median"] != "" else -99))):
            w.writerow({k: r.get(k, "") for k in cols})
    print("summary -> %s" % p)
    for r in sorted(rows, key=lambda x: -(x["avg4_median"] if x["avg4_median"] != "" else -99)):
        print("  %-16s avg4=%7s  voc=%7s  rtf=%6s  n=%s" %
              (r["model"], r["avg4_median"], r["vocals"], r["rtf_median"], r["n_seg"]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "model", "summary"])
    ap.add_argument("--model", default="")
    ap.add_argument("--label", default="", help="output csv / model-column name (default: --model)")
    ap.add_argument("--force", action="store_true", help="ignore rows already in the csv")
    ap.add_argument("--songs", type=int, default=0, help="limit songs in build (smoke test)")
    a = ap.parse_args()
    if a.cmd == "build":
        build_segments(a.songs)
    elif a.cmd == "model":
        if not a.model:
            raise SystemExit("--model required")
        run_model(a.model, label=(a.label or None), force=a.force)
    else:
        summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())

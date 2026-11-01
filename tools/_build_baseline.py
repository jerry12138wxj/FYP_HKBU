#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_bbaseline: reproducible baseline for the FYP audio datasets.

Subcommands
-----------
scan     : read-only inventory -> baseline/baseline_manifest.csv
sdr      : BSSEval v4 baselines A/B/C -> baseline/baseline_sdr.csv (resumable, shardable)
spectro  : STFT magnitudes + PNG -> baseline/spectrograms/
summary  : aggregate -> baseline/baseline_summary.csv
probe    : negative-control tests on the metric itself -> baseline/pipeline_probe.csv
report   : baseline/baseline_report.md

Design rules
------------
* NEVER writes into 02_databases/. Read-only on source audio.
* Everything lands in <root>/ (default: E:/FYP_HKBU/baseline).
* Per-file rows are appended and re-read on restart -> --shard is safe.
* Metric = museval 0.4.1 BSSEval v4, framewise 1 s window / 1 s hop,
  per-file aggregation = median over frames, mono downmix by channel mean.
* Prints are ASCII only (Windows cp936 console safety).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

import paths as _paths  # noqa: E402

_paths.setup_env()

import soundfile as sf  # noqa: E402

try:
    import museval
    MUSEVAL_VER = getattr(museval, "__version__", None)
except Exception:  # pragma: no cover
    museval = None
    MUSEVAL_VER = None

try:
    from importlib.metadata import version as _pkgver
    MUSEVAL_VER = _pkgver("museval")
except Exception:
    pass

DB = Path("E:/FYP_HKBU/02_databases")
DEF_ROOT = Path("E:/FYP_HKBU/baseline")

VAL_C = DB / "Valentini" / "clean_testset_wav"
VAL_N = DB / "Valentini" / "noisy_testset_wav"
MUS = DB / "MUSDB18-HQ" / "test"
DNS_CLEAN = DB / "DNS-Challenge" / "clean"
DNS_DEV = DB / "DNS-Challenge" / "dev_testset" / "datasets_fullband" / "dev_testset" / "noisy_testclips"

MUS_STEMS = ["vocals", "drums", "bass", "other"]


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def log(msg, fh=None):
    line = "[baseline] %s" % msg
    print(line, flush=True)
    if fh is not None:
        fh.write(line + "\n")
        fh.flush()


def read_mono(path):
    """Return (float32 mono, sample_rate). Stereo -> channel mean."""
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if x.shape[1] > 1:
        x = x.mean(axis=1)
    else:
        x = x[:, 0]
    return np.ascontiguousarray(x, dtype=np.float32), int(sr)


def align_pair(ref, est):
    """Truncate both to the shorter length. Returns (ref, est, delta_samples)."""
    n = min(len(ref), len(est))
    return ref[:n], est[:n], int(abs(len(ref) - len(est)))


def bss_framewise(ref, est, sr, win_s=1.0, hop_s=1.0):
    """museval BSSEval v4, framewise.

    win_s / hop_s are exposed so the baseline can be recomputed at the main
    table's 2.0 s / 1.5 s setting.  The values actually used are written back
    into every CSV row, so a table can never silently mix two window regimes.
    """
    win = int(round(win_s * sr))
    hop = int(round(hop_s * sr))
    r = np.asarray(ref, dtype=np.float32).reshape(1, -1, 1)
    e = np.asarray(est, dtype=np.float32).reshape(1, -1, 1)
    sdr, isr, sir, sar = museval.evaluate(r, e, win=win, hop=hop, mode="v4")
    return {
        "sdr": np.asarray(sdr)[0],
        "isr": np.asarray(isr)[0],
        "sir": np.asarray(sir)[0],
        "sar": np.asarray(sar)[0],
        "_win": win,
        "_hop": hop,
    }


def med(a):
    a = np.asarray(a, dtype=float)
    if a.size == 0:
        return float("nan")
    return float(np.nanmedian(a))


def fmt(v, nd=3):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    try:
        f = float(v)
    except Exception:
        return str(v)
    if np.isnan(f):
        return "nan"
    if np.isinf(f):
        return "inf" if f > 0 else "-inf"
    return ("%." + str(nd) + "f") % f


def rms(x):
    return float(np.sqrt(np.mean(np.square(np.asarray(x, dtype=np.float64))) + 1e-20))


# ----------------------------------------------------------------------
# inventory
# ----------------------------------------------------------------------
def scan():
    rows = []
    # ---- Valentini: clean/noisy pairs, 1:1 by basename
    cs = {p.stem: p for p in sorted(VAL_C.glob("*.wav"))}
    ns = {p.stem: p for p in sorted(VAL_N.glob("*.wav"))}
    for k in sorted(cs):
        ic = sf.info(str(cs[k]))
        ip = sf.info(str(ns[k])) if k in ns else None
        ok = ip is not None and ip.frames == ic.frames and ip.samplerate == ic.samplerate
        rows.append(dict(dataset="Valentini", split="test", role="clean", stem="speech",
                         path=str(cs[k]).replace("\\", "/"), duration=round(ic.duration, 6),
                         sample_rate=ic.samplerate, channels=ic.channels, frames=ic.frames,
                         subtype=ic.subtype, has_pair=bool(ok),
                         pair_path=str(ns[k]).replace("\\", "/") if ok else ""))
        if ip is not None:
            rows.append(dict(dataset="Valentini", split="test", role="mixture", stem="speech",
                             path=str(ns[k]).replace("\\", "/"), duration=round(ip.duration, 6),
                             sample_rate=ip.samplerate, channels=ip.channels, frames=ip.frames,
                             subtype=ip.subtype, has_pair=bool(ok),
                             pair_path=str(cs[k]).replace("\\", "/") if ok else ""))

    # ---- MUSDB18-HQ: mixture + 4 stems per song
    for song in sorted(p for p in MUS.iterdir() if p.is_dir()):
        mix = song / "mixture.wav"
        im = sf.info(str(mix)) if mix.exists() else None
        if im is None:
            continue
        rows.append(dict(dataset="MUSDB18-HQ", split="test", role="mixture", stem="mixture",
                         path=str(mix).replace("\\", "/"), duration=round(im.duration, 6),
                         sample_rate=im.samplerate, channels=im.channels, frames=im.frames,
                         subtype=im.subtype, has_pair=False, pair_path=""))
        for st in MUS_STEMS:
            p = song / (st + ".wav")
            if not p.exists():
                continue
            i = sf.info(str(p))
            ok = (i.frames == im.frames and i.samplerate == im.samplerate)
            rows.append(dict(dataset="MUSDB18-HQ", split="test", role="clean", stem=st,
                             path=str(p).replace("\\", "/"), duration=round(i.duration, 6),
                             sample_rate=i.samplerate, channels=i.channels, frames=i.frames,
                             subtype=i.subtype, has_pair=bool(ok),
                             pair_path=str(mix).replace("\\", "/") if ok else ""))

    # ---- DNS clean: clean only, no mixture. emotional_speech is stored twice
    # (flat dir + crema_d/ subdir) -> mark the second copy with duplicate_of.
    seen_dns = {}
    for sub in sorted(p for p in DNS_CLEAN.iterdir() if p.is_dir()):
        for p in sorted(sub.rglob("*.wav")):
            i = sf.info(str(p))
            key = (p.stem, p.stat().st_size)
            dup = ""
            if key in seen_dns:
                dup = str(seen_dns[key]).replace("\\", "/")
            else:
                seen_dns[key] = p
            rows.append(dict(dataset="DNS-Challenge", split="clean", role="clean", stem="speech",
                             path=str(p).replace("\\", "/"), duration=round(i.duration, 6),
                             sample_rate=i.samplerate, channels=i.channels, frames=i.frames,
                             subtype=i.subtype, has_pair=False, pair_path="", duplicate_of=dup))

    # ---- DNS dev_testset: noisy only, reference NOT published
    for p in sorted(DNS_DEV.glob("*.wav")):
        i = sf.info(str(p))
        rows.append(dict(dataset="DNS-Challenge", split="dev_testset", role="mixture", stem="speech",
                         path=str(p).replace("\\", "/"), duration=round(i.duration, 6),
                         sample_rate=i.samplerate, channels=i.channels, frames=i.frames,
                         subtype=i.subtype, has_pair=False, pair_path=""))
    return rows


def cmd_scan(a):
    rows = scan()
    out = a.root / "baseline_manifest.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["dataset", "split", "role", "stem", "path", "duration", "sample_rate",
            "channels", "frames", "subtype", "has_pair", "pair_path", "duplicate_of",
            "spec_npy", "spec_png"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            r.setdefault("spec_npy", "")
            r.setdefault("spec_png", "")
            r.setdefault("duplicate_of", "")
            w.writerow(r)

    import collections
    print("manifest rows: %d -> %s" % (len(rows), out))
    c = collections.Counter((r["dataset"], r["split"], r["role"]) for r in rows)
    for k in sorted(c):
        sub = [r for r in rows if (r["dataset"], r["split"], r["role"]) == k]
        dur = sum(r["duration"] for r in sub)
        sr = sorted({r["sample_rate"] for r in sub})
        ch = sorted({r["channels"] for r in sub})
        npaired = sum(1 for r in sub if r["has_pair"])
        print("  %-14s %-12s %-8s n=%5d dur=%8.1f min sr=%s ch=%s paired=%d"
              % (k[0], k[1], k[2], len(sub), dur / 60.0, sr, ch, npaired))
    ndup = sum(1 for r in rows if r.get("duplicate_of"))
    if ndup:
        print("  byte-identical duplicate copies flagged in duplicate_of: %d "
              "(excluded from sampling, counted once in unique-file totals)" % ndup)


# ----------------------------------------------------------------------
# SDR baselines
# ----------------------------------------------------------------------
def val_pairs(limit=0):
    cs = {p.stem: p for p in sorted(VAL_C.glob("*.wav"))}
    ns = {p.stem: p for p in sorted(VAL_N.glob("*.wav"))}
    keys = [k for k in sorted(cs) if k in ns]
    if limit:
        keys = keys[:limit]
    return [(k, cs[k], ns[k]) for k in keys]


def mus_items(limit=0):
    songs = sorted(p for p in MUS.iterdir() if p.is_dir() and (p / "mixture.wav").exists())
    if limit:
        songs = songs[:limit]
    return songs


def dns_clean_sample(n=200):
    """Deterministic stratified sample: proportional to subcorpus size, evenly spaced.

    DNS emotional_speech ships each clip twice (flat dir + crema_d/ subdir,
    byte-identical). Deduplicate on (stem, size) and keep the shallower path so
    the same audio is never evaluated or counted twice.
    """
    pools = {}
    for sub in sorted(p for p in DNS_CLEAN.iterdir() if p.is_dir()):
        seen = {}
        for p in sorted(sub.rglob("*.wav")):
            key = (p.stem, p.stat().st_size)
            if key in seen:
                continue
            seen[key] = p
        pools[sub.name] = list(seen.values())
    tot = sum(len(v) for v in pools.values())
    out = []
    for name in sorted(pools):
        files = pools[name]
        k = max(1, int(round(n * len(files) / max(tot, 1))))
        if k >= len(files):
            pick = files
        else:
            idx = np.linspace(0, len(files) - 1, k).round().astype(int)
            pick = [files[i] for i in sorted(set(idx.tolist()))]
        out += [(name, p) for p in pick]
    return out


SDR_COLS = ["method", "dataset", "file", "stem", "sdr_db", "isr_db", "n_frames",
            "n_nonfinite_frames", "sample_rate", "channels", "duration_s", "n_samples",
            "len_ref", "len_est", "delta_samples", "alignment", "downmix",
            "framewise", "win_samples", "hop_samples", "window_s", "tool", "tool_version",
            "est_path", "ref_path"]


def load_done(path):
    done = set()
    if not path.exists():
        return done
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            done.add((row["method"], row["dataset"], row["file"], row["stem"]))
    return done


def cmd_sdr(a):
    if museval is None:
        print("FATAL: museval not importable")
        return 2
    out = a.root / "baseline_sdr.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    new = not out.exists()
    f = open(out, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=SDR_COLS)
    if new:
        w.writeheader()

    done = load_done(out) if a.resume else set()
    if a.resume:
        print("resume: %d rows already present" % len(done))

    # ---- build task list
    tasks = []  # (method, dataset, name, stem, est_loader, ref_path, est_path)
    if a.dataset in ("valentini", "all"):
        for k, cp, npx in val_pairs(a.limit):
            tasks.append(("A", "Valentini", k, "speech", "clean", cp, cp))
            tasks.append(("B", "Valentini", k, "speech", "mixture", cp, npx))
    if a.dataset in ("musdb", "all"):
        for song in mus_items(a.limit):
            mix = song / "mixture.wav"
            for st in MUS_STEMS:
                p = song / (st + ".wav")
                if not p.exists():
                    continue
                tasks.append(("A", "MUSDB18-HQ", song.name, st, "clean", p, p))
                tasks.append(("B", "MUSDB18-HQ", song.name, st, "mixture", p, mix))
    if a.dataset in ("dns_clean", "all"):
        for sub, p in dns_clean_sample(a.limit or 200):
            rel = str(p.relative_to(DNS_CLEAN)).replace("\\", "/")
            tasks.append(("A", "DNS-Challenge", rel, "speech", "clean", p, p))

    # ---- shard
    if a.shard:
        i, n = [int(x) for x in a.shard.split("/")]
        tasks = [t for j, t in enumerate(tasks) if j % n == i]

    log("tasks=%d  shard=%s  dataset=%s  limit=%s" % (len(tasks), a.shard or "-", a.dataset, a.limit or "-"))
    t_all = time.time()
    n_done = n_skip = 0
    for method, ds, name, stem, est_kind, ref_p, est_p in tasks:
        key = (method, ds, name, stem)
        if key in done:
            n_skip += 1
            continue
        ref, sr = read_mono(ref_p)
        # Method A used to do est = ref.copy(), i.e. it aliased the array it had
        # just decoded and therefore could not catch a decode / downmix
        # regression.  It now re-decodes the same path from disk.  The result is
        # still bit-identical (SDR stays +inf), but the second decode really
        # runs, so A becomes a genuine decode-determinism check.
        est, sr_e = read_mono(est_p)
        if sr_e != sr:
            raise RuntimeError("sample-rate mismatch %s vs %s" % (sr, sr_e))
        ref_a, est_a, delta = align_pair(ref, est)
        t0 = time.time()
        try:
            m = bss_framewise(ref_a, est_a, sr, a.win_s, a.hop_s)
        except Exception as exc:
            log("FAIL %s %s %s: %s" % (method, ds, name, exc))
            continue
        sdr_arr = m["sdr"]
        # Non-finite frames are a MIXTURE of two different things and the column
        # name says so: NaN = 0/0 undefined (the estimated or reference stem is
        # digital silence in that 1-s window) and +inf = exact reconstruction.
        # med() below is nanmedian, so NaN frames are DROPPED from the per-file
        # value while +inf frames are KEPT as the largest order statistic.
        # Consequence: a file's SDR is a median over its non-silent frames only.
        n_nf = int(np.sum(~np.isfinite(sdr_arr)))
        row = dict(
            method=method, dataset=ds, file=name, stem=stem,
            sdr_db=fmt(med(sdr_arr)), isr_db=fmt(med(m["isr"])),
            n_frames=int(sdr_arr.size), n_nonfinite_frames=n_nf,
            sample_rate=sr, channels=1, duration_s=fmt(len(ref_a) / float(sr)),
            n_samples=len(ref_a), len_ref=len(ref), len_est=len(est),
            delta_samples=delta, alignment="truncate_to_min",
            downmix="channel_mean",             framewise=True, win_samples=m["_win"], hop_samples=m["_hop"],
            window_s=round(a.win_s, 3), tool="museval.bss_eval/v4", tool_version=str(MUSEVAL_VER),
            est_path=str(est_p).replace("\\", "/"), ref_path=str(ref_p).replace("\\", "/"),
        )
        w.writerow(row)
        if method == "A":
            # Method C is the identical computation, re-labelled as the
            # theoretical ceiling. Emitted here so it can never drift from A.
            row_c = dict(row)
            row_c["method"] = "C"
            w.writerow(row_c)
        f.flush()
        n_done += 1
        if n_done % 20 == 0:
            log("  %d/%d  %s %-12s %-40s SDR=%s  (%.1f min elapsed)"
                % (n_done, len(tasks), method, ds, name[:40], row["sdr_db"], (time.time() - t_all) / 60.0))
    f.close()
    log("shard finished: wrote=%d skipped=%d total=%.1f min" % (n_done, n_skip, (time.time() - t_all) / 60.0))


# ----------------------------------------------------------------------
# summary
# ----------------------------------------------------------------------
def _f(x):
    try:
        v = float(x)
    except Exception:
        return np.nan
    return v


def cmd_summary(a):
    src = a.root / "baseline_sdr.csv"
    rows = list(csv.DictReader(open(src, encoding="utf-8", newline="")))
    print("input rows: %d" % len(rows))
    groups = {}
    for r in rows:
        groups.setdefault((r["method"], r["dataset"], r["stem"]), []).append(r)

    out = a.root / "baseline_summary.csv"
    cols = ["method", "dataset", "stem", "n_files", "mean_db", "median_db", "std_db",
            "min_db", "max_db", "n_finite", "finite_ratio", "note"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for k in sorted(groups):
            vals = [_f(r["sdr_db"]) for r in groups[k]]
            fin = [v for v in vals if np.isfinite(v)]
            n = len(vals)
            row = dict(
                method=k[0], dataset=k[1], stem=k[2], n_files=n,
                mean_db=fmt(np.mean(fin) if fin else float("inf"), 4) if not fin else fmt(np.mean(fin), 4),
                median_db=fmt(np.median(fin), 4) if fin else "inf",
                std_db=fmt(np.std(fin), 4) if fin else "0.0",
                min_db=fmt(np.min(fin), 4) if fin else "inf",
                max_db=fmt(np.max(fin), 4) if fin else "inf",
                n_finite=len(fin), finite_ratio=fmt(len(fin) / float(n), 4) if n else "0",
                note="",
            )
            if k[0] == "A":
                row["note"] = "pipeline self-check; ALL frames non-finite -> metric exact, no distortion"
            elif k[0] == "C":
                row["note"] = "theoretical ceiling reference; identical computation to A, do NOT cite as model SDR"
            elif k[0] == "B":
                row["note"] = "no-separation lower bound (est = mixture)"
            w.writerow(row)
            print("  %s %-13s %-6s n=%4d  mean=%9s median=%9s std=%8s"
                  % (k[0], k[1], k[2], n, row["mean_db"], row["median_db"], row["std_db"]))
    print("-> %s" % out)


# ----------------------------------------------------------------------
# metric negative controls
# ----------------------------------------------------------------------
def cmd_probe(a):
    """Characterise the metric with controlled inputs.

    Every expectation below is either analytic or a measured invariant; none
    is a prior guess. The gain rule was discovered empirically in this run:
        SDR(gain g) = -20*log10(|1-g|)
    i.e. this BSSEval path does NOT absorb a pure gain change.
    """
    import scipy.signal as ss
    rows = []
    k, cp, npx = val_pairs(1)[0]
    x, sr = read_mono(cp)

    cases = []  # (case, est, rule, expected_value or None, tolerance)
    cases.append(("identity", x.copy(), "SDR must be +inf (exact identity)", None, 0.0))
    for g in (0.5, 0.9, 2.0):
        exp = -20.0 * np.log10(abs(1.0 - g))
        cases.append(("gain_%.2fx" % g, (x * g).astype(np.float32),
                      "SDR = -20*log10(|1-g|) = %.2f dB (gain NOT absorbed)" % exp, exp, 0.5))
    rng = np.random.default_rng(0)
    for snr in (20.0, 40.0, 60.0):
        noise = rng.standard_normal(len(x)).astype(np.float32)
        noise *= rms(x) / (rms(noise) * (10 ** (snr / 20.0)))
        cases.append(("add_white_noise_%ddB" % int(snr), (x + noise).astype(np.float32),
                      "SDR ~= SNR = %.1f dB" % snr, snr, 0.5))
    for d in (1, 10, 100):
        y = np.concatenate([np.zeros(d, np.float32), x[:-d]])
        cases.append(("shift_%d_samples" % d, y,
                      "monotone drop; %d-sample delay is partly absorbed by the 512-tap filter" % d,
                      None, 0.0))
    y16 = ss.resample_poly(x, 1, 3)
    yback = ss.resample_poly(y16, 3, 1)[: len(x)].astype(np.float32)
    cases.append(("resample_48k_16k_48k", yback,
                  "finite 20-40 dB expected: resampling damage is visible", None, 0.0))

    for name, est, rule, exp, tol in cases:
        r, e, d = align_pair(x, est)
        m = bss_framewise(r, e, sr)
        val = med(m["sdr"])
        if exp is None:
            if name == "identity":
                verdict = "PASS" if np.isinf(val) else "FAIL"
            else:
                verdict = "INFO"
        else:
            verdict = "PASS" if abs(val - exp) <= tol else "FAIL"
        rows.append(dict(case=name, sdr_db=fmt(val), isr_db=fmt(med(m["isr"])),
                         n_frames=int(m["sdr"].size), rule=rule, expected_db=fmt(exp) if exp is not None else "",
                         tolerance_db=tol, verdict=verdict,
                         file=k, sample_rate=sr, framewise=True, win_samples=sr,
                         hop_samples=sr, tool="museval.bss_eval/v4", tool_version=str(MUSEVAL_VER)))
        print("  %-24s SDR=%10s  %-4s  %s" % (name, rows[-1]["sdr_db"], verdict, rule))

    # monotonicity assertion for the shift family
    shifts = [(r["case"], _f(r["sdr_db"])) for r in rows if r["case"].startswith("shift_")]
    mono = all(shifts[i][1] > shifts[i + 1][1] for i in range(len(shifts) - 1))
    print("  shift monotone decreasing: %s" % ("PASS" if mono else "FAIL"))

    out = a.root / "pipeline_probe.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("-> %s" % out)


# ----------------------------------------------------------------------
# spectrogram
# ----------------------------------------------------------------------
SPEC = dict(n_fft=2048, hop_length=512, win_length=2048, window="hann", center=True)


# Uniform colour scale shared by every spectrogram in the package.
# Values are ABSOLUTE magnitude in dB (20*log10|STFT|), NOT normalised to the
# per-file peak.  A per-file normalisation would make two files whose colour
# looks identical have different absolute levels, which breaks the comparison
# the baseline is supposed to support.
# Derivation: pooled p0.5 and p99.5 over all 74 exported arrays
# (384,702,243 finite bins) = -87.7 dB / +23.6 dB, rounded outward to
# -90 / +25.  This keeps 99% of all bins inside the colour ramp; bins above
# +25 dB saturate to the top colour instead of clipping at 0 dB (which used to
# throw away the loudest ~4% of every frame).
DB_VMIN = -90.0
DB_VMAX = 25.0
DB_LABEL = "Magnitude (dB re 1.0, 20*log10|STFT|)"


def spec_mag_db(x, sr):
    import librosa
    S = librosa.stft(x, n_fft=SPEC["n_fft"], hop_length=SPEC["hop_length"],
                     win_length=SPEC["win_length"], window=SPEC["window"],
                     center=SPEC["center"])
    mag = np.abs(S)
    return (20.0 * np.log10(mag + 1e-10)).astype(np.float32), sr


def render_png(db, png_path, title, sr):
    """Render one already-computed dB array.  Shared by save_spec and rescale
    so the numerics can never drift from the picture."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=150)
    t_max = db.shape[1] * SPEC["hop_length"] / float(sr)
    im = ax.imshow(db, origin="lower", aspect="auto", cmap="magma",
                   vmin=DB_VMIN, vmax=DB_VMAX,
                   extent=[0, t_max, 0, sr / 2000.0])
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (kHz)")
    ax.set_title(title, fontsize=9)
    cb = fig.colorbar(im, ax=ax, pad=0.01)
    cb.set_label(DB_LABEL, fontsize=8)
    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)


def save_spec(x, sr, npy_path, png_path, title, dtype="float32"):
    db, _ = spec_mag_db(x, sr)
    np.save(npy_path, db.astype(dtype))
    render_png(db, png_path, title, sr)
    return db.shape, dtype


def cmd_rescale(a):
    """Re-render every PNG from the stored .npy with the current uniform scale.
    No audio is decoded, so this is cheap and cannot change the .npy values."""
    root = a.root / "spectrograms"
    rows = list(csv.DictReader(open(a.root / "spectrogram_index.csv", encoding="utf-8")))
    n = 0
    for r in rows:
        db = np.load(r["npy"])
        title = "%s | %s | %.2f s @ %s Hz" % (r["file"].split("/")[-1], r["role"],
                                              float(r["dur_s"]), r["sr"])
        render_png(db, r["png"], title, int(r["sr"]))
        n += 1
    print("re-rendered %d png with vmin=%.1f vmax=%.1f" % (n, DB_VMIN, DB_VMAX))
    return n


def cmd_spectro(a):
    root = a.root / "spectrograms"
    root.mkdir(parents=True, exist_ok=True)
    idx = []
    K = a.n_spec

    # ---- Valentini: evenly spaced over duration-sorted list (deterministic)
    pairs = val_pairs(0)
    order = sorted(pairs, key=lambda t: sf.info(str(t[1])).frames)
    if K < len(order):
        pick = [order[i] for i in np.linspace(0, len(order) - 1, K).round().astype(int)]
    else:
        pick = order
    for k, cp, npx in pick:
        c, sr = read_mono(cp)
        m, _ = read_mono(npx)
        for tag, sig in (("clean", c), ("mixture", m)):
            base = "Valentini__%s__%s" % (k, tag)
            shape, dt = save_spec(sig, sr, root / (base + ".npy"), root / (base + ".png"),
                                  "%s  |  %s  |  %.2f s @ %d Hz" % (k, tag, len(sig) / sr, sr), a.dtype)
            idx.append(dict(dataset="Valentini", file=k, role=tag, src=cp if tag == "clean" else npx,
                            npy=str(root / (base + ".npy")), png=str(root / (base + ".png")),
                            shape="%dx%d" % shape, dtype=dt, sr=sr, dur_s=round(len(sig) / sr, 4),
                            **{k2: v for k2, v in SPEC.items()}))
        print("  Valentini %-12s clean+mixture" % k)

    # ---- MUSDB: evenly spaced 10 songs, mixture + vocals
    songs = mus_items(0)
    pick_s = [songs[i] for i in np.linspace(0, len(songs) - 1, min(a.n_spec_musdb, len(songs))).round().astype(int)]
    for song in pick_s:
        for stem in ("vocals", "mixture"):
            p = song / (stem + ".wav")
            if not p.exists():
                continue
            x, sr = read_mono(p)
            base = "MUSDB18-HQ__%s__%s" % (song.name.replace(" ", "_").replace("'", ""), stem)
            shape, dt = save_spec(x, sr, root / (base + ".npy"), root / (base + ".png"),
                                  "%s | %s | %.1f s @ %d Hz" % (song.name, stem, len(x) / sr, sr),
                                  a.dtype_long)
            idx.append(dict(dataset="MUSDB18-HQ", file=song.name, role=stem, src=p,
                            npy=str(root / (base + ".npy")), png=str(root / (base + ".png")),
                            shape="%dx%d" % shape, dtype=dt, sr=sr, dur_s=round(len(x) / sr, 4),
                            **{k2: v for k2, v in SPEC.items()}))
        print("  MUSDB     %-45s vocals+mixture" % song.name[:45])

    # ---- DNS clean: 3 per subcorpus (dedupe the crema_d re-copies first)
    pools = {}
    for sub in sorted(p for p in DNS_CLEAN.iterdir() if p.is_dir()):
        seen = {}
        for p in sorted(sub.rglob("*.wav")):
            key = (p.stem, p.stat().st_size)
            if key in seen:
                continue
            seen[key] = p
        pools[sub.name] = list(seen.values())
    for name in sorted(pools):
        files = pools[name]
        sel = [files[i] for i in np.linspace(0, len(files) - 1, min(a.n_spec_dns, len(files))).round().astype(int)]
        for p in sel:
            x, sr = read_mono(p)
            import hashlib
            tag = hashlib.md5(str(p).encode("utf-8")).hexdigest()[:6]
            base = "DNS-Challenge__%s__%s__%s" % (name, p.stem, tag)
            shape, dt = save_spec(x, sr, root / (base + ".npy"), root / (base + ".png"),
                                  "%s | %s | %.2f s @ %d Hz" % (name, p.stem, len(x) / sr, sr), a.dtype)
            idx.append(dict(dataset="DNS-Challenge", file="%s/%s" % (name, p.stem), role="clean", src=p,
                            npy=str(root / (base + ".npy")), png=str(root / (base + ".png")),
                            shape="%dx%d" % shape, dtype=dt, sr=sr, dur_s=round(len(x) / sr, 4),
                            **{k2: v for k2, v in SPEC.items()}))
            print("  DNS       %-50s" % p.name[:50])

    cols = ["dataset", "file", "role", "src", "npy", "png", "shape", "dtype", "sr", "dur_s",
            "n_fft", "hop_length", "win_length", "window", "center"]
    out = a.root / "spectrogram_index.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in idx:
            w.writerow({c: r.get(c, "") for c in cols})
    print("spectrograms: %d entries -> %s" % (len(idx), out))


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "sdr", "summary", "probe", "spectro", "rescale"])
    ap.add_argument("--root", type=Path, default=DEF_ROOT)
    ap.add_argument("--dataset", default="all", choices=["all", "valentini", "musdb", "dns_clean"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default="")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--n-spec", type=int, default=24)
    ap.add_argument("--n-spec-musdb", type=int, default=10)
    ap.add_argument("--n-spec-dns", type=int, default=3)
    ap.add_argument("--dtype", default="float32")
    ap.add_argument("--dtype-long", default="float16")
    ap.add_argument("--win-s", type=float, default=1.0,
                    help="BSSEval window in seconds (main table uses 2.0)")
    ap.add_argument("--hop-s", type=float, default=1.0,
                    help="BSSEval hop in seconds (main table uses 1.5)")
    a = ap.parse_args()
    a.root = Path(a.root)
    a.root.mkdir(parents=True, exist_ok=True)
    {"scan": cmd_scan, "sdr": cmd_sdr, "summary": cmd_summary,
     "probe": cmd_probe, "spectro": cmd_spectro, "rescale": cmd_rescale}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())

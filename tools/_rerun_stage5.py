# -*- coding: utf-8 -*-
"""Stage-5 minimal closed loop, re-run into an isolated directory.

Order (fixed, per the audit brief):
    contract -> smoke -> output correctness -> perf profiling -> metrics

Hard rules baked in:
  * NOTHING is written outside --out / --logdir. Existing 03_outputs/<Model>/,
    03_outputs/_eval/ and 01_models/_weights/ are only ever read.
  * One model per subprocess is *not* used here (only 2 models, 8 GiB is fine),
    but the model is explicitly dropped + empty_cache()'d between models.
  * Any step that cannot be completed is recorded as status="blocked" with a
    reason. It is never silently skipped.

Usage:
    python tools/_rerun_stage5.py --models demucs,bsroformer_l12 \
        --songs 3 --dur 10 --out 03_outputs/rerun_20261030_1700
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import statistics as st
import subprocess
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402

import benchmark_model_universal as BM  # noqa: E402

ROOT = _paths.PROJECT_ROOT
MUSDB = os.path.join(ROOT, "02_databases", "MUSDB18-HQ", "test")
SR = 44100


# ------------------------------------------------------------------ utils
def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sha256_of(path: str, chunk: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def si_sdr(est: np.ndarray, ref: np.ndarray) -> float:
    est = np.asarray(est, dtype=np.float64)
    ref = np.asarray(ref, dtype=np.float64)
    est = est - est.mean()
    ref = ref - ref.mean()
    alpha = float(est @ ref) / (float(ref @ ref) + 1e-12)
    target = alpha * ref
    noise = est - target
    return 10.0 * np.log10((float(target @ target) + 1e-12) / (float(noise @ noise) + 1e-12))


def log(msg: str, fh) -> None:
    line = "[%s] %s" % (now(), msg)
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


def pick_window(ref: np.ndarray, dur: float, sr: int = SR) -> int:
    """按参考轨能量选窗（避免静音前奏把 SI-SDR 打成极负值）。

    50 ms 帧功率 + cumsum 滑窗，O(N) 内存；不用 librosa.feature.rms
    的大 frame_length（会实体化 ~GB 级数组）。
    """
    n = int(round(dur * sr))
    if len(ref) <= n:
        return 0
    hop = max(1, int(0.05 * sr))
    cs = np.concatenate([[0.0], np.cumsum(np.asarray(ref, dtype=np.float64) ** 2)])
    starts = np.arange(0, len(ref) - n + 1, hop)
    energy = cs[starts + n] - cs[starts]
    return int(starts[int(np.argmax(energy))])


def _db(x: float) -> float:
    return round(10.0 * np.log10(max(x, 1e-20)), 2)


def to_stereo(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], axis=-1)
    return x


def load_mono(path: str, sr_out: int = SR, dur: float | None = None) -> np.ndarray:
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != sr_out:
        import librosa
        x = librosa.resample(x, orig_sr=sr, target_sr=sr_out)
    if dur is not None:
        n = int(round(dur * sr_out))
        x = x[:n]
    return np.ascontiguousarray(x, dtype=np.float32)


# ------------------------------------------------------------------ steps
def step_contract(key: str, spec: dict, fh) -> dict:
    log("STEP 1 contract | loading %s" % key, fh)
    t0 = time.time()
    run_fn, load_s, info = spec["loader"]()
    load_wall = time.time() - t0
    names = [c.cell_contents.__class__.__name__ for c in (run_fn.__closure__ or ())]
    contract = {
        "registry_key": key,
        "label": spec.get("label", key),
        "load_wall_s": round(load_wall, 2),
        "callable": getattr(run_fn, "__name__", type(run_fn).__name__),
        "contract_sr": int(getattr(run_fn, "contract_sr", SR)),
        "closure_types": names,
        "loader_info": {k: v for k, v in (info or {}).items() if isinstance(v, (int, float, str, bool))},
    }
    # 输出轨契约：跑 1 s 探针读取 key 名
    probe = np.zeros((SR, 2), dtype=np.float32)
    out = run_fn(probe)
    contract["output_keys"] = sorted(list(out.keys()))
    contract["output_shapes"] = {k: list(np.asarray(v).shape) for k, v in out.items()}
    contract["output_dtype"] = sorted({str(np.asarray(v).dtype) for v in out.values()})
    log("  contract: sr=%d keys=%s shapes=%s" %
        (contract["contract_sr"], contract["output_keys"], contract["output_shapes"]), fh)
    return contract, run_fn


def step_smoke(run_fn, fh) -> dict:
    log("STEP 2 smoke | 2 s deterministic probe", fh)
    n = 2 * SR
    t = np.arange(n, dtype=np.float32) / SR
    sig = 0.3 * np.sin(2 * np.pi * 220 * t) + 0.05 * np.random.RandomState(0).randn(n).astype(np.float32)
    mix = to_stereo(sig)
    t0 = time.time()
    out = run_fn(mix)
    wall = time.time() - t0
    res = {"status": "pass", "wall_s": round(wall, 3), "stems": {}}
    for k, v in out.items():
        a = np.asarray(v)
        res["stems"][k] = {
            "shape": list(a.shape),
            "dtype": str(a.dtype),
            "finite": bool(np.isfinite(a).all()),
            "rms": float(np.sqrt(np.mean(a.astype(np.float64) ** 2))),
            "len_match": int(a.shape[0]) == int(mix.shape[0]),
        }
    bad = [k for k, v in res["stems"].items()
           if not v["finite"] or not v["len_match"] or v["rms"] < 1e-8]
    if bad:
        res["status"] = "fail"
        res["bad_stems"] = bad
    log("  smoke: %s | wall=%.2fs | %s" % (res["status"], wall, list(res["stems"])), fh)
    return res


def step_correctness(run_fn, song: str, dur: float, fh) -> dict:
    log("STEP 3 correctness | song=%s dur=%.1fs" % (song, dur), fh)
    voc_path = os.path.join(MUSDB, song, "vocals.wav")
    mix_path = os.path.join(MUSDB, song, "mixture.wav")
    if not (os.path.exists(voc_path) and os.path.exists(mix_path)):
        log("  blocked: missing %s" % mix_path, fh)
        return {"status": "blocked", "reason": "missing musdb files"}

    mix_full = load_mono(mix_path)
    ref_full = load_mono(voc_path)
    n_full = min(len(mix_full), len(ref_full))
    off = pick_window(ref_full[:n_full], dur)
    n = int(round(dur * SR))
    mix = mix_full[off:off + n]
    ref = ref_full[off:off + n]
    n = min(len(mix), len(ref))
    mix, ref = mix[:n], ref[:n]

    t0 = time.time()
    out = run_fn(to_stereo(mix))
    wall = time.time() - t0
    est = out.get("vocals", next(iter(out.values())))
    est = np.asarray(est)
    est = est[:, 0] if est.ndim == 2 else est

    m = min(len(est), n)
    a, b = est[:m], ref[:m]
    rms_in = float(np.sqrt(np.mean(mix.astype(np.float64) ** 2)))
    rms_out = float(np.sqrt(np.mean(a.astype(np.float64) ** 2)))

    # 确定性：同输入再跑一次
    out2 = run_fn(to_stereo(mix))
    est2 = out2.get("vocals", next(iter(out2.values())))
    est2 = np.asarray(est2)
    est2 = est2[:, 0] if est2.ndim == 2 else est2
    m2 = min(len(est2), m)
    max_diff = float(np.max(np.abs(est2[:m2] - a[:m2]))) if m2 else -1.0

    res = {
        "status": "pass",
        "song": song,
        "window_start_s": round(off / SR, 2),
        "window_rule": "argmax 10 s energy over reference vocals",
        "dur_s": round(m / SR, 3),
        "n_samples_input": int(n),
        "n_samples_output": int(len(est)),
        "length_delta_samples": int(len(est) - n),
        "length_ok": abs(len(est) - n) <= int(0.05 * SR),
        "finite": bool(np.isfinite(a).all()),
        "rms_input": round(rms_in, 6),
        "rms_output": round(rms_out, 6),
        "ref_rms_db": _db(float(np.mean(b.astype(np.float64) ** 2))),
        "ref_to_mix_db": _db(float(np.mean(b.astype(np.float64) ** 2)) /
                             (float(np.mean(mix.astype(np.float64) ** 2)) + 1e-20)),
        "rms_ratio": round(rms_out / (rms_in + 1e-12), 4),
        "peak": round(float(np.max(np.abs(a))), 4),
        "clipped_ratio": round(float(np.mean(np.abs(a) > 1.0)), 6),
        "determinism_max_abs_diff": round(max_diff, 8),
        "si_sdr_vs_clean_vocals_db": round(si_sdr(a, b), 3),
        "wall_s": round(wall, 3),
    }
    if not res["finite"] or not res["length_ok"] or res["rms_ratio"] < 0.01:
        res["status"] = "fail"
    log("  correctness: %s | len %d→%d (Δ%+d) | rms_ratio=%.3f | SI-SDR=%.2f dB | det=%.2e"
        % (res["status"], n, len(est), len(est) - n, res["rms_ratio"],
           res["si_sdr_vs_clean_vocals_db"], max_diff), fh)
    return res


def step_perf(run_fn, dur: float, fh, device="cuda") -> dict:
    log("STEP 4 perf | dur=%.1fs device=%s" % (dur, device), fh)
    n = int(round(dur * SR))
    mix = to_stereo(np.random.RandomState(1).randn(n).astype(np.float32) * 0.1)
    # 参数总量（从闭包里的 nn.Module 收集）
    mods = []
    for c in (run_fn.__closure__ or ()):
        try:
            v = c.cell_contents
        except Exception:
            continue
        if isinstance(v, torch.nn.Module):
            mods.append(v)
    params = sum(p.numel() for m in mods for p in m.parameters()) if mods else None

    if device == "cuda" and torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

    times = []
    for i in range(3):
        t0 = time.time()
        run_fn(mix)
        times.append(time.time() - t0)
        log("    run %d: %.2fs" % (i + 1, times[-1]), fh)

    peak_mb = None
    if device == "cuda" and torch.cuda.is_available():
        peak_mb = round(torch.cuda.max_memory_allocated() / 1024 ** 2, 1)

    body = times[1:] if len(times) > 2 else times  # 首跑含预热，取后两次
    med = st.median(body)
    res = {
        "status": "pass",
        "device": device,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "audio_dur_s": dur,
        "params_m": round(params / 1e6, 3) if params else None,
        "latency_s": [round(t, 3) for t in times],
        "latency_median_s": round(med, 3),
        "rtf": round(med / dur, 4),
        "peak_alloc_mb": peak_mb,
        "flops_note": "FLOPs 未在本轮复算；既有值为 04_reports/00_shared/data/model_analysis 中的 thop 交叉验证结果",
    }
    log("  perf: params=%s M | median=%.2fs | RTF=%.3f | peak=%.0f MB"
        % (res["params_m"], med, res["rtf"], peak_mb or -1), fh)
    return res


def step_metrics(run_fn, songs, dur, fh) -> dict:
    log("STEP 5 metrics | %d songs x %.0fs | SI-SDR vs clean vocals" % (len(songs), dur), fh)
    rows = []
    for s in songs:
        voc = os.path.join(MUSDB, s, "vocals.wav")
        mixp = os.path.join(MUSDB, s, "mixture.wav")
        if not (os.path.exists(voc) and os.path.exists(mixp)):
            log("  skip %s (missing)" % s, fh)
            continue
        mix_full = load_mono(mixp)
        ref_full = load_mono(voc)
        n_full = min(len(mix_full), len(ref_full))
        off = pick_window(ref_full[:n_full], dur)
        n = int(round(dur * SR))
        mix = mix_full[off:off + n]
        ref = ref_full[off:off + n]
        n = min(len(mix), len(ref))
        out = run_fn(to_stereo(mix[:n]))
        est = out.get("vocals", next(iter(out.values())))
        est = np.asarray(est)
        est = est[:, 0] if est.ndim == 2 else est
        m = min(len(est), n)
        val = si_sdr(est[:m], ref[:m])
        rows.append({"song": s, "si_sdr_db": round(val, 3),
                     "window_start_s": round(off / SR, 2),
                     "ref_rms_db": _db(float(np.mean(ref[:m].astype(np.float64) ** 2))),
                     "dur_s": round(m / SR, 2)})
        log("    %-40s SI-SDR %+7.3f dB (win @%.1fs, ref %.1f dB)"
            % (s, val, off / SR, _db(float(np.mean(ref[:m].astype(np.float64) ** 2)))), fh)

    if not rows:
        return {"status": "blocked", "reason": "no usable songs"}
    vals = [r["si_sdr_db"] for r in rows]
    res = {
        "status": "pass",
        "metric": "SI-SDR (scale-invariant SDR)",
        "ref": "MUSDB18-HQ test / vocals.wav",
        "sample_rate": SR,
        "channels": "mono (channel mean of stereo)",
        "dur_per_song_s": dur,
        "n_songs": len(rows),
        "per_song": rows,
        "mean_db": round(float(np.mean(vals)), 3),
        "median_db": round(float(np.median(vals)), 3),
        "caveat": "SI-SDR 非 museval BSSEval v4 SDR，绝对值不可与主表 04_reports 的 SDR 直接比较；仅用于本轮自洽核验",
    }
    log("  metrics: mean %+.3f dB | median %+.3f dB (n=%d)" % (res["mean_db"], res["median_db"], len(rows)), fh)
    return res


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="demucs,bsroformer_l12")
    ap.add_argument("--songs", type=int, default=3)
    ap.add_argument("--dur", type=float, default=10.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--logdir", default=None)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()

    out_dir = os.path.abspath(a.out)
    log_dir = os.path.abspath(a.logdir) if a.logdir else out_dir
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "rerun.log")

    songs = sorted(os.listdir(MUSDB))[: a.songs]
    result = {
        "meta": {
            "started": now(),
            "command": " ".join([sys.executable, "-X", "utf8", "-u"] + sys.argv),
            "cwd": os.getcwd(),
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "cudnn": str(torch.backends.cudnn.version()),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
            "gpu_total_gib": round(torch.cuda.get_device_properties(0).total_memory / 1024 ** 3, 1)
            if torch.cuda.is_available() else None,
            "sr": SR,
            "songs": songs,
            "dur_per_song": a.dur,
            "models": a.models.split(","),
        },
        "models": {},
    }
    try:
        result["meta"]["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        result["meta"]["git_dirty_count"] = len(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip().splitlines())
    except Exception:
        result["meta"]["commit"] = "unavailable"

    with open(log_path, "w", encoding="utf-8") as fh:
        log("rerun start | out=%s" % out_dir, fh)
        for key in result["meta"]["models"]:
            log("=" * 70, fh)
            log("MODEL %s" % key, fh)
            rec = {}
            fn = None
            try:
                spec = BM.REGISTRY[key]
                contract, fn = step_contract(key, spec, fh)
                rec["contract"] = contract
                rec["smoke"] = step_smoke(fn, fh)
                rec["correctness"] = step_correctness(fn, songs[0], a.dur, fh)
                rec["perf"] = step_perf(fn, a.dur, fh, device=a.device)
                rec["metrics"] = step_metrics(fn, songs, a.dur, fh)
            except Exception as e:
                rec["error"] = "%s: %s" % (type(e).__name__, e)
                rec["traceback"] = traceback.format_exc()
                log("  ERROR %s" % rec["error"], fh)
            finally:
                del fn
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            result["models"][key] = rec

        result["meta"]["finished"] = now()
        with open(os.path.join(out_dir, "rerun_report.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        log("rerun done -> %s" % os.path.join(out_dir, "rerun_report.json"), fh)

    print("\n=== SUMMARY ===")
    for k, v in result["models"].items():
        print("%-16s smoke=%s corr=%s perf_rtf=%s metrics_med=%s" % (
            k,
            (v.get("smoke") or {}).get("status"),
            (v.get("correctness") or {}).get("status"),
            (v.get("perf") or {}).get("rtf"),
            (v.get("metrics") or {}).get("median_db"),
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""口径取证（provenance）—— 让主表的每一个数字都能追到「用什么口径算的」。

两个子命令
----------
1. `window`   窗宽敏感性
   本项目全部 SDR 都由 `tools/compare_separation_methods.py::evaluate()` 产出，它调用

       museval.metrics.bss_eval(ref, est, compute_permutation=False)

   **没有传 `window` / `hop`** → 落到 museval 的签名默认值

       window = 2 * 44100 = 88200  (2.0 s)
       hop    = 1.5 * 44100 = 66150 (1.5 s)

   而多个脚本的文档里写着「1 s 窗」。本子命令在**主表自己用的那 3 个均衡片段**上，
   用同一段音频分别按两种窗宽算 SDR，量化这个不符带来的实际偏差。

   ⚠️ 门禁：目标轨在该片段里的能量占比 ≥ `--target-min`（默认 0.12）才计入。
   否则会复现本项目第 2 类陷阱 —— 稀疏目标轨（如某歌 vocals 只占 1.1% 能量）
   在两窗下都逼近退化值，差值可达 10 dB 以上，那是**片段问题不是窗宽问题**。

2. `baseline`  mixture 基线
   主表口径规定「基线 = mixture」。本子命令在**同样的 3 个均衡片段**上，
   把 mixture 自身当作估计信号算 SDR，给出分轨基线行 —— 有了它，
   「模型比 mixture 好多少」才是可读的，且与主表同源同窗。

输出
----
    04_reports/separation/data/comparison/metric_window_probe.json
    04_reports/separation/data/comparison/mixture_baseline.json

用法
----
    python tools/_metric_provenance.py all
    python tools/_metric_provenance.py window --models demucs,mdx,umx --target-min 0.12
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# ---- 路径中枢：五大模块布局，见 tools/paths.py ----
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import paths as _paths

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

sys.path.insert(0, str(_paths.TOOLS))
from bench_multisong import SONGS as BALANCED  # noqa: E402

SR = 44100
DUR_S = 10.0                                    # 主表片段长度，与 bench_multisong --duration 10 一致
STEMS = ["vocals", "drums", "bass", "other"]
OUT_WINDOW = _paths.comparison_dir() / "metric_window_probe.json"
OUT_BASE = _paths.comparison_dir() / "mixture_baseline.json"
PANEL_SEL = _paths.comparison_dir() / "panel_song_selection.json"

# 主表的子集：bench_multisong -> benchmark_model_universal 的 DEFAULT_SUBSET
# = **train**（见 model_runs.json 每条记录的 "subset" 字段）。
# 这一点必须写进脚注：主表是 in-domain 口径，与参考表（test）不可逐格对齐。
MAIN_SUBSET = "train"

MODEL_DIRS = {
    "demucs": "Demucs",
    "mdx": "MDX-Net",
    "umx": "Open-Unmix",
    "convtasnet": "Conv-TasNet",
    "mmdenselstm": "MMDenseLSTM",
}

WINDOWS = [
    ("museval_default_2s_1.5s", int(2 * SR), int(1.5 * SR)),
    ("doc_claimed_1s_1s", int(1 * SR), int(1 * SR)),
]


# ------------------------------------------------------------------ 基础
def _mono(a) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    return a if a.ndim == 1 else a.mean(axis=-1)


def _read_seg(path: Path, start: int, n: int):
    """读 wav/flac 的 [start, start+n) 样本，单声道。失败返回 (None, 原因)。"""
    try:
        info = sf.info(str(path))
    except Exception as exc:                                        # noqa: BLE001
        return None, "sf.info 失败: %s" % exc
    if info.frames < start + n:
        # 本项目第 8 类陷阱：FLAC total_samples 哨兵值会让 soundfile 报 array is too big。
        # 先比对 frames 与预期长度，不合格直接判 SKIP，不让它把整轮探针带崩。
        return None, "frames=%d < 需要 %d（哨兵/半成品文件？）" % (info.frames, start + n)
    y, _ = sf.read(str(path), start=start, frames=n, dtype="float32", always_2d=True)
    return _mono(y), None


def sdr_at(ref: np.ndarray, est: np.ndarray, window: int, hop: int) -> float:
    """与 evaluate() 完全同构：mono / compute_permutation=False / nanmedian over frames。"""
    import museval.metrics as M

    r = np.asarray(ref, np.float32).reshape(1, -1, 1)
    e = np.asarray(est, np.float32).reshape(1, -1, 1)
    sdr, _, _, _, _ = M.bss_eval(r, e, window=window, hop=hop, compute_permutation=False)
    return float(np.nanmedian(np.atleast_1d(sdr).astype(float)))


def _share(ref: np.ndarray, mix: np.ndarray) -> float:
    """目标轨在该片段里的能量占比。用于稀疏目标门禁。"""
    de = float(np.sum(np.asarray(ref, np.float64) ** 2))
    dm = float(np.sum(np.asarray(mix, np.float64) ** 2))
    return de / dm if dm > 0 else 0.0


def _window_clips() -> tuple[list[tuple[str, float]], str]:
    """窗宽探针要用的片段。

    优先用 T3.1（`_select_panel_songs.py`）**数据驱动选出来**的 3 首 test 曲目：
    它们的每一轨占比都在 22~27%，不存在稀疏目标问题。产物在
    `03_outputs/<模型>/test/<曲目>/` 里现成可读，不必重推理。
    """
    if PANEL_SEL.is_file():
        d = json.loads(PANEL_SEL.read_text(encoding="utf-8"))
        picks = [(p["song"], float(p["offset"])) for p in d.get("picked_detail", [])]
        if picks:
            return picks, "test"
    return [(s, o) for s, o in BALANCED], MAIN_SUBSET


# ------------------------------------------------------------------ window
def cmd_window(models, target_min: float) -> int:
    clips, subset = _window_clips()
    cells, skipped = [], []
    print("[window] subset=%s  clips = %d x %d stem x %d 模型"
          % (subset, len(clips), len(STEMS), len(models)))
    print("[window] gate: 目标轨能量占比 >= %.2f" % target_min)
    for song, off in clips:
        start = int(round(off * SR))
        n = int(round(DUR_S * SR))
        gt_dir = _paths.musdb_root() / subset / song
        mix, err = _read_seg(gt_dir / "mixture.wav", start, n)
        if mix is None:
            print("  [SKIP] %s: mixture %s" % (song, err))
            continue
        for st in STEMS:
            ref, err = _read_seg(gt_dir / ("%s.wav" % st), start, n)
            if ref is None:
                skipped.append({"song": song, "stem": st, "why": "GT %s" % err})
                continue
            L = min(len(ref), len(mix))
            sh = _share(ref[:L], mix[:L])
            if sh < target_min:
                skipped.append({"song": song, "stem": st,
                                "why": "目标轨能量占比 %.1f%% < %.1f%%（稀疏目标，两窗都退化）"
                                       % (sh * 100, target_min * 100)})
                continue
            for mk in models:
                mdir = MODEL_DIRS.get(mk, mk)
                est, err = _read_seg(_paths.out_test(mdir) / song / ("%s.flac" % st), start, n)
                if est is None:
                    skipped.append({"song": song, "stem": st, "model": mk, "why": err})
                    continue
                L2 = min(len(ref), len(est))
                vals = {lab: round(sdr_at(ref[:L2], est[:L2], w, h), 4)
                        for lab, w, h in WINDOWS}
                d = round(vals["museval_default_2s_1.5s"] - vals["doc_claimed_1s_1s"], 4)
                cells.append({
                    "model": mk, "song": song, "stem": st, "offset_s": off,
                    "target_energy_share": round(sh, 4),
                    "sdr_default": vals["museval_default_2s_1.5s"],
                    "sdr_1s": vals["doc_claimed_1s_1s"],
                    "delta": d,
                })
                print("  %-12s %-30s %-6s share=%5.1f%%  default=%7.3f  1s=%7.3f  d=%+6.3f"
                      % (mk, song[:30], st, sh * 100,
                         vals["museval_default_2s_1.5s"], vals["doc_claimed_1s_1s"], d))

    if not cells:
        print("[FAIL] 无可比格子")
        return 2

    per_stem = {}
    for st in STEMS:
        ds = [c["delta"] for c in cells if c["stem"] == st]
        if ds:
            per_stem[st] = {
                "n": len(ds),
                "delta_mean": round(float(np.mean(ds)), 4),
                "delta_median": round(float(np.median(ds)), 4),
                "abs_delta_max": round(float(np.max(np.abs(ds))), 4),
            }
    all_d = [c["delta"] for c in cells]
    summary = {
        "n_cells": len(cells),
        "n_skipped": len(skipped),
        "delta_mean": round(float(np.mean(all_d)), 4),
        "delta_median": round(float(np.median(all_d)), 4),
        "abs_delta_mean": round(float(np.mean(np.abs(all_d))), 4),
        "abs_delta_max": round(float(np.max(np.abs(all_d))), 4),
        "abs_delta_p90": round(float(np.percentile(np.abs(all_d), 90)), 4),
        "per_stem": per_stem,
    }
    out = {
        "purpose": "量化「evaluate() 未传 window/hop -> museval 默认 2s/1.5s」与文档声称 1s 窗的实际偏差",
        "call_site": "tools/compare_separation_methods.py::evaluate -> museval.metrics.bss_eval",
        "subset": subset,
        "clips": [{"song": s, "offset_s": o, "dur_s": DUR_S} for s, o in clips],
        "clip_source": "panel_song_selection.json（T3.1 数据驱动选出的高能量均衡片段）"
                       if subset == "test" else "bench_multisong.SONGS",
        "museval_signature_default": {"window": int(2 * SR), "hop": int(1.5 * SR)},
        "doc_claimed": {"window": int(1 * SR), "hop": int(1 * SR)},
        "aggregation": "np.nanmedian over frames; mono=mean over channels; compute_permutation=False",
        "target_energy_gate": target_min,
        "models": models,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "cells": cells,
        "skipped": skipped,
        "status": "PASS",
    }
    OUT_WINDOW.parent.mkdir(parents=True, exist_ok=True)
    OUT_WINDOW.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("")
    print("[window] n=%d (skip %d)  delta mean=%+.3f  median=%+.3f  |mean|=%.3f  |max|=%.3f  |p90|=%.3f dB"
          % (len(cells), len(skipped), summary["delta_mean"], summary["delta_median"],
             summary["abs_delta_mean"], summary["abs_delta_max"], summary["abs_delta_p90"]))
    for st, v in per_stem.items():
        print("         %-7s n=%d  mean=%+.3f  median=%+.3f  |max|=%.3f"
              % (st, v["n"], v["delta_mean"], v["delta_median"], v["abs_delta_max"]))
    print("[window] PASS -> %s" % OUT_WINDOW)
    return 0


# ------------------------------------------------------------------ baseline
def cmd_baseline() -> int:
    per_clip = []
    print("[baseline] subset=%s  mixture 自身作为估计信号（与主表同源同窗）" % MAIN_SUBSET)
    for song, off in BALANCED:
        start = int(round(off * SR))
        n = int(round(DUR_S * SR))
        gt_dir = _paths.musdb_root() / MAIN_SUBSET / song
        mix, err = _read_seg(gt_dir / "mixture.wav", start, n)
        if mix is None:
            print("  [SKIP] %s: %s" % (song, err))
            continue
        row = {"song": song, "offset_s": off}
        for st in STEMS:
            ref, err = _read_seg(gt_dir / ("%s.wav" % st), start, n)
            if ref is None:
                continue
            L = min(len(ref), len(mix))
            # 窗宽固定用 museval 默认值 = 主表实际口径，保证与主表同源
            row[st] = round(sdr_at(ref[:L], mix[:L], int(2 * SR), int(1.5 * SR)), 4)
            print("  %-30s %-6s mixture SDR = %7.3f" % (song[:30], st, row[st]))
        per_clip.append(row)

    if not per_clip:
        print("[FAIL] 无片段")
        return 2
    per_stem = {}
    for st in STEMS:
        vs = [r[st] for r in per_clip if st in r and r[st] is not None]
        if vs:
            per_stem[st] = {"median": round(float(np.median(vs)), 3),
                            "mean": round(float(np.mean(vs)), 3),
                            "values": vs}
    vals4 = [np.mean([per_stem[st]["median"] for st in STEMS])] if len(per_stem) == len(STEMS) else []
    out = {
        "purpose": "mixture 基线：把 mixture 自身当估计信号，按主表同一口径算 SDR",
        "subset": MAIN_SUBSET,
        "clips": [{"song": s, "offset_s": o, "dur_s": DUR_S} for s, o in BALANCED],
        "window": {"window": int(2 * SR), "hop": int(1.5 * SR),
                   "note": "museval bss_eval 签名默认值，即主表实际口径"},
        "aggregation": "np.nanmedian over frames; mono=mean over channels; compute_permutation=False",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "per_clip": per_clip,
        "per_stem": per_stem,
        "avg4": round(float(vals4[0]), 3) if vals4 else None,
        "status": "PASS",
    }
    OUT_BASE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("")
    for st in STEMS:
        if st in per_stem:
            print("  %-7s median=%.3f  mean=%.3f" % (st, per_stem[st]["median"], per_stem[st]["mean"]))
    print("  avg4    = %s" % out["avg4"])
    print("[baseline] PASS -> %s" % OUT_BASE)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="口径取证：窗宽敏感性 + mixture 基线")
    ap.add_argument("mode", choices=["window", "baseline", "all"], nargs="?", default="all")
    ap.add_argument("--models", default="demucs,mdx,umx")
    ap.add_argument("--target-min", type=float, default=0.12)
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    rc = 0
    if args.mode in ("window", "all"):
        rc |= cmd_window(models, args.target_min)
        print("")
    if args.mode in ("baseline", "all"):
        rc |= cmd_baseline()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

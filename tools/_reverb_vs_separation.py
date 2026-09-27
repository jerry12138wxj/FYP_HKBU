"""T4.3 分离模型在混响混音上的退化（reverb -> separation degradation）。

问题：把「干混音」和「湿混音」分别喂回板 1 的四轨分离模型，量它们相对**干 GT stem**
的 SDR 掉多少 → 得到 T60 -> ΔSDR 退化曲线。

口径（与主表一致，不得偷换）：
  - 参考 = **干 GT stem**（`dry/<stem>.wav`），不是湿 stem。
  - 指标 = `compare_separation_methods.evaluate()`（museval BSSEval v4，mono，
    **默认窗 2 s / hop 1.5 s** —— 与主表同源；见计划书 P2）。
  - 每格：4 轨各自的 SDR 中位数 → 取均值 = avg4 SDR。
  - 跨 3 片段取中位数。

门禁（防「跑通但静默错」）：
  G1 干混音自检：dry 档 avg4 SDR 不得低于同模型历史量级的 60%（否则 loader/口径错）。
  G2 电平：每轨 est rms / mixture rms 必须落在 [0.01, 10]，否则该格判 collapse。
  G3 stem 名齐全：输出必须覆盖 4 轨，缺轨即 FAIL（防 stem 顺序错/单轨模型混入）。

用法：
  python tools/_reverb_vs_separation.py <mode> [--models a,b] [--single "model|clip|cond"]
  mode: plan | run | all
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

TOOLS = Path(_paths.TOOLS)
sys.path.insert(0, str(TOOLS))

SR = 44100
REV_DIR = _paths.PROJECT_ROOT / "04_reports" / "01_separation" / "data" / "reverb"
AUDIO_ROOT = _paths.OUTPUTS / "_reverb"
OUT_JSON = REV_DIR / "reverb_vs_sep.json"
MANIFEST = REV_DIR / "reverb_manifest.json"
PY = sys.executable

STEMS = ["vocals", "drums", "bass", "other"]
CONDS = ["dry", "wet_small", "wet_hall"]
# 4 轨模型（单目标模型不参与 avg4 横比，见主表口径）
MODELS = ["demucs", "umx", "mdx", "convtasnet", "mmdenselstm", "bsrnn_all"]
# 干档 avg4 SDR 的历史量级下界（来自主表，train 10 s 片段；此处只做「别崩」粗门禁）
DRY_FLOOR = {"demucs": 5.0, "umx": 4.0, "mdx": 6.0,
             "convtasnet": 3.0, "mmdenselstm": 3.5, "bsrnn_all": 6.0}


def _mono(a):
    a = np.asarray(a, np.float32)
    return a.mean(axis=-1) if a.ndim > 1 else a


def _rms(a):
    return float(np.sqrt(np.mean(np.asarray(a, np.float64) ** 2)))


def _clips():
    return [c["clip_id"] for c in
            json.loads(MANIFEST.read_text(encoding="utf-8"))["clips"]]


def _single(mk: str, clip: str, cond: str) -> dict:
    """跑一格（模型 × 片段 × 档），返回记录。"""
    from benchmark_model_universal import REGISTRY as SEP
    from compare_separation_methods import evaluate

    run, dt_load, info = SEP[mk]["loader"]()
    d = AUDIO_ROOT / clip / cond
    mix, _ = sf.read(str(d / "mixture.wav"), dtype="float32", always_2d=True)
    est = run(mix)
    est = {k: np.asarray(v, np.float32) for k, v in est.items()}

    missing = [s for s in STEMS if s not in est]
    if missing:
        return {"model": mk, "clip_id": clip, "condition": cond, "status": "FAIL",
                "reason": "missing stems %s (got %s)" % (missing, list(est)), "sdr_avg4": None}

    mix_rms = _rms(mix)
    per_stem, levels = {}, {}
    for s in STEMS:
        gt, _ = sf.read(str(AUDIO_ROOT / clip / "dry" / ("%s.wav" % s)),
                        dtype="float32", always_2d=True)
        n = min(len(gt), len(est[s]))
        r = _rms(est[s][:n])
        levels[s] = round(r / (mix_rms + 1e-12), 4)
        ev = evaluate(_mono(gt[:n]), _mono(est[s][:n]))
        per_stem[s] = {"sdr": (round(ev["sdr"], 3) if ev["sdr"] is not None else None),
                       "si_sdr": (round(ev["si_sdr"], 3) if ev["si_sdr"] is not None else None)}
    sdrs = [per_stem[s]["sdr"] for s in STEMS if per_stem[s]["sdr"] is not None]
    avg4 = round(float(np.mean(sdrs)), 3) if len(sdrs) == 4 else None
    sis = [per_stem[s]["si_sdr"] for s in STEMS if per_stem[s]["si_sdr"] is not None]
    avg4_si = round(float(np.mean(sis)), 3) if len(sis) == 4 else None

    lvl_ok = all(0.01 <= v <= 10.0 for v in levels.values())
    gate = {"level_ok": lvl_ok, "levels": levels,
            "dry_floor_ok": (None if cond != "dry"
                             else bool(avg4 is not None and avg4 >= DRY_FLOOR.get(mk, -99)))}
    status = "PASS" if (avg4 is not None and lvl_ok) else "FAIL"
    return {"model": mk, "label": info.get("label", SEP[mk]["label"]),
            "clip_id": clip, "condition": cond, "status": status,
            "load_s": round(dt_load, 2), "sdr_avg4": avg4, "si_sdr_avg4": avg4_si,
            "per_stem": per_stem, "gate": gate,
            "mixture_rms": round(mix_rms, 6)}


def _summarize(models, results, conds):
    """每 (模型, 档) 跨片段取中位数；Δ = 档 - 干（conds[0]）。同时记录每格有效 n。"""
    dry_c = conds[0]
    summary = {}
    for mk in models:
        cells = {c: [r for r in results if r["model"] == mk and r["condition"] == c
                     and r["status"] == "PASS" and r.get("sdr_avg4") is not None]
                 for c in conds}
        dry_med = (round(float(np.median([r["sdr_avg4"] for r in cells[dry_c]])), 3)
                   if cells[dry_c] else None)
        row = {"n_%s" % dry_c: len(cells[dry_c]), "sdr_%s" % dry_c: dry_med}
        for c in conds[1:]:
            med = (round(float(np.median([r["sdr_avg4"] for r in cells[c]])), 3)
                   if cells[c] else None)
            row["n_" + c] = len(cells[c])
            row["sdr_" + c] = med
            row["d_" + c] = (round(med - dry_med, 3)
                             if (med is not None and dry_med is not None) else None)
            row["failed_" + c] = sorted("%s" % r["clip_id"].split("@")[0][:18]
                                        for r in results
                                        if r["model"] == mk and r["condition"] == c
                                        and r["status"] != "PASS")
        summary[mk] = row
    return summary


def cmd_run(models, only: str | None, batch: str | None = None,
            conds=None, out=None) -> int:
    conds = conds or CONDS
    out = Path(out) if out else OUT_JSON
    if only:
        mk, clip, cond = only.split("|")
        rec = _single(mk, clip, cond)
        print(json.dumps(rec, ensure_ascii=False))
        return 0

    # 子进程内：单模型跑满所有格（只加载一次模型）
    if batch:
        for clip in _clips():
            for cond in conds:
                print(json.dumps(_single(batch, clip, cond), ensure_ascii=False), flush=True)
        return 0

    clips = _clips()
    results = []
    for mk in models:
        print("[model] %s" % mk)
        p = subprocess.run([PY, str(Path(__file__).resolve()), "run", "--batch", mk,
                            "--conds", ",".join(conds)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        got = 0
        for ln in (p.stdout or "").strip().splitlines():
            try:
                rec = json.loads(ln)
            except Exception:                                      # noqa: BLE001
                continue
            results.append(rec)
            got += 1
            print("  %-22s %-11s %-7s avg4SDR=%s  %s" % (
                rec.get("clip_id", "")[:22], rec.get("condition"), rec.get("status"),
                rec.get("sdr_avg4"),
                "" if rec.get("status") == "PASS" else str(rec.get("reason", ""))[:80]))
        if got != len(clips) * len(conds):
            print("  [ERR] %s 只回传 %d/%d 格；stderr 尾部:\n%s" % (
                mk, got, len(clips) * len(conds), (p.stderr or "")[-400:]))
            for clip in clips:
                for cond in conds:
                    if not any(r.get("model") == mk and r.get("clip_id") == clip
                               and r.get("condition") == cond for r in results):
                        results.append({"model": mk, "clip_id": clip, "condition": cond,
                                        "status": "FAIL", "sdr_avg4": None,
                                        "reason": "no json returned"})

    # 汇总：每 (模型, 档) 跨片段取中位数；Δ = 档 - 干（conds[0]）
    summary = _summarize(models, results, conds)

    payload = {"task": "T4.3/T4.6 分离模型在退化混音上的表现",
               "metric": "museval BSSEval v4 SDR（mono，默认窗 2 s/hop 1.5 s），"
                         "每片段 4 轨 SDR 均值 = avg4，跨 3 片段取中位数",
               "reference": "干 GT stem（dry/<stem>.wav）",
               "models": models, "conditions": conds,
               "n_cells": len(results),
               "n_pass": sum(1 for r in results if r["status"] == "PASS"),
               "summary_by_model": summary,
               "results": results,
               "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
               "status": ("PASS" if all(r["status"] == "PASS" for r in results)
                          else "PARTIAL")}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n[degradation] %d/%d PASS  conds=%s" % (
        payload["n_pass"], payload["n_cells"], conds))
    hdr = "  %-16s " % "model" + "".join("%-18s" % c for c in conds)
    print(hdr)
    for mk, r in summary.items():
        line = "  %-16s " % mk
        for c in conds:
            cell = "%s(n=%s)" % (r.get("sdr_" + c), r.get("n_" + c))
            line += "%-18s" % cell
        print(line)
        for c in conds[1:]:
            if r.get("d_" + c) is not None:
                print("      d_%-12s = %s" % (c, r.get("d_" + c)))
    print("-> %s" % out)
    return 0 if payload["status"] == "PASS" else 1


def cmd_resummary(models) -> int:
    """读既有 reverb_vs_sep.json 重算 summary（免重跑推理），并写回。"""
    d = json.loads(OUT_JSON.read_text(encoding="utf-8"))
def cmd_resummary(models, out=None) -> int:
    """读既有 json 重算 summary（免重跑推理），并写回。"""
    out = Path(out) if out else OUT_JSON
    d = json.loads(out.read_text(encoding="utf-8"))
    conds = d.get("conditions") or CONDS
    use = [m for m in models if any(r["model"] == m for r in d["results"])] or d["models"]
    d["models"] = use
    d["summary_by_model"] = _summarize(use, d["results"], conds)
    d["status"] = ("PASS" if all(r["status"] == "PASS" for r in d["results"])
                   else "PARTIAL")
    out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[resummary] %s  conds=%s" % (out, conds))
    print("  %-16s " % "model" + "".join("%-20s" % c for c in conds))
    for mk, r in d["summary_by_model"].items():
        line = "  %-16s " % mk
        for c in conds:
            line += "%-20s" % ("%s(n=%s)" % (r.get("sdr_" + c), r.get("n_" + c)))
        print(line)
        for c in conds[1:]:
            if r.get("failed_" + c):
                print("      [FAIL %s] %s" % (c, ", ".join(r["failed_" + c])))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "all", "resummary"], nargs="?", default="run")
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--single", default=None)
    ap.add_argument("--batch", default=None)
    ap.add_argument("--conds", default=",".join(CONDS))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ml = [m for m in a.models.split(",") if m]
    conds = [c for c in a.conds.split(",") if c]
    if a.mode == "resummary":
        return cmd_resummary(ml, a.out)
    return cmd_run(ml, a.single, a.batch, conds, a.out)


if __name__ == "__main__":
    raise SystemExit(main())

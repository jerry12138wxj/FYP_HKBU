"""bench500: 16-model comparison table against the mixture baseline.

WHY A SEPARATE SCRIPT
---------------------
`_bench500.py summary` reports raw SI-SDR only.  Raw SI-SDR is not comparable
across stems (bass is easy, other is hard), so a 4-stem model always looks
better than a vocals-only model for a purely structural reason.  This script
therefore reports **paired delta vs mixture** (est = mixture, same 4 s window,
same SI-SDR function) and keeps the two families in two separate tables.

METRIC CONTRACT (must not drift)
--------------------------------
  * 500 segments = 50 MUSDB18-HQ test songs x 10 x 4.0 s, stereo 44.1 kHz.
  * SI-SDR via benchmark_model_universal.si_sdr (identical to the model rows):
    est is the stereo mean, ref is the mono stem, mean removed, scale invariant.
  * delta[seg, stem] = si_sdr_model[seg, stem] - si_sdr_mixture[seg, stem]
    (paired on the same segment; medians over pairs, never a difference of
    separately-taken medians).
  * avg4 = median over all pooled (segment, stem) deltas, matching the pooling
    convention already used by `_bench500.py summary`.

The mixture baseline is computed once and cached, so re-runs are idempotent.

Usage:
    python tools/_bench500_table.py                 # build tables
    python tools/_bench500_table.py --force-baseline
    python tools/_bench500_table.py --out-dir D:/FYP_HKBU_runs/bench500_table
"""
from __future__ import annotations

import argparse
import csv
import statistics
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
RESULTS = OUT / "results"
STEMS = ["vocals", "drums", "bass", "other"]
SEG_S = 4.0
N_SEG_EXPECT = 500

# 文件名里带这些词的行不参与主表（旧权重、实验分支、备份）
SKIP_TOKENS = ("preretrain", "bak", "old", "tmp", "test")


def read_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_segments():
    segs = read_csv(OUT / "segments.csv")
    if len(segs) != N_SEG_EXPECT:
        print("WARN segments.csv has %d rows, expected %d" % (len(segs), N_SEG_EXPECT))
    return segs


def mixture_baseline(segs, force=False):
    """si_sdr(mixture, stem) per (seg_id, stem), cached on disk."""
    p = OUT / "mixture_baseline.csv"
    if p.is_file() and not force:
        rows = read_csv(p)
        print("mixture baseline: cached (%d rows) <- %s" % (len(rows), p.name))
        return {(r["seg_id"], r["stem"]): float(r["si_sdr"]) for r in rows}

    import benchmark_model_universal as bm
    t0 = time.time()
    out = []
    for i, sg in enumerate(segs, 1):
        mix, gt, _sr = bm.load_clip(sg["song"], "test", SEG_S, float(sg["offset_s"]))
        x = np.asarray(mix, dtype=np.float64)
        if x.ndim > 1:
            x = x.mean(axis=1)
        for stem, ref in gt.items():
            L = min(len(ref), len(x))
            if L < 1024:
                continue
            v = float(bm.si_sdr(ref[:L], x[:L]))
            out.append(dict(seg_id=sg["seg_id"], song=sg["song"],
                            offset_s=sg["offset_s"], stem=stem, si_sdr=round(v, 3)))
        if i % 100 == 0:
            print("  baseline %d/%d  %.1f s" % (i, len(segs), time.time() - t0))
    cols = ["seg_id", "song", "offset_s", "stem", "si_sdr"]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print("mixture baseline: computed %d rows in %.1f s -> %s"
          % (len(out), time.time() - t0, p))
    return {(r["seg_id"], r["stem"]): float(r["si_sdr"]) for r in out}


def collect(base):
    """-> models[name] = dict(rows={(seg,stem): v}, rtf=[...], stems=set())"""
    models = {}
    for p in sorted(RESULTS.glob("*.csv")):
        name = p.stem
        low = name.lower()
        if any(t in low for t in SKIP_TOKENS):
            print("skip (non-primary): %s" % name)
            continue
        rows = read_csv(p)
        if not rows:
            print("skip (empty): %s" % name)
            continue
        rec = dict(rows={}, rtf=[], stems=set(), path=str(p), n_rows=len(rows))
        for r in rows:
            try:
                v = float(r["si_sdr"])
            except (TypeError, ValueError):
                continue
            rec["rows"][(r["seg_id"], r["stem"])] = v
            rec["stems"].add(r["stem"])
            try:
                rec["rtf"].append(float(r["rtf"]))
            except (TypeError, ValueError):
                pass
        models[name] = rec
    return models


def summarize(name, rec, base):
    stems_present = [s for s in STEMS if s in rec["stems"]]
    n_seg = len({seg for seg, _ in rec["rows"]})
    # 原始值统计不受基线约束：像 `vocals+other` 这种没有同口径基线的目标，
    # 仍然要能报出自己的 SI-SDR，只是不报 Δ。
    raw_all = list(rec["rows"].values())
    deltas = []
    per = {}
    for s in stems_present:
        d, r = [], []
        for (seg, stem), v in rec["rows"].items():
            if stem != s:
                continue
            r.append(v)
            k = (seg, stem)
            if k in base:
                d.append(v - base[k])
        per[s] = dict(n=len(d),
                      delta=statistics.median(d) if d else None,
                      raw=statistics.median(r) if r else None)
        deltas.extend(d)
    return dict(model=name, n_seg=n_seg, stems=stems_present,
                stems_raw=sorted(rec["stems"]),
                per=per,
                delta_pooled=statistics.median(deltas) if deltas else None,
                raw_pooled=statistics.median(raw_all) if raw_all else None,
                rtf=statistics.median(rec["rtf"]) if rec["rtf"] else None,
                complete=(n_seg >= N_SEG_EXPECT))


def fmt(v, nd=2):
    return "n/a" if v is None else ("%+.*f" % (nd, v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-baseline", action="store_true")
    ap.add_argument("--out-dir", default=r"D:\FYP_HKBU_runs\bench500_table")
    args = ap.parse_args()

    segs = load_segments()
    base = mixture_baseline(segs, force=args.force_baseline)
    models = collect(base)
    if not models:
        raise SystemExit("no result csv under %s" % RESULTS)

    rows = [summarize(n, r, base) for n, r in models.items()]
    # 对照行（不进主排序）：
    #   *_last       同一权重的 last.pt —— best 选择是否可靠的证据
    #   dprnn        重训前的旧权重（泄漏划分时期）—— 一旦 dprnn_v2 存在即降级
    alt = []
    for x in rows:
        if x["model"].endswith("_last"):
            x["alt_reason"] = "last.pt 对照（同一权重）"
            alt.append(x)
    names = {x["model"] for x in rows}
    if "dprnn_v2" in names and "dprnn" in names:
        for x in rows:
            if x["model"] == "dprnn":
                x["alt_reason"] = "重训前旧权重（验证集泄漏时期），仅作对照"
                alt.append(x)
    rows = [x for x in rows if x not in alt]
    four = [x for x in rows if len([s for s in x["stems"] if s in STEMS]) == 4]
    single = [x for x in rows if len([s for s in x["stems"] if s in STEMS]) == 1 and "vocals" in x["stems"]]
    other = [x for x in rows if x not in four and x not in single]

    four.sort(key=lambda x: -(x["delta_pooled"] if x["delta_pooled"] is not None else -99))
    single.sort(key=lambda x: -(x["per"]["vocals"]["delta"]
                               if x["per"]["vocals"]["delta"] is not None else -99))

    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ---- tidy csv -------------------------------------------------------
    cols = ["model", "family", "n_seg", "complete", "stems"]
    for s in STEMS:
        cols += ["%s_delta" % s, "%s_raw" % s, "%s_n" % s]
    cols += ["avg4_delta", "avg4_raw", "rtf_median"]
    tidy = []
    for fam, group in (("4-stem", four), ("vocals-only", single)):
        for x in group:
            rec = dict(model=x["model"], family=fam, n_seg=x["n_seg"],
                       complete=x["complete"], stems="+".join(x["stems"]),
                       avg4_delta=x["delta_pooled"] if fam == "4-stem" else "",
                       avg4_raw=x["raw_pooled"] if fam == "4-stem" else "",
                       rtf_median=x["rtf"])
            for s in STEMS:
                p = x["per"].get(s)
                rec["%s_delta" % s] = p["delta"] if p else ""
                rec["%s_raw" % s] = p["raw"] if p else ""
                rec["%s_n" % s] = p["n"] if p else ""
            tidy.append(rec)
    csv_path = outdir / "bench500_compare.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in tidy:
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})

    # ---- markdown -------------------------------------------------------
    L = []
    L.append("# bench500：16 模型优劣表（ΔSI-SDR vs mixture）\n")
    L.append("**口径（三要素不可省）**：MUSDB18-HQ **test** 50 首 × 10 段 × **4.0 s**，"
             "立体声 **44.1 kHz**；SI-SDR 取声道均值 vs 单声道 GT，"
             "与模型行同一实现（`benchmark_model_universal.si_sdr`，去均值、尺度不变）。\n")
    L.append("**Δ 的定义**：`delta[段, 轨] = 模型 SI-SDR − mixture SI-SDR`，"
             "**同一段逐对相减后再取中位数**（不是两个中位数相减）。"
             "mixture 基线 = 直接用混合信号当估计（`est = mixture`），"
             "因此 Δ>0 才代表模型真的比「不做分离」更好。\n")
    L.append("**为什么不混表**：bass 天然好分、other 天然难分，"
             "四轨均值与单轨（仅 vocals）不在同一量纲上，"
             "**单轨模型禁止与 avg4 横比**。\n")

    L.append("\n## 表 1　四轨模型（4-stem，按 avg4 Δ 降序）\n")
    L.append("| # | 模型 | avg4 Δ | vocals Δ | drums Δ | bass Δ | other Δ | RTF | 覆盖 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for i, x in enumerate(four, 1):
        g = x["per"]
        L.append("| %d | `%s` | **%s** | %s | %s | %s | %s | %s | %d/%d%s |" % (
            i, x["model"], fmt(x["delta_pooled"]),
            fmt(g.get("vocals", {}).get("delta")), fmt(g.get("drums", {}).get("delta")),
            fmt(g.get("bass", {}).get("delta")), fmt(g.get("other", {}).get("delta")),
            "n/a" if x["rtf"] is None else "%.3f" % x["rtf"],
            x["n_seg"], N_SEG_EXPECT, "" if x["complete"] else " ⚠未完成"))

    L.append("\n## 表 2　单轨模型（vocals only，按 vocals Δ 降序）\n")
    L.append("| # | 模型 | vocals Δ | vocals SI-SDR | RTF | 覆盖 |")
    L.append("|---|---|---|---|---|---|")
    for i, x in enumerate(single, 1):
        p = x["per"]["vocals"]
        L.append("| %d | `%s` | **%s** | %s | %s | %d/%d%s |" % (
            i, x["model"], fmt(p["delta"]), fmt(p["raw"]),
            "n/a" if x["rtf"] is None else "%.3f" % x["rtf"],
            x["n_seg"], N_SEG_EXPECT, "" if x["complete"] else " ⚠未完成"))

    if other:
        L.append("\n## 表 3　其他目标定义（不可与表 1 / 表 2 横比）\n")
        L.append("| 模型 | 输出目标 | 原始 SI-SDR | RTF | 覆盖 | 为什么单独放 |")
        L.append("|---|---|---|---|---|---|")
        for x in other:
            st = "+".join(x["stems_raw"])
            why = ("目标是 **vocals+other 合并**，与任何单轨/四轨口径都不同；"
                   "基线没有对应的合并参考，故**不计算 Δ**，仅报原始值"
                   if st not in STEMS else
                   "目标非标准 vocab，无法与 4-stem 均值同表")
            L.append("| `%s` | `%s` | %s | %s | %d/%d | %s |" % (
                x["model"], st, fmt(x["raw_pooled"]),
                "n/a" if x["rtf"] is None else "%.3f" % x["rtf"],
                x["n_seg"], N_SEG_EXPECT, why))

    if alt:
        L.append("\n## 表 4　对照行（已排除在排序之外）\n")
        L.append("| 模型 | avg4 Δ | vocals Δ | drums Δ | bass Δ | other Δ | 覆盖 | 说明 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for x in alt:
            g = x["per"]
            L.append("| `%s` | %s | %s | %s | %s | %s | %d/%d | %s |" % (
                x["model"], fmt(x["delta_pooled"]),
                fmt(g.get("vocals", {}).get("delta")), fmt(g.get("drums", {}).get("delta")),
                fmt(g.get("bass", {}).get("delta")), fmt(g.get("other", {}).get("delta")),
                x["n_seg"], N_SEG_EXPECT, x.get("alt_reason", "")))

    # mixture 自比必须正好 0，作为口径自检
    L.append("\n## 口径自检\n")
    L.append("- mixture 基线：`est = mixture`，故 Δ 恒为 **0.000**（本表未把基线本身列为一行）。")
    L.append("- 每模型覆盖 %d 段为满分；不足者标 ⚠，其排序位置仅供预览，**不得写进结论**。" % N_SEG_EXPECT)
    L.append("- DPRNN 原生 **11.025 kHz**，升采样回 44.1 kHz 后高频是插值，"
             "SDR 已如实承担带宽损失，不另加分。")
    L.append("- 若同目录同时存在 `dprnn.csv` 与 `dprnn_v2.csv`，前者为**泄漏划分时期的旧权重**，"
             "只作对照，不得作为 DPRNN 的当前成绩。")

    md_path = outdir / "BENCH500_COMPARE.md"
    md_path.write_bytes("\n".join(L).encode("utf-8"))

    print("wrote %s" % csv_path)
    print("wrote %s" % md_path)
    print("models: 4-stem=%d  vocals-only=%d  other=%d" % (len(four), len(single), len(other)))
    for x in four + single:
        tag = "" if x["complete"] else " PARTIAL"
        print("  %-16s %-12s delta=%s rtf=%s n=%d%s" % (
            x["model"], "4stem" if x in four else "vocals",
            fmt(x["delta_pooled"] if x in four else x["per"]["vocals"]["delta"]),
            "n/a" if x["rtf"] is None else "%.3f" % x["rtf"], x["n_seg"], tag))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

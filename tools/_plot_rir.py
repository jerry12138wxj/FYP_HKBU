"""T4.4 RIR 本体图：脉冲响应波形 + Schroeder EDC + T60/C50/DRR 标注。

产出（论文/答辩可直接贴）：
  separation/figures/comparison/fig_rir_t60.png

口径与 `_select_rirs.py::_schroeder_t60` 一致：
  - T60 = 2 x T30（-5~-25 dB 最小二乘），**拟合前剔除峰值 ±2.5 ms 直达声窗**；
  - 另给"含直达声"的 t60_full 作对照（会偏小，因为 -5 dB 点落在尖峰塌陷段）。
"""
from __future__ import annotations

import json
from pathlib import Path

import paths as _paths

def _relfig(p):
    """把工程内路径写成相对 PROJECT_ROOT 的 POSIX 串。

    交付物（JSON / MD / HTML）中**不得**出现本机绝对路径：否则换目录就变字节，
    破坏「clone 后可复现」。T8.6 实测抓出（见计划书 §9.13）。
    刻意不依赖模块级 `Path` 名（部分脚本只用 `/` 运算符，未 import Path）。
    """
    import os as _os
    try:
        return _os.path.relpath(str(p), str(_paths.PROJECT_ROOT)).replace(_os.sep, "/")
    except ValueError:                      # 跨盘符时 relpath 会抛 ValueError
        return str(p).replace(_os.sep, "/")
  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REV = _paths.PROJECT_ROOT / "04_reports" / "separation" / "data" / "reverb"
RIR_DIR = REV / "rir"
FIG = _paths.PROJECT_ROOT / "04_reports" / "separation" / "figures" / "comparison" / "fig_rir_t60.png"
SEL = REV / "rir_selection.json"

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 140})


def _edc(h, sr, drop_direct=True):
    """返回 (t, edc_db, t60_fit, band_idx)。drop_direct=False 时用整条。"""
    h = np.asarray(h, np.float64).ravel()
    if drop_direct:
        peak = int(np.argmax(np.abs(h)))
        w = max(1, int(0.0025 * sr))
        h = h.copy()
        h[max(0, peak - w): peak + w + 1] = 0.0
    e = np.cumsum(h[::-1] ** 2)[::-1]
    if e[0] <= 0:
        return None
    edc = 10.0 * np.log10(e / e[0] + 1e-30)
    t = np.arange(h.size) / sr
    ia = int(np.argmax(edc <= -5.0))
    ib = int(np.argmax(edc <= -25.0))
    t60 = None
    if edc[-1] <= -25.0 and ib > ia + 1:
        k, b = np.polyfit(t[ia:ib], edc[ia:ib], 1)
        if k < 0:
            t60 = -60.0 / k
    return t, edc, t60, (ia, ib)


def _c50_drr(h, sr):
    h = np.asarray(h, np.float64).ravel()
    peak = int(np.argmax(np.abs(h)))
    n50 = peak + int(0.050 * sr)
    head = np.sum(h[peak:n50] ** 2)
    tail = np.sum(h[n50:] ** 2)
    c50 = 10 * np.log10((head + 1e-30) / (tail + 1e-30))
    n_direct = peak + int(0.0025 * sr)
    d = np.sum(h[peak:n_direct] ** 2)
    r = np.sum(h[n_direct:] ** 2)
    drr = 10 * np.log10((d + 1e-30) / (r + 1e-30))
    return float(c50), float(drr)


def main() -> int:
    sel = json.loads(SEL.read_text(encoding="utf-8"))
    items = [("small_0p6", "Small room  T60=0.60 s", "#1f6feb"),
             ("hall_1p2", "Large hall (real AIR RIR)  T60=1.21 s", "#d29922")]

    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.2))
    rows = []
    for r, (name, title, col) in enumerate(items):
        h, sr = sf.read(str(RIR_DIR / ("%s.wav" % name)), dtype="float64", always_2d=False)
        if h.ndim > 1:
            h = h.mean(axis=1)
        rec = sel["picked"][name]
        t, edc, t60, (ia, ib) = _edc(h, sr, drop_direct=True)
        _t2, edc2, t60f, _b2 = _edc(h, sr, drop_direct=False)
        c50, drr = _c50_drr(h, sr)

        # A 波形（归一化）
        ax = axes[r][0]
        ax.plot(np.arange(h.size) / sr * 1000, h / (np.abs(h).max() + 1e-12),
                lw=0.5, color=col)
        ax.set_title("%s\nimpulse response (%.2f s @ %.0f Hz)" % (title, h.size / sr, sr),
                     fontsize=10)
        ax.set_xlabel("time (ms)" + ("  (detail view)" if r == 1 else ""))
        ax.set_ylabel("amplitude (norm.)")
        ax.set_xlim(0, min(h.size / sr * 1000, 200 if r == 0 else 400))
        if h.size / sr * 1000 > (200 if r == 0 else 400):
            ax.text(0.98, 0.95, "showing first %.0f ms of %.2f s" % (
                min(h.size / sr * 1000, 400), h.size / sr),
                transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#57606a")

        # B EDC（剔除直达声，画到 -60 dB 或末尾）
        ax = axes[r][1]
        # 🔴 edc 是**降序**数组，不能用 np.searchsorted（它假定升序，结果无意义）；
        #    与 _select_rirs 一致，用 argmax(edc <= -60) 定位首次穿越点。
        lim = (int(np.argmax(edc <= -60.0)) if edc[-1] <= -60.0 else edc.size)
        lim = int(max(lim, ib + int(0.05 * sr), int(0.1 * sr)))
        ax.plot(t[:lim] * 1000, edc[:lim], color=col, lw=1.4, label="EDC (direct removed)")
        ax.plot(_t2[:lim] * 1000, edc2[:lim], color="#8b949e", lw=1.0, ls="--",
                label="EDC (with direct sound)")
        ax.axhspan(-25, -5, color=col, alpha=0.10)
        ax.axhline(-5, color=col, lw=0.7, ls=":")
        ax.axhline(-25, color=col, lw=0.7, ls=":")
        if t60:
            k = -60.0 / t60
            xs = np.array([t[ia], t[ia] + (-60.0 - edc[ia]) / k]) * 1000
            ax.plot(xs, edc[ia] + (xs / 1000 - t[ia]) * k, color="#f85149", lw=1.6,
                    label="T30 fit -> T60=%.3f s" % t60)
        ax.set_ylim(-62, 8)
        ax.set_xlim(0, min(lim / sr * 1000, 3000))
        ax.set_title("Schroeder EDC  |  T60=%.3f s   (t60_full=%.3f s)" % (
            t60 or -1, t60f or -1), fontsize=10)
        ax.set_xlabel("time (ms)")
        ax.set_ylabel("energy (dB)")
        ax.legend(fontsize=8, loc="upper right")

        # C 指标卡
        ax = axes[r][2]
        ax.axis("off")
        card = [
            ["metric", "value"],
            ["target T60", "%.2f s" % rec["target_t60"]],
            ["T60 @ source 48k", "%.3f s" % rec["picked_t60"]],
            ["T60 @ exported 44.1k", "%.3f s" % (t60 or -1)],
            ["t60 (with direct)", "%.3f s" % (t60f or -1)],
            ["C50", "%.2f dB" % c50],
            ["DRR", "%.2f dB" % drr],
            ["length", "%.2f s" % (h.size / sr)],
            ["source", "sim SLR26" if r == 0 else "real SLR28"],
        ]
        tb = ax.table(cellText=card[1:], colLabels=card[0], loc="center", cellLoc="left")
        tb.auto_set_font_size(False)
        tb.set_fontsize(9.5)
        tb.scale(1.0, 1.55)
        for j in range(2):
            c = tb[0, j]
            c.set_facecolor(col)
            c.set_text_props(color="white", weight="bold")
        for i in range(1, len(card)):
            tb[i, 0].set_facecolor("#f0f3f6")
        ax.set_title("measured metrics", fontsize=10)

        rows.append({"name": name, "t60_source_48k": rec["picked_t60"],
                     "t60_exported_44k": round(t60, 4) if t60 else None,
                     "t60_full": round(t60f, 4) if t60f else None,
                     "c50_db": round(c50, 3), "drr_db": round(drr, 3),
                     "dur_s": round(h.size / sr, 4), "sr": sr})

    fig.suptitle("T4.4  RIR used for the reverb experiment  "
                 "(Schroeder inverse integration, direct sound removed before fitting;"
                 " T60 drop from source->export = DC removal + 48->44.1 kHz resample)",
                 fontsize=11.5, y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(FIG))
    out = REV / "rir_figure_metrics.json"
    out.write_text(json.dumps({"task": "T4.4 RIR 本体图", "metrics": rows,
                               "figure": _relfig(FIG),
                               "note": "T60 = 2 x T30(-5~-25 dB) 最小二乘，拟合前把峰值 "
                                       "±2.5 ms 直达声窗置零；t60_full 为含直达声对照。"},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("[fig] %s" % FIG)
    for r in rows:
        print("  %-11s T60 src=%s -> exp=%s  C50=%s  DRR=%s" % (
            r["name"], r["t60_source_48k"], r["t60_exported_44k"], r["c50_db"], r["drr_db"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

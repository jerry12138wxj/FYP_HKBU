"""T4.5 T60 -> ΔSDR 退化曲线（T4.3 结果的可视化）。

x = 混响强度（T60，秒）；y = avg4 SDR（museval，参考=干 GT stem）。
每个模型 3 个点：dry(T60=0) / wet_small(T60=0.49) / wet_hall(T60=1.03)。
右图直接画 ΔSDR = SDR(T60) - SDR(dry)。

产出：
  separation/figures/comparison/fig_reverb_degradation.png
"""
from __future__ import annotations

import json

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

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REV = _paths.PROJECT_ROOT / "04_reports" / "separation" / "data" / "reverb"
FIG = (_paths.PROJECT_ROOT / "04_reports" / "separation" / "figures"
       / "comparison" / "fig_reverb_degradation.png")

PRETTY = {"demucs": "Demucs (htdemucs)", "umx": "Open-Unmix (umxhq)",
          "mdx": "MDX-Net (mdx_extra)", "convtasnet": "Conv-TasNet",
          "mmdenselstm": "MMDenseLSTM", "bsrnn_all": "oBSRNN (4 ckpt)"}
ORDER = ["bsrnn_all", "mdx", "demucs", "mmdenselstm", "convtasnet", "umx"]

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 140})


def main() -> int:
    d = json.loads((REV / "reverb_vs_sep.json").read_text(encoding="utf-8"))
    rir = json.loads((REV / "rir_figure_metrics.json").read_text(encoding="utf-8"))
    t60 = {m["name"]: m["t60_exported_44k"] for m in rir["metrics"]}
    xs = [0.0, t60["small_0p6"], t60["hall_1p2"]]
    xlab = ["dry (T60=0)", "small room\nT60=%.2f s" % t60["small_0p6"],
            "large hall\nT60=%.2f s" % t60["hall_1p2"]]

    S = d["summary_by_model"]
    colors = plt.get_cmap("tab10").colors

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.0, 6.0))

    for i, mk in enumerate(ORDER):
        if mk not in S:
            continue
        r = S[mk]
        ys = [r.get("sdr_dry"), r.get("sdr_wet_small"), r.get("sdr_wet_hall")]
        ns = [r.get("n_dry_pass"), r.get("n_wet_small"), r.get("n_wet_hall")]
        if any(v is None for v in ys):
            continue
        lab = PRETTY.get(mk, mk)
        ax1.plot(xs, ys, "o-", color=colors[i], lw=2, ms=7, label=lab)
        ds = [0.0] + [round(ys[j] - ys[0], 3) for j in (1, 2)]
        ax2.plot(xs, ds, "o-", color=colors[i], lw=2, ms=7, label=lab)
        # 标注 n<3 的点（有效片段不足，值仅供参考）
        for j, n in enumerate(ns):
            if n and n < 3:
                ax1.annotate("n=%d" % n, (xs[j], ys[j]), textcoords="offset points",
                             xytext=(4, -12), fontsize=8, color=colors[i])
                ax2.annotate("n=%d" % n, (xs[j], ds[j]), textcoords="offset points",
                             xytext=(4, -12), fontsize=8, color=colors[i])

    for ax in (ax1, ax2):
        ax.set_xticks(xs)
        ax.set_xticklabels(xlab, fontsize=9)
        ax.set_xlabel("input reverberation (T60 of RIR convolved into the mixture)")
    ax1.set_ylabel("Average SDR  (museval, ref = dry GT stems)")
    ax1.set_title("Separation quality collapses under reverberation", fontsize=11.5)
    ax1.axhline(0, color="#8b949e", lw=0.8, ls="--")
    ax1.legend(fontsize=9, loc="lower left")
    ax2.set_ylabel("ΔSDR  vs dry  (dB)")
    ax2.set_title("Degradation is monotone in T60  (all 6 models)", fontsize=11.5)
    ax2.axhline(0, color="#8b949e", lw=0.8, ls="--")
    ax2.axhspan(-16, 0, color="#f85149", alpha=0.06)
    ax2.legend(fontsize=9, loc="lower left")

    note = ("metric = museval BSSEval v4 SDR (mono, 2 s/1.5 s window); ref = dry GT stems; "
            "avg4 = mean over 4 stems, median over 3 clips.\n"
            "n<3 marks cells where a stem collapsed (e.g. oBSRNN bass head on heavy reverb).")
    fig.text(0.5, 0.012, note, ha="center", fontsize=8.5, color="#57606a")
    fig.suptitle("T4.5  Reverberation -> source-separation degradation", fontsize=13, y=0.975)
    fig.tight_layout(rect=(0, 0.05, 1, 0.955))
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(FIG))

    tab = {mk: {c: S[mk].get("d_" + c) for c in ("wet_small", "wet_hall")} for mk in S}
    (REV / "reverb_degradation_curve.json").write_text(json.dumps(
        {"task": "T4.5 T60 -> ΔSDR 退化曲线", "x_t60_s": xs, "figure": _relfig(FIG),
         "delta_sdr_by_model": tab,
         "note": "ΔSDR = SDR(T60) - SDR(dry)；负值=退化。d_wet_hall 中 bsrnn_all 仅 1 个"
                 "有效片段（另 2 片段 bass 支塌陷被门禁剔除）。"},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("[fig] %s" % FIG)
    for mk in ORDER:
        if mk in tab:
            print("  %-14s d_small=%-8s d_hall=%s" % (
                mk, tab[mk]["wet_small"], tab[mk]["wet_hall"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

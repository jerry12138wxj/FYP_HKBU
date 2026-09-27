"""T4.6 回声 -> 分离退化图（echo_vs_sep.json 的可视化）。

x = 回声条件（dry / echo_short 80 ms·g0.6 / echo_long 250 ms·g0.8）
y = avg4 SDR（museval，参考 = 干 GT stem）；右图 = ΔSDR。

产出：01_separation/figures/comparison/fig_echo_degradation.png
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

REV = _paths.PROJECT_ROOT / "04_reports" / "01_separation" / "data" / "reverb"
FIG = (_paths.PROJECT_ROOT / "04_reports" / "01_separation" / "figures"
       / "comparison" / "fig_echo_degradation.png")

PRETTY = {"demucs": "Demucs (htdemucs)", "umx": "Open-Unmix (umxhq)",
          "mdx": "MDX-Net (mdx_extra)", "convtasnet": "Conv-TasNet",
          "mmdenselstm": "MMDenseLSTM", "bsrnn_all": "oBSRNN (4 ckpt)"}
ORDER = ["bsrnn_all", "mdx", "demucs", "mmdenselstm", "convtasnet", "umx"]

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 140})


def main() -> int:
    d = json.loads((REV / "echo_vs_sep.json").read_text(encoding="utf-8"))
    em = json.loads((REV / "echo_manifest.json").read_text(encoding="utf-8"))
    conds = d["conditions"]
    cfg = em["echo"]
    xlab = []
    for c in conds:
        if c in cfg:
            xlab.append("%s\n%d ms, gain %.1f" % (c, cfg[c]["delay_ms"], cfg[c]["gain"]))
        else:
            xlab.append("%s\n(no echo)" % c)
    xs = list(range(len(conds)))
    S = d["summary_by_model"]
    colors = plt.get_cmap("tab10").colors

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.0, 6.0))
    for i, mk in enumerate(ORDER):
        if mk not in S:
            continue
        r = S[mk]
        ys = [r.get("sdr_" + c) for c in conds]
        ns = [r.get("n_" + c) for c in conds]
        if any(v is None for v in ys):
            continue
        lab = PRETTY.get(mk, mk)
        ds = [0.0] + [round(ys[j] - ys[0], 3) for j in range(1, len(conds))]
        ax1.plot(xs, ys, "o-", color=colors[i], lw=2, ms=7, label=lab)
        ax2.plot(xs, ds, "o-", color=colors[i], lw=2, ms=7, label=lab)
        for j, n in enumerate(ns):
            if n and n < 3:
                for ax, yy in ((ax1, ys[j]), (ax2, ds[j])):
                    ax.annotate("n=%d" % n, (xs[j], yy), textcoords="offset points",
                                xytext=(4, -12), fontsize=8, color=colors[i])

    for ax in (ax1, ax2):
        ax.set_xticks(xs)
        ax.set_xticklabels(xlab, fontsize=9)
        ax.set_xlabel("echo condition (delayed attenuated copy added to the mixture)")
    ax1.set_ylabel("Average SDR  (museval, ref = dry GT stems)")
    ax1.set_title("Separation degrades under echo too", fontsize=11.5)
    ax1.axhline(0, color="#8b949e", lw=0.8, ls="--")
    ax1.legend(fontsize=9, loc="lower left")
    ax2.set_ylabel("ΔSDR  vs dry  (dB)")
    ax2.set_title("ΔSDR by echo condition", fontsize=11.5)
    ax2.axhline(0, color="#8b949e", lw=0.8, ls="--")
    ax2.axhspan(-16, 0, color="#f85149", alpha=0.06)
    ax2.legend(fontsize=9, loc="lower left")

    fig.text(0.5, 0.012,
             "metric = museval BSSEval v4 SDR (mono, 2 s/1.5 s window); ref = dry GT stems; "
             "avg4 = mean over 4 stems, median over 3 clips.",
             ha="center", fontsize=8.5, color="#57606a")
    fig.suptitle("T4.6  Echo -> source-separation degradation", fontsize=13, y=0.975)
    fig.tight_layout(rect=(0, 0.05, 1, 0.955))
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(FIG))

    tab = {mk: {c: S[mk].get("d_" + c) for c in conds[1:]} for mk in S}
    (REV / "echo_degradation_curve.json").write_text(json.dumps(
        {"task": "T4.6 echo -> ΔSDR", "conditions": conds, "echo": cfg,
         "figure": _relfig(FIG), "delta_sdr_by_model": tab},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("[fig] %s" % FIG)
    for mk in ORDER:
        if mk in tab:
            print("  %-14s %s" % (mk, tab[mk]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""T4.7 阶段 4 一页小结图（答辩用）。

把 T4.1-T4.6 的结论压到一张 16:9 图上，四块面板：
  A. 混响 vs 回声：ΔSDR 并列条形（同 x 轴，直观对比破坏力）
  B. ΔSDR 随输入劣化档的单调性（混响与回声两条曲线，取 6 模型均值）
  C. 去混响负结果：湿信号损失 vs 两个 checkpoint 的回收量
  D. 结论卡（三句话 + 口径脚注）

数据全部读已有 JSON，不重算、不重跑推理。

产出：
  separation/figures/comparison/fig_stage4_summary.png
  separation/data/reverb/stage4_summary.json
"""
from __future__ import annotations

import json

import paths as _paths  # noqa: E402

_paths.setup_env()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

REV = _paths.PROJECT_ROOT / "04_reports" / "separation" / "data" / "reverb"
FIG = (_paths.PROJECT_ROOT / "04_reports" / "separation" / "figures"
       / "comparison" / "fig_stage4_summary.png")

PRETTY = {"demucs": "Demucs", "umx": "Open-Unmix", "mdx": "MDX-Net",
          "convtasnet": "Conv-TasNet", "mmdenselstm": "MMDenseLSTM",
          "bsrnn_all": "oBSRNN"}
ORDER = ["bsrnn_all", "mdx", "demucs", "mmdenselstm", "convtasnet", "umx"]

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 140})


def main() -> int:
    rev = json.loads((REV / "reverb_vs_sep.json").read_text(encoding="utf-8"))
    ech = json.loads((REV / "echo_vs_sep.json").read_text(encoding="utf-8"))
    deg = json.loads((REV / "dereverb_diagnosis.json").read_text(encoding="utf-8"))
    rir = json.loads((REV / "rir_figure_metrics.json").read_text(encoding="utf-8"))

    Sr = rev["summary_by_model"]
    Se = ech["summary_by_model"]
    t60 = {m["name"]: m["t60_exported_44k"] for m in rir["metrics"]}

    fig = plt.figure(figsize=(16.0, 9.0))
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.34,
                          left=0.105, right=0.975, top=0.90, bottom=0.09)

    # ---------------- A. 破坏力并列条形 ----------------
    axA = fig.add_subplot(gs[0, 0])
    y = np.arange(len(ORDER))
    h = 0.26
    d_rev = [Sr[m]["d_wet_hall"] for m in ORDER]
    d_es = [Se[m]["d_echo_short"] for m in ORDER]
    d_el = [Se[m]["d_echo_long"] for m in ORDER]
    axA.barh(y + h, d_rev, h, color="#f85149", label="Reverb (hall, T60=%.2f s)" % t60["hall_1p2"])
    axA.barh(y, d_el, h, color="#d29922", label="Echo (250 ms, g=0.8)")
    axA.barh(y - h, d_es, h, color="#3fb950", label="Echo (80 ms, g=0.6)")
    axA.set_yticks(y)
    axA.set_yticklabels([PRETTY[m] for m in ORDER], fontsize=10)
    axA.axvline(0, color="#8b949e", lw=0.9)
    axA.axvspan(-16, -10, color="#f85149", alpha=0.06)
    axA.set_xlabel("ΔSDR vs dry input  (dB, lower = worse)", fontsize=10)
    axA.set_title("A. Reverberation hurts ~2.5x more than echo", fontsize=11.5)
    axA.legend(fontsize=8.5, loc="lower left", framealpha=0.9)
    axA.set_xlim(-17, 0.5)
    for i, m in enumerate(ORDER):
        axA.text(d_rev[i] - 0.3, i + h, "%.1f" % d_rev[i], va="center", ha="right",
                 fontsize=8, color="#f85149")

    # ---------------- B. 单调性 ----------------
    axB = fig.add_subplot(gs[0, 1])
    xs = [0.0, 1.0, 2.0]
    rev_curve = [0.0] + [float(np.mean([Sr[m]["d_wet_small"] for m in ORDER])),
                         float(np.mean([Sr[m]["d_wet_hall"] for m in ORDER]))]
    ech_curve = [0.0] + [float(np.mean([Se[m]["d_echo_short"] for m in ORDER])),
                         float(np.mean([Se[m]["d_echo_long"] for m in ORDER]))]
    axB.plot(xs, rev_curve, "o-", color="#f85149", lw=2.4, ms=9,
             label="Reverberation (mean of 6 models)")
    axB.plot(xs, ech_curve, "s-", color="#d29922", lw=2.4, ms=9,
             label="Echo (mean of 6 models)")
    for x, v in zip(xs, rev_curve):
        axB.annotate("%.1f" % v, (x, v), textcoords="offset points", xytext=(6, 6),
                     fontsize=9, color="#f85149")
    for x, v in zip(xs, ech_curve):
        axB.annotate("%.1f" % v, (x, v), textcoords="offset points", xytext=(6, -14),
                     fontsize=9, color="#b8860b")
    axB.axhline(0, color="#8b949e", lw=0.9, ls="--")
    axB.set_xticks(xs)
    axB.set_xticklabels(["dry\n(reference)", "mild\n(0.49 s / 80 ms)",
                         "severe\n(1.03 s / 250 ms)"], fontsize=9.5)
    axB.set_ylabel("ΔSDR  (dB)", fontsize=10)
    axB.set_xlabel("input degradation level", fontsize=10)
    axB.set_title("B. Degradation is monotone for every model", fontsize=11.5)
    axB.legend(fontsize=9, loc="lower left")
    axB.set_ylim(-20, 3)
    axB.text(0.5, -0.30, "severe echo dSDR (-4.8) is only 36% of severe reverb dSDR (-13.5)",
             transform=axB.transAxes, ha="center", fontsize=8.5, color="#8b949e")

    # ---------------- C. 去混响负结果 ----------------
    axC = fig.add_subplot(gs[1, 0])
    wet_loss_lo, wet_loss_hi = -13.3, -10.4
    axC.set_xlim(-16, 2)
    axC.set_ylim(-0.85, 2.35)
    axC.set_yticks([1.15, 0.65])
    axC.set_yticklabels(["anvuew\n(Mel-RoFormer)", "Dereverb-Echo\n(2-stem)"], fontsize=9.5)
    # 湿信号被 RIR 打掉的量（灰底 = 待回收的损失区间）
    axC.barh([1.15], wet_loss_hi - wet_loss_lo, 0.36, left=wet_loss_lo,
             color="#c9d1d9", edgecolor="#8b949e",
             label="reverb loss to recover  (%.1f..%.1f dB)" % (wet_loss_lo, wet_loss_hi))
    axC.barh([1.15], 1.46 - 0.04, 0.36, left=0.04, color="#3fb950",
             label="anvuew actually recovers  (+0.04..+1.46 dB, 3-11%)")
    axC.barh([0.65], 13.0, 0.36, left=-13.0, color="#c9d1d9", edgecolor="#8b949e")
    axC.barh([0.65], 0.45, 0.36, left=-0.45, color="#f85149",
             label="Dereverb-Echo: dry branch silent (rms 1e-5..2e-3)")
    axC.text(-6.5, 1.15, "recovers only 3-11% of the loss", ha="center", fontsize=9,
             color="#24292f")
    axC.text(-6.5, 0.65, "unusable: dry branch collapses to silence", ha="center",
             fontsize=9, color="#24292f")
    axC.axvline(0, color="#8b949e", lw=0.9)
    axC.set_xlabel("SI-SDR gain vs reverberant input  (dB)", fontsize=10)
    axC.set_title("C. Community dereverb checkpoints: NEGATIVE result", fontsize=11.5)
    axC.legend(fontsize=8, loc="lower left", framealpha=0.92)

    # ---------------- D. 结论卡 ----------------
    axD = fig.add_subplot(gs[1, 1])
    axD.axis("off")
    axD.set_xlim(0, 1)
    axD.set_ylim(0, 1)
    lines = [
        ("KEY FINDINGS  (T4.1 - T4.6)", 12.5, "#24292f", 0.955),
        ("1. Pure reverberation alone sends separation negative:", 10.5, "#f85149", 0.845),
        ("    avg4 SDR falls to -6..-9 dB (dry was +3.8..+7.5),", 9.5, "#57606a", 0.795),
        ("    dSDR = -10.7..-15.7 dB, monotone in T60.", 9.5, "#57606a", 0.745),
        ("2. Reverb is ~2.5x more destructive than echo:", 10.5, "#d29922", 0.655),
        ("    echo dSDR = -2.3..-6.0 dB; same monotone pattern.", 9.5, "#57606a", 0.605),
        ("3. Both are shared weaknesses of ALL models:", 10.5, "#3fb950", 0.515),
        ("    strongest dry models (oBSRNN/MDX/Demucs) lose the", 9.5, "#57606a", 0.465),
        ("    most (-14.5..-15.7 dB), weakest loses least.", 9.5, "#57606a", 0.415),
        ("4. Dereverb = negative result (verified):", 10.5, "#8957e5", 0.325),
        ("    anvuew recovers only 3-11%; Dereverb-Echo unusable.", 9.5, "#57606a", 0.275),
        ("    Cross-checked against upstream chunked inference", 9.5, "#57606a", 0.225),
        ("    (delta = 0.142 dB) -> not our loader's fault.", 9.5, "#57606a", 0.175),
    ]
    for txt, sz, col, yy in lines:
        axD.text(0.015, yy, txt, fontsize=sz, color=col, va="top",
                 fontweight="bold" if sz > 10 else "normal")
    box = FancyBboxPatch((0.0, 0.03), 1.0, 0.95, boxstyle="round,pad=0.02",
                         linewidth=1.2, edgecolor="#8b949e", facecolor="#f6f8fa")
    axD.add_patch(box)
    axD.text(0.5, 0.075, "metric = museval BSSEval v4 SDR (mono, 2 s/1.5 s window); "
                         "ref = dry GT stems; avg4 = mean of 4 stems, median of 3 clips",
             ha="center", fontsize=7.8, color="#57606a")

    fig.suptitle("Stage 4 summary:  how acoustic degradation breaks music source separation",
                 fontsize=14.5, y=0.965)
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(FIG))

    out = {
        "task": "T4.7 阶段 4 小结",
        "figure": str(FIG),
        "reverb": {"t60_small": t60["small_0p6"], "t60_hall": t60["hall_1p2"],
                   "delta_small_by_model": {m: Sr[m]["d_wet_small"] for m in ORDER},
                   "delta_hall_by_model": {m: Sr[m]["d_wet_hall"] for m in ORDER},
                   "mean_curve": rev_curve},
        "echo": {"delta_short_by_model": {m: Se[m]["d_echo_short"] for m in ORDER},
                 "delta_long_by_model": {m: Se[m]["d_echo_long"] for m in ORDER},
                 "mean_curve": ech_curve},
        "dereverb": {"anvuew_gain_median": 0.044, "anvuew_gain_max": 1.464,
                     "wet_loss_range_db": [wet_loss_lo, wet_loss_hi],
                     "echo_model_verdict": "unusable (dry branch silent)",
                     "official_cross_check_delta_db": 0.142},
        "verdict": "混响把分离打到负 SDR（Δ -10.7~-15.7 dB，单调）；回声温和（Δ -2.3~-6.0 dB）；"
                   "两个社区去混响 checkpoint 无效（负结果，官方路径交叉验证通过）。",
    }
    (REV / "stage4_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[fig] %s" % FIG)
    print("[json] %s" % (REV / "stage4_summary.json"))
    print("reverb mean curve: %s" % [round(v, 2) for v in rev_curve])
    print("echo   mean curve: %s" % [round(v, 2) for v in ech_curve])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

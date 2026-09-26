"""T5.5 dry/wet 曲线的绘图（读 denoise_drywet.json，不重推理）。

两面板：

  A. 分档的降噪强度扫描（3 个权重 × 3 个 SNR 档）
     横轴 dry（0 = 纯模型输出，1 = 完全直通），纵轴 median ΔSI-SDR。
     看点：`<5dB` 档最优在 dry=0（该降就降），`>=15dB` 档最优右移到 dry≈0.1~0.2
     （几乎无噪可降时，把模型动作稀释掉一点反而更好）。**单一固定强度不可能同时最优。**

  B. ΔPESQ 随强度的变化 —— 三个权重的最优 dry 分化
     看点：dns48/dns64 的 PESQ 峰在 dry=0.1；master64 的峰在 dry=0.0。
     这是「in-domain 权重不需要稀释」的直接证据（独立于 P16 的另一种验证）。

产出：
  figures/fig_denoise_drywet.png
"""
from __future__ import annotations

import csv

import paths as _paths  # noqa: E402

_paths.setup_env()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

DEN = _paths.DENOISER
DATA = DEN / "data"
FIGS = DEN / "figures"

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 140})

BIN_ORDER = ["<5dB", "5-15dB", ">=15dB"]
BIN_COLOR = {"<5dB": "#c9403a", "5-15dB": "#e08700", ">=15dB": "#2f7ed8"}
MODEL_TAG = {"denoiser_dns48": "dns48", "denoiser_dns64": "dns64",
             "denoiser_master64": "master64"}
MODEL_COLOR = {"denoiser_dns48": "#1d4e89", "denoiser_dns64": "#e08700",
               "denoiser_master64": "#2e8b57"}


def load_rows():
    p = DATA / "denoise_drywet.csv"
    if not p.is_file():
        raise SystemExit("[FATAL] 缺 %s，先跑 _denoise_drywet.py" % p)
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(v):
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def curve(rows, model, b, col):
    """返回 (dries, values)，按 dry 升序，跳过 None。"""
    pts = []
    for r in rows:
        if r["model"] != model or r["snr_bin"] != b:
            continue
        v = fnum(r.get(col))
        if v is not None:
            pts.append((float(r["dry"]), v))
    pts.sort()
    return [p[0] for p in pts], [p[1] for p in pts]


def fig_main(rows):
    models = sorted({r["model"] for r in rows})

    fig = plt.figure(figsize=(15.6, 6.6))
    gs = fig.add_gridspec(1, 2, wspace=0.22, left=0.058, right=0.975,
                          top=0.845, bottom=0.135)

    # ================= A. ΔSI-SDR vs dry：3 档 × 3 权重 =================
    axA = fig.add_subplot(gs[0, 0])
    # 三个权重用线型区分，三个档用颜色区分。
    LS = {"denoiser_dns48": "-", "denoiser_dns64": "--", "denoiser_master64": "-."}
    for m in models:
        for b in BIN_ORDER:
            xs, ys = curve(rows, m, b, "si_sdr_improve")
            if not xs:
                continue
            axA.plot(xs, ys, lw=2.1 if m == "denoiser_dns48" else 1.5,
                     ls=LS.get(m, "-"), color=BIN_COLOR[b],
                     alpha=1.0 if m == "denoiser_dns48" else 0.62,
                     marker="o" if m == "denoiser_dns48" else None,
                     ms=4.6, label=None)
    axA.axhline(0, color="#333", lw=1.2, ls=":")
    axA.axvline(0, color="#999", lw=1.0, ls="--")

    # 标出 dns48（粗线）三档的最优点，并给出「右移量」的直观提示
    for b in BIN_ORDER:
        xs, ys = curve(rows, "denoiser_dns48", b, "si_sdr_improve")
        if not xs:
            continue
        i = int(np.argmax(ys))
        axA.scatter([xs[i]], [ys[i]], s=145, facecolors="none",
                    edgecolors=BIN_COLOR[b], linewidths=2.3, zorder=6)
        off = (8, 10) if b != ">=15dB" else (8, -18)
        axA.annotate("optimum dry=%.1f\n(%s)" % (xs[i], b), (xs[i], ys[i]),
                     textcoords="offset points", xytext=off, fontsize=8.4,
                     color=BIN_COLOR[b], fontweight="bold")

    axA.set_xlabel("dry   (0 = pure model output = main table,  1 = full passthrough)",
                   fontsize=10.6)
    axA.set_ylabel("median Delta SI-SDR (dB)", fontsize=11)
    axA.set_title("A. Noise reduction is a TUNABLE knob, and the optimum\n"
                  "shifts right as the input gets cleaner",
                  fontsize=12.2, pad=9)
    axA.set_xlim(-0.03, 1.03)
    axA.set_ylim(-0.9, 16.4)

    # 两个图例：档位（颜色）与权重（线型），分开放在不压数据的角落
    from matplotlib.lines import Line2D
    leg_b = [Line2D([], [], color=BIN_COLOR[b], lw=2.4, marker="o", ms=4.6,
                    label="input SNR %s" % b) for b in BIN_ORDER]
    leg_m = [Line2D([], [], color="#555", lw=1.7, ls=LS[m],
                    label=MODEL_TAG.get(m, m)) for m in models]
    l1 = axA.legend(handles=leg_b, fontsize=8.6, loc="upper right",
                    title="SNR bin (colour)", title_fontsize=8.6,
                    framealpha=0.94, bbox_to_anchor=(1.0, 1.0))
    axA.add_artist(l1)
    axA.legend(handles=leg_m, fontsize=8.4, loc="center right",
               title="weight (line style)", title_fontsize=8.4,
               framealpha=0.94, bbox_to_anchor=(1.0, 0.56))

    # ================= B. ΔPESQ vs dry：峰位分化 =================
    axB = fig.add_subplot(gs[0, 1])
    for m in models:
        xs, ys = curve(rows, m, "ALL", "pesq_improve")
        if not xs:
            continue
        col = MODEL_COLOR.get(m, "#333")
        axB.plot(xs, ys, marker="s", lw=2.3, ms=5.4, color=col,
                 label=MODEL_TAG.get(m, m))
        i = int(np.argmax(ys))
        axB.scatter([xs[i]], [ys[i]], s=160, facecolors="none",
                    edgecolors=col, linewidths=2.4, zorder=6)
    axB.axhline(0, color="#333", lw=1.2, ls=":")
    axB.axvline(0, color="#999", lw=1.0, ls="--")
    # 两条竖参考带标出两个峰位；注释放在图内右下空白区（曲线向右下角收敛后留出大片空间）
    axB.axvspan(-0.03, 0.05, color="#2e8b57", alpha=0.11)
    axB.axvspan(0.06, 0.14, color="#c9403a", alpha=0.10)
    axB.annotate("master64 peak  dry=0.0\n(in-domain weight —\ndilution only hurts)",
                 xy=(0.0, 0.99), xytext=(0.24, 0.16),
                 textcoords="data", fontsize=8.4, color="#1f6340",
                 fontweight="bold", ha="left", va="bottom",
                 arrowprops=dict(arrowstyle="->", color="#1f6340", lw=1.2,
                                 shrinkA=2, shrinkB=4))
    axB.annotate("dns48 / dns64 peak  dry=0.1\n(out-of-domain —\na little input back helps)",
                 xy=(0.1, 0.74), xytext=(0.36, 0.44),
                 textcoords="data", fontsize=8.4, color="#8e2b27",
                 fontweight="bold", ha="left", va="bottom",
                 arrowprops=dict(arrowstyle="->", color="#8e2b27", lw=1.2,
                                 shrinkA=2, shrinkB=4))
    axB.set_xlabel("dry   (0 = pure model output = main table,  1 = full passthrough)",
                   fontsize=10.6)
    axB.set_ylabel("median paired Delta PESQ   (ALL clips, n=824)", fontsize=11)
    axB.set_title("B. The PESQ-optimal strength SPLITS by weight:\n"
                  "in-domain master64 peaks at 0.0, the others at 0.1",
                  fontsize=12.2, pad=9)
    axB.legend(fontsize=9.4, loc="upper right", framealpha=0.94)
    axB.set_xlim(-0.03, 1.03)
    axB.set_ylim(-0.02, 1.06)

    fig.suptitle("T5.5  dry/wet sweep — denoiser on valentini 16 kHz (P19-clean)      "
                 "estimate = (1-dry) * denoised + dry * noisy",
                 fontsize=13.4, y=0.962)
    out = FIGS / "fig_denoise_drywet.png"
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s" % out)
    return out


def main():
    rows = load_rows()
    print("[data] %d drywet rows, models=%s" % (len(rows),
                                                sorted({r["model"] for r in rows})))
    print("\n-- optimum dry per (model, metric, bin) --")
    print("%-20s %-8s %-9s %-9s" % ("model", "bin", "opt dSI-SDR", "opt dPESQ"))
    for m in sorted({r["model"] for r in rows}):
        for b in BIN_ORDER + ["ALL"]:
            xs, ys = curve(rows, m, b, "si_sdr_improve")
            xp, yp = curve(rows, m, b, "pesq_improve")
            a = xs[int(np.argmax(ys))] if xs else float("nan")
            p = xp[int(np.argmax(yp))] if xp else float("nan")
            print("%-20s %-8s %-9.1f %-9.1f" % (m, b, a, p))
    fig_main(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

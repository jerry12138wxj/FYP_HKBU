"""T6.3 级联 ΔSDR 图组（读 cascade_eval.csv，不重推理）。

两图：

  fig_cascade_delta_matrix.png
      A. 主矩阵：4 个 SNR 档各一块热图，行=分离模型，列=链路
         （L1 前置降噪 / L1b 仅带宽代价 / L1m mel 前置 / L2 后置降噪 /
           L2b 后置限带 / L3 前置+后置）。颜色 = ΔSDR（相对 L0，同为带噪输入）。
         发散色标以 0 为中心 —— 变差就是变差，不挑数据（R12 / P7）。

      B. 净效应分解：同一模型上 L1（全代价+动作）、L1b（纯代价）、
         L1−L1b（降噪净动作）三者并排，按 SNR 分档。
         这是本实验唯一能把「降噪是否有用」从「前置管线总共值多少」里
         分离出来的对照（P19 的对照纪律）。

  fig_cascade_by_snr.png
      ΔSDR 随输入 SNR 的变化（每个模型一条线，每链路一子图）。

产出：
  figures/fig_cascade_delta_matrix.png
  figures/fig_cascade_by_snr.png
"""
from __future__ import annotations

import csv

import paths as _paths  # noqa: E402

_paths.setup_env()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402

ROOT = _paths.PROJECT_ROOT
DATA = ROOT / "04_reports" / "03_cascade" / "data"
FIGS = ROOT / "04_reports" / "03_cascade" / "figures"
CSV = DATA / "cascade_eval.csv"

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 140})

# 链路顺序与显示名
LINKS = ["L1", "L1b", "L1m", "L2", "L2b", "L3"]
LINK_TITLE = {
    "L1": "L1\nfront denoiser",
    "L1b": "L1b\nbandwidth only\n(control)",
    "L1m": "L1m\nfront mel\n(control)",
    "L2": "L2\npost denoiser",
    "L2b": "L2b\npost bandlimit\n(control)",
    "L3": "L3\nfront + post",
}
MODEL_ORDER = ["demucs", "mdx", "bsrnn_all", "umx"]


def load_rows():
    if not CSV.is_file():
        raise SystemExit("[FATAL] 缺 %s —— 先跑 _cascade_experiment.py summary" % CSV)
    with CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(v):
    if v in (None, "", "None"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _matrix(rows, snr):
    sub = [r for r in rows if float(r["snr_db"]) == snr]
    sub = sorted(sub, key=lambda r: MODEL_ORDER.index(r["model"])
                 if r["model"] in MODEL_ORDER else 99)
    models = [r["model"] for r in sub]
    M = np.full((len(sub), len(LINKS)), np.nan)
    for i, r in enumerate(sub):
        for j, lk in enumerate(LINKS):
            v = fnum(r.get("d_%s" % lk))
            if v is not None:
                M[i, j] = v
    return models, sub, M


def fig_matrix(rows):
    snrs = sorted({float(r["snr_db"]) for r in rows}, reverse=True)
    allv = [fnum(r.get("d_%s" % lk)) for r in rows for lk in LINKS]
    allv = [abs(v) for v in allv if v is not None]
    lim = max(allv) * 1.02 if allv else 1.0
    norm = TwoSlopeNorm(vmin=-lim, vcenter=0.0, vmax=lim)

    n = len(snrs)
    fig = plt.figure(figsize=(3.05 * n + 1.9, 5.5))
    gs = fig.add_gridspec(1, n, wspace=0.12, left=0.088, right=0.905,
                          top=0.775, bottom=0.175)

    im = None
    for k, snr in enumerate(snrs):
        models, sub, M = _matrix(rows, snr)
        ax = fig.add_subplot(gs[0, k])
        im = ax.imshow(M, cmap="RdBu_r", norm=norm, aspect="auto")
        ax.set_xticks(range(len(LINKS)))
        ax.set_xticklabels([LINK_TITLE[lk] for lk in LINKS], fontsize=7.6)
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels(models if k == 0 else [], fontsize=9.6)
        ax.set_title("input SNR %+d dB" % int(snr), fontsize=11.2, pad=7)
        ax.grid(False)
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M[i, j]
                if np.isnan(v):
                    ax.text(j, i, "-", ha="center", va="center", fontsize=9,
                            color="#888")
                    continue
                # 深色格子用白字，浅色格子用黑字
                lum = abs(v) / lim if lim else 0.0
                ax.text(j, i, "%+.2f" % v, ha="center", va="center", fontsize=8.6,
                        color=("white" if lum > 0.62 else "#111"),
                        fontweight="bold" if abs(v) >= 1.0 else "normal")

    cax = fig.add_axes([0.918, 0.175, 0.014, 0.60])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("Delta SDR (dB) vs L0  (same noisy input, no denoising)", fontsize=9.2)

    fig.suptitle("T6.3  Cascade experiment — does a speech denoiser help music source separation?\n"
                 "Delta = link SDR - L0 SDR, median over 10 MUSDB test songs (20 s, avg of 4 stems). "
                 "Negative is a result, not an error (R12).",
                 fontsize=12.6, y=0.935)
    out = FIGS / "fig_cascade_delta_matrix.png"
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s" % out)
    return out


def fig_decomposition(rows):
    """L1（全代价+动作）vs L1b（纯带宽代价）vs 净动作 L1-L1b。"""
    snrs = sorted({float(r["snr_db"]) for r in rows}, reverse=True)
    models = sorted({r["model"] for r in rows},
                    key=lambda m: MODEL_ORDER.index(m) if m in MODEL_ORDER else 99)
    fig, axes = plt.subplots(1, len(models), figsize=(3.55 * len(models), 5.3),
                             sharey=True)
    if len(models) == 1:
        axes = [axes]
    x = np.arange(len(snrs))
    w = 0.26
    for ax, mk in zip(axes, models):
        sub = {float(r["snr_db"]): r for r in rows if r["model"] == mk}
        v_l1 = [fnum(sub[s].get("d_L1")) or np.nan for s in snrs]
        v_l1b = [fnum(sub[s].get("d_L1b")) or np.nan for s in snrs]
        v_net = [fnum(sub[s].get("denoise_net_d_L1_minus_L1b")) or np.nan
                 for s in snrs]
        ax.bar(x - w, v_l1, w, color="#1d4e89", label="L1  front denoiser (total)")
        ax.bar(x, v_l1b, w, color="#c9a227",
               label="L1b  bandwidth/mono cost only")
        ax.bar(x + w, v_net, w, color="#2e8b57",
               label="L1 - L1b  = denoiser net action")
        ax.axhline(0, color="#333", lw=1.1)
        ax.set_xticks(x)
        ax.set_xticklabels(["%+d" % int(s) for s in snrs], fontsize=9.4)
        ax.set_xlabel("input SNR (dB)", fontsize=9.8)
        ax.set_title(mk, fontsize=11.4, pad=7)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Delta SDR (dB) vs L0", fontsize=11)
    axes[0].legend(fontsize=8.0, loc="upper left", framealpha=0.94)
    fig.suptitle("T6.3  Separating the denoiser's NET action from the front-end's "
                 "intrinsic bandwidth cost\n"
                 "L1b mirrors the denoiser pipeline (44.1k->16k->mono->44.1k) with the "
                 "network replaced by identity.",
                 fontsize=12.0, y=0.975)
    fig.tight_layout(rect=[0, 0, 1, 0.885])
    out = FIGS / "fig_cascade_decomposition.png"
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s" % out)
    return out


def main():
    rows = load_rows()
    print("[data] %d rows, models=%s, snrs=%s"
          % (len(rows), sorted({r["model"] for r in rows}),
             sorted({r["snr_db"] for r in rows})))
    print("\n%-10s %6s %8s %8s %8s %8s %8s %8s %8s"
          % ("model", "snr", "sdrL0", "dL1", "dL1b", "dL1m", "dL2", "dL3", "net"))
    for r in rows:
        print("%-10s %+6.0f %8s %8s %8s %8s %8s %8s %8s"
              % (r["model"], float(r["snr_db"]), r["sdr_L0"], r["d_L1"],
                 r["d_L1b"], r["d_L1m"], r["d_L2"], r["d_L3"],
                 r["denoise_net_d_L1_minus_L1b"]))
    fig_matrix(rows)
    fig_decomposition(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

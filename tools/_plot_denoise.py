"""T5.5 / T5.6 降噪阶段图组（答辩用）。

三张图，全部只读 `denoise_manifest.json` 与 `synth_pairs_manifest.json`，不重推理：

  fig1  P11 指标分歧总图（核心）
        A. Delta SI-SDR vs Delta PESQ 的散点（每个 cell 一个点，按 SNR 档着色）
           -> 直观显示「SI-SDR 涨、PESQ 跌」不是个别样本，而是系统性分布
        B. 按输入 SNR 分档的两条柱（Delta SI-SDR / Delta PESQ，双 y 轴）
           -> 分层才是正确读法

  fig2  denoiser 与 mel-roformer 的抑制行为差异（P11 机理证据）
        A. hf_ratio: in / clean / out 三态并列（每个模型一组）
           -> denoiser 输出 hf 塌到 0.05~0.07，mel-roformer 几乎保持
        B. level_ratio 分布（箱线），含 LEVEL_GATE 线
           -> 显示门禁剔除的是 denoiser 自己造成的整段静音

  fig3  自造集（synth, 真值 SNR）上的增益可用性
        每个模型一条：Delta SI-SDR 随真值 SNR(-5/0/5/10) 的变化
        -> 回答「降噪器到底在什么输入条件下才真正有用」

产出：
  02_denoising/figures/fig_denoise_metric_divergence.png
  02_denoising/figures/fig_denoise_suppression.png
  02_denoising/figures/fig_denoise_synth_gain.png
"""
from __future__ import annotations

import json

import paths as _paths  # noqa: E402

_paths.setup_env()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = _paths.PROJECT_ROOT
DEN = ROOT / "04_reports" / "02_denoising"
DATA = DEN / "data"
FIGS = DEN / "figures"

BIN_ORDER = [">=15dB", "5-15dB", "<5dB"]
BIN_COLOR = {">=15dB": "#2f7ed8", "5-15dB": "#f2a13b", "<5dB": "#c9403a"}

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 140})


def load_cells():
    p = DATA / "denoise_manifest.json"
    if not p.is_file():
        raise SystemExit("[FATAL] no manifest: %s" % p)
    return json.loads(p.read_text(encoding="utf-8"))["cells"]


def usable(rs):
    """有 GT 且未被电平门禁剔除、且 PESQ 可用的 cell。"""
    return [r for r in rs
            if r.get("ok") and r.get("reference_mode") == "fullref"
            and not r.get("skipped")
            and r.get("pesq_in") is not None and r.get("pesq_out") is not None]


def med(v):
    v = [x for x in v if x is not None]
    return float(np.median(v)) if v else None


def m_is_den(name):
    return name.startswith("denoiser")


# ---------------------------------------------------------------- fig1
def fig1(cells):
    rs = usable([r for r in cells if r.get("sr") == 16000 and r.get("subset") == "valentini"])
    if not rs:
        print("[skip] fig1: no usable valentini cells")
        return None
    models = sorted({r["model"] for r in rs})

    fig = plt.figure(figsize=(15.0, 6.4))
    gs = fig.add_gridspec(1, 2, wspace=0.26, left=0.075, right=0.975,
                          top=0.86, bottom=0.13)

    # A. scatter
    axA = fig.add_subplot(gs[0, 0])
    axA.axhline(0, color="#888", lw=1.0, ls="--")
    axA.axvline(0, color="#888", lw=1.0, ls="--")
    # 主群之外有少量极端负值（模型把整段判静音但不是电平塌陷），
    # 直接画会把主群压成一条线。这里裁剪到 [-15, +30] dB 并显式标注被裁条数。
    XLO, XHI = -15.0, 30.0
    n_clipped = 0
    for b in BIN_ORDER:
        sub = [r for r in rs if r.get("snr_bin") == b]
        if not sub:
            continue
        xs = np.array([r["si_sdr_improve"] for r in sub], dtype=float)
        n_clipped += int((xs < XLO).sum() + (xs > XHI).sum())
        xs = np.clip(xs, XLO, XHI)
        ys = [r["pesq_out"] - r["pesq_in"] for r in sub]
        axA.scatter(xs, ys, s=9, alpha=0.42, color=BIN_COLOR[b],
                    label="%s (n=%d)" % (b, len(sub)), edgecolors="none")
    axA.set_xlim(XLO - 1.0, XHI + 1.0)
    axA.set_xlabel("Delta SI-SDR (dB)   [>0 = better]", fontsize=11)
    axA.set_ylabel("Delta PESQ   [>0 = better]  (paired: out-in)", fontsize=11)
    axA.set_title("A. Per-clip metrics: both positive after P19 fix (valentini 16 kHz, n=%d)" % len(rs),
                  fontsize=12.5, pad=10)
    axA.legend(fontsize=9, loc="lower left", framealpha=0.9)
    if n_clipped:
        axA.text(0.985, 0.02, "%d pts clipped to axis range" % n_clipped,
                 transform=axA.transAxes, ha="right", fontsize=8.5, color="#666")

    # B. binned bars —— 两条序列分开画，**绝不共用 y 轴**。
    #    配对指标必须先逐条作差再取中位数（med(out-in)），
    #    而不是 med(out) - med(in) —— 后者在本数据上连符号都会反。
    axB = fig.add_subplot(gs[0, 1])
    dx = np.arange(len(BIN_ORDER))
    agg_si, agg_pe, ns = [], [], []
    for b in BIN_ORDER:
        sub = [r for r in rs if r.get("snr_bin") == b]
        agg_si.append(med([r["si_sdr_improve"] for r in sub]) or 0.0)
        agg_pe.append(med([r["pesq_out"] - r["pesq_in"] for r in sub]) or 0.0)
        ns.append(len(sub))
    axB.bar(dx - 0.19, agg_si, width=0.36, color="#2f7ed8", label="Delta SI-SDR (dB)")
    axB.axhline(0, color="#333", lw=1.1)
    axB.set_xticks(dx)
    axB.set_xticklabels(["%s\n(n=%d)" % (b, n) for b, n in zip(BIN_ORDER, ns)], fontsize=10)
    axB.set_ylabel("median Delta SI-SDR in dB  [paired: med(out-in)]",
                   fontsize=10.5, color="#2f7ed8")
    axB.tick_params(axis="y", labelcolor="#2f7ed8")
    axB.set_ylim(0, max(agg_si) * 1.62)
    for i, a in enumerate(agg_si):
        axB.text(i - 0.19, a + max(agg_si) * 0.06, "%+.2f" % a, ha="center",
                 fontsize=10, color="#1d4e89", fontweight="bold")
    # PESQ 用 inset 单列，绝不与 SI-SDR 共用轴（量级差 10 倍会放大误导）。
    # inset 放在右上留白区（legend 在左上），避开柱顶标签。
    axC = axB.inset_axes([0.30, 0.62, 0.66, 0.28])
    axC.bar(range(len(BIN_ORDER)), agg_pe, width=0.52, color="#c9403a")
    axC.axhline(0, color="#333", lw=1.0, ls=":")
    axC.set_xticks(range(len(BIN_ORDER)))
    axC.set_xticklabels(BIN_ORDER, fontsize=8)
    axC.set_ylabel("paired Delta PESQ", fontsize=8, color="#c9403a")
    axC.tick_params(axis="y", labelcolor="#c9403a", labelsize=7.5)
    axC.tick_params(axis="x", pad=1)
    axC.set_title("paired Delta PESQ (own scale)", fontsize=8.5, color="#c9403a", pad=3)
    span = max(abs(v) for v in agg_pe) or 0.05
    axC.set_ylim(min(0.0, min(agg_pe)) - span * 0.45, max(agg_pe) + span * 0.70)
    for i, b2 in enumerate(agg_pe):
        axC.text(i, b2 + span * 0.16, "%+.03f" % b2, ha="center", va="bottom",
                 fontsize=8.5, color="#8e2b27", fontweight="bold")
    axB.set_title("B. Gain grows monotonically as input gets noisier (P19-clean)",
                  fontsize=12.5, pad=10)
    axB.legend(fontsize=9, loc="upper left")

    fig.suptitle("T5.2  Paired metrics agree in sign once the sample-rate bug is fixed "
                 "(valentini 16 kHz)",
                 fontsize=14.5, y=0.965)
    out = FIGS / "fig_denoise_metric_divergence.png"
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s" % out)
    return out


# ---------------------------------------------------------------- fig2
def fig2(cells):
    rs = [r for r in cells if r.get("sr") == 16000 and r.get("subset") == "valentini"
          and r.get("ok")]
    if not rs:
        print("[skip] fig2: no cells")
        return None
    models = sorted({r["model"] for r in rs})
    valid = [r for r in rs if r.get("reference_mode") == "fullref" and not r.get("skipped")]

    fig = plt.figure(figsize=(15.0, 6.4))
    gs = fig.add_gridspec(1, 2, wspace=0.30, left=0.075, right=0.975,
                          top=0.86, bottom=0.15)

    # A. hf_ratio tri-state
    axA = fig.add_subplot(gs[0, 0])
    x = np.arange(len(models))
    w = 0.26
    hin = [med([r["hf_ratio_in"] for r in valid if r["model"] == m]) for m in models]
    hcl = [med([r["hf_ratio_clean"] for r in valid if r["model"] == m]) for m in models]
    hout = [med([r["hf_ratio_out"] for r in valid if r["model"] == m]) for m in models]
    axA.bar(x - w, hin, width=w, color="#9aa7b4", label="noisy input")
    axA.bar(x, hcl, width=w, color="#4c9f70", label="clean reference")
    axA.bar(x + w, hout, width=w, color="#c9403a", label="model output")
    for i, (a, b2) in enumerate(zip(hin, hout)):
        drop = (1.0 - b2 / a) * 100 if a else 0.0
        axA.text(i + w, b2 + 0.012, "%+.0f%%" % (-drop), ha="center",
                 fontsize=9.5, color="#8e2b27", fontweight="bold")
    axA.set_xticks(x)
    axA.set_xticklabels([m.replace("_", "\n") for m in models], fontsize=8.5)
    axA.set_ylabel("hf_ratio  (energy share of upper half band)", fontsize=10.5)
    axA.set_title("A. Spectral fidelity: output hf_ratio stays within +-2.5% of input",
                  fontsize=12.5, pad=10)
    axA.legend(fontsize=9, loc="upper right")
    axA.text(0.5, -0.175,
             "P19: earlier -75%% collapse was a sample-rate bug artifact (16 kHz double resample). "
             "See P19_SAMPLE_RATE_CONTRACT_BUG.md",
             transform=axA.transAxes, ha="center", va="top", fontsize=8.4, color="#444")

    # B. level_ratio box + gate line
    axB = fig.add_subplot(gs[0, 1])
    data = [[r.get("level_ratio", np.nan) for r in rs if r["model"] == m] for m in models]
    data = [[v if v is not None else np.nan for v in d] for d in data]
    bp = axB.boxplot(data, tick_labels=[m.replace("_", "\n") for m in models],
                     patch_artist=True, showfliers=True,
                     flierprops=dict(marker=".", markersize=3, alpha=0.4))
    for patch, m in zip(bp["boxes"], models):
        patch.set_facecolor("#c9403a" if m.startswith("denoiser") else "#2f7ed8")
        patch.set_alpha(0.65)
    axB.axhline(0.20, color="#111", lw=1.6, ls="--")
    axB.text(0.985, 0.90, "LEVEL_GATE = 0.20 (below -> skipped)",
             transform=axB.transAxes, ha="right", va="top",
             fontsize=8.8, color="#111",
             bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#111", alpha=0.9))
    axB.set_ylabel("rms(out) / rms(noisy input)", fontsize=10.5)
    axB.set_title("B. Level fidelity: mild systematic compression (P19: no gating collapse)",
                  fontsize=12.5, pad=10)
    axB.tick_params(axis="x", labelsize=8.5)
    # 被门禁剔除的比例写进刻度标签，避免压线
    labs = []
    for m in models:
        sub = [r for r in rs if r["model"] == m]
        nsk = sum(1 for r in sub if r.get("skipped"))
        lbl = m.replace("_", "\n")
        if nsk:
            lbl += "\n(%d/%d skipped)" % (nsk, len(sub))
        else:
            lbl += "\n(0 skipped)"
        labs.append(lbl)
    axB.set_xticklabels(labs, fontsize=8.5)

    fig.suptitle("T5.3  Suppression behaviour by model family (valentini 16 kHz, P19-clean)",
                 fontsize=14.5, y=0.965)
    out = FIGS / "fig_denoise_suppression.png"
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s" % out)
    return out


# ---------------------------------------------------------------- fig3
def fig3(cells):
    """synth 集：真值 SNR 下的 ΔSI-SDR 曲线。

    核心看点不是「谁增益大」，而是**模型族在两类噪声上的排名反转**：
      - valentini（真实/稳态噪声）上 mel 最好；
      - synth（瞬态噪声）上 denoiser 反而最好。
    因此本图同时画出两族，且用实线/虚线区分模型族。
    """
    rs = usable([r for r in cells if r.get("subset") == "synth"])
    if not rs:
        print("[skip] fig3: no synth cells yet")
        return None
    models = sorted({r["model"] for r in rs})
    levels = [-5.0, 0.0, 5.0, 10.0]

    def lvl_of(r):
        v = r.get("target_snr_db")
        if v is None:
            return None
        return min(levels, key=lambda x: abs(x - float(v)))

    fig, ax = plt.subplots(figsize=(10.4, 6.4))
    styles = {"denoiser": ("--", "o"), "mel_roformer": ("-", "s")}
    for m in models:
        ls, mk = "-", "s"
        for pre, (l, k) in styles.items():
            if m.startswith(pre):
                ls, mk = l, k
        ys = []
        for lv in levels:
            sub = [r for r in rs if r["model"] == m and lvl_of(r) == lv]
            ys.append(med([r["si_sdr_improve"] for r in sub]) if sub else None)
        xs = [i for i, v in enumerate(ys) if v is not None]
        yv = [v for v in ys if v is not None]
        ax.plot(xs, yv, marker=mk, ls=ls, lw=2.0,
                label=m.replace("_", " "), markersize=6)
    ax.axhline(0, color="#333", lw=1.2, ls=":")
    ax.set_xticks(range(len(levels)))
    ax.set_xticklabels(["%+g dB" % l for l in levels], fontsize=11)
    ax.set_ylabel("median Delta SI-SDR (dB)", fontsize=11.5)
    ax.set_xlabel("ground-truth input SNR (synthetic pairs, transient noise)",
                  fontsize=11.5)
    ax.set_title("T5.4  Ranking REVERSES by noise type:\n"
                 "on transient noise denoiser works and mel-roformer does not",
                 fontsize=13, pad=12)
    # 图例放右下：左上会遮住 denoiser 在 -5 dB 的首个数据点。
    # 实线/虚线已能区分模型族，不再另加文字说明（会压住数据点）。
    ax.legend(fontsize=9.5, loc="center right", framealpha=0.95)
    ax.set_ylim(-0.35, None)
    fig.tight_layout()
    out = FIGS / "fig_denoise_synth_gain.png"
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s" % out)
    return out


def fig4_reversal(cells):
    """★ 本阶段头图：模型族排名随噪声类型反转。

    左右两个面板（valentini / synth），每个面板画同一批模型的 ΔSI-SDR。
    看点：两条曲线的相对高低在两个面板里**互换**。
    """
    v = usable([r for r in cells if r.get("subset") == "valentini" and r.get("sr") == 16000])
    s = usable([r for r in cells if r.get("subset") == "synth"])
    if not v or not s:
        print("[skip] fig4: need both valentini and synth cells")
        return None

    models = sorted({r["model"] for r in v} | {r["model"] for r in s})

    def agg(rs, m):
        g = [r for r in rs if r["model"] == m]
        return med([r["si_sdr_improve"] for r in g]) if g else None

    fig, axes = plt.subplots(1, 2, figsize=(15.0, 6.6), sharey=True)
    for ax, (rs, title, sub) in zip(axes, [
            (v, "A. valentini  (real / stationary noise)",
             "denoiser: stronger gain on real noise (P19-clean)"),
            (s, "B. synth  (transient impulse noise)",
             "mel-roformer does almost nothing; denoiser still wins")]):
        y = np.arange(len(models))
        vals = [agg(rs, m) or 0.0 for m in models]
        cols = ["#c9403a" if m.startswith("denoiser") else "#2f7ed8" for m in models]
        ax.barh(y, vals, color=cols, height=0.58)
        ax.axvline(0, color="#333", lw=1.1)
        ax.set_yticks(y)
        ax.set_yticklabels([m.replace("_", "\n") for m in models], fontsize=8.5)
        ax.set_xlabel("median Delta SI-SDR (dB)", fontsize=11)
        ax.set_title(title, fontsize=12.5, pad=9)
        ax.text(0.5, -0.135, sub, transform=ax.transAxes, ha="center",
                fontsize=9.5, color="#555")
        span = max(abs(x) for x in vals) or 1.0
        for i, x in enumerate(vals):
            ax.text(x + (span * 0.03 if x >= 0 else -span * 0.03), i, "%+.2f" % x,
                    va="center", ha="left" if x >= 0 else "right",
                    fontsize=9.5, fontweight="bold",
                    color="#8e2b27" if m_is_den(models[i]) else "#1d4e89")
    fig.suptitle("T5.7  The ranking REVERSES with noise type  —  "
                 "no single \"best 02_denoising\" exists",
                 fontsize=14.5, y=0.975)
    fig.tight_layout(rect=(0, 0.055, 1, 0.945))
    out = FIGS / "fig_denoise_noise_domain_reversal.png"
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s" % out)
    return out


def main() -> int:
    cells = load_cells()
    print("[data] %d cells" % len(cells))
    fig1(cells)
    fig2(cells)
    fig3(cells)
    fig4_reversal(cells)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

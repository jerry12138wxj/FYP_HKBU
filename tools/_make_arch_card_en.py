# -*- coding: utf-8 -*-
"""Architecture comparison card (English) for the DMC progress report.

One figure that replaces three separate architecture explainers, keeping the
per-chapter figure budget at three.  It is deliberately a *card*: the concept
flow on the left of each column is written from the source paper, and the
right-hand cost strip is read from model_profile.csv at run time so no number
is typed in by hand.

Writes: 04_reports/00_shared/figures/progress_report/pr_fig_arch_compare_en.png
Run   : python tools/_make_arch_card_en.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["savefig.dpi"] = 300
plt.rcParams["figure.dpi"] = 300

OUT = _paths.REPORTS / "00_shared" / "figures" / "progress_report"
PROFILE = _paths.MODEL_ANALYSIS / "model_profile.csv"

INK = "#111827"
MUTED = "#6b7280"
HEAD = "#1F3A66"

# ---------------------------------------------------------------- inputs
MODELS = [
    {
        "key": "demucs",
        "name": "Demucs v4  (HTDemucs)",
        "task": "4-stem separation · 44.1 kHz stereo",
        "flow": [
            ("Input", "Stereo mixture, 44.1 kHz"),
            ("Time branch", "1-D U-Net encoder / decoder\nover the raw waveform"),
            ("Spectral branch", "2-D U-Net over the\ncomplex spectrogram"),
            ("Cross-domain", "Transformer layers exchange\ninformation between the two"),
            ("Output", "Four stems: vocals, drums,\nbass, other"),
        ],
        "note": "Hybrid time/spectral Transformer.\n"
                "Couples two U-Nets through\ntransformer bottleneck.",
    },
    {
        "key": "bsrnn_all",
        "name": "BSRNN  (oBSRNN, 4 checkpoints)",
        "task": "4-stem separation · 44.1 kHz stereo",
        "flow": [
            ("Input", "Stereo mixture, 44.1 kHz"),
            ("Band split", "Spectrogram divided into\nnon-overlapping sub-bands"),
            ("Intra-band", "Per-band bidirectional RNNa\nmodels the time axis"),
            ("Inter-band", "Second RNN models the\nfrequency axis across bands"),
            ("Output", "Four stems via per-band\nmask estimation"),
        ],
        "note": "Fully spectral, band-split RNN.\n"
                "Highest measured separation\nquality of the benchmark.",
        "caveat": "Four checkpoints are run in sequence\n(one per stem), so cost is summed.",
    },
    {
        "key": "denoiser_master64",
        "name": "denoiser  (master64)",
        "task": "Noise cancellation · 16 kHz mono",
        "flow": [
            ("Input", "Noisy speech, 16 kHz mono"),
            ("Encoder", "1-D convolutions downsample\nthe waveform"),
            ("Bottleneck", "Two LSTM layers model\nthe temporal context"),
            ("Skip links", "Encoder features injected\ndirectly into the decoder"),
            ("Output", "Clean speech waveform\n(same rate and length)"),
        ],
        "note": "Causal waveform-domain\nencoder–decoder.\n"
                "Trained on DNS + Valentini.",
        "caveat": "Causal design is what allows\nreal-time operation.",
    },
]

# ---------------------------------------------------------------- helpers
def _load_profile():
    out = {}
    with open(PROFILE, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[r["model_key"]] = r
    return out


def _f(v, nd=1, suffix=""):
    try:
        return f"{float(v):,.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def draw_column(ax, m, prof):
    """Draw one model column: title, concept flow, cost strip."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ---- title block
    ax.add_patch(FancyBboxPatch((0.0, 0.905), 1.0, 0.095,
                                boxstyle="round,pad=0.004,rounding_size=0.012",
                                fc=HEAD, ec="none", transform=ax.transAxes))
    ax.text(0.5, 0.966, m["name"], ha="center", va="center", fontsize=11.2,
            fontweight="bold", color="white", transform=ax.transAxes)
    ax.text(0.5, 0.927, m["task"], ha="center", va="center", fontsize=8.2,
            color="#D6E0F0", transform=ax.transAxes)

    # ---- concept flow
    n = len(m["flow"])
    top, bottom = 0.875, 0.395
    step = (top - bottom) / n
    bh = step * 0.70
    for i, (head, body) in enumerate(m["flow"]):
        y = top - (i + 1) * step + (step - bh) / 2
        ax.add_patch(FancyBboxPatch((0.045, y), 0.91, bh,
                                    boxstyle="round,pad=0.004,rounding_size=0.012",
                                    fc="#F1F5FB", ec="#9FB3D1", lw=0.9,
                                    transform=ax.transAxes))
        ax.text(0.075, y + bh * 0.66, head, ha="left", va="center", fontsize=8.4,
                fontweight="bold", color=HEAD, transform=ax.transAxes)
        ax.text(0.075, y + bh * 0.27, body, ha="left", va="center", fontsize=7.5,
                color=INK, transform=ax.transAxes, linespacing=1.35)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((0.5, y), (0.5, y - (step - bh)),
                                         arrowstyle="-|>", mutation_scale=9,
                                         color="#7C93B4", lw=1.0,
                                         transform=ax.transAxes))

    # ---- note
    ax.text(0.5, 0.300, m["note"], ha="center", va="top", fontsize=7.8,
            color=INK, transform=ax.transAxes, linespacing=1.45,
            style="italic")
    if m.get("caveat"):
        ax.text(0.5, 0.207, m["caveat"], ha="center", va="top", fontsize=7.2,
                color=MUTED, transform=ax.transAxes, linespacing=1.4)

    # ---- cost strip (read from profile.csv, never typed)
    r = prof.get(m["key"], {})
    rows = [
        ("Parameters", _f(r.get("params_M"), 1, " M")),
        ("FLOPs", _f((float(r.get("macs_G") or 0) * 2 / 1000) if r.get("macs_G") else None, 2, " T")),
        ("Peak VRAM", _f(r.get("peak_vram_mb"), 1, " MB")),
        ("Latency", _f(r.get("latency_s"), 4, " s")),
    ]
    y0 = 0.132
    ax.add_patch(FancyBboxPatch((0.045, y0 - 0.128), 0.91, 0.158,
                                boxstyle="round,pad=0.004,rounding_size=0.012",
                                fc="#FAFAF7", ec="#CFCFCF", lw=0.9,
                                transform=ax.transAxes))
    for j, (k, v) in enumerate(rows):
        x = 0.075 + j * 0.2225
        ax.text(x, y0 + 0.005, k, ha="left", va="center", fontsize=7.0,
                color=MUTED, transform=ax.transAxes)
        ax.text(x, y0 - 0.058, v, ha="left", va="center", fontsize=9.0,
                fontweight="bold", color=INK, transform=ax.transAxes)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    prof = _load_profile()

    fig = plt.figure(figsize=(13.8, 9.2))
    gs = fig.add_gridspec(1, 3, wspace=0.075, left=0.022, right=0.978,
                          top=0.905, bottom=0.055)
    for i, m in enumerate(MODELS):
        draw_column(fig.add_subplot(gs[0, i]), m, prof)

    fig.suptitle("Architecture of the three candidate models\n"
                 "concept flow from the source papers; cost strip measured locally on one 10 s input",
                 fontsize=13.0, fontweight="bold", color=INK, y=0.965)
    fig.text(0.5, 0.018,
             "FLOPs follow the same convention as the main table (2 × MACs, lower bound: STFT and fused attention "
             "are not counted by the counter).\n"
             "The BSRNN cost strip sums four checkpoints because the four-stem configuration runs them in sequence.",
             ha="center", fontsize=7.8, color=MUTED, linespacing=1.5)

    p = OUT / "pr_fig_arch_compare_en.png"
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {p}  ({p.stat().st_size/1024:.0f} KB)")
    print("[status] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

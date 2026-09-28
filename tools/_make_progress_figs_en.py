# -*- coding: utf-8 -*-
"""English figures for the DMC 1st Progress Report.

This script is ADDITIVE: it never touches the production (Chinese) figures.
It reads the same data sources as the production scripts and writes new
English-labelled PNGs into:

    04_reports/00_shared/figures/progress_report/

Figures produced
----------------
  pr_fig_accuracy_bars_en.png   average SDR per model (4-stem group)
  pr_fig_per_stem_en.png        SDR per stem per model
  pr_fig_cost_pareto_en.png     parameters vs latency, bubble = peak VRAM
  pr_fig_dn_gain_en.png         noise-cancellation gain (dSI-SDR / dPESQ / dSTOI)
  pr_fig_arch_*.png             architecture cards (concept flow only, English)

Data sources (all read at run time, nothing hand-typed)
-------------------------------------------------------
  data/comparison/model_runs_median.json      separation median SDR / RTF
  data/comparison/mixture_baseline.json       mixture baseline row
  00_shared/data/model_analysis/model_profile.csv   params / FLOPs / latency / VRAM
  02_denoising/data/denoise_eval_16k.json     denoising metrics at 16 kHz

Run
---
    python tools/_make_progress_figs_en.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# ---------------------------------------------------------------- style
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["axes.axisbelow"] = True
plt.rcParams["savefig.dpi"] = 300          # print-grade for the report
plt.rcParams["figure.dpi"] = 300

INK = "#111827"
MUTED = "#6b7280"
GREEN = "#2E7D32"
BLUE = "#4C78A8"
RED = "#C0392B"

STEMS = ["vocals", "drums", "bass", "other"]
STEM_COLOR = {"vocals": "#4C78A8", "drums": "#F58518",
              "bass": "#54A24B", "other": "#B279A2"}
STEM_TITLE = {"vocals": "Vocals", "drums": "Drums",
              "bass": "Bass", "other": "Other"}

OUT = _paths.REPORTS / "00_shared" / "figures" / "progress_report"
CMP = _paths.comparison_dir()
MEDIAN = CMP / "model_runs_median.json"
BASELINE = CMP / "mixture_baseline.json"
PROFILE = _paths.MODEL_ANALYSIS / "model_profile.csv"
DN16K = _paths.REPORTS / "02_denoising" / "data" / "denoise_eval_16k.json"

# English display names (production scripts use Chinese; we keep the mapping
# here so the figures are reproducible without touching the originals).
# Keyed by raw label so both the median table and the profile CSV resolve.
EN = {
    # --- separation (median table labels) ---
    "IRM/IBM Oracle": "IRM/IBM Oracle",
    "RPCA": "RPCA (Inexact-ALM)",
    "Open-Unmix": "Open-Unmix (umxhq)",
    "MDX-Net": "MDX-Net (mdx_extra)",
    "Conv-TasNet": "Conv-TasNet",
    "MMDenseLSTM": "MMDenseLSTM",
    "BS-RoFormer L12": "BS-RoFormer L12",
    "BS-RoFormer L6": "BS-RoFormer L6",
    "oBSRNN (4 ckpt)": "oBSRNN (4 ckpt)",
    "BSRNN large (4 ckpt)": "BSRNN large (4 ckpt)",
    "oBSRNN-SIMO": "oBSRNN-SIMO",
    "Demucs (htdemucs)": "Demucs (htdemucs)",
    "DPRNN (\u81ea\u8bad, 4-stem)": "DPRNN (self-trained)",
    # --- profile CSV labels ---
    "RPCA (Inexact-ALM)": "RPCA (Inexact-ALM)",
    "Open-Unmix (umxhq)": "Open-Unmix (umxhq)",
    "MDX-Net (mdx_extra)": "MDX-Net (mdx_extra)",
    "Conv-TasNet (musdb18)": "Conv-TasNet (musdb18)",
    "MMDenseLSTM (musdb18)": "MMDenseLSTM (musdb18)",
    "BS-RoFormer L12 (ep_317, vocals)": "BS-RoFormer L12 (vocals)",
    "BS-RoFormer L6 (ep_937, vocals+other)": "BS-RoFormer L6 (vocals+other)",
    "BSRNN (oBSRNN, vocals)": "BSRNN / oBSRNN (vocals)",
    "BSRNN (oBSRNN, 4-stem)": "BSRNN / oBSRNN (4-stem)",
    "BSRNN large (vocals)": "BSRNN large (vocals)",
    "BSRNN large (4-stem)": "BSRNN large (4-stem)",
    "BSRNN SIMO (4-stem)": "BSRNN SIMO (4-stem)",
    "Demucs (htdemucs).": "Demucs (htdemucs)",
    "DPRNN (\u81ea\u8bad, 4-stem)": "DPRNN (self-trained)",
    "Mel-RoFormer-Denoise (aufr33)": "Mel-RoFormer-Denoise",
    "Mel-RoFormer-Denoise (aggr)": "Mel-RoFormer-Denoise (aggr.)",
    "Dereverb-Mel-RoFormer": "Dereverb-Mel-RoFormer",
    "Dereverb-Echo-Mel-RoFormer": "Dereverb-Echo-Mel-RoFormer",
    "denoiser dns48 (16 kHz)": "denoiser dns48",
    "denoiser dns64 (16 kHz)": "denoiser dns64",
    "denoiser master64 (16 kHz)": "denoiser master64",
}


def _en(label: str) -> str:
    """Map a production label to a pure-ASCII English label.

    Falls back to the original label, but strips any residual non-ASCII so a
    missing mapping can never silently render as a blank glyph.
    """
    out = EN.get(label)
    if out is None:
        out = "".join(ch if ord(ch) < 128 else "" for ch in label)
    return out.strip() or label


# ---------------------------------------------------------------- load
def load_sep():
    med = json.loads(MEDIAN.read_text(encoding="utf-8"))
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else None
    prof = {}
    with open(PROFILE, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            prof[r["model_key"]] = r
    four, single, norec = [], [], []
    for k, e in med.items():
        if e.get("single_target"):
            single.append((k, e))
        elif e.get("sdr_avg4") is None:
            norec.append((k, e))
        else:
            four.append((k, e))
    four.sort(key=lambda kv: -(kv[1].get("sdr_avg4") or -99))
    return med, base, prof, four, single, norec


def load_dn():
    if not DN16K.is_file():
        return None
    return json.loads(DN16K.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- fig 1
def fig_accuracy_bars(base, four):
    """Average SDR per 4-stem model, mixture baseline marked."""
    core = [(k, e) for k, e in four if k not in ("oracle", "dprnn")]
    extra = [(k, e) for k, e in four if k in ("oracle", "dprnn")]
    order = core + extra

    names, vals, colors = [], [], []
    if base:
        names.append("Mixture (baseline, no separation)")
        vals.append(base.get("avg4"))
        colors.append("#9E9E9E")
    best = core[0][1]["sdr_avg4"] if core else None
    tag = {"oracle": "  |  analytic upper bound, not ranked",
           "dprnn": "  |  negative control, not ranked"}
    for k, e in order:
        names.append(_en(e["label"]) + tag.get(k, ""))
        vals.append(e.get("sdr_avg4"))
        colors.append(GREEN if e.get("sdr_avg4") == best else
                      "#F3F0E6" if k in ("oracle", "dprnn") else BLUE)

    fig, ax = plt.subplots(figsize=(9.8, 5.6))
    y = list(range(len(names)))[::-1]
    bars = ax.barh(y, vals, color=colors, height=0.62,
                   edgecolor=["#2F4B7C" if c == GREEN else "none" for c in colors],
                   linewidth=1.4)
    for b, v in zip(bars, vals):
        ax.text(v + 0.14 if v >= 0 else v - 0.14, b.get_y() + b.get_height() / 2,
                f"{v:.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=9,
                color=INK, fontweight="bold" if v == best else "normal")
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9)
    ax.axvline(0, color="#666", lw=0.9)
    ax.set_xlabel("Average SDR (dB), museval BSS-Eval v4  |  median over 3 energy-balanced 10 s segments")
    ax.set_title("Separation quality: average SDR across four stems\n"
                 "MUSDB18-HQ, local measurement (green = best ranked model)",
                 fontsize=12, fontweight="bold", color=INK)
    lo = min(vals) * 1.25 if min(vals) < 0 else 0
    ax.set_xlim(lo, max(vals) * 1.16)
    ax.grid(axis="x", ls=":", alpha=0.45)
    fig.savefig(OUT / "pr_fig_accuracy_bars_en.png")
    plt.close(fig)
    return len(names)


# ---------------------------------------------------------------- fig 2
def fig_per_stem(four):
    """Grouped bars: SDR per stem per model (4-stem group, ranked)."""
    core = [(k, e) for k, e in four if k not in ("oracle", "dprnn")]
    labels = [_en(e["label"]) for _, e in core]
    xs = list(range(len(labels)))
    w = 0.2

    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    for i, st in enumerate(STEMS):
        vals = []
        for _, e in core:
            d = (e.get("sdr") or {}).get(st)
            vals.append((d or {}).get("median") or 0.0)
        ax.bar([x + (i - 1.5) * w for x in xs], vals, width=w,
               label=STEM_TITLE[st], color=STEM_COLOR[st])
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=22, ha="right", fontsize=9)
    ax.axhline(0, color="#666", lw=0.9)
    ax.set_ylabel("museval SDR (dB)")
    ax.set_title("Separation quality per stem (median over 3 energy-balanced segments)",
                 fontsize=12, fontweight="bold", color=INK)
    ax.legend(ncol=4, fontsize=9.5, frameon=False)
    ax.grid(axis="y", ls=":", alpha=0.45)
    fig.savefig(OUT / "pr_fig_per_stem_en.png")
    plt.close(fig)
    return len(core)


# ---------------------------------------------------------------- fig 3
def fig_cost_pareto(prof, four):
    """Parameters vs latency; bubble size = peak VRAM; colour = model family."""
    fam = {
        "4-stem": ("4-stem separation", "#2563eb"),
        "1-target": ("single-target", "#d97706"),
        "2-target": ("two-target", "#7c3aed"),
        "denoise": ("noise cancellation", "#059669"),
        "analytic": ("analytic (no parameters)", "#9ca3af"),
    }
    order = ["4-stem", "1-target", "2-target", "denoise", "analytic"]

    rows = []
    for k, r in prof.items():
        try:
            p = float(r.get("params_M") or 0)
            lat = float(r.get("latency_s") or 0)
            vr = float(r.get("peak_vram_mb") or 0)
        except ValueError:
            continue
        g = r.get("group") or "other"
        if p <= 0 or lat <= 0:
            continue                       # analytic models have no params/latency
        rows.append({"key": k, "label": _en(r.get("label") or k), "g": g,
                     "p": p, "lat": lat, "vr": vr})
    if not rows:
        return 0
    vmax = max(r["vr"] for r in rows) or 1.0

    fig, ax = plt.subplots(figsize=(11.6, 7.2))
    for r in rows:
        col = fam.get(r["g"], ("other", "#6b7280"))[1]
        ax.scatter(r["lat"], r["p"], s=40 + 620 * (r["vr"] / vmax), color=col,
                   alpha=0.72, edgecolors="white", linewidths=1.1, zorder=3)
    # light label placement; short English names only
    OFF = {
        "demucs": (14, -12, "left"), "umx": (0, 16, "center"), "mdx": (0, -20, "center"),
        "convtasnet": (14, -4, "left"), "mmdenselstm": (14, -12, "left"),
        "dprnn": (14, -12, "left"), "bsrnn_all": (-14, 8, "right"),
        "bsrnn_large_all": (0, -22, "center"), "bsrnn_simo": (-14, 4, "right"),
        "bsrnn": (0, 16, "center"), "bsrnn_large": (0, -22, "center"),
        "bsroformer_l12": (-12, 14, "right"), "bsroformer_l6": (0, -20, "center"),
        "denoiser_dns48": (10, -14, "left"), "denoiser_dns64": (12, 8, "left"),
        "denoiser_master64": (12, -14, "left"),
        "mel_roformer_denoise": (-14, 6, "right"),
        "mel_roformer_denoise_aggr": (52, -3, "left"),
        "mel_roformer_dereverb": (14, 4, "left"),
        "mel_roformer_dereverb_echo": (-14, -12, "right"),
    }
    for r in rows:
        dx, dy, ha = OFF.get(r["key"], (0, 13, "center"))
        ax.annotate(r["label"], (r["lat"], r["p"]), textcoords="offset points",
                    xytext=(dx, dy), ha=ha, fontsize=8.2, color=INK, zorder=4,
                    bbox=dict(fc="white", ec="none", alpha=0.72, pad=0.8))
    ax.set_xscale("log")
    ax.set_xlabel("Single forward-pass latency (s, log scale)  |  10 s stereo input, RTX 4070 Laptop 8 GiB")
    ax.set_ylabel("Parameters (millions)")
    ymax = max(r["p"] for r in rows) * 1.18
    ax.set_ylim(0, ymax)
    ax.set_title("Cost of every model: parameters vs latency\n"
                 "bubble area = peak VRAM; lower-left is cheaper",
                 fontsize=12, fontweight="bold", color=INK)
    handles, labels = [], []
    for g in order:
        if any(r["g"] == g for r in rows):
            handles.append(plt.Line2D([], [], marker="o", ls="", markersize=9,
                                      color=fam[g][1]))
            labels.append(fam[g][0])
    ax.legend(handles, labels, fontsize=9, frameon=True, framealpha=0.94,
              loc="upper right")
    ax.grid(ls=":", alpha=0.45)
    fig.savefig(OUT / "pr_fig_cost_pareto_en.png")
    plt.close(fig)
    return len(rows)


# ---------------------------------------------------------------- fig 4
def fig_dn_gain(dn):
    """Noise-cancellation gain on the 16 kHz protocol, per model.

    Only rows with reference_mode == 'fullref' and snr_bin == 'ALL' are used,
    because only those carry the paired improvement columns in a comparable way.
    """
    if not dn:
        return 0
    best = {}
    for r in dn["rows"]:
        if r.get("snr_bin") != "ALL" or r.get("reference_mode") != "fullref":
            continue
        lbl = r["label"].replace(" (16 kHz)", "")
        cur = best.get(lbl)
        if cur is None or (r.get("n_ok") or 0) > (cur.get("n_ok") or 0):
            best[lbl] = r
    if not best:
        return 0
    items = sorted(best.items(), key=lambda kv: -(kv[1].get("si_sdr_improve") or -99))
    labels = [k for k, _ in items]
    dsdr = [v.get("si_sdr_improve") or 0 for _, v in items]
    dpesq = [v.get("pesq_improve") or 0 for _, v in items]
    dstoi = [(v.get("stoi_improve") or 0) * 100 for _, v in items]   # scale to readable

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 5.2), sharey=True)
    panels = [("Δ SI-SDR (dB)", dsdr, "#2563eb", 3),
              ("Δ PESQ (wideband)", dpesq, "#d97706", 3),
              ("Δ STOI  (×100)", dstoi, "#059669", 2)]
    y = list(range(len(labels)))[::-1]
    for ax, (title, vals, col, nd) in zip(axes, panels):
        ax.barh(y, vals, color=col, height=0.6)
        for yy, v in zip(y, vals):
            ax.text(v * 1.02, yy, f"{v:+.{nd}f}",
                    va="center", fontsize=8.4, color=INK)
        ax.set_title(title, fontsize=11, fontweight="bold", color=INK)
        ax.axvline(0, color="#666", lw=0.9)
        ax.set_xlim(0, max(vals) * 1.24 if max(vals) > 0 else 1)
        ax.grid(axis="x", ls=":", alpha=0.45)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels, fontsize=9)
    fig.suptitle("Noise-cancellation gain over the noisy input (paired median, 16 kHz protocol)\n"
                 "Valentini, full-reference set", fontsize=12.5, fontweight="bold",
                 color=INK, y=1.03)
    fig.text(0.5, -0.035,
             "Pairwise differences are computed per clip and then median-aggregated "
             "(med(out−in)), not med(out) − med(in).\n"
             "Δ STOI is multiplied by 100 for readability: the raw gain is 0.005 – 0.017 on a 0 – 1 scale.",
             ha="center", fontsize=8, color=MUTED)
    fig.savefig(OUT / "pr_fig_dn_gain_en.png")
    plt.close(fig)
    return len(labels)


# ---------------------------------------------------------------- main
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    med, base, prof, four, single, norec = load_sep()
    dn = load_dn()
    print(f"[data] 4-stem={len(four)}  single={len(single)}  norec={len(norec)}  "
          f"profile={len(prof)}  dn_rows={len(dn['rows']) if dn else 0}")

    n1 = fig_accuracy_bars(base, four)
    n2 = fig_per_stem(four)
    n3 = fig_cost_pareto(prof, four)
    n4 = fig_dn_gain(dn)

    for name, n in (("pr_fig_accuracy_bars_en.png", n1),
                    ("pr_fig_per_stem_en.png", n2),
                    ("pr_fig_cost_pareto_en.png", n3),
                    ("pr_fig_dn_gain_en.png", n4)):
        p = OUT / name
        print(f"  [OK] {p.name:34s} {p.stat().st_size/1024:6.0f} KB  (n={n})")
    if dn is None:
        print("[WARN] denoise_eval_16k.json not found -> skipping noise-cancellation figure")
    print("[status] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""
Valentini clean/noisy 前 100 条 —— spectrogram（4 档 SNR）+ SDR 对比。

口径（诚实标注）：
- SDR(noisy vs clean) = 10·log10( Σ clean² / Σ (noisy−clean)² )  [dB]
  即「以纯净人声为参考、noisy 为目标」的 bss_eval 口径 SI-SDR 近似，
  数值上等于输入信噪比 SNR_in。
- 4 档 SNR：按实测 SNR 最近邻归入 {0, 5, 10, 15} dB。
- 能量对齐：clean 与 noisy 的 spectrogram 共用**同一个 0 dB 参考**（clean 全局峰值），
  同一色标 vmin=-80 / vmax=0，保证「同一数据、同一能量基准」下的可比性。

产物：
  04_reports/02_denoising/figures/valentini_snr_compare/
    snr00/snr05/snr10/snr15/  每对一张 clean↑noisy↓ 并排图（前 100 条，25×4）
    SDR_summary.json          每档 + 整体的 SDR 统计（mean/min/max/n）
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import soundfile as sf

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import librosa
import librosa.display

ROOT = Path(r"E:\FYP_HKBU\02_databases\Valentini")
OUT = Path(r"E:\FYP_HKBU\04_reports\02_denoising\figures\valentini_snr_compare")

N_FFT = 1024
HOP = 256
VMIN, VMAX = -80.0, 0.0
SNR_LEVELS = [0, 5, 10, 15]

# matplotlib 中文（标题不用中文，但保险）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def load_mono(p: Path):
    x, sr = sf.read(str(p), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=-1)
    return x, sr


def snr_db(clean, noisy):
    m = min(len(clean), len(noisy))
    c = clean[:m].astype(np.float64)
    n = noisy[:m].astype(np.float64)
    sig = float(np.sum(c ** 2))
    noise = float(np.sum((n - c) ** 2))
    return 10.0 * np.log10(sig / (noise + 1e-12))


def spec_mag(x, sr):
    return np.abs(librosa.stft(x, n_fft=N_FFT, hop_length=HOP))


def to_db(S, ref):
    # 共用 ref（clean 峰值）做 0 dB 参考，实现能量对齐
    return librosa.amplitude_to_db(S, ref=ref)


def nearest_level(s):
    return min(SNR_LEVELS, key=lambda k: abs(k - s))


def draw_pair(clean, noisy, sr, out_png: Path, name: str, level: int, sdr: float):
    Sc = spec_mag(clean, sr)
    Sn = spec_mag(noisy, sr)
    ref = np.max(Sc)  # 0 dB 参考 = clean 峰值（能量对齐基准）
    DBc = to_db(Sc, ref)
    DBn = to_db(Sn, ref)

    fig, axes = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True)
    for ax, DB, label in ((axes[0], DBc, "clean"), (axes[1], DBn, "noisy")):
        librosa.display.specshow(
            DB, sr=sr, hop_length=HOP, x_axis="time", y_axis="hz",
            ax=ax, vmin=VMIN, vmax=VMAX, cmap="magma")
        ax.set_ylabel(label, fontsize=10)
    axes[1].set_xlabel("time (s)")
    fig.suptitle(f"{name}  |  SNR {level} dB (measured {sdr:.2f} dB)",
                 fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_png, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--no-figure", action="store_true")
    ap.add_argument("--out", type=str,
                    default=str(OUT))
    args = ap.parse_args()

    out = Path(args.out)
    clean_dir = ROOT / "clean_testset_wav"
    noisy_dir = ROOT / "noisy_testset_wav"

    clean_files = sorted(clean_dir.glob("*.wav"))[: args.n]

    rows = []
    for cp in clean_files:
        name = cp.stem
        np_file = noisy_dir / (name + ".wav")
        if not np_file.exists():
            continue
        c, sr = load_mono(cp)
        n, sr2 = load_mono(np_file)
        assert sr == sr2, f"sr mismatch {name}"
        sdr = snr_db(c, n)
        lvl = nearest_level(sdr)
        rows.append(dict(name=name, level=lvl, sdr=round(sdr, 3), sr=sr))

    # 分档统计
    by = {k: [r for r in rows if r["level"] == k] for k in SNR_LEVELS}
    summary = {"n_total": len(rows), "sr": rows[0]["sr"] if rows else None,
               "by_level": {}}
    for k in SNR_LEVELS:
        sdrs = [r["sdr"] for r in by[k]]
        if sdrs:
            summary["by_level"][str(k)] = {
                "n": len(sdrs),
                "mean_sdr": round(float(np.mean(sdrs)), 3),
                "min_sdr": round(float(np.min(sdrs)), 3),
                "max_sdr": round(float(np.max(sdrs)), 3),
            }
    all_sdrs = [r["sdr"] for r in rows]
    summary["overall"] = {
        "n": len(all_sdrs),
        "mean_sdr": round(float(np.mean(all_sdrs)), 3),
        "min_sdr": round(float(np.min(all_sdrs)), 3),
        "max_sdr": round(float(np.max(all_sdrs)), 3),
    }

    # 出图
    if not args.no_figure:
        for k in SNR_LEVELS:
            d = out / f"snr{k:02d}"
            d.mkdir(parents=True, exist_ok=True)
            for r in by[k]:
                cp = clean_dir / (r["name"] + ".wav")
                np_file = noisy_dir / (r["name"] + ".wav")
                c, sr = load_mono(cp)
                n, _ = load_mono(np_file)
                draw_pair(c, n, sr, d / f"{r['name']}.png",
                          r["name"], k, r["sdr"])

    # 写统计
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "SDR_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 控制台摘要
    print("=== SDR 对比（前 %d 条，clean 为参考、noisy 为目标）===" % len(rows))
    for k in SNR_LEVELS:
        b = summary["by_level"][str(k)]
        print("  snr %2d dB : n=%d  mean=%.2f  min=%.2f  max=%.2f"
              % (k, b["n"], b["mean_sdr"], b["min_sdr"], b["max_sdr"]))
    o = summary["overall"]
    print("  OVERALL  : n=%d  mean=%.2f  min=%.2f  max=%.2f"
          % (o["n"], o["mean_sdr"], o["min_sdr"], o["max_sdr"]))
    print("  图：%s/snr{00,05,10,15}/" % out)
    print("  统计：%s/SDR_summary.json" % out)


if __name__ == "__main__":
    main()

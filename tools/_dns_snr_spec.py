# -*- coding: utf-8 -*-
"""DNS-Challenge clean(语音) + noise(噪声) 合成 noisy 配对 → spectrogram + SDR。

背景：DNS 的 clean 与 noise 是**独立资源池、无配对**（与 Valentini 不同）。
本脚本随机配对 clean 语音 + noise 噪声，合成 noisy（精确控制 SNR），
对每对做 clean↑noisy↓ 并排 spectrogram + SDR 对比。

SDR 口径（与 valentini 一致）：SDR = 10·log10( Σclean² / Σ(noisy−clean)² )
= 合成时的目标 SNR（应为精确值，因 gain 是解析算的）。

产物（另存文件夹）：
  <out>/
    pairs.csv           配对清单（pair_id, clean, noise）
    snr00/05/10/15/     每档每对一张 clean↑noisy↓ 图
    audio/              合成的 noisy（pair_id__snrXX.wav）
    SDR_summary.json    每档 + 整体 SDR 统计
"""
import argparse
import csv
import json
import random
from pathlib import Path

import numpy as np
import soundfile as sf

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import librosa
import librosa.display

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

CLEAN = Path(r"E:\FYP_HKBU\02_databases\DNS-Challenge\clean")
NOISE = Path(r"E:\FYP_HKBU\02_databases\DNS-Challenge\noise\freesound\datasets_fullband\noise_fullband")
OUT = Path(r"E:\FYP_HKBU\04_reports\02_denoising\figures\dns_snr_compare_v2")

SR = 48000
N_FFT, HOP = 1024, 256
VMIN, VMAX = -80.0, 0.0
SNR_LEVELS = [0, 5, 10, 15]


def load_mono(p: Path, sr=SR):
    x, _sr = sf.read(str(p), dtype="float32", always_2d=True)
    if _sr != sr:
        import torch
        import torchaudio.functional as AF
        t = torch.as_tensor(np.ascontiguousarray(x.T))
        x = AF.resample(t, _sr, sr).numpy().T
    return x.mean(axis=1).astype(np.float32)


def _pick_non_silent(files, n, rng, thresh=1e-5):
    """随机选 n 个非静音文件（rms >= thresh），避免 -inf/巨大 SDR 污染统计。"""
    pool = list(files)
    rng.shuffle(pool)
    picked = []
    for f in pool:
        x = load_mono(f)
        if float(np.sqrt(np.mean(x ** 2))) < thresh:
            continue
        picked.append(f)
        if len(picked) >= n:
            break
    return picked


def mix_at_snr(clean, noise, target_db):
    """noisy = clean + gain*noise，使 SNR(clean/noise) = target_db。"""
    c = clean.astype(np.float64)
    n = noise[: len(c)].astype(np.float64)
    pc = float(np.sum(c ** 2))
    pn = float(np.sum(n ** 2))
    if pn < 1e-12 or pc < 1e-12:
        gain = 0.0
    else:
        gain = np.sqrt(pc / (pn * 10 ** (target_db / 10.0)))
    noisy = c + gain * n
    return noisy.astype(np.float32), gain


def sdr_db(clean, noisy):
    c = clean.astype(np.float64)
    n = noisy.astype(np.float64)
    m = min(len(c), len(n))
    sig = float(np.sum(c[:m] ** 2))
    err = float(np.sum((n[:m] - c[:m]) ** 2))
    return 10.0 * np.log10(sig / (err + 1e-12))


def draw_pair(clean, noisy, sr, out_png, title, sdr):
    Sc = np.abs(librosa.stft(clean, n_fft=N_FFT, hop_length=HOP))
    Sn = np.abs(librosa.stft(noisy, n_fft=N_FFT, hop_length=HOP))
    ref = float(Sc.max())
    DBc = librosa.amplitude_to_db(Sc, ref=ref)
    DBn = librosa.amplitude_to_db(Sn, ref=ref)
    fig, axes = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True)
    for ax, DB, label in ((axes[0], DBc, "clean"), (axes[1], DBn, "noisy")):
        librosa.display.specshow(DB, sr=sr, hop_length=HOP, x_axis="time", y_axis="hz",
                                 ax=ax, vmin=VMIN, vmax=VMAX, cmap="magma")
        ax.set_ylabel(label, fontsize=10)
    axes[1].set_xlabel("time (s)")
    fig.suptitle(f"{title}  |  SNR {sdr:.2f} dB", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_png, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="配对数量")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--snr", type=str, default="0,5,10,15")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--out", type=str, default=str(OUT))
    a = ap.parse_args()

    levels = [int(x) for x in a.snr.split(",")]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    clean_files = sorted(CLEAN.rglob("*.wav"))
    noise_files = sorted(NOISE.glob("*.wav"))
    rng = random.Random(a.seed)
    clean_pick = _pick_non_silent(clean_files, a.n, rng)
    noise_pick = _pick_non_silent(noise_files, a.n, rng)
    n = min(len(clean_pick), len(noise_pick))
    pairs = list(zip(clean_pick[:n], noise_pick[:n]))

    # 配对清单
    pairs_csv = out / "pairs.csv"
    with open(pairs_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pair_id", "clean", "noise"])
        for i, (c, no) in enumerate(pairs):
            w.writerow([i, str(c.relative_to(CLEAN)), no.name])

    rows = []
    audio_dir = out / "audio"
    if not a.no_audio:
        audio_dir.mkdir(parents=True, exist_ok=True)

    for i, (cp, np_) in enumerate(pairs):
        clean = load_mono(cp)
        noise = load_mono(np_)
        m = min(len(clean), len(noise))
        clean = clean[:m]
        noise = noise[:m]
        if m < SR // 2:  # 短于 0.5s 跳过
            continue
        for lv in levels:
            noisy, gain = mix_at_snr(clean, noise, lv)
            sdr = sdr_db(clean, noisy)
            rows.append(dict(pair=i, level=lv, sdr=round(sdr, 3),
                             clean=cp.name, noise=np_.name))
            if not a.no_audio:
                sf.write(str(audio_dir / f"{i:04d}__snr{lv:02d}.wav"), noisy, SR,
                         subtype="PCM_16")
            d = out / f"snr{lv:02d}"
            d.mkdir(parents=True, exist_ok=True)
            draw_pair(clean, noisy, SR, d / f"pair{i:04d}.png",
                      f"pair {i}  clean={cp.name}  +  noise={np_.name}", sdr)

    # SDR 统计
    by = {lv: [r for r in rows if r["level"] == lv] for lv in levels}
    summary = {"n_pairs": n, "sr": SR, "by_level": {}}
    for lv in levels:
        sdrs = [r["sdr"] for r in by[lv]]
        if sdrs:
            summary["by_level"][str(lv)] = {
                "n": len(sdrs),
                "mean_sdr": round(float(np.mean(sdrs)), 3),
                "min_sdr": round(float(np.min(sdrs)), 3),
                "max_sdr": round(float(np.max(sdrs)), 3),
            }
    alls = [r["sdr"] for r in rows]
    summary["overall"] = {
        "n": len(alls),
        "mean_sdr": round(float(np.mean(alls)), 3),
        "min_sdr": round(float(np.min(alls)), 3),
        "max_sdr": round(float(np.max(alls)), 3),
    }
    with open(out / "SDR_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=== DNS clean+noise 合成配对 SDR（n_pairs=%d）===" % n)
    for lv in levels:
        b = summary["by_level"][str(lv)]
        print("  snr %2d dB : n=%d  mean=%.2f  min=%.2f  max=%.2f"
              % (lv, b["n"], b["mean_sdr"], b["min_sdr"], b["max_sdr"]))
    o = summary["overall"]
    print("  OVERALL  : n=%d  mean=%.2f  min=%.2f  max=%.2f" % (o["n"], o["mean_sdr"], o["min_sdr"], o["max_sdr"]))
    print("  清单：%s" % pairs_csv)
    print("  图/音频/统计：%s/" % out)


if __name__ == "__main__":
    main()

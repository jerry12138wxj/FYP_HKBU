# -*- coding: utf-8 -*-
"""把 valentini_snr_compare 下 4 档的 spectrogram 拼成总览图（每档一张 mosaic）。

输入：04_reports/02_denoising/figures/valentini_snr_compare/snr{00,05,10,15}/*.png
输出：同目录 overview_snr{00,05,10,15}.png
"""
import math
from pathlib import Path

from PIL import Image

ROOT = Path(r"E:\FYP_HKBU\04_reports\02_denoising\figures\valentini_snr_compare")
THUMB_W, THUMB_H = 160, 92  # 原图 1040x598 的等比缩略
LEVELS = [0, 5, 10, 15]


def mosaic(files, level):
    n = len(files)
    cols = 15
    rows = math.ceil(n / cols)
    gap = 3
    pad = 20
    # 标题区
    title_h = 46
    W = cols * THUMB_W + (cols - 1) * gap + 2 * pad
    H = title_h + rows * THUMB_H + (rows - 1) * gap + 2 * pad
    canvas = Image.new("RGB", (W, H), (18, 18, 22))
    from PIL import ImageDraw
    d = ImageDraw.Draw(canvas)
    d.text((pad, 10), f"Valentini 全量 spectrogram  —  SNR {level} dB 档（n={n}，clean 上 / noisy 下）",
           fill=(240, 240, 240))
    for i, f in enumerate(files):
        r, c = divmod(i, cols)
        x = pad + c * (THUMB_W + gap)
        y = title_h + r * (THUMB_H + gap)
        try:
            im = Image.open(f).convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS)
            canvas.paste(im, (x, y))
        except Exception as e:
            print("  skip", f.name, e)
    out = ROOT / f"overview_snr{level:02d}.png"
    canvas.save(out, optimize=True)
    print(f"overview_snr{level:02d}.png  {n} 张 -> {cols}x{rows}  ({W}x{H})")


def main():
    for lv in LEVELS:
        d = ROOT / f"snr{lv:02d}"
        files = sorted(d.glob("*.png"))
        if not files:
            print(f"snr{lv:02d} 空，跳过")
            continue
        mosaic(files, lv)
    print("DONE")


if __name__ == "__main__":
    main()

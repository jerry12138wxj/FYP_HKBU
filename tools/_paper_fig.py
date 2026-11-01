# -*- coding: utf-8 -*-
"""
================================================================================
 论文原理图例裁剪器（旁路）
--------------------------------------------------------------------------------
 项目要求：「论文中有原理图例则复制出来」。本脚本按图注定位，把图注上方那一块
 矢量图/位图原样裁成 PNG（不重绘、不臆造）。

 边界规则
 --------
 * 底边界：`--caption` 命中的图注文本块上沿
 * 顶边界：优先 `--top-text`（同页图注上方的另一处文字，取其块下沿）
           其次取水平范围内的矢量绘图/位图并集上沿
           最后回退到上一段正文下沿
 * 左右边界：`--x-mode caption`（默认，图注宽度=图宽，双栏论文安全）
             `--x-mode graphics`（图比图注宽时用，如 JOSS 单栏居中图注）
             `--x-mode full`（整页宽）
 * `--pad-top` 向上再放宽 N 磅（波形/坐标轴被切一截时用）

 用法
 ----
   PY tools/_paper_fig.py --pdf x.pdf --page 3 --caption "MMDenseLSTM architecture" --top-text "Fig. 2"
   PY tools/_paper_fig.py --pdf x.pdf --page 3 --caption "..." --x-mode graphics
   PY tools/_paper_fig.py --pdf x.pdf --page 2 --caption "..." --pad-top 40

 只读 PDF，不修改原文件。
================================================================================
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymupdf

PAD = 4.0
MINPX = 8


def _block_of(page, hit):
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        if b[0] - 2 <= hit.x0 and b[2] + 2 >= hit.x1 and b[1] - 2 <= hit.y0 and b[3] + 2 >= hit.y1:
            return b
    return None


def _graphics(page):
    rects = []
    for d in page.get_drawings():
        r = d["rect"]
        if r.width > MINPX and r.height > MINPX:
            rects.append(r)
    for info in page.get_images(full=True):
        try:
            for r in page.get_image_rects(info[0]):
                if r.width > MINPX and r.height > MINPX:
                    rects.append(r)
        except Exception:
            continue
    return rects


def _clip_rect(page, cap_hit, a):
    cb = _block_of(page, cap_hit)
    if cb:
        cx0, cy0, cx1, cy1 = cb[0], cb[1], cb[2], cb[3]
    else:
        cx0, cy0, cx1, cy1 = cap_hit.x0, cap_hit.y0, cap_hit.x1, cap_hit.y1

    gfx = _graphics(page)
    by_y = [r for r in gfx if r.y1 <= cy0 + 1]

    top, src = None, ""
    if a.top_text:
        hits = [h for h in page.search_for(a.top_text) if h.y0 < cy0 - 5]
        if hits:
            h = max(hits, key=lambda r: r.y0)
            tb = _block_of(page, h)
            top = tb[3] if tb else h.y1
            src = "top-text"
        else:
            src = "top-text MISS"
    if top is None:
        band = [r for r in by_y if r.x1 > cx0 - 10 and r.x0 < cx1 + 10]
        if band:
            top, src = min(r.y0 for r in band), "graphics-y"
        else:
            prv = [b[3] for b in page.get_text("blocks") if b[6] == 0 and b[3] < cy0 - 2]
            top, src = (max(prv) + 2 if prv else page.rect.y0 + 40), "text-gap"

    if a.x_mode == "full":
        x0, x1 = page.rect.x0 + 6, page.rect.x1 - 6
    elif a.x_mode == "graphics":
        near = [r for r in by_y if r.y0 >= top - 2]
        if near:
            x0, x1 = min(r.x0 for r in near), max(r.x1 for r in near)
        else:
            x0, x1 = cx0, cx1
    else:
        x0, x1 = cx0, cx1

    clip = pymupdf.Rect(max(page.rect.x0 + 6, x0 - PAD),
                        max(page.rect.y0 + 6, top - a.pad_top),
                        min(page.rect.x1 - 6, x1 + PAD),
                        cy0 - 2)
    if a.debug:
        print("  caption-block=(%.0f,%.0f,%.0f,%.0f) top-src=%s x-mode=%s"
              % (cx0, cy0, cx1, cy1, src, a.x_mode))
        print("  clip=(%.0f,%.0f,%.0f,%.0f)  %.0fx%.0f pt"
              % (clip.x0, clip.y0, clip.x1, clip.y1, clip.width, clip.height))
    return clip


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--top-text", default="")
    ap.add_argument("--x-mode", choices=["caption", "graphics", "full"], default="caption")
    ap.add_argument("--pad-top", type=float, default=0.0)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", default="")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    pdf = Path(a.pdf)
    doc = pymupdf.open(str(pdf))
    page = doc[a.page - 1]
    hits = page.search_for(a.caption)
    if not hits:
        print("!! 该页找不到 %r" % a.caption)
        return 2
    clip = _clip_rect(page, hits[0], a)
    if clip.height < 50 or clip.width < 50:
        print("!! 裁切区域过小 %.0fx%.0f pt" % (clip.width, clip.height))
        return 3
    pix = page.get_pixmap(dpi=a.dpi, clip=clip)
    out = Path(a.out) if a.out else pdf.with_name("%s_fig_p%d.png" % (pdf.stem, a.page))
    pix.save(str(out))
    print("OK %s  %dx%d" % (out.name, pix.width, pix.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())

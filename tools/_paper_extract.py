# -*- coding: utf-8 -*-
"""
================================================================================
 论文 PDF 抽取工具（旁路，不改任何主流程）
--------------------------------------------------------------------------------
 目的：为本项目每个模型建立「来源论文 → 原文摘抄 → 原理图例」的可核查材料。

 三个子命令
 ----------
   text   : 逐页导出纯文本（带 `=== PAGE n ===` 分隔），供人工/agent 摘抄原文
   render : 整页渲染 PNG（200 dpi），用于目视确认原理图在哪一页、是否清晰
   fig    : 按标题短语定位图注，自动裁出「图注上方那一块」= 原理图例

 用法
 ----
   PY tools/_paper_extract.py text   --pdf a.pdf
   PY tools/_paper_extract.py render --pdf a.pdf --pages 2,3
   PY tools/_paper_extract.py fig    --pdf a.pdf --page 3 --caption "Fig. 1" --out fig1.png

 设计说明
 --------
 * 不写 `04_reports` 之外的任何路径；默认输出到 PDF 同目录。
 * `fig` 的裁剪逻辑：取图注文本块的 bbox，向上回溯到「上一段正文的底部」为止，
   左右各留 4% 页边距。若图注在图下方（绝大多数论文），结果即整张图；
   若图注在图上方，用 `--caption-below`。
 * 只读 PDF，不修改、不重命名原文件。
================================================================================
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymupdf


def _open(pdf: str) -> pymupdf.Document:
    p = Path(pdf)
    if not p.is_file():
        raise SystemExit("找不到 PDF: %s" % p)
    return pymupdf.open(str(p))


def cmd_text(args) -> int:
    doc = _open(args.pdf)
    out = Path(args.pdf).with_suffix(".txt")
    chunks = []
    for i, page in enumerate(doc, start=1):
        chunks.append("=== PAGE %d ===" % i)
        chunks.append(page.get_text("text"))
    out.write_text("\n".join(chunks), encoding="utf-8")
    print("%s -> %s  (%d pages, %d chars)"
          % (Path(args.pdf).name, out.name, doc.page_count, sum(len(c) for c in chunks)))
    return 0


def cmd_render(args) -> int:
    doc = _open(args.pdf)
    pages = _parse_pages(args.pages, doc.page_count)
    stem = Path(args.pdf).stem
    for n in pages:
        pix = doc[n - 1].get_pixmap(dpi=args.dpi)
        f = Path(args.pdf).parent / ("%s_p%d.png" % (stem, n))
        pix.save(str(f))
        print("%s  %dx%d" % (f.name, pix.width, pix.height))
    return 0


def cmd_fig(args) -> int:
    doc = _open(args.pdf)
    page = doc[args.page - 1]
    rect = page.rect
    hits = page.search_for(args.caption)
    if not hits:
        raise SystemExit("该页找不到图注 %r；先用 text/render 看实际写法" % args.caption)
    cap = hits[0]
    # 图注通常只占一到两行；向下扩到下一段文本块开始处
    blocks = [b for b in page.get_text("blocks") if b[6] == 0]
    cap_block = None
    for b in blocks:
        if b[1] <= cap.y0 + 2 and b[3] >= cap.y1 - 2:
            cap_block = b
            break
    cap_top = cap_block[1] if cap_block else cap.y0
    if args.caption_below:
        top = cap_top
        bottom = None
        for b in blocks:
            if b[1] > cap_top + 2:
                bottom = b[1]
                break
        bottom = bottom if bottom is not None else rect.y1 - 40
    else:
        bottom = cap_top - 2
        top = None
        for b in blocks:
            if b[3] < bottom - 2:
                top = b[3]
            else:
                break
        top = top if top is not None else 40
    x0 = rect.x0 + rect.width * 0.04
    x1 = rect.x1 - rect.width * 0.04
    clip = pymupdf.Rect(x0, max(40, top + 1), x1, min(rect.y1 - 40, bottom))
    if clip.height < 60:
        raise SystemExit("裁切区域过小(%.0f pt)，请检查 --caption / --caption-below" % clip.height)
    pix = page.get_pixmap(dpi=args.dpi, clip=clip)
    out = Path(args.out) if args.out else Path(args.pdf).with_name(
        "%s_fig_p%d.png" % (Path(args.pdf).stem, args.page))
    pix.save(str(out))
    print("%s  %dx%d  (clip %.0f,%.0f - %.0f,%.0f)"
          % (out.name, pix.width, pix.height, clip.x0, clip.y0, clip.x1, clip.y1))
    return 0


def _parse_pages(spec: str, total: int) -> list[int]:
    if not spec or spec == "all":
        return list(range(1, total + 1))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return [p for p in out if 1 <= p <= total]


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("text")
    t.add_argument("--pdf", required=True)
    t.set_defaults(func=cmd_text)

    r = sub.add_parser("render")
    r.add_argument("--pdf", required=True)
    r.add_argument("--pages", default="all")
    r.add_argument("--dpi", type=int, default=200)
    r.set_defaults(func=cmd_render)

    f = sub.add_parser("fig")
    f.add_argument("--pdf", required=True)
    f.add_argument("--page", type=int, required=True)
    f.add_argument("--caption", required=True)
    f.add_argument("--caption-below", action="store_true")
    f.add_argument("--dpi", type=int, default=220)
    f.add_argument("--out", default="")
    f.set_defaults(func=cmd_fig)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

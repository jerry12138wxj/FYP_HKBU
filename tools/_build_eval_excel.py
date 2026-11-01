# -*- coding: utf-8 -*-
"""把 `_eval_pipeline.py` 产出的 results.json 汇总成 Excel（2 sheet，图嵌入格子）。

Sheet「分离模型」:  sep:* 管线，按 (模型, 数据库) 分组
Sheet「级联」:      cascade:* 管线，按 (组合, 数据库) 分组

每个分组一个区块：
  - 头部：模型 | 数据库 | 样本数(有效/总数) | Delta SDR ± (max/min − avg)
  - 体：3 行代表样本（接近均值 / 最高 / 最低 各 3 个），图**嵌入独立格子**
        （图行高度=图高，图锚定到 B/C/D 格，下方标注行写样本名 + SDR + 运行时间）

极端值过滤（防止退化样本污染统计）：
  - 时长 < MIN_DUR 秒的极短片段（无时间结构，SDR 无意义）
  - SDR < MIN_SDR dB 的样本（wham「输出 vs 输入」度量下，输出接近静音 = 退化）

这些过滤函数同时被 `_export_table_audio.py` 复用，保证表格与导出音频口径一致。

用法：
  python tools/_build_eval_excel.py --root 03_outputs/_eval --out 03_outputs/Final_Eval_Report.xlsx
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

IMG_W = 380      # px
IMG_H = 240
COL_W = 58       # 列宽（约 380px）
ROW_H = 185      # 图行高（≈ 240px 图高，让图完整落在格内）
CAP_ROW_H = 34   # 标注行高

HDR = "Delta SDR ± (max/min − avg)"

# ---- 极端值过滤阈值（与 _export_table_audio.py 保持一致）----
MIN_DUR = 1.0      # 秒：短于此视为退化片段
MIN_SDR = -25.0    # dB：wham 自参照度量下，输出近静音视为退化


def is_keep(r: dict) -> bool:
    """是否保留该样本（True=保留）。"""
    d = r.get("dur_s") or 0.0
    if d < MIN_DUR:
        return False
    s = r.get("sdr_db")
    if s is None or s == float("inf"):
        return True
    return s >= MIN_SDR


def filter_recs(recs):
    """返回过滤后的样本列表。"""
    return [r for r in recs if is_keep(r)]


def _pick_reps(recs):
    """返回 [('接近均值', [rec x3]), ('最高 SDR', [rec x3]), ('最低 SDR', [rec x3])]

    基于「过滤后」的样本选择代表，保证表格里不出现被剔除的极端样本。
    """
    scored = [r for r in filter_recs(recs)
              if r.get("sdr_db") is not None and r["sdr_db"] != float("inf")]
    if not scored:
        return [("SDR N/A（无参考）", recs[:9])]
    scored = sorted(scored, key=lambda r: r.get("sdr_db", -999))

    mean = float(np.mean([r["sdr_db"] for r in scored]))
    top = sorted(scored, key=lambda r: r["sdr_db"], reverse=True)[:3]
    low = sorted(scored, key=lambda r: r["sdr_db"])[:3]
    near = sorted(scored, key=lambda r: abs(r["sdr_db"] - mean))[:3]
    return [("最接近均值 (mean=%.2f)" % mean, near),
            ("最高 SDR", top),
            ("最低 SDR", low)]


def select_reps(recs):
    """返回代表样本的扁平列表（去重、按顺序），供音频导出使用。"""
    out, seen = [], set()
    for _, reps in _pick_reps(recs):
        for r in reps:
            if r["sample"] not in seen:
                seen.add(r["sample"])
                out.append(r)
    return out


def _sdr_txt(r):
    v = r.get("sdr_db")
    if v is None:
        return "N/A"
    if v == float("inf"):
        return "inf"
    return "%.2f" % v


def _rt_txt(r):
    v = r.get("infer_s")
    if not isinstance(v, (int, float)):
        return "?"
    return "%.1fs" % v


def _stats(recs):
    kept = filter_recs(recs)
    sdrs = [r["sdr_db"] for r in kept
            if r.get("sdr_db") is not None and r["sdr_db"] != float("inf")]
    if not sdrs:
        return None, None, None
    return float(np.min(sdrs)), float(np.max(sdrs)), float(np.mean(sdrs))


def _sdr_cell(mn, mx, mean):
    """mean ± (max−mean / min−mean)。"""
    if mean is None:
        return "N/A"
    return "%.2f ± (%+.2f / %+.2f)" % (mean, mx - mean, mn - mean)


def _block(ws, row, label, db, recs):
    """写一个分组区块，返回下一个可用行号。"""
    grp_fill = PatternFill("solid", fgColor="D9E2F3")
    cap_font = Font(size=9)
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    kept = filter_recs(recs)
    n_txt = str(len(kept)) if len(kept) == len(recs) else "%d/%d" % (len(kept), len(recs))
    ws.cell(row=row, column=1, value=label).font = Font(bold=True, size=11)
    ws.cell(row=row, column=2, value=db)
    mn, mx, mean = _stats(recs)
    ws.cell(row=row, column=3, value=n_txt)
    ws.cell(row=row, column=4, value=_sdr_cell(mn, mx, mean)).font = Font(bold=True)
    for c in range(1, 5):
        ws.cell(row=row, column=c).fill = grp_fill
    row += 1

    # 代表样本：图行(高，图嵌入格子) + 标注行(矮)
    for group_name, reps in _pick_reps(recs):
        lbl = ws.cell(row=row, column=1, value=group_name)
        lbl.font = Font(bold=True, size=10)
        lbl.alignment = Alignment(vertical="center", wrap_text=True)

        ws.row_dimensions[row].height = ROW_H
        for j, r in enumerate(reps):
            col = 2 + j
            ws.cell(row=row, column=col).border = border
            fig = r.get("figure")
            if fig and Path(fig).exists():
                img = XLImage(fig)
                img.width, img.height = IMG_W, IMG_H
                ws.add_image(img, "%s%d" % (get_column_letter(col), row))
        row += 1

        ws.row_dimensions[row].height = CAP_ROW_H
        for j, r in enumerate(reps):
            col = 2 + j
            cell = ws.cell(row=row, column=col,
                           value="%s\nSDR %s dB | %s" % (r["sample"], _sdr_txt(r), _rt_txt(r)))
            cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
            cell.font = cap_font
            cell.border = border
        row += 1
    return row + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="含多个 results.json 的根目录")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    root = Path(a.root)
    sep_groups, cas_groups = [], []

    for jf in sorted(root.rglob("results.json")):
        recs = json.loads(jf.read_text(encoding="utf-8"))
        if not recs:
            continue
        label = recs[0].get("label", "?")
        db = recs[0].get("db", "?")
        pipe = recs[0].get("pipeline", "?")
        (sep_groups if pipe.startswith("sep:") else cas_groups).append((label, db, recs))

    wb = Workbook()

    ws = wb.active
    ws.title = "分离模型"
    ws.append(["模型", "数据库", "样本数", HDR])
    for c in range(1, 5):
        ws.cell(row=1, column=c).font = Font(bold=True, color="FFFFFF")
        ws.cell(row=1, column=c).fill = PatternFill("solid", fgColor="4472C4")
    row = 2
    for label, db, recs in sorted(sep_groups, key=lambda x: (x[0], x[1])):
        row = _block(ws, row, label, db, recs)

    ws2 = wb.create_sheet("级联")
    ws2.append(["级联组合", "数据库", "样本数", HDR])
    for c in range(1, 5):
        ws2.cell(row=1, column=c).font = Font(bold=True, color="FFFFFF")
        ws2.cell(row=1, column=c).fill = PatternFill("solid", fgColor="C55A11")
    row2 = 2
    for label, db, recs in sorted(cas_groups, key=lambda x: (x[0], x[1])):
        row2 = _block(ws2, row2, label, db, recs)

    for w in (ws, ws2):
        w.column_dimensions["A"].width = 34
        for c in range(2, 5):
            w.column_dimensions[get_column_letter(c)].width = COL_W
        w.row_dimensions[1].height = 20

    wb.save(a.out)
    print("WROTE", a.out)
    print("分离模型分组:", len(sep_groups), " 级联分组:", len(cas_groups))


if __name__ == "__main__":
    main()

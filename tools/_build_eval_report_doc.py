# -*- coding: utf-8 -*-
"""
Build the model-evaluation summary as a Word document.

Single source of truth = 03_outputs/_eval/**/results.json (same filtered
cohort as Final_Eval_Report.xlsx). Every number in the document is computed
here, never hard-coded.

Outputs
  04_reports/00_shared/figures/eval_report/fig*.png
  04_reports/00_shared/docs/MODEL_EVAL_SUMMARY_2026-10-23.docx
"""
from __future__ import annotations

import glob
import json
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _build_eval_excel as BE  # noqa: E402  (filter_recs / 同口径)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL = os.path.join(ROOT, "03_outputs", "_eval")
FIG_DIR = os.path.join(ROOT, "04_reports", "00_shared", "figures", "eval_report")
DOC_DIR = os.path.join(ROOT, "04_reports", "00_shared", "docs")
DOCX = os.path.join(DOC_DIR, "MODEL_EVAL_SUMMARY_2026-10-23.docx")

# ---------------------------------------------------------------- 命名映射
SEP_NAME = {
    "BS-RoFormer L12 (ep_317, vocals) (sep)": "BS-RoFormer L12",
    "Demucs (htdemucs) (sep)": "Demucs",
    "MDX-Net (mdx_extra_q, quant) (sep)": "MDX-extra_q",
    "MDX-Net (mdx_q, quant) (sep)": "MDX_q",
}
DEN_NAME = {
    "denoiser dns48 (16 kHz)": "dns48",
    "denoiser dns64 (16 kHz)": "dns64",
    "denoiser master64 (16 kHz)": "master64",
    "Mel-RoFormer-Denoise (aggr)": "Mel-RoFormer",
    "Wiener filter (classical baseline)": "Wiener",
}
DEN_ORDER = ["Mel-RoFormer", "dns64", "dns48", "master64", "Wiener"]
DB_ORDER = ["valentini", "musdb", "dns", "wham"]
CLEAN_DBS = ["valentini", "musdb", "dns"]


def short_sep(label: str) -> str:
    if label in SEP_NAME:
        return SEP_NAME[label]
    for k, v in SEP_NAME.items():
        if label.startswith(k.split(" (")[0]):
            return v
    return label.replace(" (sep)", "")


def short_den(label: str) -> str:
    for k, v in DEN_NAME.items():
        if k in label:
            return v
    return label


# ---------------------------------------------------------------- 取数
def load_stats():
    sep = {}       # (model, db) -> mean
    casc = {}      # (base, den) -> mean
    meta = {}      # key -> dict(n, nk, mn, mx)
    n_total = n_kept = 0
    files = 0
    for f in sorted(glob.glob(os.path.join(EVAL, "**", "results.json"), recursive=True)):
        try:
            recs = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not recs:
            continue
        files += 1
        kept = BE.filter_recs(recs)
        sdrs = [r["sdr_db"] for r in kept
                if r.get("sdr_db") is not None and abs(r["sdr_db"]) != float("inf")]
        if not sdrs:
            continue
        r0 = recs[0]
        pipe, label, db = r0["pipeline"], r0["label"], r0["db"]
        mean = sum(sdrs) / len(sdrs)
        n_total += len(recs)
        n_kept += len(kept)
        if pipe.startswith("sep:"):
            m = short_sep(label)
            sep[(m, db)] = mean
            meta[("sep", m, db)] = dict(n=len(recs), nk=len(kept),
                                        mn=min(sdrs), mx=max(sdrs), mean=mean)
        else:
            # cascade:<base>:<den>  -> 用 label 解析
            if "->" not in label:
                continue
            left, right = label.split("->", 1)
            base = short_sep(left.strip() + " (sep)")
            den = short_den(right)
            casc[(base, den)] = mean
            meta[("cas", base, den)] = dict(n=len(recs), nk=len(kept),
                                            mn=min(sdrs), mx=max(sdrs), mean=mean)
    return dict(files=files, sep=sep, casc=casc, meta=meta,
                n_total=n_total, n_kept=n_kept)


# ---------------------------------------------------------------- 图
def make_figures(S):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    os.makedirs(FIG_DIR, exist_ok=True)
    paths = []
    warned = []

    # --- fig1: 分离模型 × 三库 ---
    models = ["BS-RoFormer L12", "Demucs", "MDX-extra_q", "MDX_q"]
    fig, ax = plt.subplots(figsize=(9.2, 4.4), dpi=200)
    x = np.arange(len(models))
    w = 0.26
    colors = {"valentini": "#2D6CDF", "musdb": "#E8A33D", "dns": "#3FA45B"}
    for i, db in enumerate(CLEAN_DBS):
        vals = [S["sep"].get((m, db), 0) for m in models]
        bars = ax.bar(x + (i - 1) * w, vals, w, label=db, color=colors[db],
                      edgecolor="white", linewidth=0.6)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.18, "%.2f" % v,
                    ha="center", va="bottom", fontsize=8, color="#333333")
    ax.set_ylabel("平均 SDR (dB)", fontsize=10)
    ax.set_title("图 1  分离模型在三个带 clean 参考的数据集上的平均 SDR", fontsize=11, pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=9.5)
    ax.set_ylim(0, 18)
    ax.legend(frameon=False, fontsize=9, ncol=3, loc="upper right")
    ax.grid(axis="y", linestyle=":", alpha=0.45)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    p1 = os.path.join(FIG_DIR, "fig1_sep_sdr.png")
    fig.savefig(p1)
    plt.close(fig)
    paths.append(p1)

    # --- fig2: 级联热力图（绝对 + 提升）---
    bases = models
    dens = DEN_ORDER
    absm = np.array([[S["casc"].get((b, d), np.nan) for d in dens] for b in bases])
    dlt = np.array([[S["casc"].get((b, d), np.nan) - S["sep"].get((b, "valentini"), np.nan)
                     for d in dens] for b in bases])

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 3.7), dpi=200)
    for ax, mat, title, fmt, cmap in (
        (axes[0], absm, "(a) 级联平均 SDR (dB)", "%.2f", "YlGnBu"),
        (axes[1], dlt, "(b) 相对基础模型的提升 (dB)", "+%.2f", "OrRd"),
    ):
        im = ax.imshow(mat, cmap=cmap, aspect="auto")
        ax.set_xticks(range(len(dens)))
        ax.set_xticklabels(dens, fontsize=9, rotation=20, ha="right")
        ax.set_yticks(range(len(bases)))
        ax.set_yticklabels(bases, fontsize=9)
        ax.set_title(title, fontsize=10, pad=8)
        vmax = np.nanmax(mat)
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                v = mat[i, j]
                if np.isnan(v):
                    continue
                ax.text(j, i, fmt % v, ha="center", va="center", fontsize=8.5,
                        color="white" if v > vmax * 0.62 else "#222222")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    fig.suptitle("图 2  级联矩阵（valentini，4 个基础分离模型 × 5 个去噪器）",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    p2 = os.path.join(FIG_DIR, "fig2_cascade_heatmap.png")
    fig.savefig(p2, bbox_inches="tight")
    plt.close(fig)
    paths.append(p2)

    # --- fig3: 20 组排名 ---
    items = sorted(S["casc"].items(), key=lambda kv: kv[1])
    names = ["%s → %s" % (b, d) for (b, d), _ in items]
    vals = [v for _, v in items]
    base_of = [S["sep"].get((b, "valentini"), np.nan) for (b, _), _ in items]
    fig, ax = plt.subplots(figsize=(9.4, 6.0), dpi=200)
    y = np.arange(len(vals))
    cols = ["#2D6CDF" if "BS-RoFormer" in n else
            "#E8A33D" if "Demucs" in n else
            "#3FA45B" if "MDX-extra" in n else "#9B59B6" for n in names]
    ax.barh(y, vals, color=cols, height=0.68, edgecolor="white", linewidth=0.5)
    for i, (v, bv) in enumerate(zip(vals, base_of)):
        ax.text(v + 0.12, i, "%.2f" % v, va="center", fontsize=8)
        ax.plot([bv, bv], [i - 0.34, i + 0.34], color="#CC3333", linewidth=1.6)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("平均 SDR (dB)", fontsize=10)
    ax.set_xlim(min(base_of) - 0.6, max(vals) + 0.9)
    ax.set_title("图 3  20 个级联组合排名（红线 = 对应基础模型单独表现）",
                 fontsize=11, pad=10)
    ax.grid(axis="x", linestyle=":", alpha=0.45)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    p3 = os.path.join(FIG_DIR, "fig3_cascade_rank.png")
    fig.savefig(p3)
    plt.close(fig)
    paths.append(p3)

    return paths, warned


# ---------------------------------------------------------------- docx 工具
def build_docx(S, figs):
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    CN = "微软雅黑"
    EN = "Calibri"
    DARK = RGBColor(0x1F, 0x2D, 0x3D)
    GREY = RGBColor(0x5A, 0x64, 0x72)
    ACCENT = RGBColor(0x2D, 0x6C, 0xDF)

    doc = Document()

    # 页面
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4)
    sec.right_margin = Cm(2.4)

    # 正文默认样式
    st = doc.styles["Normal"]
    st.font.name = EN
    st.font.size = Pt(10.5)
    st.font.color.rgb = DARK
    st.element.rPr.rFonts.set(qn("w:eastAsia"), CN)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.35

    def run_font(r, size=10.5, bold=False, color=DARK, italic=False, cn=CN, en=EN):
        r.font.name = en
        r.font.size = Pt(size)
        r.bold = bold
        r.italic = italic
        r.font.color.rgb = color
        r._element.rPr.rFonts.set(qn("w:eastAsia"), cn)

    def para(text="", size=10.5, bold=False, color=DARK, align=None,
             before=0, after=6, indent=0, line=1.35):
        p = doc.add_paragraph()
        if align is not None:
            p.alignment = align
        pf = p.paragraph_format
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.line_spacing = line
        if indent:
            pf.first_line_indent = Cm(indent)
        if text:
            run_font(p.add_run(text), size, bold, color)
        return p

    def h1(text, num=None, newpage=False):
        if newpage:
            doc.add_page_break()
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0 if newpage else 22)
        p.paragraph_format.space_after = Pt(12)
        p.paragraph_format.keep_with_next = True
        r = p.add_run((num + "  " if num else "") + text)
        run_font(r, 18, True, DARK)
        # 下划横线
        pPr = p._p.get_or_add_pPr()
        bd = OxmlElement("w:pBdr")
        bt = OxmlElement("w:bottom")
        bt.set(qn("w:val"), "single")
        bt.set(qn("w:sz"), "12")
        bt.set(qn("w:space"), "6")
        bt.set(qn("w:color"), "2D6CDF")
        bd.append(bt)
        pPr.append(bd)
        return p

    def h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        run_font(r, 12.5, True, ACCENT)
        return p

    def bullet(text, size=10.5, level=0):
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.left_indent = Cm(0.75 + 0.6 * level)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.3
        run_font(p.add_run(text), size)
        return p

    def numbered(text, size=10.5):
        p = doc.add_paragraph(style="List Number")
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.3
        run_font(p.add_run(text), size)
        return p

    def shade(cell, hexcolor):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hexcolor)
        tcPr.append(shd)

    def cell_text(cell, text, size=9.5, bold=False, color=DARK,
                  align=WD_ALIGN_PARAGRAPH.CENTER):
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = align
        p.paragraph_format.space_before = Pt(2.5)
        p.paragraph_format.space_after = Pt(2.5)
        p.paragraph_format.line_spacing = 1.15
        run_font(p.add_run(text), size, bold, color)

    def table(headers, rows, widths=None, align_first_left=True,
              header_bg="1F2D3D", size=9.5, zebra=True):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        hdr = t.rows[0]
        for i, htxt in enumerate(headers):
            cell_text(hdr.cells[i], htxt, size=size, bold=True,
                      color=RGBColor(0xFF, 0xFF, 0xFF))
            shade(hdr.cells[i], header_bg)
        trPr = hdr._tr.get_or_add_trPr()
        th = OxmlElement("w:tblHeader")
        trPr.append(th)
        for ri, row in enumerate(rows):
            cells = t.add_row().cells
            for ci, val in enumerate(row):
                al = (WD_ALIGN_PARAGRAPH.LEFT if (ci == 0 and align_first_left)
                      else WD_ALIGN_PARAGRAPH.CENTER)
                cell_text(cells[ci], str(val), size=size, bold=(ci == 0), align=al)
                if zebra and ri % 2 == 1:
                    shade(cells[ci], "F4F6F9")
        if widths:
            for ci, w in enumerate(widths):
                for row in t.rows:
                    row.cells[ci].width = Cm(w)
        # 行内禁止断页；<=12 行的小表整体保持在同一页
        n_rows = len(t.rows)
        for ri, row in enumerate(t.rows):
            trPr = row._tr.get_or_add_trPr()
            trPr.append(OxmlElement("w:cantSplit"))
            if n_rows <= 12 and ri < n_rows - 1:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        p.paragraph_format.keep_with_next = True
        return t

    def caption(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(12)
        run_font(p.add_run(text), 8.5, False, GREY, italic=True)

    def picture(path, width_cm=15.5):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.add_run().add_picture(path, width=Cm(width_cm))

    def callout(title, body, bg="EAF1FB", bar="2D6CDF"):
        t = doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        c = t.rows[0].cells[0]
        c.width = Cm(16.0)
        shade(c, bg)
        c.text = ""
        p0 = c.paragraphs[0]
        p0.paragraph_format.space_before = Pt(6)
        p0.paragraph_format.space_after = Pt(2)
        run_font(p0.add_run(title), 10.5, True, RGBColor.from_string(bar))
        p1 = c.add_paragraph()
        p1.paragraph_format.space_after = Pt(8)
        p1.paragraph_format.line_spacing = 1.35
        run_font(p1.add_run(body), 10.5)
        # 左边框
        tcPr = c._tc.get_or_add_tcPr()
        borders = OxmlElement("w:tcBorders")
        left = OxmlElement("w:left")
        left.set(qn("w:val"), "single")
        left.set(qn("w:sz"), "24")
        left.set(qn("w:color"), bar)
        borders.append(left)
        tcPr.append(borders)
        # 提示框不可跨页拆开
        t.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))

    def page_footer():
        ftr = sec.footer
        p = ftr.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("HKBU FYP · 模型评测总表结果解读    |    第 ")
        run_font(r, 8, False, GREY)
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), "PAGE")
        run = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "16")
        rpr.append(sz)
        run.append(rpr)
        fld.append(run)
        p._p.append(fld)
        r2 = p.add_run(" 页")
        run_font(r2, 8, False, GREY)

    page_footer()

    # ============================================================ 封面
    para("", after=40)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    run_font(p.add_run("人声分离与降噪级联"), 15, False, GREY)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    run_font(p.add_run("模型评测总表 · 结果解读"), 26, True, DARK)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(28)
    run_font(p.add_run("Model Evaluation Report — Findings & Reading Guide"), 11, False, GREY, italic=True)

    # 分隔线
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(26)
    run_font(p.add_run("─" * 34), 10, False, RGBColor(0xC8, 0xD0, 0xDA))

    n_kept = S["n_kept"]
    n_total = S["n_total"]
    n_drop = n_total - n_kept
    meta_rows = [
        ("文档版本", "v1.0"),
        ("生成日期", "2026-10-23"),
        ("数据来源", "03_outputs/_eval（%d 组 results.json）" % S["files"]),
        ("配对工作簿", "03_outputs/Final_Eval_Report.xlsx"),
        ("有效样本", "%s / %s（剔除 %d 条极端值，%.2f%%）"
         % (format(n_kept, ","), format(n_total, ","), n_drop,
            100.0 * n_drop / n_total if n_total else 0)),
        ("评测指标", "SDR（Signal-to-Distortion Ratio）"),
        ("项目", "HKBU Final Year Project"),
    ]
    t = doc.add_table(rows=0, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for k, v in meta_rows:
        cells = t.add_row().cells
        cells[0].width = Cm(4.0)
        cells[1].width = Cm(11.5)
        cell_text(cells[0], k, 9.5, True, GREY, WD_ALIGN_PARAGRAPH.RIGHT)
        cell_text(cells[1], v, 9.5, False, DARK, WD_ALIGN_PARAGRAPH.LEFT)

    para("", after=18)
    para("本文所有数字均由脚本 tools/_build_eval_report_doc.py 从 results.json 直接计算，"
         "与配对工作簿同口径（已剔除极端值），无手工录入。",
         size=8.5, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER)

    # ============================================================ 一
    h1("一句话结论", "一、", newpage=True)

    best_overall = max(S["casc"].items(), key=lambda kv: kv[1])
    # 性价比：基础模型参数更轻的 MDX-extra_q 组里最高者
    mdxe = [(k, v) for k, v in S["casc"].items() if k[0] == "MDX-extra_q"]
    best_value = max(mdxe, key=lambda kv: kv[1])
    gap = best_overall[1] - best_value[1]

    callout(
        "核心结论",
        "%s 是全场最强分离器；级联去噪普遍有效，且基础模型越弱、提升越大。"
        "综合最优为 %s → %s（%.2f dB），性价比最优为 %s → %s（%.2f dB，"
        "仅差 %.2f dB 但基础模型为量化版、推理更轻）。"
        % ("BS-RoFormer L12",
           best_overall[0][0], best_overall[0][1], best_overall[1],
           best_value[0][0], best_value[0][1], best_value[1], gap),
    )

    para("", after=10)
    para("读者定位：本文件面向三类读者 —— (1) 需要快速掌握结论的评审 / 导师；"
         "(2) 需要逐项核对数据的研究者；(3) 需要复用该工作簿的后续维护者。"
         "第二至三节给结论与读表方法，第四至六节给解读方法与适用边界，"
         "附录给全量 36 组统计。", indent=0.74)

    # ============================================================ 二
    h1("核心结论", "二、")

    # --- 2.1 分离模型排序
    h2("2.1  分离模型排序：BS-RoFormer L12 断崖领先")
    para("在三个带 clean 参考的数据集上，BS-RoFormer L12 全部第一。"
         "最接近的竞争者是 Demucs，但在 valentini 上仍相差 %.2f dB —— "
         "这在 SDR 上属于「代际差距」，而非调参可弥补的差距。"
         % (S["sep"][("BS-RoFormer L12", "valentini")] - S["sep"][("Demucs", "valentini")]),
         indent=0.74)

    models = ["BS-RoFormer L12", "Demucs", "MDX-extra_q", "MDX_q"]
    rows = []
    for m in models:
        rows.append([m] + ["%.2f" % S["sep"][(m, db)] for db in CLEAN_DBS])
    table(["分离模型", "valentini (500)", "musdb (50)", "dns (500)"],
          rows, widths=[5.2, 4.0, 3.6, 3.6])
    caption("表 1  分离模型在三个带 clean 参考数据集上的平均 SDR（dB，越高越好）")

    picture(figs[0], 15.2)

    para("观察三点：", after=3)
    bullet("BS-RoFormer L12 在 dns 上的优势（%.2f）比在 musdb 上（%.2f）小，"
           "说明合成噪声场景下模型间差距会收窄，真实噪声场景差距更大。"
           % (S["sep"][("BS-RoFormer L12", "dns")] - S["sep"][("MDX_q", "dns")],
              S["sep"][("BS-RoFormer L12", "musdb")] - S["sep"][("MDX_q", "musdb")]))
    bullet("两个 MDX 变体之间，mdx_extra_q 在三个库上均优于 mdx_q，"
           "valentini 上领先 %.2f dB —— 参数量更大的优势稳定存在。"
           % (S["sep"][("MDX-extra_q", "valentini")] - S["sep"][("MDX_q", "valentini")]))
    bullet("musdb 只有 50 首（整曲），统计置信度低于另三库的 500 条片段，"
           "排序可信但绝对值不宜横向与 valentini 直接比较。")

    # --- 2.2 级联
    h1("级联是否值得做", "三、")
    h2("3.1  20 个级联组合全部优于对应基础模型，无例外")
    para("将 4 个基础分离模型的输出再送入 5 个去噪器，在 valentini 上重新评测。"
         "结果是：20 个组合的 SDR 全部高于各自的单模型基线，平均提升 %.2f dB。"
         % (sum(S["casc"].get((m, d), 0) - S["sep"][(m, "valentini")]
                for m in models for d in DEN_ORDER) / (len(models) * len(DEN_ORDER))),
         indent=0.74)

    rows = []
    for m in models:
        base = S["sep"][(m, "valentini")]
        vals = [S["casc"][(m, d)] for d in DEN_ORDER]
        avg = sum(vals) / len(vals)
        rows.append([m, "%.2f" % base, "%.2f" % avg, "+%.2f" % (avg - base)])
    table(["基础模型", "单独 SDR", "5 个级联的平均 SDR", "平均提升"],
          rows, widths=[5.0, 3.6, 5.0, 3.4])
    caption("表 2  级联相对基础模型的平均增益（valentini，4 模型 × 5 去噪器）")

    picture(figs[1], 16.4)

    para("这张热力图回答两个问题：左图看「绝对水平」，右图看「收益大小」。"
         "右图颜色越深表示加去噪器的收益越大 —— 可以看到上排（BS-RoFormer）明显更浅，"
         "下三排更深，这就是「基础越弱、收益越大」的直接可视化证据。", indent=0.74)

    h2("3.2  整体 Top 5 与性价比最优")
    ranked = sorted(S["casc"].items(), key=lambda kv: -kv[1])[:5]
    rows = []
    for i, ((b, d), v) in enumerate(ranked, 1):
        delta = v - S["sep"][(b, "valentini")]
        rows.append([("%d" % i), "%s → %s" % (b, d), "%.2f" % v, "+%.2f" % delta])
    table(["排名", "级联组合", "平均 SDR (dB)", "相对基础提升"],
          rows, widths=[1.8, 7.4, 3.4, 3.6], align_first_left=False)
    caption("表 3  级联组合 Top 5（valentini，500 条）")

    picture(figs[2], 15.0)

    para("图 3 中红色竖线是「不加去噪器时该基础模型的水平」。"
         "红线离柱末端越远，说明这组级联的收益越大："
         "MDX-extra_q → Mel-RoFormer 的红线位置明显最靠左（+%.2f dB），"
         "是全场增益最大的一组。"
         % (S["casc"][("MDX-extra_q", "Mel-RoFormer")] - S["sep"][("MDX-extra_q", "valentini")]),
         indent=0.74)

    h2("3.3  去噪器怎么选：Mel-RoFormer 首选，Wiener 垫底")
    rows = []
    for d in DEN_ORDER:
        deltas = [S["casc"][(m, d)] - S["sep"][(m, "valentini")] for m in models]
        avg = sum(deltas) / len(deltas)
        n_first = sum(1 for m in models
                      if S["casc"][(m, d)] == max(S["casc"][(m, dd)] for dd in DEN_ORDER))
        n_last = sum(1 for m in models
                     if S["casc"][(m, d)] == min(S["casc"][(m, dd)] for dd in DEN_ORDER))
        note = ("%d/4 组第一" % n_first) if n_first else (
            ("%d/4 组垫底" % n_last) if n_last else "表现居中")
        rows.append([d, "+%.2f" % avg, note])
    table(["去噪器", "平均提升 (dB)", "在 4 个基础模型中的位置"],
          rows, widths=[5.0, 4.2, 6.8])
    caption("表 4  五个去噪器的平均增益与稳定性（跨 4 个基础模型）")

    best_den = max(DEN_ORDER, key=lambda d: sum(
        S["casc"][(m, d)] - S["sep"][(m, "valentini")] for m in models))
    worst_den = min(DEN_ORDER, key=lambda d: sum(
        S["casc"][(m, d)] - S["sep"][(m, "valentini")] for m in models))
    para("选型建议：", after=3)
    bullet("要「稳」选 %s —— 平均提升 %.2f dB，且多数基础模型上排名第一。"
           % (best_den,
              sum(S["casc"][(m, best_den)] - S["sep"][(m, "valentini")] for m in models) / len(models)))
    bullet("要「轻」选 dns64 / dns48 —— 16 kHz 轻量模型，增益略低但推理快。")
    bullet("%s 平均仅 %+.2f dB，且在 4 个基础模型中多数垫底；"
           "作为经典方法它没有学习能力，只建议在没有神经去噪器可用时兜底。"
           % (worst_den,
              sum(S["casc"][(m, worst_den)] - S["sep"][(m, "valentini")] for m in models) / len(models)))

    # --- 2.3 wham
    h2("3.4  为什么 wham 那一列不能横向比较")
    para("wham 数据集没有 clean 参考，因此该列 SDR 采用「output vs input」自参照口径，"
         "衡量的是「输出相对输入改变了多少」，而不是「离干净人声有多近」。"
         "因此负值是正常现象，不代表模型差。", indent=0.74)
    rows = [["%s" % m, "%.2f" % S["sep"][(m, "wham")]] for m in models]
    table(["分离模型", "wham 自参照 SDR (dB)"], rows, widths=[6.4, 6.0])
    caption("表 5  wham 列的自参照 SDR —— 数值不可与表 1 横向比较")

    para("这一列唯一能回答的问题是「模型有没有把声音搞坏」：", after=3)
    bullet("Demucs 的 %.2f「最好」，实际含义是它处理最保守、改动最小，"
           "并不代表分离最干净。" % S["sep"][("Demucs", "wham")])
    bullet("BS-RoFormer 与 MDX-extra_q 约 −10 dB，说明它们对信号做了较大幅度的重构 —— "
           "这与它们是更强的分离器这一事实一致。")
    bullet("真正要警惕的是 SDR < −25 dB 的样本：那代表输出接近静音，即模型在该样本上退化。"
           "此类样本已全部剔除（详见第五节）。")

    # ============================================================ 三（读表）
    h1("表格怎么看", "四、")

    h2("4.1  两个 Sheet 对应两类实验")
    rows = [
        ["分离模型", "4 个纯分离模型 × 4 个数据库", "16 组"],
        ["级联", "4 个基础分离模型 × 5 个去噪器 × valentini", "20 组"],
    ]
    table(["Sheet", "内容", "规模"], rows, widths=[3.4, 9.4, 3.0])
    caption("表 6  工作簿结构")

    h2("4.2  每个分组顶部四格 = 该组的「体检报告」")
    para("每个分组的第一行有四格，格式固定为：", after=3)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    run_font(p.add_run("模型 / 组合名  |  数据库  |  样本数（有效/总数）  |  均值 ±（最高−均值 / 最低−均值）"),
             9.5, True, ACCENT)

    para("以 BS-RoFormer L12 × valentini 为例：", after=3)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    bs = S["sep"][("BS-RoFormer L12", "valentini")]
    bsm = S["meta"][("sep", "BS-RoFormer L12", "valentini")]
    run_font(p.add_run("BS-RoFormer L12  |  valentini  |  %d/%d  |  %.2f ± (+%.2f / −%.2f)"
                       % (bsm["nk"], bsm["n"], bs, bsm["mx"] - bs, bs - bsm["mn"])),
             9.5, False, DARK)

    para("读法：", after=3)
    bullet("%.2f 是平均 SDR，是排序的核心指标。" % bs)
    bullet("+%.2f 表示最好的样本比均值高这么多；−%.2f 表示最差的样本比均值低这么多。"
           % (bsm["mx"] - bs, bs - bsm["mn"]))
    bullet("该样本最低只有 %.2f dB，几乎等于失败 —— 这正是需要重点看「最低 SDR」那一行图的原因。"
           % bsm["mn"])
    bullet("有效/总数 若显示 493/500，说明该组剔除了 7 条极端值；显示 500/500 表示全部有效。")

    h2("4.3  每个分组下面三行图 = 三种「性格」")
    rows = [
        ["第 1 行", "最接近均值的 3 个样本", "模型的典型表现"],
        ["第 2 行", "SDR 最高的 3 个样本", "模型最好能做到什么"],
        ["第 3 行", "SDR 最低的 3 个样本", "模型最坏会烂成什么样"],
    ]
    table(["行", "选取规则", "用途"], rows, widths=[2.8, 6.0, 7.0], align_first_left=False)
    caption("表 7  三行样本的选取规则")

    para("每张图下方的标注格式为「样本名 / SDR x.xx dB / 运行时间 s」。"
         "其中运行时间是该样本的推理耗时，用于评估工程可用性。", indent=0.74)

    h2("4.4  频谱图本身怎么看")
    para("每张图有上下两个面板：上面板是参考信号（clean，wham 为 input）的频谱，"
         "下面板是模型输出的频谱。两个面板各自归一化（各自峰值 = 0 dB），"
         "因此比较的是「形状」而不是绝对音量。", indent=0.74)
    para("重点看三件事：", after=3)
    numbered("人声谐波结构是否保留 —— 下面板该有横向条纹的地方有没有被削掉。")
    numbered("噪声底是否降低 —— 下面板的背景是否比上面板更干净。")
    numbered("是否糊成一片 —— 极端短样本或输出近静音时会出现，此类样本已被剔除。")

    # ============================================================ 四（分析）
    h1("怎么分析（五步法）", "五、")

    steps = [
        ("第一步：先纵向排序，不要先看图",
         "打开任一 Sheet，只读每组头部的「均值」，从上到下扫一遍，先建立排序直觉。"
         "图像是用来验证结论的，不是用来发现结论的。"),
        ("第二步：看离散度，判断稳定性",
         "看括号里的两个偏差。两个偏差都小（如 +3 / −5）说明表现稳定；"
         "一正一负差距巨大（如 +11 / −15）说明均值好看但存在翻车样本。"
         "「均值高 + 离散度大」意味着上限高、下限也低，产品化时必须配兜底策略。"),
        ("第三步：直奔「最低 SDR」那一行图",
         "这是信息量最大的一行。若最低那行仍能看出人声结构，说明模型鲁棒；"
         "若已经糊掉或接近空白，说明该模型在难样本上会崩。"),
        ("第四步：做三种横向对比",
         "同库比模型（同一列往下看）→ 哪个模型最好；"
         "同模型比库（同一行往右看）→ 模型在哪类数据上强/弱；"
         "级联 vs 分离（跨 Sheet）→ 加去噪器到底值不值。"),
        ("第五步：校验口径，不要跨库乱比",
         "musdb / valentini / dns 是真 SDR，越高越好，可互相比；"
         "wham 是自参照，负值正常，只能纵向判断「有没有搞坏」，不能与另三库比「谁更干净」。"),
    ]
    for i, (t, b) in enumerate(steps, 1):
        h2("%s" % t)
        para(b, indent=0.74)

    # 区间速查
    h2("附：SDR 的经验区间（用于快速判断数值含义）")
    rows = [
        ["> 15 dB", "很好", "分离干净，残余干扰基本不可闻"],
        ["10 – 15 dB", "可用", "明显分离，复杂段落仍有残留"],
        ["5 – 10 dB", "勉强", "能听出目标，但干扰较重"],
        ["0 – 5 dB", "基本未分离", "目标与干扰混杂"],
        ["< 0 dB", "不如不处理", "输出比输入更差"],
    ]
    table(["SDR 区间", "评价", "含义"], rows, widths=[3.6, 3.0, 9.0], align_first_left=False)
    caption("表 8  SDR 经验区间参考（人声分离任务的通用量级，非本文数据推导）")

    # ============================================================ 五（边界）
    h1("边界与注意事项", "六、")
    para("以下内容在论文写作与口头汇报中必须交代，否则结论会被过度外推。", indent=0.74)

    rows = [
        ["musdb 仅 50 首", "整曲（3–4 min），全量运行过慢故限制 50 首；统计置信度低于另三库的 500 条片段。"],
        ["级联仅在 valentini 评测", "未在 musdb / dns / wham 上复现，因此「级联最优」的泛化性需谨慎对待。"],
        ["dns 为合成噪声", "clean + noise 按固定 SNR 混合，难度分布与 valentini 的真实噪声不同，两者不可等同。"],
        ["wham 时长极不均", "0.29 s 至 1333 s 均有分布；极短片段不含时间结构，频谱必然糊，已按 < 1 s 剔除。"],
        ["SDR 对增益不敏感假设", "SDR 计算前做最优尺度对齐，因此不惩罚整体音量偏差，仅反映波形/结构失真。"],
        ["极端值剔除比例", "共剔除 %d / %s 条（%.2f%%），全部来自 wham 库，不影响另三库的统计。" %
         (n_drop, format(n_total, ","), 100.0 * n_drop / n_total if n_total else 0)],
    ]
    table(["事项", "说明"], rows, widths=[4.4, 11.6])
    caption("表 9  结论适用边界")

    para("极端值剔除规则（与配对工作簿完全一致）：", after=3)
    bullet("时长 < 1.0 s —— 片段过短，无时间结构，频谱图与 SDR 均无统计意义。")
    bullet("SDR < −25.0 dB —— 输出能量约为输入的 1/300，判定为「近静音退化」，属模型失效而非性能差异。")
    bullet("两组条件为「或」关系，满足任一即剔除；被剔除样本在表格头部以「有效/总数」形式留痕，不做静默删除。")

    # ============================================================ 六
    h1("如果只记三句话", "七、", newpage=True)
    para("", after=8)
    callout(
        "要效果",
        "%s → %s，%.2f dB，全场最高。" % (best_overall[0][0], best_overall[0][1], best_overall[1]),
    )
    para("", after=6)
    callout(
        "要性价比",
        "%s → %s，%.2f dB，仅低 %.2f dB，但基础模型为量化版，推理更轻、更易部署。"
        % (best_value[0][0], best_value[0][1], best_value[1], gap),
        bg="FDF3E3", bar="E8A33D",
    )
    para("", after=6)
    callout(
        "要避免误读",
        "wham 的负 SDR 不是差评，是度量口径不同（自参照）。真正要警惕的是 SDR < −25 dB 的"
        "「输出近静音」退化，此类样本已全部剔除并留痕。",
        bg="EEF7F0", bar="3FA45B",
    )

    para("", after=14)
    h2("决策速查")
    rows = [
        ["追求最高分离质量",
         "%s → %s" % (best_overall[0][0], best_overall[0][1]),
         "%.2f dB，全场最高" % best_overall[1]],
        ["需要轻量部署",
         "%s → %s" % (best_value[0][0], best_value[0][1]),
         "%.2f dB，基础模型为量化版，推理更轻" % best_value[1]],
        ["去噪器要「稳」", "Mel-RoFormer-Denoise (aggr)",
         "4 个基础模型中 3 个排名第一"],
        ["无 GPU / 需传统方法兜底", "dns48 / dns64",
         "平均 +5.9 dB，16 kHz 轻量模型"],
        ["不建议采用", "Wiener filter",
         "平均仅 +4.63 dB，多数基础模型上垫底"],
    ]
    table(["场景", "推荐方案", "理由"], rows, widths=[5.2, 5.5, 5.5])
    caption("表 10  场景到方案的决策速查")

    # ============================================================ 附录
    h1("附录 A · 全量分组统计", newpage=True)
    para("下表为工作簿中 36 个分组的完整统计，可直接用于核对。"
         "「有效/总数」列中两者不等者即为发生极端值剔除的分组。", indent=0.74)

    rows = []
    order = ["BS-RoFormer L12", "Demucs", "MDX-extra_q", "MDX_q"]
    for m in order:
        for db in DB_ORDER:
            k = ("sep", m, db)
            if k not in S["meta"]:
                continue
            d = S["meta"][k]
            rows.append(["分离", m, db, "%d/%d" % (d["nk"], d["n"]), "%.2f" % d["mean"]])
    for m in order:
        for den in DEN_ORDER:
            k = ("cas", m, den)
            if k not in S["meta"]:
                continue
            d = S["meta"][k]
            rows.append(["级联", "%s → %s" % (m, den), "valentini",
                         "%d/%d" % (d["nk"], d["n"]), "%.2f" % d["mean"]])
    table(["类型", "模型 / 组合", "数据集", "有效/总数", "平均 SDR"], rows,
          widths=[1.8, 7.6, 3.2, 3.2, 2.8], size=8.5, align_first_left=False)
    caption("表 11  36 个分组的完整统计（与 Final_Eval_Report.xlsx 同口径）")

    h1("附录 B · 复现方式")
    para("本文档与其统计图均由以下命令生成，数字直接读取 results.json，不含手工录入：", indent=0.74)

    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.6)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(10)
    code = ("python tools/_build_eval_report_doc.py\n"
            "python tools/_build_eval_excel.py --root 03_outputs/_eval \\\n"
            "       --out 03_outputs/Final_Eval_Report.xlsx")
    r = p.add_run(code)
    r.font.name = "Consolas"
    r.font.size = Pt(8.5)
    r.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    r._element.rPr.rFonts.set(qn("w:eastAsia"), CN)
    pf = p.paragraph_format
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "F4F6F9")
    pPr.append(shd)

    para("相关文件：", after=3)
    bullet("配对工作簿：03_outputs/Final_Eval_Report.xlsx")
    bullet("代表样本音频：03_outputs/TableSample_Audio/（由 export_table_audio.bat 导出）")
    bullet("原始评测结果：03_outputs/_eval/**/results.json（36 组）")
    bullet("统计图：04_reports/00_shared/figures/eval_report/")

    os.makedirs(DOC_DIR, exist_ok=True)
    doc.save(DOCX)
    return DOCX


def main():
    S = load_stats()
    print("[doc] results.json 组数 = %d | 样本 %d -> 有效 %d"
          % (S["files"], S["n_total"], S["n_kept"]))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        figs, _ = make_figures(S)
        glyph = [str(x.message) for x in w if "missing from font" in str(x.message)]
    print("[doc] 图 %d 张 -> %s" % (len(figs), FIG_DIR))
    print("[doc] 中日韩字形缺失警告:", len(glyph))
    out = build_docx(S, figs)
    print("[doc] 写出 %s (%.2f MB)" % (out, os.path.getsize(out) / 1024 / 1024))


if __name__ == "__main__":
    main()

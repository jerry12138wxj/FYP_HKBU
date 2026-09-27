# -*- coding: utf-8 -*-
"""T3.4 · 按参考表样式重绘 Average SDR 表（MD + PNG）。

产出
----
    04_reports/01_separation/docs/MEDIAN_TABLE_REDRAWN.md        <- D5 交付物（主/副表 + 口径脚注）
    04_reports/01_separation/figures/comparison/fig_avg_sdr_table.png  <- 论文/答辩可直接贴

数据源（全部现读，不写死任何数字）
----------------------------------
| 文件 | 提供 |
|---|---|
| `data/comparison/model_runs_median.json` | 主表：3 均衡片段中位数 SDR / SI-SDR / RTF |
| `data/comparison/model_runs.json` | 每条记录的 `subset`（判定主表跑在 train 还是 test） |
| `00_shared/data/model_analysis/model_profile.csv` | Size (M) / FLOPs (G) / 单次时延 |
| `data/comparison/test_run_model_summary.csv` | 副表：test 集 50 首整曲耗时 / RTF / 轨数 |
| `data/comparison/metric_window_probe.json` | 窗宽口径实测偏差（脚注用） |
| `data/comparison/mixture_baseline.json` | mixture 基线行 |

设计要点
--------
1. **参考表样式** = 「Average SDR 主列 + 分轨列 + Size + FLOPs」，按四轨均值降序。
2. **分组纪律不破**：四轨完整组 / 单目标组 / 解析组分表；mixture 基线与 Oracle 上界
   单列且**不参与排名**，避免"把 oracle 当模型"。
3. 脚注不写"参考表如何"，只写**本表口径三要素 + 实测差异**，可答辩护身。
4. 所有数字现读 JSON/CSV；任何一项读不到就报错退出（不静默填 0）——本项目反复踩
   "跑通但指标静默错"。

用法
----
    python tools/_make_sdr_table.py
    python tools/_make_sdr_table.py --no-figure
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

# ---- 路径中枢：五大模块布局，见 tools/paths.py ----
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import paths as _paths

_paths.setup_env()

CMP = _paths.comparison_dir()
MEDIAN = CMP / "model_runs_median.json"
RUNS = CMP / "model_runs.json"
SUMMARY = CMP / "test_run_model_summary.csv"
WINDOW_PROBE = CMP / "metric_window_probe.json"
BASELINE = CMP / "mixture_baseline.json"
PROFILE = _paths.MODEL_ANALYSIS / "model_profile.csv"

OUT_MD = _paths.DOCS / "MEDIAN_TABLE_REDRAWN.md"
OUT_PNG = _paths.FIGURES_COMPARISON / "fig_avg_sdr_table.png"

STEMS = ["vocals", "drums", "bass", "other"]
STEM_ZH = {"vocals": "人声", "drums": "鼓", "bass": "贝斯", "other": "其他"}

# 显示名（与 MODEL_REGISTRY 一致）
SHOW = {
    "oracle": "IRM/IBM Oracle",
    "rpca": "RPCA (Inexact-ALM)",
    "umx": "Open-Unmix (umxhq)",
    "mdx": "MDX-Net (mdx_extra)",
    "convtasnet": "Conv-TasNet",
    "mmdenselstm": "MMDenseLSTM",
    "bsroformer_l12": "BS-RoFormer L12",
    "bsroformer_l6": "BS-RoFormer L6",
    "bsrnn_all": "oBSRNN (4 ckpt)",
    "bsrnn_large_all": "BSRNN large (4 ckpt)",
    "bsrnn_simo": "oBSRNN-SIMO (14/50)",
    "demucs": "Demucs (htdemucs)",
    "dprnn": "DPRNN (自训 5 h, 4-stem)",
}

# 参考表数值（用户提供，登记在 FYP_ROADMAP_2026-09-22.md §7）。
# 只用于脚注「差异说明」，不参与任何计算；来源已在正文标明。
REF_ROWS = [
    ("Demucs", "6.03", "128 M", "参考表是**原版 Demucs (v1)**；本项目用 **HTDemucs**（混合时域/频域），不是同一个模型"),
    ("DPRNN-TasNet", "6.01", "—", "参考表是**官方 MUSDB 训练权重**；本项目是**自训 5 h**（官方只发语音权重），欠训练"),
    ("MMDenseLSTM", "6.00", "4.88 M", "片段选择不同：本项目排除「开头低频引子」类能量陷阱片段"),
    ("Conv-TasNet", "5.70", "—", "同上；本项目为 musdb18 预训练权重"),
    ("Open-Unmix (UMX)", "5.30", "8.90 M", "同上"),
    ("RPCA+DRNN", "5.80", "—", "论文未公开代码，**本机无法复现**（既有审计结论）；口径为单声道 2 源，不与四轨同轴"),
]


def _fmt(v, nd=2):
    if v is None or v == "":
        return "—"
    try:
        return "%.*f" % (nd, float(v))
    except (TypeError, ValueError):
        return str(v)


def _load():
    med = json.loads(MEDIAN.read_text(encoding="utf-8"))
    prof = {}
    with open(PROFILE, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            prof[r["model_key"]] = r
    summ = {}
    with open(SUMMARY, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            summ[r["model_key"]] = r
    probe = json.loads(WINDOW_PROBE.read_text(encoding="utf-8")) if WINDOW_PROBE.is_file() else None
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else None
    runs = json.loads(RUNS.read_text(encoding="utf-8"))["runs"]
    subsets = sorted({rec.get("subset") for rec in
                      (runs.get(list(runs)[0]) or {}).values() if isinstance(rec, dict)})
    return med, prof, summ, probe, base, subsets


def _split(med):
    """按分组切分：四轨完整组 / 单目标组 / 无归属组。"""
    four, single, norec = [], [], []
    for k, e in med.items():
        if e.get("single_target"):
            single.append((k, e))
        elif e.get("sdr_avg4") is None:
            norec.append((k, e))
        else:
            four.append((k, e))
    four.sort(key=lambda kv: -(kv[1].get("sdr_avg4") or -99))
    single.sort(key=lambda kv: -(kv[1]["single_target"]["sdr_median"] or -99))
    return four, single, norec


def _rank_core(four):
    """排名核心 = 深度四轨模型；Oracle 是解析上界、DPRNN 是负面对照，单列不排名。"""
    core = [(k, e) for k, e in four if k not in ("oracle", "dprnn")]
    extra = [(k, e) for k, e in four if k in ("oracle", "dprnn")]
    return core, extra


# ------------------------------------------------------------------ MD
def build_md(med, prof, summ, probe, base, subsets) -> str:
    four, single, norec = _split(med)
    core, extra = _rank_core(four)
    L = []
    A = L.append

    A("# Average SDR 主表（参考表样式重绘）")
    A("")
    A("> 交付物 **D5** ｜ 任务 **T3.4** ｜ 生成 %s ｜ 生成脚本 `tools/_make_sdr_table.py`" % time.strftime("%Y-%m-%d %H:%M"))
    A("> 数据源：`data/comparison/model_runs_median.json`（本机实测，非论文引用值）"
      " ｜ 数字可由脚本一键重生成")
    A("")
    A("> 📌 **一句话**：本表列序照参考表（**Average SDR + 分轨 + Size + FLOPs**），"
      "但**数值全部是本机复现口径**，不与参考表逐格对齐 —— 口径要素见 §5，差异原因见 §6。"
      "**答辩必读 §5 / §6**。")
    A("")

    # ---------------- 1 主表
    A("## 1. 主表 · 四轨完整组（唯一可横向比较的一张表）")
    A("")
    A("| # | 模型 | **Average SDR** | 人声 | 鼓 | 贝斯 | 其他 | Size (M) | FLOPs (G) | RTF |")
    A("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    if base:
        A("| — | **Mixture（基线）** | **%s** | %s | %s | %s | %s | — | — | — |" % (
            _fmt(base.get("avg4")),
            _fmt(base["per_stem"]["vocals"]["median"]),
            _fmt(base["per_stem"]["drums"]["median"]),
            _fmt(base["per_stem"]["bass"]["median"]),
            _fmt(base["per_stem"]["other"]["median"])))
    for i, (k, e) in enumerate(core, 1):
        p = prof.get(k, {})
        s = e.get("sdr") or {}
        A("| %d | %s | **%s** | %s | %s | %s | %s | %s | %s | %s |" % (
            i, SHOW.get(k, e["label"]), _fmt(e.get("sdr_avg4")),
            *[_fmt((s.get(st) or {}).get("median")) for st in STEMS],
            _fmt(p.get("params_M"), 2), _fmt(p.get("flops_G"), 1) if p.get("flops_G") else "—",
            _fmt(e.get("rtf"), 3)))
    A("")
    A("**不参与排名、单独列出的两行**（跨组不可比，见 §5 口径脚注）：")
    A("")
    A("| 类别 | 模型 | Average SDR | 人声 | 鼓 | 贝斯 | 其他 | Size (M) | FLOPs (G) | RTF |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k, e in extra:
        p = prof.get(k, {})
        s = e.get("sdr") or {}
        tag = "解析上界（无参数）" if k == "oracle" else "负面对照（自训欠拟合）"
        A("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            tag, SHOW.get(k, e["label"]), _fmt(e.get("sdr_avg4")),
            *[_fmt((s.get(st) or {}).get("median")) for st in STEMS],
            _fmt(p.get("params_M"), 2), _fmt(p.get("flops_G"), 1) if p.get("flops_G") else "—",
            _fmt(e.get("rtf"), 3)))
    A("")
    if norec:
        names = "、".join(SHOW.get(k, e["label"]) for k, e in norec)
        A("> 另有 **%s**：稀疏分量**没有天然 stem 归属**，不出四轨均值、不进本表排名。" % names)
        A("")

    # ---------------- 2 单目标
    A("## 2. 单目标组（只产 1 条轨，**不可**与 §1 同轴比较）")
    A("")
    A("| # | 模型 | 目标轨 | museval SDR | SI-SDR | Size (M) | FLOPs (G) | RTF |")
    A("|---:|---|---|---:|---:|---:|---:|---:|")
    for i, (k, e) in enumerate(single, 1):
        p = prof.get(k, {})
        st = e["single_target"]
        A("| %d | %s | `%s` | **%s** | %s | %s | %s | %s |" % (
            i, SHOW.get(k, e["label"]), st["name"], _fmt(st["sdr_median"]),
            _fmt(st.get("si_sdr_median")), _fmt(p.get("params_M"), 2),
            _fmt(p.get("flops_G"), 1) if p.get("flops_G") else "—", _fmt(e.get("rtf"), 3)))
    A("")

    # ---------------- 3 SI-SDR
    A("## 3. 附表 · 分轨 SI-SDR（尺度不变，跨数据集可比）")
    A("")
    A("| 模型 | 人声 | 鼓 | 贝斯 | 其他 |")
    A("|---|---:|---:|---:|---:|")
    for k, e in core + extra:
        si = e.get("si_sdr") or {}
        A("| %s | %s |" % (SHOW.get(k, e["label"]),
                           " | ".join(_fmt((si.get(st) or {}).get("median")) for st in STEMS)))
    A("")
    A("> 单目标模型只评目标轨，其 SI-SDR 已列在 §2，不与本表同轴。")
    A("")

    # ---------------- 4 副表（test 集整曲）
    A("## 4. 副表 · MUSDB18-HQ **test** 集 50 首整曲（**口径与 §1 不同**，只看耗时与规模）")
    A("")
    A("| 模型 | 跑满 50 首 | 输出轨 | 墙钟中位 (s/首) | 推理中位 (s/首) | RTF 中位 | SDR 中位 ‡ | 输出体积 (MB) |")
    A("|---|---:|---|---:|---:|---:|---:|---:|")
    order = ["demucs", "mdx", "umx", "convtasnet", "mmdenselstm", "dprnn", "oracle",
             "bsrnn_simo", "bsrnn", "bsrnn_large", "bsroformer_l6", "bsroformer_l12",
             "rpca", "bsrnn_all", "bsrnn_large_all"]
    for k in order:
        r = summ.get(k)
        if not r:
            continue
        ok = "是" if r["complete_50"] == "True" else "**否（%s/50）**" % r["status_PASS"]
        A("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["model"], ok, r.get("n_tracks_set") or "—",
            _fmt(float(r["wall_median_s"]), 1) if r.get("wall_median_s") else "—",
            _fmt(float(r["infer_median_s"]), 1) if r.get("infer_median_s") else "—",
            _fmt(float(r["rtf_median"]), 3) if r.get("rtf_median") else "—",
            _fmt(float(r["sdr_mean_median"]), 2) if r.get("sdr_mean_median") else "—",
            _fmt(float(r["out_mb_total"]), 1) if r.get("out_mb_total") else "—"))
    A("")
    A("> ‡ `sdr_mean_median`：**每首歌**先对该模型输出的各轨 SDR 取平均，再对 50 首取中位数。"
      "→ **四轨模型 = 四轨均值；单目标模型（BSRNN-opt / BSRNN-large / BS-RoFormer L6 / L12）= 目标轨 SDR**，"
      "两类**不可同轴比较**。且本列为 `test` 集整曲、§1 为 `train` 集 10 s 片段，两列也不是一条轴。")
    A("")

    # ---------------- 5 脚注：口径
    A("## 5. 口径脚注（引用本表必须一并声明）")
    A("")
    A("| 项 | 本表取值 | 说明 |")
    A("|---|---|---|")
    A("| 指标 | **museval BSSEval v4** 的 SDR | `compute_permutation=False`；与 museval 官方口径一致 |")
    A("| 声道 | **单声道**（`mean(axis=-1)`） | 四轨模型仍以立体声输入，评测前降为 mono |")
    sub = "、".join(subsets) if subsets else "train"
    A("| 数据集 / 子集 | **MUSDB18-HQ `%s`** | 🔴 主表跑在 **`%s`** 子集（`model_runs.json` 每条记录的 `subset` 字段可核），"
      "即**训练集本身** → 属 **in-domain 口径，数字偏乐观**；副表 §4 为 `test` 集 |" % (sub, sub))
    A("| 片段 | 3 个**能量均衡**片段 × 10 s | 每轨占比 14~43%；刻意避开「开头低频引子」类能量陷阱片段 |")
    A("| 聚合 | **中位数** | 先对窗取 `nanmedian`，再对 3 个片段取中位数（median-of-median） |")
    if probe:
        sm = probe["summary"]
        A("| **分析窗** | **window = 2 s / hop = 1.5 s**（88200 / 66150 样本） | 🔴 `evaluate()` **未传** `window`/`hop`，"
          "落到 museval 签名默认值；而多处脚本文档写的是「1 s 窗」，**与实现不符** |")
        A("| 窗宽影响（实测） | |Δ| 均值 **%.3f dB**、90 分位 **%.3f dB**、最大 **%.3f dB**（n=%d 格，`metric_window_probe.json`）"
          " | 在 T3.1 选出的高能量片段上实测；按轨看 **bass 最敏感**（mean %+.3f dB），other 最稳（mean %+.3f dB） |" % (
              sm["abs_delta_mean"], sm["abs_delta_p90"], sm["abs_delta_max"], sm["n_cells"],
              sm["per_stem"].get("bass", {}).get("delta_mean", 0.0),
              sm["per_stem"].get("other", {}).get("delta_mean", 0.0)))
    A("| 基线 | **mixture**（%s dB，四轨均值） | 基线行在 §1 顶部；模型相对基线的增益才是可读结论 |"
      % (_fmt(base.get("avg4")) if base else "—"))
    A("| RTF | 推理秒数 ÷ 音频秒数 | **受机器负载影响**，本机为 RTX 4070 Laptop 8 GiB 单卡；同一模型两次可差 2×，只做量级参考 |")
    A("| FLOPs | `FlopCounterMode`，**口径 = 2×MACs** | ⚠️ 只统计 torch 调度的算子，**`torch.stft` 与融合注意力不计入 → 是下界**；"
      "跨架构比较须配合实测时延 |")
    A("| Size | `sum(p.numel())`，取模型实例 | 非配置文件声明值；多 ckpt 模型为**合计** |")
    A("")
    A("> 🔴 **两处必须主动交代的口径缺陷**（不要等被问）：")
    A("> 1. **主表在 `train` 子集上**：MUSDB18 train 正是多数对比模型的训练集 → 属 in-domain，"
      "数值系统性偏乐观；与参考表（`test`）差得远，**这不是实现错误而是口径差异**。")
    A("> 2. **实际窗宽 2 s / hop 1.5 s，不是文档写的 1 s**：已量化为 |Δ| 均值 %s dB（见上表）。"
      "若要与其他论文对齐，需把 `evaluate()` 补上 `window=44100, hop=44100` 后整表重跑。" % (
          _fmt(probe["summary"]["abs_delta_mean"], 3) if probe else "—"))
    A("")

    # ---------------- 6 与参考表差异
    A("## 6. 与参考表的差异说明（答辩预案）")
    A("")
    A("| 模型 | 参考表 Average SDR | 本机 | 差异主因（按贡献排序） |")
    A("|---|---:|---:|---|")
    ours = {k: e for k, e in core + extra + single}
    keymap = {"Demucs": "demucs", "DPRNN-TasNet": "dprnn", "MMDenseLSTM": "mmdenselstm",
              "Conv-TasNet": "convtasnet", "Open-Unmix (UMX)": "umx", "RPCA+DRNN": None}
    for name, refv, refsize, why in REF_ROWS:
        k = keymap.get(name)
        mine = _fmt(ours[k].get("sdr_avg4")) if k in ours else "**无产出**"
        A("| %s | %s | %s | %s |" % (name, refv, mine, why))
    A("")
    A("> 参考表数值（含 Size 口径）来自用户提供的参考表，登记于 `00_shared/docs/FYP_ROADMAP_2026-09-22.md` §7 与 "
      "`MODEL_PROFILE_2026-09-22.md` §5，**本文件不对其做任何重新计算**。")
    A(">")
    A("> **三条通用差异**：① **子集不同**（本表 train / 参考表 test）；"
      "② **实现版本不同**（HTDemucs vs Demucs v1；自训 DPRNN vs 官方权重）；"
      "③ **评价口径不同**（mono、2 s 窗、3 均衡片段中位数 vs 参考表的整曲/其他池）。")
    A(">")
    A("> **答辩一句话**：「本表是同任务、同数据集族、**本机复现口径**下的实测结果；"
      "与参考表的数值差异来自实现版本与评价片段选择，逐格对齐需要原版 Demucs(v1) 与官方 DPRNN 权重，"
      "成本高、收益低 —— 我们选择把差异写清楚而不是硬凑数字。」")
    A("")

    # ---------------- 7 复现
    A("## 7. 复现命令")
    A("")
    A("```bash")
    A("# ① 重算主表（需 GPU；3 片段 × 模型）")
    A("python tools/bench_multisong.py")
    A("python tools/median_over_clips.py --write 04_reports/01_separation/docs/MEDIAN_TABLE.md")
    A("# ② 口径取证（窗宽偏差 + mixture 基线）")
    A("python tools/_metric_provenance.py all")
    A("# ③ 重绘本表（MD + PNG，纯 CPU）")
    A("python tools/_make_sdr_table.py")
    A("```")
    A("")
    A("> 解释器必须用 venv：`C:\\Users\\jerry\\.workbuddy\\binaries\\python\\envs\\fyp_audio\\Scripts\\python.exe`")
    A("")
    return "\n".join(L)


# ------------------------------------------------------------------ PNG
def build_png(med, prof, base):
    four, _, _ = _split(med)
    core, extra = _rank_core(four)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    header = ["#", "模型", "Average\nSDR", "人声", "鼓", "贝斯", "其他", "Size\n(M)", "FLOPs\n(G)"]
    rows, colors = [], []
    if base:
        ps = base["per_stem"]
        rows.append(["—", "Mixture（基线）", _fmt(base.get("avg4")),
                     _fmt(ps["vocals"]["median"]), _fmt(ps["drums"]["median"]),
                     _fmt(ps["bass"]["median"]), _fmt(ps["other"]["median"]), "—", "—"])
        colors.append("#EDEDED")
    best = core[0][1]["sdr_avg4"] if core else None
    for i, (k, e) in enumerate(core, 1):
        p = prof.get(k, {})
        s = e.get("sdr") or {}
        rows.append([str(i), SHORT.get(k, SHOW.get(k, e["label"])), _fmt(e.get("sdr_avg4")),
                     *[_fmt((s.get(st) or {}).get("median")) for st in STEMS],
                     _fmt(p.get("params_M"), 2),
                     _fmt(p.get("flops_G"), 1) if p.get("flops_G") else "—"])
        colors.append("#DCEBD8" if e.get("sdr_avg4") == best else "#FFFFFF")
    for k, e in extra:
        p = prof.get(k, {})
        s = e.get("sdr") or {}
        tag = "解析上界" if k == "oracle" else "负面对照"
        rows.append(["—", "%s（%s）" % (SHORT.get(k, SHOW.get(k, e["label"])), tag), _fmt(e.get("sdr_avg4")),
                     *[_fmt((s.get(st) or {}).get("median")) for st in STEMS],
                     _fmt(p.get("params_M"), 2),
                     _fmt(p.get("flops_G"), 1) if p.get("flops_G") else "—"])
        colors.append("#F3F0E6")

    fig_w, fig_h = 12.6, 0.62 * (len(rows) + 4.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    ax.set_title("Average SDR（museval BSSEval v4）· 四轨完整组\n"
                 "MUSDB18-HQ train · 3 个能量均衡片段 × 10 s 中位数 · 本机实测",
                 fontsize=13, fontweight="bold", pad=14)
    tbl = ax.table(cellText=rows, colLabels=header, loc="center", cellLoc="center",
                   colWidths=[0.045, 0.235, 0.115, 0.085, 0.085, 0.085, 0.085, 0.09, 0.095])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10.5)

    # 边框：细灰网格 + 表头深底白字；表头行与末行加粗框线，做出三线表观感。
    # （不用 Cell.visible_edges —— 与 facecolor 同时用会让表头背景消失，已实测；
    #   也不手工 ax.plot 画线 —— `loc=` 模式下 Table 单元格坐标不是纯 axes 坐标，实测会画飞）
    last = len(rows)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0 or r == last:
            cell.set_edgecolor("#2F4B7C")
            cell.set_linewidth(1.6)
        else:
            cell.set_edgecolor("#CFCFCF")
            cell.set_linewidth(0.6)
        if r == 0:
            cell.set_facecolor("#1F3A66" if c == 2 else "#2F4B7C")
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor(colors[r - 1])
            if c == 2:
                cell.set_text_props(fontweight="bold")

    # 行高显式设定，避免两行表头被裁掉（默认高度按字号推，表格字号非默认时不可靠）
    H_HEAD, H_ROW = 0.072, 0.062
    for c in range(len(header)):
        tbl[(0, c)].set_height(H_HEAD)
    for r in range(1, len(rows) + 1):
        for c in range(len(header)):
            tbl[(r, c)].set_height(H_ROW)

    note = ("脚注（与正文不同，此处为纯文本）：\n"
            "1. 指标 = museval BSSEval v4（compute_permutation=False），单声道；分析窗取 museval 默认 2 s / hop 1.5 s。\n"
            "2. 数据子集 = MUSDB18-HQ train（in-domain，数字偏乐观）；3 个能量均衡片段各 10 s，取中位数。\n"
            "3. 单目标模型（BS-RoFormer / BSRNN 单轨）不产 4 stem，不入本表；RPCA 稀疏分量无 stem 归属，亦不入表；\n"
            "   IRM/IBM Oracle 为解析上界、DPRNN 为自训负面对照，均不参与排名。\n"
            "4. FLOPs = FlopCounterMode（口径 2xMACs）下界，不含 torch.stft 与融合注意力；5. 基线 = mixture 自身作估计信号。")
    fig.text(0.5, 0.004, note, ha="center", va="bottom", fontsize=8.2,
             color="#333333", linespacing=1.5)
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return OUT_PNG


SHORT = {
    "bsrnn_simo": "oBSRNN-SIMO",
    "bsrnn_all": "oBSRNN (4 ckpt)",
    "bsrnn_large_all": "BSRNN large (4 ckpt)",
    "mmdenselstm": "MMDenseLSTM",
    "convtasnet": "Conv-TasNet",
    "demucs": "Demucs (htdemucs)",
    "umx": "Open-Unmix",
    "mdx": "MDX-Net",
    "oracle": "IRM/IBM Oracle",
    "dprnn": "DPRNN (自训)",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="T3.4 重绘 Average SDR 表")
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args()

    med, prof, summ, probe, base, subsets = _load()
    if not med:
        print("[FAIL] model_runs_median.json 为空")
        return 2
    print("[table] 主表条目 %d 个；profile %d 行；summary %d 行；subset=%s"
          % (len(med), len(prof), len(summ), subsets))
    if probe is None:
        print("[WARN] 缺 metric_window_probe.json -> 脚注将无法给出窗宽实测偏差")
    if base is None:
        print("[WARN] 缺 mixture_baseline.json -> 主表无基线行")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    md = build_md(med, prof, summ, probe, base, subsets)
    OUT_MD.write_text(md, encoding="utf-8")
    print("[OK] MD   -> %s  (%.1f KB)" % (OUT_MD, OUT_MD.stat().st_size / 1024))

    if not args.no_figure:
        p = build_png(med, prof, base)
        print("[OK] PNG  -> %s  (%.0f KB)" % (p, p.stat().st_size / 1024))
    print("[status] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

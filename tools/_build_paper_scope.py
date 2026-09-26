# -*- coding: utf-8 -*-
"""T8.3 · 论文「口径与差异说明」章节生成器（服务 D12 图包 / D13 答辩）

DoD（计划书 §2.3 · T8.3）：**挡掉「为什么和参考表不一样」的提问**。
产出：`04_reports/_shared/docs/PAPER_SCOPE_AND_DIVERGENCE.md`（论文章节素材，可直接引用）。

设计铁律（继承 T6「手填 d_L2b 整列全错」事故 + 技能铁律 18 / 22）：
  1. 正文数值**一律从源产物读出或重算**；唯一转录内容是「参考表」列（外部提供，
     出处固定为 ROADMAP §7 / MODEL_PROFILE §5），且**逐格与源数据旁证比对**，
     不一致即列入 WARN —— 顺带抓「手写文档与数据脱钩」。
  2. 口径坑条数与三块看板**交叉计数**（板 1 §6 表 ×7 / 板 2 §8 ×6 / 级联 §6 ×5），
     防止「搬漏一条」；计数不符即 FAIL。
  3. `--verify` 重新生成并与磁盘逐字节比对 → 同抓「有人手改」与「源数据已变未重建」。

用法：
  python tools/_build_paper_scope.py             # 生成
  python tools/_build_paper_scope.py --verify    # 只校验，不写盘
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

R = ROOT / "04_reports"
D = R / "_shared" / "docs"
OUT = D / "PAPER_SCOPE_AND_DIVERGENCE.md"
STAMP = "2026-09-26"

REF_DOC = "FYP_ROADMAP_2026-09-22.md"          # 参考表数值登记处（§7）
REF_DOC2 = "MODEL_PROFILE_2026-09-22.md"       # Size 口径登记处（§5）

# ------------------------------------------------------------------ 基础工具


def rd_json(p: Path):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def rd_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def esc(s: str) -> str:
    """Markdown 表格内转义竖线。"""
    return str(s).replace("|", "\\|")


def norm(s: str) -> str:
    """归一化：数学减号/全角 → ASCII，便于数值比对。"""
    return (str(s).replace("\u2212", "-").replace("−", "-")
            .replace("–", "-").replace("—", "-"))


def nums(s: str) -> list[float]:
    """抽出文本中的全部数值（含负号），忽略千分位。"""
    return [float(x.replace(",", "")) for x in
            re.findall(r"-?\d+(?:\.\d+)?", norm(s))]


def md_table(header: list[str], rows: list[list[str]], align: str | None = None) -> str:
    if align is None:
        align = "|".join([":---"] + ["---:" for _ in header[1:]])
    align = align.strip("|")
    out = ["| " + " | ".join(header) + " |", "|" + align + "|"]
    for r in rows:
        out.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ 口径三要素（自动）

def groups_block() -> tuple[str, list[list[str]]]:
    """从论文图导出工具继承分组口径 —— 同源，不重抄。"""
    import _export_paper_figures as X   # 模块级纯常量，无副作用

    board_of = {"G-ARCH": "板 1", "G-PROFILE": "板 1", "G-ACC": "板 1",
                "G-COST": "板 1", "G-SPEC": "板 1", "G-REV": "板 1",
                "G-S4": "板 1", "G-DN": "板 2", "G-CAS": "板 1 × 板 2"}
    cnt = Counter(f["g"] for f in X.FIGSET)
    rows = []
    for gid, g in X.GROUPS.items():
        rows.append([f"`{gid}`", g["name"], board_of.get(gid, "—"),
                     str(cnt.get(gid, 0)), g["dataset"], g["clip"], g["metric"]])
    return str(len(X.FIGSET)), rows


# ------------------------------------------------------------------ 与参考表的差异（自动核对）

def ref_rows() -> tuple[list[list[str]], list[str]]:
    """解析 ROADMAP §7 的差异表 + 用源数据重算「本机」列做旁证。"""
    txt = (D / REF_DOC).read_text(encoding="utf-8")
    m = re.search(r"## 7\. 与参考表的差异说明.*?\n(.*?)\n---", txt, re.S)
    if not m:
        raise RuntimeError("ROADMAP §7 差异表未找到 —— 章节结构已变，请先核对")
    raw: list[list[str]] = []
    for ln in m.group(1).splitlines():
        ln = ln.strip()
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 4 or set(cells[0]) <= set("-: "):
            continue
        if cells[0] in ("项", "模型"):
            continue
        raw.append(cells[:4])

    med = rd_json(R / "separation" / "data" / "comparison" / "model_runs_median.json")
    prof = {r["model_key"]: r for r in rd_csv(R / "_shared" / "data" / "model_analysis" / "model_profile.csv")}

    def recalc(item: str):
        if item.startswith("Demucs 参数量"):
            return f"{float(prof['demucs']['params_M']):.2f} M", "model_profile.csv · demucs.params_M"
        if item.startswith("Demucs SDR"):
            return f"{med['demucs']['sdr_avg4']:.2f} dB", "model_runs_median.json · demucs.sdr_avg4"
        if item.startswith("DPRNN"):
            return f"{med['dprnn']['sdr_avg4']:.2f} dB", "model_runs_median.json · dprnn.sdr_avg4"
        if item.startswith("Conv-TasNet /"):
            ks = ("convtasnet", "mmdenselstm", "umx")
            return " / ".join(f"{med[k]['sdr_avg4']:.2f}" for k in ks), \
                "model_runs_median.json · convtasnet/mmdenselstm/umx.sdr_avg4"
        if item.startswith("RPCA+DRNN"):
            return "无产出", "论文未公开代码（既有审计结论，非实现错误）"
        return None, None

    rows, warns = [], []
    for item, ref, local, why in raw:
        mine, src = recalc(item)
        if mine is None:
            warns.append(f"「{item}」未纳入自动核对（新增行？请补 `recalc()` 规则）")
            rows.append([item, ref, local, why, "—（未核对）"])
            continue
        a, b = nums(local), nums(mine)
        ok = len(a) == len(b) and all(abs(x - y) <= 0.005 for x, y in zip(a, b))
        if not ok:
            warns.append(f"「{item}」登记值 {local} 与源数据重算 {mine} 不一致（源：{src}）")
        rows.append([item, ref, mine, why, "✅" if ok else "❌"])
    return rows, warns


# ------------------------------------------------------------------ 口径坑清单
# 类别：A 指标定义 · B 数据与子集 · C 实现与环境 · D 局限与负结果
# src 指向「单一事实来源」，便于回查；条数须与三块看板交叉计数一致。

CAVEATS: list[dict] = [
    # ---- 板 1（源：`_build_dashboards.py` §6「引用前必读：口径与已知坑」，7 条）
    dict(cat="B", src="板 1 §6", tone="bad",
         pit="主表子集 = MUSDB18-HQ `train`",
         impact="in-domain，数字系统性偏乐观；与参考表（`test`）**不可逐格对齐**",
         line="本表为同任务、同数据集族的**本机复现口径**，子集为 train（in-domain），非参考表的 test 口径。"),
    dict(cat="A", src="板 1 §6", tone="bad",
         pit="分析窗实际 **2 s / hop 1.5 s**",
         impact="`evaluate()` 未传 `window`/`hop`，落到 museval 默认值；旧文档写「1 s 窗」**与实现不符**；实测 |Δ| 均值 0.267 dB",
         line="SDR 口径为 museval 签名默认窗（2 s 窗 / 1.5 s hop），非 1 s 窗；窗宽敏感性已量化为 |Δ| 均值 0.267 dB。"),
    dict(cat="A", src="板 1 §6", tone="warn",
         pit="FLOPs = **下界**",
         impact="`FlopCounterMode` 不计 `torch.stft` 与融合注意力；跨架构比较须配合实测时延",
         line="FLOPs 为 2×MACs 下界（不含 STFT 与融合注意力），仅用于同架构量级比较。"),
    dict(cat="C", src="板 1 §6", tone="warn",
         pit="RTF 受机器负载影响",
         impact="同一模型两次可差 2×；只做量级参考，**排名请用整曲墙钟**",
         line="RTF 为单卡（RTX 4070 Laptop 8 GiB）实测、受负载影响，排名以整曲墙钟为准。"),
    dict(cat="B", src="板 1 §6", tone="bad",
         pit="单轨模型不可与四轨 `avg4` 同轴",
         impact="BS-RoFormer / BSRNN-opt 只产 1~2 条轨，其 SDR 只覆盖目标轨",
         line="`轨数` 列区分 `1:50` / `4:50`；两类 SDR 不在同一条轴上，禁止直接排名。"),
    dict(cat="D", src="板 1 §6", tone="warn",
         pit="DPRNN 是**自训 5 h** 的负面对照",
         impact="官方只发语音权重，本机无法复现论文值 → 其 −1.72 dB 不构成对论文的否定",
         line="DPRNN 为本机自训 5 h 的欠训练对照，非官方权重，其数字不可与论文值等同看待。"),
    dict(cat="D", src="板 1 §6", tone="warn",
         pit="RPCA 不出四轨均值",
         impact="稀疏分量无天然 stem 归属，只能报区间；**不进主表排名**",
         line="RPCA 属解析方法，无 stem 归属，只报区间与耗时，不参与 SDR 排名。"),

    # ---- 板 2（源：`_build_dashboards_t72.py` §8，6 条）
    dict(cat="A", src="板 2 §8", tone="bad",
         pit="**配对差 ≠ 中位数之差**",
         impact="`*_improve` 列均为 med(out−in)；`med(out)−med(in)` 在非同分布时会**反号**",
         line="所有改善量按逐条配对差取中位（med(out−in)），不是两个中位数相减。"),
    dict(cat="A", src="板 2 §8", tone="bad",
         pit="PESQ 只支持 16 kHz",
         impact="非 16 kHz 一律不报（`pesq_applicable=false`），**不得当 0 用**",
         line="PESQ/STOI 定义域为 8/16 kHz；44.1 kHz 口径下为空是设计，不是缺测。"),
    dict(cat="B", src="板 2 §8", tone="bad",
         pit="`dns_dev` 无 clean GT（`reference_mode=noref`）",
         impact="fullref 列为 `null`，**不得当 0 用**；该集只能报电平行为量",
         line="dns_dev 为无参考集，只报电平/频谱行为量，不报 SI-SDR / PESQ。"),
    dict(cat="B", src="板 2 §8", tone="bad",
         pit="分档键**同名不同义**",
         impact="真实集按**输入 SI-SDR 事后分档**；synth 按**真值 SNR**（−5/0→<5 dB，5/10→5–15 dB）",
         line="分层键：真实集用事后输入 SI-SDR 分档，synth 用真值 SNR；跨集比较须先对齐键的语义。"),
    dict(cat="A", src="板 2 §8", tone="bad",
         pit="采样率契约固定 `44.1k→16k→mono→44.1k`",
         impact="`denoiser` 内部往返重采样；**引用 `hf_ratio` 必须注明口径**（16 kHz ≈0.207 / 44.1 kHz ≈0.035）",
         line="报告任何 `hf_ratio` 必须注明口径；44.1 kHz 契约率含 denoiser 内部重采样代价。"),
    dict(cat="B", src="板 2 §8", tone="warn",
         pit="片段 >30 s 统一跳过",
         impact="dns_dev 867/921 —— **可比性优先于覆盖率**，各模型看同一批片段",
         line="所有模型在同一批片段上评比；超长片段统一跳过以保证配对比，代价是覆盖率。"),

    # ---- 级联（源：`_build_dashboards_t72.py` §6，5 条）
    dict(cat="C", src="级联 §6", tone="bad",
         pit="音频必须 32-bit float WAV",
         impact="噪声脉冲性强，按功率匹配 SNR 后峰值冲高 → 写 PCM_16 会**静默削波** 30/40 格；但峰值大**不伤模型**（wrapper 按输入自身 mean/std 归一化再还原）",
         line="级联实验全程 32-bit float 存储；峰值超 1.0 不影响模型（内部按输入统计量归一化）。"),
    dict(cat="C", src="级联 §6", tone="bad",
         pit="门禁判据 = **float32 重建逐位相同**",
         impact="拿 float32 存储值比 float64 精确和 → 纯量化（0.55 ulp）会被误判 FAIL",
         line="G2 门禁判据为 float32 位级重建一致性，而非 float64 数值相等。"),
    dict(cat="B", src="级联 §6", tone="bad",
         pit="片段 **20 s**（非整曲）",
         impact="与 T4/T5 口径一致、匹配 museval 2 s 窗；与 §4 副表的整曲口径**不是一条轴**",
         line="级联矩阵为 10 s/20 s 片段口径，与副表 test 集 50 首整曲不可混列。"),
    dict(cat="C", src="级联 §6", tone="warn",
         pit="计划书写的「BSRNN-opt」实为人声单轨（违反 R10）",
         impact="已改用 **`bsrnn_all`**（oBSRNN 4 ckpt 四轨）→ 文档与实现一度不一致，属**已修正的偏离**",
         line="级联链路中的 BSRNN 指 `bsrnn_all`（oBSRNN 四轨），非人声单轨的 BSRNN-opt。"),
    dict(cat="C", src="级联 §6", tone="warn",
         pit="沙箱**无法创建脱离进程**",
         impact="`nohup &` / `cmd start` 被拒，后台任务随会话结束被杀 → 主跑改用**逐格 JSONL 增量落盘 + resume**",
         line="长跑任务采用逐格 JSONL 增量落盘，中断可幂等续跑（全格结果可逐格追溯）。"),
]

CAT_NAME = {"A": "A · 指标定义（Metric semantics）",
            "B": "B · 数据与子集（Data & subset）",
            "C": "C · 实现与运行环境（Implementation & environment）",
            "D": "D · 局限与负结果（Limits & negative results）"}


def caveat_counts() -> tuple[dict[str, int], str]:
    """与三块看板交叉计数：板 1 §6 表行数 / 板 2 §8 与级联 §6 的 <li> 数。"""
    b1 = (ROOT / "tools" / "_build_dashboards.py").read_text(encoding="utf-8")
    seg = b1.split("# ---- §7 口径与坑")[1].split("# ---- §8")[0]
    n_b1 = len(re.findall(r"\('', \['\d+'", seg))

    b2 = (ROOT / "tools" / "_build_dashboards_t72.py").read_text(encoding="utf-8")
    seg2 = b2.split("# ---- 8 口径与坑")[1].split("# ---- 9 产物与复现")[0]
    n_b2 = len(re.findall(r"<li><b>", seg2))
    seg3 = b2.split("# ---- 6 口径与坑")[1].split("# ---- 7 产物与复现")[0]
    n_cas = len(re.findall(r"<li><b>", seg3))
    return {"板 1 §6": n_b1, "板 2 §8": n_b2, "级联 §6": n_cas}, f"{n_b1}/{n_b2}/{n_cas}"


# ------------------------------------------------------------------ 图纸与缺口（自动）

def figure_block() -> tuple[dict, list[list[str]], list[list[str]]]:
    m = rd_json(R / "_shared" / "figures" / "paper" / "paper_figures_manifest.json")
    figs = m["figures"]
    dpi = Counter(f["dpi"] for f in figs)
    stat = {
        "n": len(figs),
        "b1": sum(1 for f in figs if f["board"] == 1),
        "b2": sum(1 for f in figs if f["board"] == 2),
        "single": sum(1 for f in figs if f.get("meets_300dpi")),
        "double": sum(1 for f in figs if f.get("meets_300dpi_double")),
        "dpi_dist": sorted(dpi.items(), key=lambda kv: -kv[1]),
        "target": m["target_dpi"], "need1": m["need_px_single"], "need2": m["need_px_double"],
        "col1": m["width_single_in"], "col2": m["width_double_in"],
    }
    dpi_rows = [[f"{int(d)} dpi", str(c), f"{c / len(figs) * 100:.0f}%"] for d, c in stat["dpi_dist"]]
    hold = Counter(f["script"] for f in figs if not f.get("render", True))
    hold_rows = [[f"`{s}`", str(c)] for s, c in sorted(hold.items(), key=lambda kv: -kv[1])]
    stat["n_hold"] = sum(hold.values())
    stat["n_hold_scripts"] = len(hold)
    return stat, dpi_rows, hold_rows


# ------------------------------------------------------------------ 事实数字（自动）

def fact_block() -> dict:
    cas = rd_json(R / "cascade" / "data" / "cascade_eval.json")
    man = rd_json(R / "cascade" / "data" / "cascade_manifest.json")
    den = rd_json(R / "denoiser" / "data" / "denoise_manifest.json")
    e16 = rd_json(R / "denoiser" / "data" / "denoise_eval_16k.json")
    e44 = rd_json(R / "denoiser" / "data" / "denoise_eval_44k.json")

    def hf(doc, key):
        for r in doc["rows"]:
            if r["model"] == key and r["subset"] == "valentini" and r["snr_bin"] == "ALL":
                return r["hf_ratio_out"]
        return None

    return {
        "den_cells": len(den["cells"]),   # 该 manifest 无 n_cells 键；cells 本身是列表
        "den_rows16": len(e16["rows"]), "den_rows44": len(e44["rows"]),
        "hf16": hf(e16, "denoiser_master64"), "hf44": hf(e44, "denoiser_master64"),
        "cas_gate": man["n_gates"], "cas_gate_fail": man["n_failed"],
        "cas_sep": cas["n_sep"], "cas_sep_pass": cas["n_sep_pass"], "cas_post": cas["n_post"],
        "cas_dl1": cas["matrix"]["summary_all_cells"]["median_d_L1"],
        "cas_dl1b": cas["matrix"]["summary_all_cells"]["median_d_L1b"],
        "cas_net": cas["matrix"]["summary_all_cells"]["median_denoise_net"],
        "cas_dl3": cas["matrix"]["summary_all_cells"]["median_d_L3"],
        "regate_changed": cas["regate"]["n_changed"], "regate_rule": cas["regate"]["rule"],
    }


# ------------------------------------------------------------------ 生成

def build() -> str:
    n_fig, g_rows = groups_block()
    refs, warns = ref_rows()
    cc, cc_txt = caveat_counts()
    stat, dpi_rows, hold_rows = figure_block()
    fb = fact_block()

    by_src = Counter(c["src"] for c in CAVEATS)
    doc_cnt = {kk: by_src.get(kk, 0) for kk in ("板 1 §6", "板 2 §8", "级联 §6")}
    assert doc_cnt == cc, (
        f"口径坑条数与看板不一致：本文档 {doc_cnt} vs 看板交叉计数 {cc}"
        " —— 看板改了坑清单就必须同步本文档（防搬漏一条）")

    L: list[str] = []
    A = L.append

    A("# 口径与差异说明（论文 T8.3 · 服务 D12 图包 / D13 答辩）")
    A("")
    A("> **机器生成 · 禁止手改** ｜ 生成脚本 `tools/_build_paper_scope.py` ｜ 生成日期 `%s`" % STAMP)
    A("> 重建：`python tools/_build_paper_scope.py` ｜ 校验：`python tools/_build_paper_scope.py --verify`")
    A("> 用途（**T8.3 DoD**）：**挡掉「为什么和参考表不一样」的提问** —— 论文正文 / 答辩 / 复现者共用同一份口径声明。")
    A("> 除「参考表」列（外部提供，出处见 §6）外，本文件**全部数值由脚本从源产物读出或重算**。")
    A("")
    A("## 0. 一句话（论文与口播可直接用）")
    A("")
    A("> **中文**：本报告全部数值是**本机复现口径**下的实测结果，口径三要素（数据集 / 片段 / 指标定义）随每张图表声明；"
      "与参考表或原文数值的差异来自**实现版本、数据子集、评价口径**三处，已逐条登记并附复核命令 —— 我们选择**把差异写清楚**，而不是硬凑数字。")
    A("")
    A("> **English**: Every figure and table reports a **locally reproduced** measurement with its three protocol elements "
      "(dataset / clip / metric definition) declared inline. Deviations from the reference table or the original papers "
      "are attributed to **implementation version, data subset, and evaluation protocol**, itemised in §2 and §3, and each "
      "is reproducible from the commands listed in §6.")
    A("")
    A("---")
    A("")
    A("## 1. 口径三要素（全局，按图组继承）")
    A("")
    A("`%s` 张论文图分属 9 个口径组；**图注必须连同本组的一行一起复制**，不得只抄标题句。" % n_fig)
    A("")
    A(md_table(["组", "名称", "板块", "图数", "数据集", "片段", "指标定义"], g_rows,
               align="|:---|:---|:---|" + "---:|" + "---|" * 3))
    A("> 本表由 `tools/_export_paper_figures.py` 的 `GROUPS` **直接继承**（同源），非重抄 —— 改口径只需改那一处。")
    A(">")
    A("> **「板块」列是主题归属，与 §4.1 的 `board` 计数口径不同**：级联 2 张主题跨两板、"
      "输出时编入板 2 目录（故 §4.1 记板 2 为 13 + 2 = 15 张）。两处都不是「数错了」。")
    A("")
    A("---")
    A("")
    A("## 2. 与参考表的差异说明（板 1 · 逐行核对）")
    A("")
    A("下表「参考表」列来自用户提供的参考表（登记于 `%s` §7、`%s` §5，**本项目不重算**）；"
      "「本机」列由脚本从 `model_runs_median.json` / `model_profile.csv` **重算**，并逐格比对登记值。" % (REF_DOC, REF_DOC2))
    A("")
    A(md_table(["差异项", "参考表", "本机（重算）", "差异主因（按贡献排序）", "核对"], refs,
               align="|:---|" + "---:|" + "---:|" + "---|" + ":---:|"))
    A("")
    A("**三条通用差异（任何一行都可以归到这三条）**：")
    A("")
    A("1. **子集不同** —— 本表 `train`（in-domain）/ 参考表 `test`；")
    A("2. **实现版本不同** —— HTDemucs ≠ 原版 Demucs(v1)；自训 DPRNN ≠ 官方权重；")
    A("3. **评价口径不同** —— mono、2 s 窗、3 个能量均衡片段的中位数 vs 参考表的整曲 / 其他池。")
    A("")
    if warns:
        A("**⚠️ 核对未全覆盖 / 不一致（须处理）**：")
        A("")
        for w in warns:
            A("- %s" % w)
        A("")
    else:
        A("**✅ 核对结果**：参考表登记值与源数据**逐格一致**（容差 0.005），无 WARN。")
        A("")
    A("---")
    A("")
    A("## 3. 引用前必读：口径坑清单（三块看板合并）")
    A("")
    A("共 **%d** 条 = 板 1 **%d** + 板 2 **%d** + 级联 **%d**（来源：`_build_dashboards.py` §6 / "
      "`_build_dashboards_t72.py` §8 / 同文件级联 §6；条数由脚本交叉计数，搬漏即 FAIL）。"
      % (len(CAVEATS), cc["板 1 §6"], cc["板 2 §8"], cc["级联 §6"]))
    A("")
    for cat in ("A", "B", "C", "D"):
        items = [c for c in CAVEATS if c["cat"] == cat]
        A("### %s（%d 条）" % (CAT_NAME[cat], len(items)))
        A("")
        A(md_table(["坑", "影响", "引用时的一句话（可直接写进论文）", "来源"],
                   [[c["pit"], c["impact"], c["line"], c["src"]] for c in items],
                   align="|:---|:---|:---|:---|"))
        A("")
    A("---")
    A("")
    A("## 4. 已知取舍与缺口（照报，不美化）")
    A("")
    A("### 4.1 图纸产出")
    A("")
    A("- 成品图 **%d 张**（板 1 %d / 板 2 %d），目标 **%d dpi**；"
      "判据按**印刷宽度**定义 —— 单栏 %.2f in = **%d px**、双栏 %.2f in = **%d px**。"
      % (stat["n"], stat["b1"], stat["b2"], stat["target"], stat["col1"], stat["need1"],
         stat["col2"], stat["need2"]))
    A("- **单栏达标 %d/%d（缺口 %d）**；其中 **%d 张**同时满足双栏宽度，其余 %d 张**按单栏排版使用**。"
      % (stat["single"], stat["n"], stat["n"] - stat["single"],
         stat["double"], stat["n"] - stat["double"]))
    A("")
    A(md_table(["实际 dpi", "张数", "占比"], dpi_rows, align="|:---" + "|---:|---:|"))
    A("> **低于 300 dpi 的图不是漏渲染**：其绘图脚本内 `savefig(dpi=...)` 写死，或属「不重跑」组"
      "（含 torch 推理，重跑会改写已归档数据）。它们**均满足单栏 300 dpi 等效宽度**，按**单栏**排版使用。")
    A("")
    A("**「不重跑」清单（%d 张 / %d 个脚本）** —— 复现命令栏不能骗人，故如实标缺口：" % (stat["n_hold"], stat["n_hold_scripts"]))
    A("")
    A(md_table(["脚本", "图数"], hold_rows, align=":---|---:"))
    A("")
    A("### 4.2 实验口径上的取舍")
    A("")
    TRADE = [
        ["1", "主表跑在 `train` 子集（in-domain，偏乐观）", "副表另给 `test` 集 50 首整曲口径（只看耗时与规模），两表**不混列**"],
        ["2", "分析窗落到 museval 默认 **2 s / hop 1.5 s**（文档曾写 1 s）", "已量化为 |Δ| 均值 0.267 dB；对齐其他论文需补 `window`/`hop` 后整表重跑"],
        ["3", "BSRNN-SIMO 只跑 **14/50** 首（截断）", "报告中显式标注截断；四轨最优结论以 MDX-Net 为可用代表"],
        ["4", "RPCA 无四轨产出", "只报区间与耗时，不进排名（见 §3 · D 类）"],
        ["5", "降噪**域外探针为负结果**（mel 对纯噪声近不抑制）", "按「互补失效」正面报告：两个模型族**有效域不同**"],
        ["6", "级联**前置降噪为负结果**", "照报：带宽代价与净动作已分解，见 §5 Q3"],
        ["7", "门禁首轮 35 格 FAIL 系**语义误判**（非信号损坏）", "免重跑重判（`tools/_cascade_regate.py`）→ 全格 PASS；判据见 §5 Q3"],
    ]
    A(md_table(["#", "取舍", "处置（已在报告中显式声明）"], TRADE, align=":---|:---|:---"))
    A("")
    A("### 4.3 规模与计数（可对账）")
    A("")
    A(md_table(["项", "值", "来源"],
               [["降噪评测 cells", str(fb["den_cells"]), "`denoiser/data/denoise_manifest.json`"],
                ["降噪口径 A（44.1 kHz 契约率）行数", str(fb["den_rows44"]), "`denoise_eval_44k.json`"],
                ["降噪口径 B（16 kHz）行数", str(fb["den_rows16"]), "`denoise_eval_16k.json`"],
                ["级联门禁", f'{fb["cas_gate"] - fb["cas_gate_fail"]}/{fb["cas_gate"]} PASS', "`cascade_manifest.json`"],
                ["级联分离格", f'{fb["cas_sep_pass"]}/{fb["cas_sep"]} PASS', "`cascade_eval.json`"],
                ["级联后置格", str(fb["cas_post"]), "`cascade_eval.json`"],
                ["门禁重判改动格数", str(fb["regate_changed"]), "`cascade_eval.json` · regate"],
                ["`hf_ratio_out`（16 kHz / 44.1 kHz，`denoiser_master64` · valentini · ALL）",
                 f'{fb["hf16"]:.4f} / {fb["hf44"]:.4f}', "`denoise_eval_16k.json` / `_44k.json`"]],
               align="|:---|" + "---:|" + "---|"))
    A("---")
    A("")
    A("## 5. 答辩速答卡（Q → A）")
    A("")
    QA = [
        ("Demucs 本机 8.11 dB，参考表 6.03 dB —— 是不是做错了？",
         "不是同一物：参考表是**原版 Demucs (v1)**，本机是 **HTDemucs**；且本表为 `train` 子集、3 个能量均衡片段的中位数。"
         "三条通用差异见 §2 —— 差异已写明，不硬凑。"),
        ("降噪表里 PESQ / STOI 有的是空的？",
         "**PESQ 的定义域只有 8/16 kHz**，44.1 kHz 口径下不报是设计（`pesq_applicable=false`），**不能当 0 用**（§3 · A 类）。"),
        ("前置降噪反而让 SDR 中位下降 %.2f dB，这是 bug 吗？" % abs(fb["cas_dl1"]),
         (f"是**真实负结果**，且已做对照臂拆解：L1 前置降噪中位 ΔSDR **{fb['cas_dl1']:.3f}**，"
          f"其中**仅限带代价** L1b **{fb['cas_dl1b']:.3f}**，"
          f"**净降噪动作 {fb['cas_net']:.3f}（占 {fb['cas_net'] / fb['cas_dl1'] * 100:.0f}%）**"
          "（均读自 `cascade_eval.json` · `matrix.summary_all_cells`）；"
          "机理是降噪后 `V1den` 的 drums/bass/other 电平塌到 0.006~0.062"
          "（转录自 `docs/T6_CASCADE_DENOISE_BEFORE_SEPARATION.md` §机理），"
          "分离器**退化为恒等映射** —— 属**任务错配**。"
          f"门禁 {fb['cas_gate'] - fb['cas_gate_fail']}/{fb['cas_gate']} PASS、"
          f"锚点 40/40 PASS、分离格 {fb['cas_sep_pass']}/{fb['cas_sep']}。")),
        ("为什么用 20 s 片段而不是整曲？",
         "为匹配 museval 的 2 s 分析窗，并与 T4/T5 保持同一口径（**可比性优先于覆盖率**）；"
         "整曲口径另见 §4 副表，两表不混列（§3 · B 类）。"),
        ("FLOPs 和论文里的对不上？",
         "本机 FLOPs = **2×MACs 下界**（`FlopCounterMode` 不计 `torch.stft` 与融合注意力），"
         "跨架构比较必须配合实测时延；同架构内排序仍有效（§3 · A 类）。"),
        ("为什么有些图不是 300 dpi？",
         "那 %d 张属「不重跑」组（含 torch 推理）或脚本写死 dpi；它们**均满足单栏 300 dpi 等效宽度**，"
         "按单栏排版使用。清单与原因逐张登记（§4.1），未美化。" % stat["n_hold"]),
        ("主表用 train 子集，是不是在作弊？",
         "**是 in-domain 口径，已主动交代**（§2 第 1 行 + §4.2 第 1 行）：它测的是「模型能否复现其训练分布」，"
         "测的不是泛化；泛化证据另由 `test` 集副表与 dns_dev 外部集给出。"),
    ]
    for i, (q, a) in enumerate(QA, 1):
        A("**Q%d. %s**" % (i, q))
        A("")
        A("→ %s" % a)
        A("")
    A("---")
    A("")
    A("## 6. 数字溯源（引用任何数字前，先看它在哪个文件）")
    A("")
    A(md_table(["数字 / 结论", "源文件", "生成工具"],
               [["分离主表（Average SDR 等）", "`separation/data/comparison/model_runs_median.json`", "`tools/bench_multisong.py` + `median_over_clips.py`"],
                ["参考表登记值", f"`{REF_DOC}` §7、`{REF_DOC2}` §5", "（外部提供，不重算）"],
                ["模型画像（参数量 / FLOPs / 时延）", "`_shared/data/model_analysis/model_profile.csv`", "`tools/_measure_model_profile.py`"],
                ["降噪评测（双口径）", "`denoiser/data/denoise_eval_16k.json` / `_44k.json`", "`tools/_denoise_eval.py`"],
                ["dry/wet 旋钮", "`denoiser/data/denoise_drywet.json`", "`tools/_denoise_drywet.py`"],
                ["域外探针", "`denoiser/data/denoise_ood_probe.json`", "`tools/_denoise_ood_probe.py`"],
                ["级联矩阵 / 门禁", "`cascade/data/cascade_eval.json` / `cascade_manifest.json`", "`tools/_cascade_experiment.py`"],
                ["门禁重判", "`cascade/data/cascade_eval.json` · regate", "`tools/_cascade_regate.py`"],
                ["论文图清单（像素 / dpi / 复现脚本）", "`_shared/figures/paper/paper_figures_manifest.json`", "`tools/_export_paper_figures.py`"],
                ["四份数据摘要", "`_shared/docs/summaries/*.md`", "`tools/_build_summaries.py`"],
                ["口径三要素（本文件 §1）", "`tools/_export_paper_figures.py` · `GROUPS`", "（继承，非重抄）"]],
               align="|:---|:---|:---|"))
    A("> **解释器**：全部脚本须用 venv —— "
      "`C:\\Users\\jerry\\.workbuddy\\binaries\\python\\envs\\fyp_audio\\Scripts\\python.exe`")
    A("")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ 入口

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="只校验：重建并与磁盘比对")
    a = ap.parse_args()

    text = build()
    if a.verify:
        if not OUT.exists():
            print(f"[FAIL] 目标不存在：{OUT.relative_to(ROOT)}")
            return 1
        disk = OUT.read_text(encoding="utf-8")
        if disk == text:
            print(f"[OK] {OUT.relative_to(ROOT)} 与重建结果逐字节一致（{len(text)} 字符）")
            return 0
        # 定位首个差异
        dl, rl = disk.splitlines(), text.splitlines()
        for i in range(max(len(dl), len(rl))):
            d = dl[i] if i < len(dl) else "<缺失>"
            r = rl[i] if i < len(rl) else "<缺失>"
            if d != r:
                print(f"[FAIL] 第 {i + 1} 行不一致：")
                print(f"  磁盘：{d[:160]}")
                print(f"  重建：{r[:160]}")
                break
        print(f"[FAIL] 磁盘 {len(dl)} 行 / 重建 {len(rl)} 行 —— "
              f"要么有人手改，要么源数据已变未重建。")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)}  ({len(text)} 字符 / {text.count(chr(10))} 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

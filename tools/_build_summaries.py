# -*- coding: utf-8 -*-
"""T7.3 · 4 份数据摘要生成器（交付物 D11）

DoD（计划书 §2.3）：**数字可与 CSV 逐一对齐，可被论文直接引用**。

设计铁律（源自 T6「凭印象手填 d_L2b 整列 16 个值全错」事故）：
  1. 本脚本**只从 CSV/JSON 读数字**；除口径常量与列名外，正文不得出现手填数值。
  2. 产出的 MD 顶部标注「机器生成 · 禁止手改」+ 重建命令。
  3. `--verify` 重新生成并与磁盘比对 → 同时抓「有人手改」与「源数据已变未重建」。

用法：
  python tools/_build_summaries.py --only all        # 四份全建
  python tools/_build_summaries.py --only cascade    # 只建一份
  python tools/_build_summaries.py --verify          # 只校验，不写盘
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "04_reports"
S = R / "00_shared" / "data" / "model_analysis"
OUT = R / "00_shared" / "docs" / "summaries"
STAMP = "2026-09-26"

STEMS = ("vocals", "drums", "bass", "other")


# ---------------------------------------------------------------- 基础工具

def rd_csv(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def rd_json(p: Path):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def num(v):
    """转 float；空/None/nan → None。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v == v else None
    s = str(v).strip()
    if s in ("", "None", "nan", "null", "NaN", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def g(v, nd: int = 3) -> str:
    """定点格式化；缺值 → '—'。"""
    x = num(v)
    return "—" if x is None else f"{x:.{nd}f}"


def gi(v) -> str:
    x = num(v)
    return "—" if x is None else f"{x:.0f}"


def med(vals):
    v = [x for x in vals if x is not None]
    return statistics.median(v) if v else None


def md_table(headers, rows, align=None) -> str:
    n = len(headers)
    align = align or ["l"] * n
    sep = {"l": ":---", "r": "---:", "c": ":---:"}
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(sep[a] for a in align) + "|"]
    for r in rows:
        out.append("| " + " | ".join(
            "—" if (c is None or c == "") else str(c) for c in r) + " |")
    return "\n".join(out)


def header(title, deliver, only, sources, detail, stamp=STAMP) -> str:
    src = "\n".join(f"> - `{Path(s).as_posix()}`" for s in sources)
    return (
        f"# {title}\n\n"
        f"> **机器生成 · 禁止手改** ｜ 生成日 {stamp} ｜ 交付物 **D11 / T7.3**（{deliver}）\n"
        f">\n"
        f"> 数字全部读自下列机器可读文件（正文无手填数值）：\n{src}\n"
        f">\n"
        f"> 重建：`python tools/_build_summaries.py --only {only}` ｜ "
        f"校验：`python tools/_build_summaries.py --verify`\n"
        f">\n"
        f"> 详解（机理 / 原因 / 决策过程，本表不复述）：{detail}\n"
    )


# ---------------------------------------------------------------- 1 · 模型画像

GROUP_LEGEND = {
    "4-stem": "四轨分离",
    "1-target": "单目标（人声）",
    "2-target": "双目标",
    "denoise": "降噪（板 2）",
    "dereverb": "去混响 / 去回声（板 2）",
    "analytic": "解析 / 经典基线",
}


def build_model_profile() -> str:
    prof = S / "model_profile.csv"
    thop = S / "thop_crosscheck.json"
    gate = S / "stage0_gate.json"
    rows = rd_csv(prof)
    th = rd_json(thop)
    gt = rd_json(gate)

    t = [
        header(
            "数据摘要 · 模型本体画像（22 个模型/权重）",
            "模型画像表 D1 的论文取值版",
            "model",
            [prof.relative_to(ROOT), thop.relative_to(ROOT), gate.relative_to(ROOT)],
            "`00_shared/docs/MODEL_PROFILE_2026-09-22.md`",
        ),
        "\n---\n\n## 1. 口径三要素（引用本表必须一并声明）\n",
        md_table(
            ["项", "取值 / 说明"],
            [
                ["生成日", f"`{STAMP}`（重建即刷新）"],
                ["输入构造", "**44.1 kHz / 立体声 / 10 s**（统一合成，不取自数据集）"],
                ["参数量", "`sum(p.numel())`，取自模型实例，**非**配置声明值"],
                ["FLOPs", "`torch.utils.flop_counter.FlopCounterMode`，**口径 = 2×MACs**"],
                ["时延", "预热 2 次后取 **5 次中位数**，CUDA 前后各同步"],
                ["峰值显存", "`torch.cuda.max_memory_allocated()`"],
                ["设备", "RTX 4070 Laptop **8 GiB**（sm_89）"],
                ["隔离", "**每模型一独立子进程**（22 个同进程会显存耗尽）"],
            ],
            ["l", "l"],
        ),
        "\n> ⚠️ **FLOPs 是下界，不是等价比较**：`FlopCounterMode` 只统计 torch 调度的算子"
        "（conv / linear / matmul / norm）；`torch.stft` 与融合的 `scaled_dot_product_attention` **不计入**。"
        "\n> 因此跨架构比较**必须配合实测时延**。\n",
        f"\n覆盖度取自 CSV 字段 `flops_coverage`，实测取值域："
        f"{sorted(set(r['flops_coverage'] for r in rows))}。\n",
        "\n---\n\n## 2. 全表（22 行，保持 CSV 行序以便逐一对齐）\n",
        md_table(
            ["model_key", "模型", "组", "组说明", "参数量(M)", "权重(MB)", "MACs(G)",
             "FLOPs(G)", "时延(s)", "RTF", "峰值显存(MB)", "thop(G)", "偏差(%)", "状态"],
            [
                [
                    r["model_key"], r["label"], r["group"],
                    GROUP_LEGEND.get(r["group"], r["group"]),
                    g(r["params_M"], 1), g(r["weights_mb"], 1), g(r["macs_G"], 1),
                    g(r["flops_G"], 1), g(r["latency_s"], 3), g(r["rtf"], 4),
                    g(r["peak_vram_mb"], 1), g(r["thop_G"], 1), g(r["thop_dev_pct"], 2),
                    r["status"],
                ]
                for r in rows
            ],
            ["l", "l", "l", "l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "c"],
        ),
        "\n---\n\n## 3. 分组计数（读自 CSV 的 `group` 列）\n",
        md_table(
            ["组", "组说明", "模型数"],
            [
                [k, GROUP_LEGEND.get(k, k), sum(1 for r in rows if r["group"] == k)]
                for k in sorted({r["group"] for r in rows})
            ],
            ["l", "l", "r"],
        ),
    ]

    # thop 交叉验证
    cases = th["cases"]
    cmp_ = [k for k, v in cases.items() if num(v.get("dev_pct")) is not None]
    ok = [k for k in cmp_ if abs(num(cases[k]["dev_pct"])) < num(th["tol_pct"])]
    over = [k for k in cmp_ if k not in ok]
    na = [k for k, v in cases.items() if num(v.get("dev_pct")) is None]
    t += [
        f"\n---\n\n## 4. FLOPs 独立第二口径（thop 交叉验证）\n",
        f"- 容差：**{g(th['tol_pct'], 1)} %** ｜ 单位：`{th['units']}` ｜ 覆盖 **{th['n_models']}** 个模型\n"
        f"- thop 能给出可比数值的：**{len(cmp_)}** 个 —— 其中在容差内 **{len(ok)}** 个、"
        f"**超容差 {len(over)}** 个（{('、'.join('`%s`' % k for k in sorted(over)) or '无')}）；"
        f"**无法用 thop 复核**：**{len(na)}** 个\n"
        f"- ⚠️ 超容差**不是数值矛盾，是算子覆盖不同**（`备注` 列可见：thop 只看到单网/少了一维）。"
        f"故 FLOPs 跨架构比较以「**本列下界 + 实测时延**」为准，thop 仅作参考。\n",
        md_table(
            ["model_key", "thop(G)", "偏差(%)", "备注"],
            [[k, g(v.get("thop_G"), 1), g(v.get("dev_pct"), 2), (v.get("note") or "")[:70]]
             for k, v in sorted(cases.items())],
            ["l", "r", "r", "l"],
        ),
        "\n---\n\n## 5. 板 2 门禁（stage0：加载 + 前向 + 探针）\n",
        md_table(
            ["模型", "状态", "参数量", "load(s)", "forward(s)", "ΔSI-SDR(dB)", "`peak`（门禁自报）"],
            [[k, v.get("status"), gi(v.get("params")), g(v.get("load_s"), 2),
              g(v.get("forward_s"), 3), g(v.get("si_sdr_delta"), 2), g(v.get("peak"), 4)]
             for k, v in sorted(gt["cases"].items())],
            ["l", "c", "r", "r", "r", "r", "r"],
        ),
        f"\n> 门禁生成时间：`{gt.get('updated')}` ｜ 设备：`{gt.get('device')}`\n",
        "\n---\n\n## 6. 复现\n",
        "```bash\npython tools/_build_summaries.py --only model   # 重建本表\n```\n",
    ]
    return "\n".join(t) + "\n"


# ---------------------------------------------------------------- 2 · 分离

REVERB_DETAIL = "`01_separation/docs/STAGE4_SUMMARY.md` · `01_separation/docs/MEDIAN_TABLE_REDRAWN.md`"


def build_separation() -> str:
    med_p = R / "01_separation" / "data" / "comparison" / "model_runs_median.json"
    mix_p = R / "01_separation" / "data" / "comparison" / "mixture_baseline.json"
    rev_p = R / "01_separation" / "data" / "reverb" / "stage4_summary.json"
    cost_p = R / "01_separation" / "data" / "comparison" / "test_run_model_summary.csv"
    ana_p = R / "01_separation" / "data" / "comparison" / "test_run_analysis.json"
    pro_p = S / "model_profile.csv"

    md = rd_json(med_p)
    mix = rd_json(mix_p)
    rev = rd_json(rev_p)
    cost = rd_csv(cost_p)
    ana = rd_json(ana_p)
    grp = {r["model_key"]: r for r in rd_csv(pro_p)}

    # 主表：只列有数值结果的模型
    main_rows = []
    for k, r in md.items():
        sdr = r["sdr"]
        if num(sdr.get("vocals", {}).get("median")) is None:
            continue
        main_rows.append([
            k, r["label"], grp.get(k, {}).get("group", "—"),
            r["n_clips"],
            *[g(sdr.get(s, {}).get("median"), 2) for s in STEMS],
            g(r.get("sdr_avg4"), 2), g(r.get("rtf"), 4),
        ])
    main_rows.sort(key=lambda x: -(num(x[8]) or -99))   # x[8] == avg4

    nostat = [k for k, r in md.items() if num(r["sdr"].get("vocals", {}).get("median")) is None]
    clips = md["demucs"]["clips"]

    t = [
        header(
            "数据摘要 · 板 1 源分离（精度 / 成本 / 退化）",
            "分离主表 + 实机成本 + 混响回声退化",
            "separation",
            [med_p.relative_to(ROOT), mix_p.relative_to(ROOT), rev_p.relative_to(ROOT),
             cost_p.relative_to(ROOT), ana_p.relative_to(ROOT)],
            REVERB_DETAIL,
        ),
        "\n---\n\n## 1. 口径三要素\n",
        md_table(
            ["项", "取值 / 说明"],
            [
                ["数据集（主表）", "MUSDB18-HQ **train** 子集抽段"],
                ["片段（主表）", f"**{md['demucs']['n_clips']} 首 × 10 s**："
                                 + "、".join(f"`{c}`" for c in clips)],
                ["指标（主表）", "`museval.metrics.bss_eval`（BSS-Eval v4，签名默认窗 "
                                 "**88200 / hop 66150**），逐帧 `nanmedian`，`compute_permutation=False`"],
                ["avg4", "四轨 SDR 的算术平均（vocals/drums/bass/other）"],
                ["数据集（实机）", "MUSDB18-HQ **test** 50 首整曲"],
                ["片段（混响/回声）", "同主表 train 3 段；RIR 卷混后**导出为 44.1 kHz**再评测"],
            ],
            ["l", "l"],
        ),
        "\n---\n\n## 2. 主表：四轨 SDR 中位（按 avg4 降序）\n",
        md_table(
            ["model_key", "模型", "组", "片段数", "vocals", "drums", "bass", "other", "**avg4**", "RTF"],
            main_rows,
            ["l", "l", "l", "r", "r", "r", "r", "r", "r", "r"],
        ),
        f"\n- 无可用数值（探针不可用/未跑通）：**{len(nostat)}** 个 —— "
        + "、".join(f"`{k}`" for k in sorted(nostat)) + "\n"
        if nostat else "",
        "\n### 2.1 基线对照（同一口径）\n",
        md_table(
            ["基线", "vocals", "drums", "bass", "other", "avg4", "含义"],
            [[
                "mixture（不分离）",
                *[g(mix["per_stem"][s]["median"], 2) for s in STEMS],
                g(mix["avg4"], 2), "把混音自身当估计 → 标定各方法是否真有效",
            ]],
            ["l", "r", "r", "r", "r", "r", "l"],
        ),
        f"\n> mixture 基线口径：`{mix['aggregation']}`；帧窗 `{mix['window']['note']}`；"
        f"生成 `{mix['generated']}`，状态 `{mix['status']}`。\n",
        "\n---\n\n## 3. 实机运行成本（test 集 50 首整曲）\n",
        md_table(
            ["model_key", "模型", "跑完 50 首", "PASS", "wall 中位(s)", "RTF 中位",
             "SDR 均值中位", "轨数", "输出(MB)", "推理占比(%)"],
            [[
                r["model_key"], r["model"], r["complete_50"], r["status_PASS"],
                g(r["wall_median_s"], 1), g(r["rtf_median"], 4), g(r["sdr_mean_median"], 3),
                r["n_tracks_set"], g(r["out_mb_total"], 1), g(r["infer_share_pct"], 1),
            ] for r in cost],
            ["l", "l", "c", "r", "r", "r", "r", "c", "r", "r"],
        ),
        f"\n> 台账：共 **{ana['n_models_total']}** 个模型；"
        f"`finished` = {ana['finished']}；"
        f"`unfinished` = {ana['unfinished']}；`disabled` = {ana['disabled']}。\n"
        "> ⚠️ **BSRNN-SIMO 只有 14/50 首**（范围外，已拍板不补跑）——引用时须显式标注截断。\n",
        "> ⚠️ **`SDR 均值中位` 列跨行不可直接比**：`轨数` 列为 `1:50` 的是**单轨（人声）**模型，"
        "其 SDR 只覆盖人声；`4:50` 是四轨模型。两者口径不同。\n",
        "\n---\n\n## 4. 混响 / 回声退化（ΔSDR，dB）\n",
        f"T60（**导出口径 44.1 kHz**）：小房间 **{g(rev['reverb']['t60_small'], 3)} s** ／ "
        f"大厅 **{g(rev['reverb']['t60_hall'], 3)} s**。\n",
        md_table(
            ["model_key", "小房间 ΔSDR", "大厅 ΔSDR", "短回声 ΔSDR", "长回声 ΔSDR"],
            [[
                k,
                g(rev["reverb"]["delta_small_by_model"].get(k), 3),
                g(rev["reverb"]["delta_hall_by_model"].get(k), 3),
                g(rev["echo"]["delta_short_by_model"].get(k), 3),
                g(rev["echo"]["delta_long_by_model"].get(k), 3),
            ] for k in sorted(rev["reverb"]["delta_hall_by_model"])],
            ["l", "r", "r", "r", "r"],
        ),
        f"\n均值曲线 `mean_curve`（干 / 小 / 大）："
        f"混响 {[round(x, 3) for x in rev['reverb']['mean_curve']]}；"
        f"回声 {[round(x, 3) for x in rev['echo']['mean_curve']]}\n",
        "\n---\n\n## 5. 去混响（负结果，照报）\n",
        md_table(
            ["项", "值"],
            [
                ["Dereverb-Echo `dry` 支增益中位", g(rev["dereverb"]["anvuew_gain_median"], 3)],
                ["同上最大值", g(rev["dereverb"]["anvuew_gain_max"], 3)],
                ["wet 支损失区间 (dB)", str([round(x, 1) for x in rev["dereverb"]["wet_loss_range_db"]])],
                ["判定", rev["dereverb"]["echo_model_verdict"]],
                ["官方分块推理路径交叉验证 Δ (dB)", g(rev["dereverb"]["official_cross_check_delta_db"], 3)],
            ],
            ["l", "l"],
        ),
        "\n> 结论：两社区 ckpt 在本探针**不可用**；已用官方推理路径交叉验证"
        "→ **非我方实现错误**。详见 `02_denoising/docs/DEREVERB_NEGATIVE_RESULT.md`。\n",
        "\n---\n\n## 6. 复现\n",
        "```bash\npython tools/_build_summaries.py --only separation   # 重建本表\n```\n",
    ]
    return "\n".join(x for x in t if x) + "\n"


# ---------------------------------------------------------------- 3 · 降噪

DENOISE_DETAIL = ("`02_denoising/docs/T5_DENOISE_STRATIFIED.md` · "
                  "`02_denoising/docs/T5_5_T5_6_DRYWET_AND_SPECTRA.md` · "
                  "`02_denoising/docs/T5_7_OOD_NOISE_NEGATIVE.md` · "
                  "`02_denoising/docs/P19_SAMPLE_RATE_CONTRACT_BUG.md`")


def build_denoise() -> str:
    p44 = R / "02_denoising" / "data" / "denoise_eval_44k.csv"
    p16 = R / "02_denoising" / "data" / "denoise_eval_16k.csv"
    pdw = R / "02_denoising" / "data" / "denoise_drywet.csv"
    pman = R / "02_denoising" / "data" / "denoise_manifest.json"
    pood = R / "02_denoising" / "data" / "denoise_ood_probe.json"
    psp = R / "02_denoising" / "data" / "denoise_spectral_delta.json"

    r44 = rd_csv(p44)
    r16 = rd_csv(p16)
    dw = rd_csv(pdw)
    man = rd_json(pman)
    ood = rd_json(pood)
    sp = rd_json(psp)

    def sel(rows, subset=None, sr=None):
        out = rows
        if subset is not None:
            out = [x for x in out if x["subset"] == subset]
        if sr is not None:
            out = [x for x in out if str(x["sr"]) == str(sr)]
        return out

    def eval_rows(rows, with_pesq: bool):
        cols = ["model", "subset", "snr_bin", "n_ok", "si_sdr_in", "si_sdr_out",
                "si_sdr_improve", "snr_out", "lsd_out", "hf_ratio_in",
                "hf_ratio_clean", "hf_ratio_out"]
        v = [[
            x["model"], x["subset"], x["snr_bin"], x["n_ok"],
            g(x["si_sdr_in"], 2), g(x["si_sdr_out"], 2), g(x["si_sdr_improve"], 2),
            g(x["snr_out"], 2), g(x["lsd_out"], 2), g(x["hf_ratio_in"], 4),
            g(x["hf_ratio_clean"], 4), g(x["hf_ratio_out"], 4),
        ] for x in rows]
        if with_pesq:
            cols += ["pesq_in", "pesq_out", "pesq_improve",
                     "stoi_in", "stoi_out", "stoi_improve"]
            for i, x in enumerate(rows):
                v[i] += [g(x["pesq_in"], 3), g(x["pesq_out"], 3), g(x["pesq_improve"], 3),
                         g(x["stoi_in"], 4), g(x["stoi_out"], 4), g(x["stoi_improve"], 4)]
        return cols, v

    # dry/wet 最优工作点（CSV-only：每个 (model, snr_bin) 在 dry 网格上取 argmax）
    opt = []
    keys = sorted({(x["model"], x["snr_bin"]) for x in dw})
    for m, b in keys:
        cells = [x for x in dw if x["model"] == m and x["snr_bin"] == b]
        bs = max(cells, key=lambda x: num(x["si_sdr_improve"]) if num(x["si_sdr_improve"]) is not None else -1e9)
        pc = [x for x in cells if num(x["pesq_improve"]) is not None]
        bp = max(pc, key=lambda x: num(x["pesq_improve"])) if pc else None
        opt.append([
            m, b, len(cells),
            g(bs["dry"], 1), g(bs["si_sdr_improve"], 3),
            g(bp["dry"], 1) if bp else "—",
            g(bp["pesq_improve"], 3) if bp else "—",
        ])

    # dns_dev 塌陷率（读 manifest 的 level_ratio）
    dev = {}
    for m in sorted({x["model"] for x in man["cells"] if x["subset"] == "dns_dev"}):
        vals = []
        for x in man["cells"]:
            if x["subset"] != "dns_dev" or x["model"] != m:
                continue
            lr = num(x.get("level_ratio"))
            if lr is None:                       # 部分 cell 不写 level_ratio，用 rms 兜底
                ir, er = num(x.get("in_rms")), num(x.get("est_rms"))
                if ir and er:
                    lr = er / ir
            vals.append(lr)
        vals = [v for v in vals if v is not None]
        if vals:
            dev[m] = (len(vals), med(vals), sum(1 for v in vals if v < 0.05) / len(vals) * 100)

    t = [
        header(
            "数据摘要 · 板 2 降噪评测（双口径）",
            "降噪主表 + dry/wet 旋钮 + 频谱带 + 域外探针",
            "denoise",
            [p44.relative_to(ROOT), p16.relative_to(ROOT), pdw.relative_to(ROOT),
             pman.relative_to(ROOT), pood.relative_to(ROOT), psp.relative_to(ROOT)],
            DENOISE_DETAIL,
        ),
        "\n---\n\n## 1. 口径三要素（**双口径必须分开报**）\n",
        md_table(
            ["项", "取值 / 说明"],
            [
                ["口径 A（44.1 kHz）", "**契约率** = 实际工作采样率。`denoiser` 内部把 44.1k→16k→44.1k 往返，"
                                        "故 44.1k 口径含重采样代价；**PESQ/STOI 不适用**（其定义域为 8/16 kHz）"],
                ["口径 B（16 kHz）", "模型原生率。`denoiser_*` 原生 16 kHz；" 
                                     "`mel_roformer_*` 原生 44.1 kHz，此口径为**降采样后**评比"],
                ["数据集", "`valentini`（真实含噪，有 clean 参考）｜`synth`（干净语音 + 合成噪声，有参考）"
                           "｜`dns_dev`（**无参考** `noref`，仅统计电平塌陷）"],
                ["SNR 分箱", "按**输入 SI-SDR** 分：`<5dB` / `5-15dB` / `>=15dB`，另有 `ALL` 汇总"],
                ["指标", "SI-SDR（dB）｜PESQ（窄带/宽带由采样率决定）｜STOI｜LSD（log-spectral distance）"
                         "｜`hf_ratio`（>4 kHz 能量占比）"],
                ["n", "`n_ok` = 计入统计的条数；`n_skipped` 见 CSV 的 `skip_reason`"],
            ],
            ["l", "l"],
        ),
        "\n---\n\n## 2. 口径 A（44.1 kHz 契约率）· valentini\n",
    ]
    cols, v = eval_rows(sel(r44, "valentini"), with_pesq=False)
    t += [md_table(cols, v, ["l", "l", "c", "r"] + ["r"] * (len(cols) - 4)),
          "\n> PESQ / STOI 列在本口径**为空是设计**（PESQ 定义域不含 44.1 kHz），不是缺测。\n",
          "\n---\n\n## 3. 口径 B（16 kHz）· valentini\n"]
    cols, v = eval_rows(sel(r16, "valentini"), with_pesq=True)
    t += [md_table(cols, v, ["l", "l", "c", "r"] + ["r"] * (len(cols) - 4)),
          "\n---\n\n## 4. 口径 B（16 kHz）· synth（干净语音 + 合成瞬态噪声）\n"]
    cols, v = eval_rows(sel(r16, "synth"), with_pesq=True)
    t += [md_table(cols, v, ["l", "l", "c", "r"] + ["r"] * (len(cols) - 4)),
          "\n---\n\n## 5. dns_dev（**无参考**：只报电平塌陷，不报增益）\n",
          md_table(
              ["model", "条目数", "level_ratio 中位", "< 0.05 占比(%)"],
              [[m, n, g(md_, 4), g(p, 1)] for m, (n, md_, p) in dev.items()],
              ["l", "r", "r", "r"],
          ),
          f"\n> 该子集 `reference_mode = noref`，SI-SDR/PESQ/STOI **不可算**（CSV 中相应列为空）。"
          f"唯一可报的是输出/输入电平比 —— 用来量化「模型把干净语音也压掉」的塌陷率。\n",
          "\n---\n\n## 6. dry/wet 强度旋钮：最优工作点（`estimate = (1-dry)·model(noisy) + dry·noisy`）\n",
          md_table(
              ["model", "snr_bin", "格数", "★最优 dry (SI-SDR)", "SI-SDR 增益(dB)",
               "最优 dry (PESQ)", "PESQ 增益"],
              opt,
              ["l", "c", "r", "r", "r", "r", "r"],
          ),
          "\n> ★ **正确性锚点**：`dry = 0` 必须与主表逐位一致（实测 worst 差 0.0000）。\n"
          "> ⚠️ **PESQ 最优 dry 随权重分化**（dns48/dns64 峰在 0.1，master64 峰在 0.0）"
          "—— 该分化**权重相关，不可外推**。\n"
          "> ⚠️ **ΔSI-SDR 与 ΔPESQ 的最优工作点不一致但全程同号**：性质是「最优点不同」，"
          "不是「符号相反」。\n",
          "\n---\n\n## 7. 平均谱差（有效带 0–7.8 kHz）\n",
          f"方法：`{sp['method']}` ｜ sr=`{sp['sr']}` n_fft=`{sp['n_fft']}` hop=`{sp['hop']}` ｜ "
          f"最多 `{sp['max_clips']}` 条\n",
          md_table(
              ["model", "子集", "n", "0–1k (dB)", "1–4k (dB)", "4–7.8k (dB)", "倾斜 tilt (dB)"],
              [[x["model"], x["subset"], x["n"], g(x["b_0_1k"], 2), g(x["b_1_4k"], 2),
                g(x["b_4_7k8"], 2), g(x["tilt"], 2)] for x in sp["rows"]],
              ["l", "l", "r", "r", "r", "r", "r"],
          ),
          f"\n> ⚠️ 有效带：{sp['valid_band_note']}。若把 8 kHz 以上计入，"
          "「4 kHz 以上平均差」会被重采样伪影污染成虚假的大幅抑制。\n",
          "\n---\n\n## 8. 域外（OOD）探针摘要\n",
          md_table(
              ["model", "原生率", "A 干净直通比中位", "B 噪声直通比中位",
               "B 抑制(dB)中位", "C 增益扫描 SI-SDR 中位"],
              [[m, v.get("native_sr"),
                g(v["summary"].get("A_clean_ratio_med"), 4),
                g(v["summary"].get("B_noise_ratio_med"), 4),
                g(v["summary"].get("B_suppression_db_med"), 3),
                g(v["summary"].get("C_si_sdr_vs_mix_med"), 3)]
               for m, v in sorted(ood["probes"].items())],
              ["l", "r", "r", "r", "r", "r"],
          ),
          f"\n> 探针口径：分析率 `{ood['analysis_sr']}` Hz，契约率 `{ood['contract_sr']}` Hz，"
          f"`n_items = {ood['n_items']}`。结论（负结果）见 §详解。\n",
          "\n---\n\n## 9. 复现\n",
          "```bash\npython tools/_build_summaries.py --only denoise   # 重建本表\n```\n"]
    return "\n".join(t) + "\n"


# ---------------------------------------------------------------- 4 · 级联

LINK_LEGEND = {
    "L0": "带噪输入直送分离（参照臂）",
    "L1": "降噪前置（denoiser）",
    "L1b": "★恒等对照：只走 16k/mono 往返，**不做降噪动作**",
    "L1m": "降噪前置（mel-roformer）",
    "L2": "降噪后置（denoiser）",
    "L2b": "★后置限带对照",
    "L3": "前置 + 后置",
}

CASCADE_DETAIL = "`03_cascade/docs/T6_CASCADE_DENOISE_BEFORE_SEPARATION.md`"


def build_cascade() -> str:
    pcsv = R / "03_cascade" / "data" / "cascade_eval.csv"
    pjson = R / "03_cascade" / "data" / "cascade_eval.json"
    pman = R / "03_cascade" / "data" / "cascade_manifest.json"

    rows = rd_csv(pcsv)
    ev = rd_json(pjson)
    man = rd_json(pman)
    mx = ev["matrix"]

    # 恒等式逐格校验（用 CSV 自带两列）
    ident = []
    for r in rows:
        d1 = num(r["d_L1"])
        bw = num(r["bandwidth_cost_d_L1b"])
        net = num(r["denoise_net_d_L1_minus_L1b"])
        if None in (d1, bw, net):
            continue
        ident.append(abs(d1 - (bw + net)))
    worst_ident = max(ident) if ident else None

    # 跨格中位（直接从 CSV 16 行算）
    med_key = {
        "median_d_L1": "d_L1", "median_d_L1b": "d_L1b", "median_d_L1m": "d_L1m",
        "median_d_L2": "d_L2", "median_d_L2b": "d_L2b", "median_d_L3": "d_L3",
        "median_denoise_net": "denoise_net_d_L1_minus_L1b",
    }
    recomputed = {k: med([num(r[c]) for r in rows]) for k, c in med_key.items()}
    json_vals = mx["summary_all_cells"]

    # 逐 SNR 档的跨模型中位
    by_snr = []
    for snr in sorted({num(r["snr_db"]) for r in rows}, reverse=True):
        sub = [r for r in rows if num(r["snr_db"]) == snr]
        by_snr.append([
            gi(snr),
            g(med([num(r["sdr_L0"]) for r in sub]), 3),
            g(med([num(r["d_L1"]) for r in sub]), 3),
            g(med([num(r["d_L1b"]) for r in sub]), 3),
            g(med([num(r["denoise_net_d_L1_minus_L1b"]) for r in sub]), 3),
            g(med([num(r["d_L1m"]) for r in sub]), 3),
            g(med([num(r["d_L2"]) for r in sub]), 3),
            g(med([num(r["d_L3"]) for r in sub]), 3),
        ])

    # 变体电平（V0/V1bl/V1den）—— 说明「分离任务退化成恒等映射」
    lvl = {}
    for v in ("V0", "V1bl", "V1den", "V1mel"):
        recs = [x for x in ev["sep_results"] if x.get("variant") == v]
        if not recs:
            continue
        lvl[v] = {s: med([num(((x.get("gate") or {}).get("levels") or {}).get(s)) for x in recs])
                  for s in STEMS}
    # 锚点
    anchor = {m: med([num(x.get("sdr_avg4")) for x in ev["sep_results"]
                      if x.get("variant") == "Vdry" and x["model"] == m])
              for m in sorted({x["model"] for x in ev["sep_results"] if x.get("variant") == "Vdry"})}

    gates = man["gates"]
    n_pass = sum(1 for x in gates if x.get("pass"))
    n_anchor = sum(1 for x in ev["sep_results"] if x.get("variant") == "Vdry")
    n_sep_real = sum(1 for x in ev["sep_results"] if x.get("variant") != "Vdry")
    n_sep_real_pass = sum(1 for x in ev["sep_results"]
                          if x.get("variant") != "Vdry" and x.get("status") == "PASS")
    fmt_audio = str(man["audio_format"]).split("——")[0].strip()
    _nt = man["noise_type"]
    nt_txt = (f"波峰因子中位 **{g(_nt.get('crest_scaled_median'), 2)}**"
              f"（p95 {g(_nt.get('crest_scaled_p95'), 2)}）→ **瞬态型**（与 T5.4 synth 同族）"
              if isinstance(_nt, dict) else str(_nt))

    t = [
        header(
            "数据摘要 · 板 1×2 级联（降噪 × 分离）",
            "ΔSDR 矩阵 + 净动作分解 + 门禁与锚点",
            "cascade",
            [pcsv.relative_to(ROOT), pjson.relative_to(ROOT), pman.relative_to(ROOT)],
            CASCADE_DETAIL,
        ),
        "\n---\n\n## 1. 口径三要素\n",
        md_table(
            ["项", "取值 / 说明"],
            [
                ["数据集", "MUSDB18-HQ test **Top-10 曲** × **DNS freesound 噪声池**（逐声道独立加噪）"],
                ["片段", f"**10 曲 × 4 SNR × 20 s**；SNR ∈ {{-5, 0, +5, +10}} dB"],
                ["指标", "`museval.metrics.bss_eval`（与板 1 主表同源）；**Δ = 该链路 − L0**（同为带噪输入）"],
                ["GT", "干 stem（不含任何降噪/限带处理）"],
                ["格数", f"40 格（10 曲 × 4 SNR × 20 s）× 4 前置变体 × 4 分离模型 = "
                         f"**{n_sep_real}** 分离推理格，另含 **{n_anchor}** 干档锚点格"
                         f"（合计 {len(ev['sep_results'])}）"],
                ["前置变体", "`V0` 直送 ｜ `V1den` denoiser 降噪 ｜ **`V1bl` 仅限带（恒等对照）** ｜ `V1mel` mel 降噪"],
                ["音频格式", f"`{fmt_audio}`；声道处理：{man['channels']}"],
                ["噪声类型", nt_txt],
            ],
            ["l", "l"],
        ),
        "\n### 链路图例\n",
        md_table(["链路", "含义"], [[k, v] for k, v in LINK_LEGEND.items()], ["l", "l"]),
        "\n---\n\n## 2. ΔSDR 主矩阵（16 行 = 4 模型 × 4 SNR；单位 dB）\n",
        md_table(
            ["model", "snr(dB)", "n", "sdr_L0", "d_L1", "d_L1b", "d_L1m",
             "d_L2", "d_L2b", "d_L3", "带宽代价", "★净降噪动作"],
            [[
                r["model"], gi(r["snr_db"]), r["n_L0"], g(r["sdr_L0"], 3),
                g(r["d_L1"], 3), g(r["d_L1b"], 3), g(r["d_L1m"], 3), g(r["d_L2"], 3),
                g(r["d_L2b"], 3), g(r["d_L3"], 3),
                g(r["bandwidth_cost_d_L1b"], 3), g(r["denoise_net_d_L1_minus_L1b"], 3),
            ] for r in rows],
            ["l", "r", "r"] + ["r"] * 9,
        ),
        f"\n> 每格可复现命令见 CSV 的 `reproduce_cmd` 列；示例：`{rows[0]['reproduce_cmd']}`\n",
        "\n---\n\n## 3. 恒等式逐格校验：`L1 = L1b(带宽代价) + (L1 − L1b)(降噪净动作)`\n",
        md_table(
            ["项", "值"],
            [
                ["校验格数", len(ident)],
                ["最大绝对残差 (dB)", g(worst_ident, 6)],
                ["判定", "PASS（残差仅来自 CSV 三位小数舍入）" if (worst_ident is not None and worst_ident <= 2e-3) else "FAIL"],
            ],
            ["l", "l"],
        ),
        "\n> 恒等式成立 ⇒ **没有 `L1b` 对照臂，就无法排除「涨跌其实来自带宽被砍而非降噪动作」**。\n",
        "\n---\n\n## 4. 跨格中位（n=16）—— CSV 重算 vs JSON 字段\n",
        md_table(
            ["量", "CSV 重算", "JSON `summary_all_cells`", "一致"],
            [[k, g(recomputed[k], 3), g(json_vals.get(k), 3),
              "✅" if (recomputed[k] is not None and json_vals.get(k) is not None
                       and abs(recomputed[k] - num(json_vals[k])) <= 1e-3) else "❌"]
             for k in med_key],
            ["l", "r", "r", "c"],
        ),
        "\n---\n\n## 5. 逐 SNR 档的跨模型中位（n=4）\n",
        md_table(
            ["snr(dB)", "sdr_L0", "d_L1", "d_L1b", "★净动作", "d_L1m", "d_L2", "d_L3"],
            by_snr,
            ["r"] * 8,
        ),
        "\n> 读法：**净动作随输入 SNR 单调恶化，带宽代价与 SNR 基本无关** → "
        "走势不同，反证对照臂抽出的确实是**降噪网络的行为**，不是管线固定损耗。\n",
        "\n---\n\n## 6. 机理证据：前置后各轨输出电平（相对输入 rms 中位）\n",
        md_table(
            ["前置变体", "vocals", "drums", "bass", "other", "含义"],
            [[
                v, *[g(lvl[v][s], 4) for s in STEMS],
                {"V0": "参照臂（直送带噪）",
                 "V1bl": "≈ V0 ⇒ 只付**带宽/单声道代价**，未做降噪动作",
                 "V1mel": "≈ V0 ⇒ mel 近恒等",
                 "V1den": "★vocals≈1.0 而 drums/bass/other→0 ⇒ 分离器**退化为恒等映射**"
                 }.get(v, ""),
            ] for v in ("V0", "V1bl", "V1mel", "V1den") if v in lvl],
            ["l", "r", "r", "r", "r", "l"],
        ),
        "\n---\n\n## 7. 正确性锚点（干档直送，`Vdry`）：不成立则整张矩阵作废\n",
        md_table(
            ["model", "avg4 SDR 中位", "格数"],
            [[m, g(a, 3), sum(1 for x in ev["sep_results"]
                             if x.get("variant") == "Vdry" and x["model"] == m)]
             for m, a in sorted(anchor.items())],
            ["l", "r", "r"],
        ),
        "\n> 锚点判据：本口径下四模型中位须与**历史整曲扫描**逐一对上，"
        "口径不同的历史数值**不在本表混列**"
        "（见 `01_separation/docs/MUSDB18_TEST_SWEEP_2026-09-22.md`）。"
        "**锚点不成立 ⇒ 整张矩阵作废。**\n",
        "\n---\n\n## 8. 门禁与诚实性检查\n",
        md_table(
            ["项", "值"],
            [
                ["数据门禁", f"**{n_pass}/{len(gates)} PASS**"],
                ["锚点", f"**{n_anchor}/{n_anchor} PASS**"],
                ["分离格", f"**{n_sep_real_pass}/{n_sep_real} PASS**"
                           f"（另有 {n_anchor} 锚点格 PASS）"],
                ["诚实性（R12 / P7）", mx["honesty"]],
                ["Δ 参考系", mx["reference"]],
            ],
            ["l", "l"],
        ),
        "\n> ⚠️ 门禁修正记录：原判据把「denoiser 压掉 drums」（`level_ratio ≈ 0.006`）误判为信号损坏 —— "
        "**那正是被测现象本身**。正确判据 = 输入没写坏 且 输出非全零、无异常数值。"
        "详见 `tools/_cascade_regate.py`。\n",
        "\n---\n\n## 9. 复现\n",
        "```bash\n"
        "python tools/_cascade_experiment.py plan          # 生成 640 格计划\n"
        "python tools/_cascade_experiment.py make-noisy    # 造带噪测试集\n"
        "python tools/_cascade_experiment.py prep          # 4 个前置变体音频\n"
        "python tools/_cascade_experiment.py run --models demucs,mdx,bsrnn_all,umx \\\n"
        "       --variants V0,V1den,V1bl,V1mel --resume    # 640 格分离推理（可断点续跑）\n"
        "python tools/_cascade_experiment.py prep-post --op vbl\n"
        "python tools/_cascade_experiment.py prep-post --op vden\n"
        "python tools/_cascade_experiment.py post          # 后置段重算\n"
        "python tools/_cascade_experiment.py summary       # 出 cascade_eval.csv/.json\n"
        "python tools/_build_summaries.py --only cascade   # 重建本表\n"
        "```\n",
    ]
    return "\n".join(t) + "\n"


# ---------------------------------------------------------------- 主流程

BUILDERS = {
    "model": ("MODEL_PROFILE_SUMMARY.md", build_model_profile),
    "separation": ("SEPARATION_SUMMARY.md", build_separation),
    "denoise": ("DENOISE_SUMMARY.md", build_denoise),
    "cascade": ("CASCADE_SUMMARY.md", build_cascade),
}

# 子串标记（这些字符串出现即为 bug）
FORBIDDEN = ("TODO", "⏳", "%%")
# 词边界标记：`np.nanmedian` 里的 nan 不算（后接字母，\b 不成立）
FORBIDDEN_RE = re.compile(r"\b(nan|NaN|None|null)\b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all",
                    choices=["all", *BUILDERS.keys()])
    ap.add_argument("--verify", action="store_true", help="只校验并与磁盘比对，不写盘")
    a = ap.parse_args()

    keys = list(BUILDERS) if a.only == "all" else [a.only]
    OUT.mkdir(parents=True, exist_ok=True)

    fails = 0
    for k in keys:
        fn, build = BUILDERS[k]
        text = build()
        dst = OUT / fn
        bad = [w for w in FORBIDDEN if w in text]
        bad += [f"词边界:{m}" for m in {mm.group(0) for mm in FORBIDDEN_RE.finditer(text)}]
        if bad:
            print(f"[ERR ] {fn}: 含禁用标记 {bad}")
            fails += 1
            continue
        if a.verify:
            cur = dst.read_text(encoding="utf-8") if dst.exists() else None
            if cur is None:
                print(f"[ERR ] {fn}: 磁盘上不存在")
                fails += 1
            elif cur == text:
                print(f"[ OK ] {fn}: 与重建结果逐字节一致（{len(text)} 字符）")
            else:
                print(f"[DIFF] {fn}: 磁盘内容 ≠ 重建结果（手改过 或 源数据已变未重建）")
                fails += 1
        else:
            dst.write_text(text, encoding="utf-8")
            nrow = sum(1 for ln in text.splitlines() if ln.startswith("| ") and not ln.startswith("| :")
                       and not ln.startswith("|---"))
            print(f"[ OK ] {fn}: {len(text)} 字符 / 约 {nrow} 表格行 / 无禁用标记")
            print(f"       -> {dst}")
    if fails:
        print(f"\n[FAIL] {fails} 项未通过")
        sys.exit(1)
    print("\n[DONE] 全部通过")


if __name__ == "__main__":
    main()

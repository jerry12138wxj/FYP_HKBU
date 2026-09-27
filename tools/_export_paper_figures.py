# -*- coding: utf-8 -*-
"""T8.1 / T8.2 · 论文图表包导出（交付物 D12）

D12 DoD：**全部 300 dpi，图注含口径三要素（数据集 / 片段 / 指标定义）**。

机制（零改动原绘图脚本）
    各绘图脚本用 `plt.rcParams["figure.dpi"]=130/140` 且 `savefig()` **不传 dpi**，
    故 matplotlib 走 `savefig.dpi`。本工具注入 `MATPLOTLIBRC`（内含 `savefig.dpi: 300`）
    后重跑脚本 → **同一物理尺寸、像素 ×2.14**，是真重渲染，不是改 DPI 标签。

安全前置（重要）
    部分脚本**会重算/改写数据**。本工具：
      1. 渲染前对所有 `04_reports/**/data/**` 的 json/csv 做内容快照（剥掉 volatile 键）；
      2. 渲染后再次快照并逐文件比对 → **任何数值变化立即 FAIL 并列出**；
      3. 显式标记 `render=False` 的图（含 torch / 写死 dpi）**不重跑**，如实记录为缺口。

用法
    python tools/_export_paper_figures.py --board 1 check     # 只体检，不写盘
    python tools/_export_paper_figures.py --board 1 render    # 渲染 + 导出 + 校验
    python tools/_export_paper_figures.py --board 1 captions  # 出 docs/PAPER_FIGURES.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "04_reports"
PAPER = R / "00_shared" / "figures" / "paper"
DOC = R / "00_shared" / "docs" / "PAPER_FIGURES.md"   # 基名；实际按板分文件，见 doc_for()
MPLRC = ROOT / "tools" / "_scratch" / "mplrc_paper"
TARGET_DPI = 300
COL_SINGLE_IN, COL_DOUBLE_IN = 3.35, 7.0     # 单栏 8.5 cm / 双栏 17.8 cm
NEED_ONE = int(TARGET_DPI * COL_SINGLE_IN)   # 1005 px
NEED_TWO = int(TARGET_DPI * COL_DOUBLE_IN)   # 2100 px

# ------------------------------------------------------------------ 口径分组
# 图注的「口径三要素」按组继承（同组图共用一个实验口径），避免逐图手抄失真。
GROUPS = {
    "G-ARCH": dict(
        name="架构原理图",
        dataset="N/A（结构示意，不含实验数据）",
        clip="N/A",
        metric="框内 shape / 参数量取自 `graph_*.json` 溯源；成本口径见模型画像摘要",
    ),
    "G-PROFILE": dict(
        name="模型画像图",
        dataset="统一**合成**输入（不取自数据集）",
        clip="10 s / 44.1 kHz / 立体声",
        metric="参数量 `sum(numel)`；FLOPs = 2×MACs **下界**；时延 5 次中位数",
    ),
    "G-ACC": dict(
        name="分离精度图",
        dataset="MUSDB18-HQ **train** 抽段",
        clip="3 首 × 10 s",
        metric="`museval.metrics.bss_eval` SDR（窗 88200 / hop 66150，逐帧 nanmedian）",
    ),
    "G-COST": dict(
        name="实机成本图",
        dataset="MUSDB18-HQ **test** 50 首",
        clip="整曲",
        metric="wall time / RTF / SDR 均值；**单轨模型（1:50）的 SDR 不可与四轨（4:50）直接比**",
    ),
    "G-SPEC": dict(
        name="信号级频谱图",
        dataset="MUSDB18-HQ train 抽段",
        clip="见各图注（默认 10 s）",
        metric="STFT 幅度（dB）；窗长对比图用 win 1024 vs 128",
    ),
    "G-REV": dict(
        name="混响 / 回声退化图",
        dataset="MUSDB18-HQ train 抽段 + AIR/合成 RIR",
        clip="3 首 × 10 s",
        metric="ΔSDR(dB) = 湿 − 干；**T60 为导出口径 44.1 kHz**（非源 48 kHz）",
    ),
    "G-DN": dict(
        name="板 2 降噪结果图",
        dataset="`valentini`（真实含噪，有 clean 参考）+ `synth`（干净语音 + 合成瞬态噪声）",
        clip="整条 utterance（valentini 824 条 / synth 800 条），16 kHz 口径",
        metric="SI-SDR(dB) / PESQ / STOI / LSD；`hf_ratio` = >4 kHz 能量占比",
    ),
    "G-CAS": dict(
        name="板 1×2 级联图",
        dataset="MUSDB18-HQ test Top-10 曲 × DNS freesound 噪声池（逐声道独立加噪）",
        clip="10 曲 × 4 SNR × 20 s",
        metric="ΔSDR(dB) = 该链路 − L0；GT = 干 stem；museval bss_eval（与板 1 主表同源）",
    ),
    "G-S4": dict(
        name="阶段 4 一页汇总",
        dataset="同 G-REV（混响 + 回声两组实验汇总）",
        clip="3 首 × 10 s",
        metric="ΔSDR(dB)；曲线为 6 模型均值，大厅档 `bsrnn_all` n=1 已标注不参与排名",
    ),
}

# ------------------------------------------------------------------ 论文图清单
# render=False  = 不重跑（含 torch 重算 / 写死 dpi），如实记为缺口
FIGSET: list[dict] = [
    dict(id="fig-arch-irm", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_01_irm_ibm_oracle.png",
         script="_plot_model_arch.py", title="IRM / IBM Oracle 结构（解析基线）"),
    dict(id="fig-arch-rpca", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_02_rpca_inexact_alm.png",
         script="_plot_model_arch.py", title="RPCA (Inexact-ALM) 流程"),
    dict(id="fig-arch-convtasnet", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_03_conv_tasnet.png",
         script="_plot_model_arch.py", title="Conv-TasNet（时域分离）"),
    dict(id="fig-arch-dprnn", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_04_dprnn.png",
         script="_plot_model_arch.py", title="DPRNN（自训）"),
    dict(id="fig-arch-mmdenselstm", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_05_mmdenselstm.png",
         script="_plot_model_arch.py", title="MMDenseLSTM"),
    dict(id="fig-arch-umx", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_06_open_unmix_umxhq.png",
         script="_plot_model_arch.py", title="Open-Unmix (umxhq)"),
    dict(id="fig-arch-demucs", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_07_demucs_v4_htdemucs.png",
         script="_plot_model_arch.py", title="Demucs v4 / HTDemucs"),
    dict(id="fig-arch-mdx", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_08_mdx_net_kuielab_mdx_extra.png",
         script="_plot_model_arch.py", title="MDX-Net (KUIELAB mdx_extra)"),
    dict(id="fig-arch-bsroformer", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_09_bs_roformer.png",
         script="_plot_model_arch.py", title="BS-RoFormer"),
    dict(id="fig-arch-bsrnn", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_10_bsrnn.png",
         script="_plot_model_arch.py", title="BSRNN（oBSRNN）"),
    dict(id="fig-arch-denoiser", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_11_denoiser.png",
         script="_plot_model_arch.py", title="denoiser（板 2）"),
    dict(id="fig-arch-melden", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_12_mel_band_roformer_denoise_aufr33.png",
         script="_plot_model_arch.py", title="Mel-Band-RoFormer-Denoise (aufr33)"),
    dict(id="fig-arch-dereverb", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_13_mel_band_roformer_dereverb_anvuew.png",
         script="_plot_model_arch.py", title="Mel-Band-RoFormer-Dereverb (anvuew)"),
    dict(id="fig-arch-dereverb-echo", b=1, g="G-ARCH", src="00_shared/figures/model_arch/arch_14_mel_band_roformer_dereverb_echo_sucial.png",
         script="_plot_model_arch.py", title="Mel-Band-RoFormer-Dereverb-Echo (sucial)"),
    dict(id="fig-profile-params-flops", b=1, g="G-PROFILE",
         src="00_shared/figures/model_arch/profile_params_flops.png",
         script="_plot_model_profile.py", title="参数量 / FLOPs 对比"),
    dict(id="fig-profile-pareto", b=1, g="G-PROFILE",
         src="00_shared/figures/model_arch/profile_pareto.png",
         script="_plot_model_profile.py", title="成本—容量 Pareto"),
    dict(id="fig-acc-main-table", b=1, g="G-ACC",
         src="01_separation/figures/comparison/fig_avg_sdr_table.png",
         script="_make_sdr_table.py", title="分离精度主表（重绘）",
         note="脚本已写死 `dpi=300`，原生达标"),
    dict(id="fig-acc-bars", b=1, g="G-ACC",
         src="01_separation/figures/comparison/fig_median_sdr_bars.png",
         script="plot_median_summary.py", title="分模型 SDR 中位条形图"),
    dict(id="fig-acc-per-stem", b=1, g="G-ACC",
         src="01_separation/figures/comparison/fig_median_per_stem.png",
         script="plot_median_summary.py", title="逐轨 SDR 中位"),
    dict(id="fig-acc-pareto", b=1, g="G-ACC",
         src="01_separation/figures/comparison/fig_median_pareto.png",
         script="plot_median_summary.py", title="精度—速度 Pareto"),
    dict(id="fig-acc-dsdr", b=1, g="G-ACC",
         src="01_separation/figures/comparison/fig_compare_dsdr.png",
         script="compare_separation_methods.py", title="与基线对照的 ΔSDR",
         render=False, note="脚本 `import torch` 且写死 `dpi=150` → **不重跑**（会触发重算与数据改写）"),
    dict(id="fig-rev-degradation", b=1, g="G-REV",
         src="01_separation/figures/comparison/fig_reverb_degradation.png",
         script="_plot_reverb_curve.py", title="混响 T60 → ΔSDR 退化曲线"),
    dict(id="fig-rev-rir-t60", b=1, g="G-REV",
         src="01_separation/figures/comparison/fig_rir_t60.png",
         script="_plot_rir.py", title="RIR 本体与 T60 估计（已剔直达声）"),
    dict(id="fig-echo-degradation", b=1, g="G-REV",
         src="01_separation/figures/comparison/fig_echo_degradation.png",
         script="_plot_echo_curve.py", title="回声延迟/增益 → ΔSDR 退化曲线"),
    dict(id="fig-stage4-summary", b=1, g="G-S4",
         src="01_separation/figures/comparison/fig_stage4_summary.png",
         script="_plot_stage4_summary.py", title="阶段 4 答辩一页图"),
    dict(id="fig-cost-time-per-song", b=1, g="G-COST",
         src="01_separation/figures/figs_time/fig1_time_per_song.png",
         script="plot_bench_10songs.py", title="逐曲推理耗时"),
    dict(id="fig-cost-cumulative", b=1, g="G-COST",
         src="01_separation/figures/figs_time/fig2_time_cumulative.png",
         script="plot_bench_10songs.py", title="累计耗时"),
    dict(id="fig-cost-rtf", b=1, g="G-COST",
         src="01_separation/figures/figs_time/fig3_rtf_per_song.png",
         script="plot_bench_10songs.py", title="逐曲 RTF"),
    dict(id="fig-cost-dist", b=1, g="G-COST",
         src="01_separation/figures/figs_time/fig4_time_distribution.png",
         script="plot_bench_10songs.py", title="耗时分布"),
    dict(id="fig-cost-vs-acc", b=1, g="G-COST",
         src="01_separation/figures/figs_time/fig5_time_vs_accuracy.png",
         script="plot_bench_10songs.py", title="耗时 vs 精度"),
    dict(id="fig-cost-panels", b=1, g="G-COST",
         src="01_separation/figures/figs_time/fig6_compare_panels.png",
         script="plot_bench_10songs.py", title="成本多面板对比"),
    dict(id="fig-cost-pareto", b=1, g="G-COST",
         src="01_separation/figures/figs_time/fig7_pareto_speed_accuracy.png",
         script="plot_bench_10songs.py", title="速度—精度 Pareto"),
    dict(id="fig-spec-mixture", b=1, g="G-SPEC",
         src="01_separation/figures/audio_analysis/fig3_spectrogram_mixture.png",
         script="_make_spectrogram_panels.py", title="混音时频谱"),
    dict(id="fig-spec-vocals", b=1, g="G-SPEC",
         src="01_separation/figures/audio_analysis/fig3_spectrogram_vocals.png",
         script="_make_spectrogram_panels.py", title="人声轨时频谱"),
    dict(id="fig-spec-win1024", b=1, g="G-SPEC",
         src="01_separation/figures/audio_analysis/fig4_spectrogram_win1024.png",
         script="_make_spectrogram_panels.py", title="窗长对比：win 1024"),
    dict(id="fig-spec-win128", b=1, g="G-SPEC",
         src="01_separation/figures/audio_analysis/fig4_spectrogram_win128.png",
         script="_make_spectrogram_panels.py", title="窗长对比：win 128"),
    dict(id="fig-spec-waveform", b=1, g="G-SPEC",
         src="01_separation/figures/audio_analysis/fig1_waveform_mixture_vocals.png",
         script="_make_spectrogram_panels.py", title="波形：混音 vs 人声"),
    dict(id="fig-spec-sr", b=1, g="G-SPEC",
         src="01_separation/figures/audio_analysis/fig2_waveform_sr_compare.png",
         script="_make_spectrogram_panels.py", title="采样率对比波形"),
    # ------------------------------------------------------------ 板 2 (T8.2)
    dict(id="fig-dn-suppression", b=2, g="G-DN", src="02_denoising/figures/fig_denoise_suppression.png",
         script="_plot_denoise.py", title="降噪抑制量（按模型 / SNR 档）"),
    dict(id="fig-dn-synth-gain", b=2, g="G-DN", src="02_denoising/figures/fig_denoise_synth_gain.png",
         script="_plot_denoise.py", title="合成集增益（干净语音 + 瞬态噪声）"),
    dict(id="fig-dn-domain-reversal", b=2, g="G-DN",
         src="02_denoising/figures/fig_denoise_noise_domain_reversal.png",
         script="_plot_denoise.py", title="噪声域反转（真实噪声 vs 合成噪声）"),
    dict(id="fig-dn-metric-divergence", b=2, g="G-DN",
         src="02_denoising/figures/fig_denoise_metric_divergence.png",
         script="_denoise_diagnosis.py", title="三指标分歧诊断",
         render=False, note="脚本载入 `_denoise_registry` 做推理 -> **不重跑**（避免与已归档结果分歧）"),
    dict(id="fig-dn-drywet", b=2, g="G-DN", src="02_denoising/figures/fig_denoise_drywet.png",
         script="_plot_denoise_drywet.py", title="dry/wet 强度旋钮曲线"),
    dict(id="fig-dn-spec-master64-val", b=2, g="G-DN",
         src="02_denoising/figures/denoise/t5_6_denoiser_master64_valentini_spectral.png",
         script="_plot_denoise_spectral.py", title="频谱前后对比：master64 × valentini",
         render=False, note="脚本载入 `_denoise_registry` 做推理 -> **不重跑**"),
    dict(id="fig-dn-spec-master64-syn", b=2, g="G-DN",
         src="02_denoising/figures/denoise/t5_6_denoiser_master64_synth_spectral.png",
         script="_plot_denoise_spectral.py", title="频谱前后对比：master64 × synth",
         render=False, note="同上"),
    dict(id="fig-dn-spec-mel-val", b=2, g="G-DN",
         src="02_denoising/figures/denoise/t5_6_mel_roformer_denoise_valentini_spectral.png",
         script="_plot_denoise_spectral.py", title="频谱前后对比：mel-roformer × valentini",
         render=False, note="同上"),
    dict(id="fig-dn-spec-mel-syn", b=2, g="G-DN",
         src="02_denoising/figures/denoise/t5_6_mel_roformer_denoise_synth_spectral.png",
         script="_plot_denoise_spectral.py", title="频谱前后对比：mel-roformer × synth",
         render=False, note="同上"),
    dict(id="fig-dn-dspec-master64-val", b=2, g="G-DN",
         src="02_denoising/figures/denoise/t5_6_denoiser_master64_valentini_delta_spectrum.png",
         script="_plot_denoise_spectrum_delta.py", title="平均谱差：master64 × valentini",
         render=False, note="脚本载入 `_denoise_registry` 做推理 -> **不重跑**"),
    dict(id="fig-dn-dspec-master64-syn", b=2, g="G-DN",
         src="02_denoising/figures/denoise/t5_6_denoiser_master64_synth_delta_spectrum.png",
         script="_plot_denoise_spectrum_delta.py", title="平均谱差：master64 × synth",
         render=False, note="同上"),
    dict(id="fig-dn-dspec-mel-val", b=2, g="G-DN",
         src="02_denoising/figures/denoise/t5_6_mel_roformer_denoise_valentini_delta_spectrum.png",
         script="_plot_denoise_spectrum_delta.py", title="平均谱差：mel-roformer × valentini",
         render=False, note="同上"),
    dict(id="fig-dn-dspec-mel-syn", b=2, g="G-DN",
         src="02_denoising/figures/denoise/t5_6_mel_roformer_denoise_synth_delta_spectrum.png",
         script="_plot_denoise_spectrum_delta.py", title="平均谱差：mel-roformer × synth",
         render=False, note="同上"),
    dict(id="fig-cas-delta-matrix", b=2, g="G-CAS",
         src="03_cascade/figures/fig_cascade_delta_matrix.png",
         script="_plot_cascade.py", title="级联 ΔSDR 主矩阵（4 SNR × 4 模型 × 6 链路）"),
    dict(id="fig-cas-decomposition", b=2, g="G-CAS",
         src="03_cascade/figures/fig_cascade_decomposition.png",
         script="_plot_cascade.py", title="级联净动作分解（L1 vs L1b vs L1−L1b）"),
]

VOLATILE = {"generated", "updated", "timestamp", "created", "date"}
# 计时字段：重跑必然变化，属「运行环境」而非「实验内容」。**单独成集，用于二级判定**——
# 内容漂移（fatal）与计时漂移（可接受）必须分开报，绝不能靠放宽一级判据来消警。
TIMING = {"elapsed_s", "elapsed", "elapsed_sec", "duration_s", "wall_s"}


# ------------------------------------------------------------------ 数据快照
# pre-image / 精确 diff —— 只报「某文件变了」不足以定位，必须能给出字段级线索。

PRE = ROOT / "tools" / "_scratch" / "_pre_snapshot"


def keep_pre() -> None:
    """渲染前把 data/ 下的 json/csv 原样留一份，便于事后给出精确 diff。

    ⚠️ **绝不 rmtree**：本环境有批量删除护栏（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`），
    rmtree 会抛异常并让整条渲染流程 rc=1（实测：板 2 因此一张图都没出）。
    改为**覆盖写** + 落 `_index.json` 记录本次留了哪些文件（用于识别「新增」）。
    """
    PRE.mkdir(parents=True, exist_ok=True)
    idx = []
    for p in sorted(R.rglob("*")):
        if "data" not in p.parts or p.suffix.lower() not in (".json", ".csv"):
            continue
        rel = p.relative_to(ROOT).as_posix()
        dst = PRE / p.relative_to(R)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        idx.append(rel)
    (PRE / "_index.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"pre-image: {len(idx)} 个文件 -> {PRE.relative_to(ROOT).as_posix()}（覆盖写，不删）")


def _first_diff(x, y, path: str, out: list) -> None:
    """递归找出前若干处差异（跳过 volatile/计时键），写入 out。"""
    if len(out) >= 6:
        return
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if k in VOLATILE or k in TIMING:
                continue
            if k not in x or k not in y:
                out.append(f"{path}.{k}: 仅一侧存在")
                continue
            _first_diff(x[k], y[k], f"{path}.{k}", out)
    elif isinstance(x, list) and isinstance(y, list):
        if len(x) != len(y):
            out.append(f"{path}: 长度 {len(x)} -> {len(y)}")
        for i, (xi, yi) in enumerate(zip(x, y)):
            _first_diff(xi, yi, f"{path}[{i}]", out)
    elif x != y:
        out.append(f"{path}: {x!r} -> {y!r}")


def report_diff(files: list[str]) -> None:
    """对漂移文件给出 pre-image vs 现行的首处内容差异。"""
    for rel in files:
        pre = PRE / rel
        cur = ROOT / rel
        if not pre.exists() or not cur.exists():
            print(f"         {rel}: pre-image 缺失（本次新增或已被删），无法定位")
            continue
        if cur.suffix.lower() != ".json":
            print(f"         {rel}: 非 json，请人工比对")
            continue
        try:
            a = json.loads(pre.read_text(encoding="utf-8-sig"))
            b = json.loads(cur.read_text(encoding="utf-8-sig"))
        except Exception as e:                                       # noqa: BLE001
            print(f"         {rel}: 解析失败 {e}")
            continue
        out: list = []
        _first_diff(a, b, "", out)
        print(f"         {rel}:")
        for line in out or ["（剥掉 volatile/计时键后无内容差异）"]:
            print("           " + line)


def _norm(obj, strip=None):
    """剥掉 volatile 键后规范化，用于内容比对（避免时间戳造成的假 diff）。

    strip 供**二级判定**追加计时字段；默认只剥 VOLATILE。
    """
    drop = VOLATILE if strip is None else (VOLATILE | strip)
    if isinstance(obj, dict):
        return {k: _norm(v, strip) for k, v in sorted(obj.items()) if k not in drop}
    if isinstance(obj, list):
        return [_norm(x, strip) for x in obj]
    return obj


def snapshot_data(strip=None) -> dict[str, str]:
    snap = {}
    for p in sorted(R.rglob("*")):
        if "data" not in p.parts or p.suffix.lower() not in (".json", ".csv"):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if p.suffix.lower() == ".json":
            try:
                blob = json.dumps(_norm(json.loads(p.read_text(encoding="utf-8-sig")), strip),
                                  ensure_ascii=False, sort_keys=True)
            except Exception as e:                                   # noqa: BLE001
                blob = f"<unparsable:{e}>"
        else:
            blob = p.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        snap[rel] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return snap


def doc_for(board: int) -> Path:
    """captions 产物按板分文件 —— 单文件会被后跑的 board 覆盖（本轮踩到）。"""
    return DOC.with_name(f"{DOC.stem}_B{board}{DOC.suffix}")


def dpi_of(p: Path):
    from PIL import Image
    with Image.open(p) as im:
        d = im.info.get("dpi") or (0, 0)
        return im.size, (float(d[0]), float(d[1]))


# ------------------------------------------------------------------ 动作

def do_check(board: int) -> int:
    figs = [f for f in FIGSET if f["b"] == board]
    bad = 0
    print("%-26s %-13s %-6s %-11s %-11s %s"
          % ("id", "像素", "dpi", f"单栏{NEED_ONE}px", f"双栏{NEED_TWO}px", "状态"))
    print("-" * 104)
    for f in figs:
        p = R / f["src"]
        if not p.exists():
            print("%-26s MISSING" % f["id"])
            bad += 1
            continue
        (w, h), d = dpi_of(p)
        one, two = w >= NEED_ONE, w >= NEED_TWO
        st = "双栏达标" if two else ("仅单栏达标" if one else "不达标")
        if f.get("render", True) and not two:
            st += "·可重渲染↑"
        if not one:
            bad += 1
            st += "·缺口"
        print("%-26s %-13s %-6s %-11s %-11s %s" % (
            f["id"], f"{w}x{h}", f"{d[0]:.0f}", "是" if one else "否",
            "是" if two else "否", st))
    print("-" * 104)
    ex = [(f, dpi_of(R / f["src"])[0][0]) for f in figs if (R / f["src"]).exists()]
    print(f"板 {board}：{len(figs)} 张 ｜ 双栏达标 {sum(1 for _, w in ex if w >= NEED_TWO)}"
          f" ｜ 仅单栏达标 {sum(1 for _, w in ex if NEED_ONE <= w < NEED_TWO)}"
          f" ｜ 不达标 {bad}")
    return 0


def do_render(board: int) -> int:
    figs = [f for f in FIGSET if f["b"] == board]
    todo = [f for f in figs if f.get("render", True)]
    scripts = sorted({f["script"] for f in todo})

    MPLRC.mkdir(parents=True, exist_ok=True)
    (MPLRC / "matplotlibrc").write_text(f"savefig.dpi: {TARGET_DPI}\n", encoding="utf-8")

    before = snapshot_data()                 # 一级：剥时间戳
    before_t = snapshot_data(TIMING)         # 二级：再剥计时字段
    keep_pre()
    print(f"数据快照：{len(before)} 个 json/csv（pre-image 已留 tools/_scratch/_pre_snapshot/）\n")

    env = dict(os.environ, MATPLOTLIBRC=str(MPLRC))
    runs = []
    for sc in scripts:
        sp = ROOT / "tools" / sc
        if not sp.exists():
            print(f"[SKIP] 脚本不存在：{sc}")
            continue
        r = subprocess.run([sys.executable, "-u", str(sp)], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        runs.append((sc, r.returncode))
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        print(f"[{'OK ' if r.returncode == 0 else 'ERR'}] {sc:<34} rc={r.returncode}  {tail[0][:70]}")

    after = snapshot_data()
    after_t = snapshot_data(TIMING)

    def _drift(x, y):
        return [k for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)]

    drift = _drift(before, after)            # 一级漂移（含计时字段）
    drift_t = _drift(before_t, after_t)      # 二级漂移（再剥计时字段）= 真·内容漂移
    print()
    if drift_t:
        print(f"[FAIL] 重跑导致 {len(drift_t)} 个数据文件**内容**变化（不得接受）：")
        for k in drift_t:
            print(f"       - {k}")
        print("       字段级线索（pre-image vs 现行，已跳过 volatile/计时键）：")
        report_diff(drift_t)
        return 1
    if drift:
        print(f"[WARN] {len(drift)} 个数据文件有漂移，但**全部来自计时/时间戳字段**，"
              f"实验内容稳定 -> 接受：")
        for k in drift:
            print(f"       ~ {k}")
        report_diff(drift)
        print(f"[ OK ] 内容零漂移（二级判据：{len(before_t)} 个文件在剥掉计时字段后逐项一致）")
    else:
        print(f"[ OK ] 数据零漂移（{len(before)} 个文件逐项一致，含 volatile 键剥离）")

    PAPER.mkdir(parents=True, exist_ok=True)
    recs = []
    bad = 0
    for f in figs:
        p = R / f["src"]
        if not p.exists():
            print(f"[MISS] {f['id']}: 源图不存在 {f['src']}")
            bad += 1
            continue
        (w, h), d = dpi_of(p)
        dst = PAPER / f"{f['id']}.png"
        shutil.copy2(p, dst)
        meet, meet_two = w >= NEED_ONE, w >= NEED_TWO   # 300 dpi @ 单栏为最低要求
        if not meet:
            bad += 1
        recs.append(dict(id=f["id"], board=f["b"], group=f["g"], title=f["title"],
                         src=f["src"], out=dst.relative_to(ROOT).as_posix(),
                         px=[w, h], dpi=round(max(d), 1),
                         meets_300dpi=meet, meets_300dpi_double=meet_two,
                         script=f["script"], render=bool(f.get("render", True)),
                         note=f.get("note", "")))
        print(f"[{' OK ' if meet else 'GAP '}] {f['id']:<26} {w}x{h} @{max(d):.0f}dpi "
              f"{'双栏' if meet_two else '单栏'}达标 -> {dst.name}")

    write_manifest(board, recs)
    return 0


def write_manifest(board: int, recs: list[dict]) -> Path:
    man = PAPER / "paper_figures_manifest.json"
    old = {}
    if man.exists():
        try:
            old = json.loads(man.read_text(encoding="utf-8"))
        except Exception:                                            # noqa: BLE001
            old = {}
    boards = {b: v for b, v in (old.get("boards") or {}).items()}
    boards[str(board)] = recs
    allr = [r for b in sorted(boards, key=int) for r in boards[b]]
    man.write_text(json.dumps(
        dict(target_dpi=TARGET_DPI,
             width_single_in=COL_SINGLE_IN, width_double_in=COL_DOUBLE_IN,
             need_px_single=NEED_ONE, need_px_double=NEED_TWO,
             boards=boards, n=len(allr),
             n_meet=sum(1 for r in allr if r.get("meets_300dpi")),
             n_meet_double=sum(1 for r in allr if r.get("meets_300dpi_double")),
             figures=allr), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n清单 -> {man.relative_to(ROOT)} ｜ 板 {sorted(boards)} 共 {len(allr)} 张 ｜ "
          f"单栏达标 {sum(1 for r in allr if r.get('meets_300dpi'))} / "
          f"双栏达标 {sum(1 for r in allr if r.get('meets_300dpi_double'))}")
    return man


def do_refresh(board: int) -> int:
    """只重扫磁盘 PNG 重建清单，**不重跑任何脚本**。"""
    recs = []
    for f in [x for x in FIGSET if x["b"] == board]:
        p = R / f["src"]
        if not p.exists():
            print(f"[MISS] {f['id']}: {f['src']}")
            continue
        (w, h), d = dpi_of(p)
        recs.append(dict(id=f["id"], board=f["b"], group=f["g"], title=f["title"],
                         src=f["src"], out=(PAPER / f"{f['id']}.png").relative_to(ROOT).as_posix(),
                         px=[w, h], dpi=round(max(d), 1),
                         meets_300dpi=w >= NEED_ONE, meets_300dpi_double=w >= NEED_TWO,
                         script=f["script"], render=bool(f.get("render", True)),
                         note=f.get("note", "")))
    PAPER.mkdir(parents=True, exist_ok=True)
    write_manifest(board, recs)
    for r in recs:
        print(f"  {'双栏' if r['meets_300dpi_double'] else ('单栏' if r['meets_300dpi'] else 'GAP ')}"
              f"  {r['id']:<26} {r['px'][0]}×{r['px'][1]} @{r['dpi']:.0f}dpi")
    return 0


def do_captions(board: int) -> int:
    man = R / "00_shared" / "figures" / "paper" / "paper_figures_manifest.json"
    if not man.exists():
        print("[ERR] 先跑 render")
        return 1
    m = json.loads(man.read_text(encoding="utf-8"))
    recs = [r for r in m["figures"] if r["board"] == board]
    L = [f"# 论文图表包 · 板 {board}（交付物 D12 / T8.{1 if board == 1 else 2}）", "",
         "> 生成：`tools/_export_paper_figures.py --board %d captions` ｜ "
         "目标：**%d dpi** + 图注含**口径三要素**（数据集 / 片段 / 指标定义）" % (board, m["target_dpi"]),
         "> 成品目录：`04_reports/00_shared/figures/paper/` ｜ 清单：`paper_figures_manifest.json`",
         "> **判据：300 dpi 是「印刷宽度」的函数** —— 单栏 %.2f in 需 **%d px**；"
         "双栏 %.2f in 需 **%d px**" % (m["width_single_in"], m["need_px_single"],
                                      m["width_double_in"], m["need_px_double"]),
         "> 本板 **%d** 张：**双栏达标 %d** ｜ 仅单栏达标 %d ｜ 不达标 %d"
         % (len(recs),
            sum(1 for r in recs if r.get("meets_300dpi_double")),
            sum(1 for r in recs if r.get("meets_300dpi") and not r.get("meets_300dpi_double")),
            sum(1 for r in recs if not r.get("meets_300dpi"))), "",
         "## 0. 使用方式", "",
         "1. 图注**连同口径三要素一起复制**，不要只抄标题句 —— 这是挡掉「为什么和参考表不一样」的第一道防线。",
         "2. **按印刷宽度用图**：`双栏` 列为 ✅ 的可双栏跨栏；只有 `单栏` ✅ 的请按单栏宽度排版。",
         "3. `复现命令` 列标「不重跑」的图，其脚本会载入模型做推理 —— 重跑前须单独评审，"
         "避免与已归档结果产生口径分歧。", "",
         "## 1. 图表清单（按分组）", ""]

    cur = None
    for r in recs:
        if r["group"] != cur:
            cur = r["group"]
            g = GROUPS[cur]
            L += [f"### {cur} · {g['name']}", "",
                  f"**口径三要素** ｜ 数据集：{g['dataset']} ｜ 片段：{g['clip']} ｜ 指标：{g['metric']}", ""]
            L += ["| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |",
                  "|:---|:---|:---|:---|:---:|:---:|:---|"]
        cmd = f"python tools/{r['script']}" if r["render"] else "—（不重跑）"
        L.append(f"| `{r['id']}` | {r['title']} | {r['px'][0]}×{r['px'][1]} | {r['dpi']:.0f} | "
                 f"{'✅' if r.get('meets_300dpi') else '❌'} | "
                 f"{'✅' if r.get('meets_300dpi_double') else '❌'} | `{cmd}` |")
        if r["note"]:
            L.append(f"| | ↳ {r['note']} | | | | | |")
    L += ["", "## 2. 口径提醒（引用任一图前必读）", "",
          "- **FLOPs 是下界**（`FlopCounterMode` 不计 STFT 与融合注意力）→ 跨架构比较须配合实测时延。",
          "- **单轨模型的 SDR 不可与四轨直接比**（`1:50` vs `4:50`）。",
          "- **T60 用导出口径 44.1 kHz**（源 48 kHz 值另存）；RIR 估 T60 前须剔直达声 ±2.5 ms。",
          "- 精度图口径为 **train 抽段 3 首 × 10 s**，与实机 test 集 50 首整曲**不是同一口径**。", ""]
    out = doc_for(board)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"-> {out.relative_to(ROOT)}  ({len(L)} 行)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", type=int, default=1, choices=[1, 2])
    ap.add_argument("action", choices=["check", "render", "captions", "refresh"])
    a = ap.parse_args()
    if a.action == "check":
        sys.exit(do_check(a.board))
    if a.action == "render":
        sys.exit(do_render(a.board))
    if a.action == "refresh":
        sys.exit(do_refresh(a.board))
    sys.exit(do_captions(a.board))


if __name__ == "__main__":
    main()

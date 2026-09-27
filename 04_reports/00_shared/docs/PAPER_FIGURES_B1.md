# 论文图表包 · 板 1（交付物 D12 / T8.1）

> 生成：`tools/_export_paper_figures.py --board 1 captions` ｜ 目标：**300 dpi** + 图注含**口径三要素**（数据集 / 片段 / 指标定义）
> 成品目录：`04_reports/00_shared/figures/paper/` ｜ 清单：`paper_figures_manifest.json`
> **判据：300 dpi 是「印刷宽度」的函数** —— 单栏 3.35 in 需 **1005 px**；双栏 7.00 in 需 **2100 px**
> 本板 **38** 张：**双栏达标 30** ｜ 仅单栏达标 8 ｜ 不达标 0

## 0. 使用方式

1. 图注**连同口径三要素一起复制**，不要只抄标题句 —— 这是挡掉「为什么和参考表不一样」的第一道防线。
2. **按印刷宽度用图**：`双栏` 列为 ✅ 的可双栏跨栏；只有 `单栏` ✅ 的请按单栏宽度排版。
3. `复现命令` 列标「不重跑」的图，其脚本会载入模型做推理 —— 重跑前须单独评审，避免与已归档结果产生口径分歧。

## 1. 图表清单（按分组）

### G-ARCH · 架构原理图

**口径三要素** ｜ 数据集：N/A（结构示意，不含实验数据） ｜ 片段：N/A ｜ 指标：框内 shape / 参数量取自 `graph_*.json` 溯源；成本口径见模型画像摘要

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-arch-irm` | IRM / IBM Oracle 结构（解析基线） | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-rpca` | RPCA (Inexact-ALM) 流程 | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-convtasnet` | Conv-TasNet（时域分离） | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-dprnn` | DPRNN（自训） | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-mmdenselstm` | MMDenseLSTM | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-umx` | Open-Unmix (umxhq) | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-demucs` | Demucs v4 / HTDemucs | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-mdx` | MDX-Net (KUIELAB mdx_extra) | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-bsroformer` | BS-RoFormer | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-bsrnn` | BSRNN（oBSRNN） | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-denoiser` | denoiser（板 2） | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-melden` | Mel-Band-RoFormer-Denoise (aufr33) | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-dereverb` | Mel-Band-RoFormer-Dereverb (anvuew) | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
| `fig-arch-dereverb-echo` | Mel-Band-RoFormer-Dereverb-Echo (sucial) | 4680×2850 | 300 | ✅ | ✅ | `python tools/_plot_model_arch.py` |
### G-PROFILE · 模型画像图

**口径三要素** ｜ 数据集：统一**合成**输入（不取自数据集） ｜ 片段：10 s / 44.1 kHz / 立体声 ｜ 指标：参数量 `sum(numel)`；FLOPs = 2×MACs **下界**；时延 5 次中位数

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-profile-params-flops` | 参数量 / FLOPs 对比 | 4073×2594 | 300 | ✅ | ✅ | `python tools/_plot_model_profile.py` |
| `fig-profile-pareto` | 成本—容量 Pareto | 3271×2047 | 300 | ✅ | ✅ | `python tools/_plot_model_profile.py` |
### G-ACC · 分离精度图

**口径三要素** ｜ 数据集：MUSDB18-HQ **train** 抽段 ｜ 片段：3 首 × 10 s ｜ 指标：`museval.metrics.bss_eval` SDR（窗 88200 / hop 66150，逐帧 nanmedian）

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-acc-main-table` | 分离精度主表（重绘） | 2989×2667 | 300 | ✅ | ✅ | `python tools/_make_sdr_table.py` |
| | ↳ 脚本已写死 `dpi=300`，原生达标 | | | | | |
| `fig-acc-bars` | 分模型 SDR 中位条形图 | 2738×1464 | 300 | ✅ | ✅ | `python tools/plot_median_summary.py` |
| `fig-acc-per-stem` | 逐轨 SDR 中位 | 2757×1587 | 300 | ✅ | ✅ | `python tools/plot_median_summary.py` |
| `fig-acc-pareto` | 精度—速度 Pareto | 2653×1563 | 300 | ✅ | ✅ | `python tools/plot_median_summary.py` |
| `fig-acc-dsdr` | 与基线对照的 ΔSDR | 1650×909 | 150 | ✅ | ❌ | `—（不重跑）` |
| | ↳ 脚本 `import torch` 且写死 `dpi=150` → **不重跑**（会触发重算与数据改写） | | | | | |
### G-REV · 混响 / 回声退化图

**口径三要素** ｜ 数据集：MUSDB18-HQ train 抽段 + AIR/合成 RIR ｜ 片段：3 首 × 10 s ｜ 指标：ΔSDR(dB) = 湿 − 干；**T60 为导出口径 44.1 kHz**（非源 48 kHz）

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-rev-degradation` | 混响 T60 → ΔSDR 退化曲线 | 4500×1800 | 300 | ✅ | ✅ | `python tools/_plot_reverb_curve.py` |
| `fig-rev-rir-t60` | RIR 本体与 T60 估计（已剔直达声） | 4650×2460 | 300 | ✅ | ✅ | `python tools/_plot_rir.py` |
| `fig-echo-degradation` | 回声延迟/增益 → ΔSDR 退化曲线 | 4500×1800 | 300 | ✅ | ✅ | `python tools/_plot_echo_curve.py` |
### G-S4 · 阶段 4 一页汇总

**口径三要素** ｜ 数据集：同 G-REV（混响 + 回声两组实验汇总） ｜ 片段：3 首 × 10 s ｜ 指标：ΔSDR(dB)；曲线为 6 模型均值，大厅档 `bsrnn_all` n=1 已标注不参与排名

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-stage4-summary` | 阶段 4 答辩一页图 | 4800×2700 | 300 | ✅ | ✅ | `python tools/_plot_stage4_summary.py` |
### G-COST · 实机成本图

**口径三要素** ｜ 数据集：MUSDB18-HQ **test** 50 首 ｜ 片段：整曲 ｜ 指标：wall time / RTF / SDR 均值；**单轨模型（1:50）的 SDR 不可与四轨（4:50）直接比**

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-cost-time-per-song` | 逐曲推理耗时 | 1846×962 | 150 | ✅ | ❌ | `python tools/plot_bench_10songs.py` |
| `fig-cost-cumulative` | 累计耗时 | 1625×901 | 150 | ✅ | ❌ | `python tools/plot_bench_10songs.py` |
| `fig-cost-rtf` | 逐曲 RTF | 1851×962 | 150 | ✅ | ❌ | `python tools/plot_bench_10songs.py` |
| `fig-cost-dist` | 耗时分布 | 1148×874 | 150 | ✅ | ❌ | `python tools/plot_bench_10songs.py` |
| `fig-cost-vs-acc` | 耗时 vs 精度 | 1854×910 | 150 | ✅ | ❌ | `python tools/plot_bench_10songs.py` |
| `fig-cost-panels` | 成本多面板对比 | 1742×1371 | 150 | ✅ | ❌ | `python tools/plot_bench_10songs.py` |
| `fig-cost-pareto` | 速度—精度 Pareto | 1499×1001 | 150 | ✅ | ❌ | `python tools/plot_bench_10songs.py` |
### G-SPEC · 信号级频谱图

**口径三要素** ｜ 数据集：MUSDB18-HQ train 抽段 ｜ 片段：见各图注（默认 10 s） ｜ 指标：STFT 幅度（dB）；窗长对比图用 win 1024 vs 128

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-spec-mixture` | 混音时频谱 | 2100×750 | 150 | ✅ | ✅ | `python tools/_make_spectrogram_panels.py` |
| `fig-spec-vocals` | 人声轨时频谱 | 2100×750 | 150 | ✅ | ✅ | `python tools/_make_spectrogram_panels.py` |
| `fig-spec-win1024` | 窗长对比：win 1024 | 2250×750 | 150 | ✅ | ✅ | `python tools/_make_spectrogram_panels.py` |
| `fig-spec-win128` | 窗长对比：win 128 | 2250×750 | 150 | ✅ | ✅ | `python tools/_make_spectrogram_panels.py` |
| `fig-spec-waveform` | 波形：混音 vs 人声 | 2100×900 | 150 | ✅ | ✅ | `python tools/_make_spectrogram_panels.py` |
| `fig-spec-sr` | 采样率对比波形 | 2100×1350 | 150 | ✅ | ✅ | `python tools/_make_spectrogram_panels.py` |

## 2. 口径提醒（引用任一图前必读）

- **FLOPs 是下界**（`FlopCounterMode` 不计 STFT 与融合注意力）→ 跨架构比较须配合实测时延。
- **单轨模型的 SDR 不可与四轨直接比**（`1:50` vs `4:50`）。
- **T60 用导出口径 44.1 kHz**（源 48 kHz 值另存）；RIR 估 T60 前须剔直达声 ±2.5 ms。
- 精度图口径为 **train 抽段 3 首 × 10 s**，与实机 test 集 50 首整曲**不是同一口径**。


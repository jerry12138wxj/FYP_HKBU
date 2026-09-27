# 论文图表包 · 板 2（交付物 D12 / T8.2）

> 生成：`tools/_export_paper_figures.py --board 2 captions` ｜ 目标：**300 dpi** + 图注含**口径三要素**（数据集 / 片段 / 指标定义）
> 成品目录：`04_reports/00_shared/figures/paper/` ｜ 清单：`paper_figures_manifest.json`
> **判据：300 dpi 是「印刷宽度」的函数** —— 单栏 3.35 in 需 **1005 px**；双栏 7.00 in 需 **2100 px**
> 本板 **15** 张：**双栏达标 11** ｜ 仅单栏达标 4 ｜ 不达标 0

## 0. 使用方式

1. 图注**连同口径三要素一起复制**，不要只抄标题句 —— 这是挡掉「为什么和参考表不一样」的第一道防线。
2. **按印刷宽度用图**：`双栏` 列为 ✅ 的可双栏跨栏；只有 `单栏` ✅ 的请按单栏宽度排版。
3. `复现命令` 列标「不重跑」的图，其脚本会载入模型做推理 —— 重跑前须单独评审，避免与已归档结果产生口径分歧。

## 1. 图表清单（按分组）

### G-DN · 板 2 降噪结果图

**口径三要素** ｜ 数据集：`valentini`（真实含噪，有 clean 参考）+ `synth`（干净语音 + 合成瞬态噪声） ｜ 片段：整条 utterance（valentini 824 条 / synth 800 条），16 kHz 口径 ｜ 指标：SI-SDR(dB) / PESQ / STOI / LSD；`hf_ratio` = >4 kHz 能量占比

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-dn-suppression` | 降噪抑制量（按模型 / SNR 档） | 4500×1920 | 300 | ✅ | ✅ | `python tools/_plot_denoise.py` |
| `fig-dn-synth-gain` | 合成集增益（干净语音 + 瞬态噪声） | 3120×1920 | 300 | ✅ | ✅ | `python tools/_plot_denoise.py` |
| `fig-dn-domain-reversal` | 噪声域反转（真实噪声 vs 合成噪声） | 4500×1980 | 300 | ✅ | ✅ | `python tools/_plot_denoise.py` |
| `fig-dn-metric-divergence` | 三指标分歧诊断 | 4500×1920 | 300 | ✅ | ✅ | `—（不重跑）` |
| | ↳ 脚本载入 `_denoise_registry` 做推理 -> **不重跑**（避免与已归档结果分歧） | | | | | |
| `fig-dn-drywet` | dry/wet 强度旋钮曲线 | 4680×1980 | 300 | ✅ | ✅ | `python tools/_plot_denoise_drywet.py` |
| `fig-dn-spec-master64-val` | 频谱前后对比：master64 × valentini | 2240×1596 | 140 | ✅ | ✅ | `—（不重跑）` |
| | ↳ 脚本载入 `_denoise_registry` 做推理 -> **不重跑** | | | | | |
| `fig-dn-spec-master64-syn` | 频谱前后对比：master64 × synth | 2240×1596 | 140 | ✅ | ✅ | `—（不重跑）` |
| | ↳ 同上 | | | | | |
| `fig-dn-spec-mel-val` | 频谱前后对比：mel-roformer × valentini | 2240×1596 | 140 | ✅ | ✅ | `—（不重跑）` |
| | ↳ 同上 | | | | | |
| `fig-dn-spec-mel-syn` | 频谱前后对比：mel-roformer × synth | 2240×1596 | 140 | ✅ | ✅ | `—（不重跑）` |
| | ↳ 同上 | | | | | |
| `fig-dn-dspec-master64-val` | 平均谱差：master64 × valentini | 1484×854 | 140 | ✅ | ❌ | `—（不重跑）` |
| | ↳ 脚本载入 `_denoise_registry` 做推理 -> **不重跑** | | | | | |
| `fig-dn-dspec-master64-syn` | 平均谱差：master64 × synth | 1484×854 | 140 | ✅ | ❌ | `—（不重跑）` |
| | ↳ 同上 | | | | | |
| `fig-dn-dspec-mel-val` | 平均谱差：mel-roformer × valentini | 1484×854 | 140 | ✅ | ❌ | `—（不重跑）` |
| | ↳ 同上 | | | | | |
| `fig-dn-dspec-mel-syn` | 平均谱差：mel-roformer × synth | 1484×854 | 140 | ✅ | ❌ | `—（不重跑）` |
| | ↳ 同上 | | | | | |
### G-CAS · 板 1×2 级联图

**口径三要素** ｜ 数据集：MUSDB18-HQ test Top-10 曲 × DNS freesound 噪声池（逐声道独立加噪） ｜ 片段：10 曲 × 4 SNR × 20 s ｜ 指标：ΔSDR(dB) = 该链路 − L0；GT = 干 stem；museval bss_eval（与板 1 主表同源）

| id | 图题 | 像素 | dpi | 单栏 | 双栏 | 复现命令 |
|:---|:---|:---|:---|:---:|:---:|:---|
| `fig-cas-delta-matrix` | 级联 ΔSDR 主矩阵（4 SNR × 4 模型 × 6 链路） | 4230×1650 | 300 | ✅ | ✅ | `python tools/_plot_cascade.py` |
| `fig-cas-decomposition` | 级联净动作分解（L1 vs L1b vs L1−L1b） | 4260×1590 | 300 | ✅ | ✅ | `python tools/_plot_cascade.py` |

## 2. 口径提醒（引用任一图前必读）

- **FLOPs 是下界**（`FlopCounterMode` 不计 STFT 与融合注意力）→ 跨架构比较须配合实测时延。
- **单轨模型的 SDR 不可与四轨直接比**（`1:50` vs `4:50`）。
- **T60 用导出口径 44.1 kHz**（源 48 kHz 值另存）；RIR 估 T60 前须剔直达声 ±2.5 ms。
- 精度图口径为 **train 抽段 3 首 × 10 s**，与实机 test 集 50 首整曲**不是同一口径**。


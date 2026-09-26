# 数据摘要 · 板 1 源分离（精度 / 成本 / 退化）

> **机器生成 · 禁止手改** ｜ 生成日 2026-09-26 ｜ 交付物 **D11 / T7.3**（分离主表 + 实机成本 + 混响回声退化）
>
> 数字全部读自下列机器可读文件（正文无手填数值）：
> - `04_reports/separation/data/comparison/model_runs_median.json`
> - `04_reports/separation/data/comparison/mixture_baseline.json`
> - `04_reports/separation/data/reverb/stage4_summary.json`
> - `04_reports/separation/data/comparison/test_run_model_summary.csv`
> - `04_reports/separation/data/comparison/test_run_analysis.json`
>
> 重建：`python tools/_build_summaries.py --only separation` ｜ 校验：`python tools/_build_summaries.py --verify`
>
> 详解（机理 / 原因 / 决策过程，本表不复述）：`separation/docs/STAGE4_SUMMARY.md` · `separation/docs/MEDIAN_TABLE_REDRAWN.md`


---

## 1. 口径三要素

| 项 | 取值 / 说明 |
|:---|:---|
| 数据集（主表） | MUSDB18-HQ **train** 子集抽段 |
| 片段（主表） | **3 首 × 10 s**：`ANiMAL - Clinic A`、`Creepoid - OldTree`、`Dark Ride - Burning Bridges` |
| 指标（主表） | `museval.metrics.bss_eval`（BSS-Eval v4，签名默认窗 **88200 / hop 66150**），逐帧 `nanmedian`，`compute_permutation=False` |
| avg4 | 四轨 SDR 的算术平均（vocals/drums/bass/other） |
| 数据集（实机） | MUSDB18-HQ **test** 50 首整曲 |
| 片段（混响/回声） | 同主表 train 3 段；RIR 卷混后**导出为 44.1 kHz**再评测 |

---

## 2. 主表：四轨 SDR 中位（按 avg4 降序）

| model_key | 模型 | 组 | 片段数 | vocals | drums | bass | other | **avg4** | RTF |
|:---|:---|:---|---:|---:|---:|---:|---:|---:|---:|
| bsrnn_simo | oBSRNN-SIMO | 4-stem | 3 | 8.65 | 9.66 | 11.72 | 7.03 | 9.27 | 0.1914 |
| bsrnn_all | oBSRNN (4 ckpt) | 4-stem | 3 | 9.17 | 9.19 | 11.92 | 6.37 | 9.16 | 0.4182 |
| mdx | MDX-Net | 4-stem | 3 | 7.97 | 8.65 | 12.98 | 6.26 | 8.96 | 0.1374 |
| bsrnn_large_all | BSRNN large (4 ckpt) | 4-stem | 3 | 8.28 | 9.24 | 10.66 | 5.49 | 8.42 | 0.3209 |
| oracle | IRM/IBM Oracle | analytic | 3 | 10.03 | 8.48 | 8.55 | 6.15 | 8.30 | 0.0071 |
| demucs | Demucs (htdemucs) | 4-stem | 3 | 7.11 | 8.96 | 10.87 | 5.49 | 8.11 | 0.0278 |
| umx | Open-Unmix | 4-stem | 3 | 6.05 | 7.31 | 8.35 | 4.90 | 6.65 | 0.0588 |
| mmdenselstm | MMDenseLSTM | 4-stem | 3 | 5.60 | 7.15 | 7.36 | 4.96 | 6.27 | 0.0822 |
| convtasnet | Conv-TasNet | 4-stem | 3 | 5.00 | 7.78 | 9.29 | 1.66 | 5.93 | 0.1763 |
| dprnn | DPRNN (自训, 4-stem) | 4-stem | 3 | -2.18 | -1.86 | -0.82 | -2.02 | -1.72 | 0.0310 |
| bsroformer_l12 | BS-RoFormer L12 | 1-target | 3 | 9.69 | — | — | — | — | 0.4942 |

- 无可用数值（探针不可用/未跑通）：**2** 个 —— `bsroformer_l6`、`rpca`


### 2.1 基线对照（同一口径）

| 基线 | vocals | drums | bass | other | avg4 | 含义 |
|:---|---:|---:|---:|---:|---:|:---|
| mixture（不分离） | -5.29 | -5.88 | -4.06 | -5.99 | -5.30 | 把混音自身当估计 → 标定各方法是否真有效 |

> mixture 基线口径：`np.nanmedian over frames; mono=mean over channels; compute_permutation=False`；帧窗 `museval bss_eval 签名默认值，即主表实际口径`；生成 `2026-09-23 03:10:43`，状态 `PASS`。


---

## 3. 实机运行成本（test 集 50 首整曲）

| model_key | 模型 | 跑完 50 首 | PASS | wall 中位(s) | RTF 中位 | SDR 均值中位 | 轨数 | 输出(MB) | 推理占比(%) |
|:---|:---|:---:|---:|---:|---:|---:|:---:|---:|---:|
| bsrnn_large | BSRNN-large | True | 50 | 46.7 | 0.1198 | 10.142 | 1:50 | 618.7 | 62.8 |
| dprnn | DPRNN | True | 50 | 51.4 | 0.0183 | -1.510 | 4:50 | 1204.7 | 9.0 |
| oracle | Oracle-IRM | True | 50 | 52.0 | 0.0135 | 9.017 | 4:50 | 1352.6 | 6.6 |
| bsrnn | BSRNN-opt | True | 50 | 54.8 | 0.1475 | 10.415 | 1:50 | 598.3 | 66.8 |
| demucs | Demucs | True | 50 | 57.0 | 0.0316 | 9.052 | 4:50 | 3272.8 | 14.0 |
| bsroformer_l6 | BS-RoFormer-L6 | True | 50 | 62.9 | 0.1775 | 10.461 | 1:50 | 1023.9 | 70.4 |
| umx | Open-Unmix | True | 50 | 65.0 | 0.0676 | 5.490 | 4:50 | 2782.5 | 26.0 |
| mmdenselstm | MMDenseLSTM | True | 50 | 66.0 | 0.0627 | 5.646 | 4:50 | 2773.8 | 24.8 |
| mdx | MDX-Net | True | 50 | 68.9 | 0.0630 | 9.872 | 4:50 | 3299.0 | 23.4 |
| bsroformer_l12 | BS-RoFormer-L12 | True | 50 | 83.2 | 0.2640 | 13.553 | 1:50 | 635.5 | 77.9 |
| convtasnet | Conv-TasNet | True | 50 | 89.5 | 0.1608 | 5.593 | 4:50 | 3658.3 | 45.8 |
| bsrnn_simo | BSRNN-SIMO | False | 14 | 144.6 | 0.3929 | 9.374 | 4:14 | 674.4 | 63.7 |
| rpca | RPCA | False | 0 | — | — | — | — | 0.0 | — |
| bsrnn_all | BSRNN-all(4ckpt) | False | 0 | — | — | — | — | 0.0 | — |
| bsrnn_large_all | BSRNN-large-all(4ckpt) | False | 0 | — | — | — | — | 0.0 | — |

> 台账：共 **15** 个模型；`finished` = ['oracle', 'demucs', 'umx', 'mdx', 'convtasnet', 'mmdenselstm', 'bsroformer_l12', 'bsroformer_l6', 'bsrnn', 'bsrnn_large', 'dprnn']；`unfinished` = ['bsrnn_simo', 'rpca', 'bsrnn_all', 'bsrnn_large_all']；`disabled` = ['rpca', 'bsrnn_all', 'bsrnn_large_all', 'bsrnn_simo']。
> ⚠️ **BSRNN-SIMO 只有 14/50 首**（范围外，已拍板不补跑）——引用时须显式标注截断。

> ⚠️ **`SDR 均值中位` 列跨行不可直接比**：`轨数` 列为 `1:50` 的是**单轨（人声）**模型，其 SDR 只覆盖人声；`4:50` 是四轨模型。两者口径不同。


---

## 4. 混响 / 回声退化（ΔSDR，dB）

T60（**导出口径 44.1 kHz**）：小房间 **0.491 s** ／ 大厅 **1.026 s**。

| model_key | 小房间 ΔSDR | 大厅 ΔSDR | 短回声 ΔSDR | 长回声 ΔSDR |
|:---|---:|---:|---:|---:|
| bsrnn_all | -5.844 | -14.544 | -4.589 | -6.037 |
| convtasnet | -3.476 | -10.683 | -2.598 | -3.570 |
| demucs | -5.648 | -15.648 | -4.215 | -5.868 |
| mdx | -5.940 | -15.231 | -4.324 | -5.966 |
| mmdenselstm | -3.967 | -13.537 | -2.716 | -3.944 |
| umx | -3.350 | -11.450 | -2.318 | -3.329 |

均值曲线 `mean_curve`（干 / 小 / 大）：混响 [0.0, -4.704, -13.516]；回声 [0.0, -3.46, -4.786]


---

## 5. 去混响（负结果，照报）

| 项 | 值 |
|:---|:---|
| Dereverb-Echo `dry` 支增益中位 | 0.044 |
| 同上最大值 | 1.464 |
| wet 支损失区间 (dB) | [-13.3, -10.4] |
| 判定 | unusable (dry branch silent) |
| 官方分块推理路径交叉验证 Δ (dB) | 0.142 |

> 结论：两社区 ckpt 在本探针**不可用**；已用官方推理路径交叉验证→ **非我方实现错误**。详见 `denoiser/docs/DEREVERB_NEGATIVE_RESULT.md`。


---

## 6. 复现

```bash
python tools/_build_summaries.py --only separation   # 重建本表
```


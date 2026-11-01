# 降噪模型 · Valentini 全量产物图集（F2 代表性子集）

## 一、这批图是什么

- 来源：`tools/_denoise_export_valentini.py` 把 **7 个降噪模型** 跑遍 Valentini 全量 **824** 条带噪片段，产物落在 `03_outputs/_valentini_denoise/<模型>/<片段>.wav`。
- 本批图只对其中 **12 条代表片段** 出图（F2 口径，非全量 5768 单元）。
- 出图格式与 `01_separation` 侧**完全一致**：每单元 **11** 张图（fig1 / fig2 / fig3×2 / fig4×4 / fig5 / fig6×2）+ `caption.json`。
- 与既有图**同树存放**（A1 隔离目录下新增 `valentini/` 命名空间）：

```
figures/_model_figs/<模型slug>/valentini/<片段id>/fig*.png
```

- 单元数：12 条片段 × 7 模型 = **84 单元 / 924 张图**

## 二、片段怎么选的（分层）

输入质量指标（逐样本对齐，实测 824 对全部等长）：

```
SNR_in = 10 · log10( sum(clean²) / sum((noisy-clean)²) )   [dB]
```

按 SNR 三分位分档（poor / mid / good），每档再按 **SNR 四分位**取窗、窗内取 **时长 maximin** 的一条 → 每档 4 条，共 12 条，同时覆盖质量与时长两个维度。选择清单见 `tools/_scratch/valentini_f2_selection.json`。

| # | 片段 | 输入 SNR (dB) | 时长 (s) | 档 |
|---|---|---|---|---|
| 1 | `p232_021` | 11.92 | 8.51 | good |
| 2 | `p232_045` | 14.38 | 1.24 | good |
| 3 | `p232_020` | 16.23 | 3.62 | good |
| 4 | `p232_024` | 16.80 | 5.52 | good |
| 5 | `p257_326` | 5.94 | 1.74 | mid |
| 6 | `p257_089` | 6.44 | 2.89 | mid |
| 7 | `p257_100` | 10.11 | 1.47 | mid |
| 8 | `p232_172` | 10.86 | 2.02 | mid |
| 9 | `p257_199` | -3.09 | 4.22 | poor |
| 10 | `p257_102` | 1.25 | 2.59 | poor |
| 11 | `p232_019` | 2.05 | 6.74 | poor |
| 12 | `p232_298` | 5.13 | 1.60 | poor |

## 三、模型与产物口径

| 模型 | registry key | 原生采样率 | 增强目标 stem |
|---|---|---|---|
| Denoiser-DNS48 | `denoiser_dns48` | 16000 Hz / 1 ch | enhanced（单轨降噪/去混响） |
| Denoiser-DNS64 | `denoiser_dns64` | 16000 Hz / 1 ch | enhanced（单轨降噪/去混响） |
| Denoiser-Master64 | `denoiser_master64` | 16000 Hz / 1 ch | enhanced（单轨降噪/去混响） |
| Mel-RoFormer-Denoise | `mel_roformer_denoise` | 44100 Hz / 2 ch | enhanced（单轨降噪/去混响） |
| Mel-RoFormer-Denoise-Aggr | `mel_roformer_denoise_aggr` | 44100 Hz / 2 ch | enhanced（单轨降噪/去混响） |
| Mel-RoFormer-Dereverb | `mel_roformer_dereverb` | 44100 Hz / 2 ch | enhanced（单轨降噪/去混响） |
| Mel-RoFormer-Dereverb-Echo | `mel_roformer_dereverb_echo` | 44100 Hz / 2 ch | dry（2-stem 的干声, 去混响残留） |

🔴 采样率口径：产物保存为**各模型原生格式**（mel_roformer \* → 44100 Hz/2ch，denoiser \* → 16000 Hz/1ch）。本批图以**产物自身采样率**为对比率，把 clean 参考重采样到同一率 —— 不把 16k 产物上采样到 44.1k 冒充原生。

📌 与探针图的区别：`figures/_model_figs/<slug>/p232_001/` 是此前 `stage0_gate` 的 **1.74 s 探针**；本批 `.../valentini/p232_001/` 是 **全量导出的整段**（约 2–3 s）。同名不同源，看 `caption.json` 的 `source` 字段区分。

## 四、单元清单

| 模型 | 片段 | 输入SNR | 档 | 产物路径 |
|---|---|---|---|---|
| Denoiser-DNS48 | `p232_021` | 11.92 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p232_021` |
| Denoiser-DNS48 | `p232_045` | 14.38 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p232_045` |
| Denoiser-DNS48 | `p232_020` | 16.23 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p232_020` |
| Denoiser-DNS48 | `p232_024` | 16.80 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p232_024` |
| Denoiser-DNS48 | `p257_326` | 5.94 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p257_326` |
| Denoiser-DNS48 | `p257_089` | 6.44 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p257_089` |
| Denoiser-DNS48 | `p257_100` | 10.11 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p257_100` |
| Denoiser-DNS48 | `p232_172` | 10.86 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p232_172` |
| Denoiser-DNS48 | `p257_199` | -3.09 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p257_199` |
| Denoiser-DNS48 | `p257_102` | 1.25 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p257_102` |
| Denoiser-DNS48 | `p232_019` | 2.05 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p232_019` |
| Denoiser-DNS48 | `p232_298` | 5.13 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-dns48/valentini/p232_298` |
| Denoiser-DNS64 | `p232_021` | 11.92 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p232_021` |
| Denoiser-DNS64 | `p232_045` | 14.38 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p232_045` |
| Denoiser-DNS64 | `p232_020` | 16.23 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p232_020` |
| Denoiser-DNS64 | `p232_024` | 16.80 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p232_024` |
| Denoiser-DNS64 | `p257_326` | 5.94 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p257_326` |
| Denoiser-DNS64 | `p257_089` | 6.44 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p257_089` |
| Denoiser-DNS64 | `p257_100` | 10.11 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p257_100` |
| Denoiser-DNS64 | `p232_172` | 10.86 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p232_172` |
| Denoiser-DNS64 | `p257_199` | -3.09 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p257_199` |
| Denoiser-DNS64 | `p257_102` | 1.25 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p257_102` |
| Denoiser-DNS64 | `p232_019` | 2.05 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p232_019` |
| Denoiser-DNS64 | `p232_298` | 5.13 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-dns64/valentini/p232_298` |
| Denoiser-Master64 | `p232_021` | 11.92 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p232_021` |
| Denoiser-Master64 | `p232_045` | 14.38 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p232_045` |
| Denoiser-Master64 | `p232_020` | 16.23 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p232_020` |
| Denoiser-Master64 | `p232_024` | 16.80 | good | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p232_024` |
| Denoiser-Master64 | `p257_326` | 5.94 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p257_326` |
| Denoiser-Master64 | `p257_089` | 6.44 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p257_089` |
| Denoiser-Master64 | `p257_100` | 10.11 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p257_100` |
| Denoiser-Master64 | `p232_172` | 10.86 | mid | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p232_172` |
| Denoiser-Master64 | `p257_199` | -3.09 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p257_199` |
| Denoiser-Master64 | `p257_102` | 1.25 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p257_102` |
| Denoiser-Master64 | `p232_019` | 2.05 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p232_019` |
| Denoiser-Master64 | `p232_298` | 5.13 | poor | `04_reports/02_denoising/figures/_model_figs/denoiser-master64/valentini/p232_298` |
| Mel-RoFormer-Denoise | `p232_021` | 11.92 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p232_021` |
| Mel-RoFormer-Denoise | `p232_045` | 14.38 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p232_045` |
| Mel-RoFormer-Denoise | `p232_020` | 16.23 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p232_020` |
| Mel-RoFormer-Denoise | `p232_024` | 16.80 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p232_024` |
| Mel-RoFormer-Denoise | `p257_326` | 5.94 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p257_326` |
| Mel-RoFormer-Denoise | `p257_089` | 6.44 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p257_089` |
| Mel-RoFormer-Denoise | `p257_100` | 10.11 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p257_100` |
| Mel-RoFormer-Denoise | `p232_172` | 10.86 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p232_172` |
| Mel-RoFormer-Denoise | `p257_199` | -3.09 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p257_199` |
| Mel-RoFormer-Denoise | `p257_102` | 1.25 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p257_102` |
| Mel-RoFormer-Denoise | `p232_019` | 2.05 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p232_019` |
| Mel-RoFormer-Denoise | `p232_298` | 5.13 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise/valentini/p232_298` |
| Mel-RoFormer-Denoise-Aggr | `p232_021` | 11.92 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p232_021` |
| Mel-RoFormer-Denoise-Aggr | `p232_045` | 14.38 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p232_045` |
| Mel-RoFormer-Denoise-Aggr | `p232_020` | 16.23 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p232_020` |
| Mel-RoFormer-Denoise-Aggr | `p232_024` | 16.80 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p232_024` |
| Mel-RoFormer-Denoise-Aggr | `p257_326` | 5.94 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p257_326` |
| Mel-RoFormer-Denoise-Aggr | `p257_089` | 6.44 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p257_089` |
| Mel-RoFormer-Denoise-Aggr | `p257_100` | 10.11 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p257_100` |
| Mel-RoFormer-Denoise-Aggr | `p232_172` | 10.86 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p232_172` |
| Mel-RoFormer-Denoise-Aggr | `p257_199` | -3.09 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p257_199` |
| Mel-RoFormer-Denoise-Aggr | `p257_102` | 1.25 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p257_102` |
| Mel-RoFormer-Denoise-Aggr | `p232_019` | 2.05 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p232_019` |
| Mel-RoFormer-Denoise-Aggr | `p232_298` | 5.13 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-denoise-aggr/valentini/p232_298` |
| Mel-RoFormer-Dereverb | `p232_021` | 11.92 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p232_021` |
| Mel-RoFormer-Dereverb | `p232_045` | 14.38 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p232_045` |
| Mel-RoFormer-Dereverb | `p232_020` | 16.23 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p232_020` |
| Mel-RoFormer-Dereverb | `p232_024` | 16.80 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p232_024` |
| Mel-RoFormer-Dereverb | `p257_326` | 5.94 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p257_326` |
| Mel-RoFormer-Dereverb | `p257_089` | 6.44 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p257_089` |
| Mel-RoFormer-Dereverb | `p257_100` | 10.11 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p257_100` |
| Mel-RoFormer-Dereverb | `p232_172` | 10.86 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p232_172` |
| Mel-RoFormer-Dereverb | `p257_199` | -3.09 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p257_199` |
| Mel-RoFormer-Dereverb | `p257_102` | 1.25 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p257_102` |
| Mel-RoFormer-Dereverb | `p232_019` | 2.05 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p232_019` |
| Mel-RoFormer-Dereverb | `p232_298` | 5.13 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb/valentini/p232_298` |
| Mel-RoFormer-Dereverb-Echo | `p232_021` | 11.92 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p232_021` |
| Mel-RoFormer-Dereverb-Echo | `p232_045` | 14.38 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p232_045` |
| Mel-RoFormer-Dereverb-Echo | `p232_020` | 16.23 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p232_020` |
| Mel-RoFormer-Dereverb-Echo | `p232_024` | 16.80 | good | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p232_024` |
| Mel-RoFormer-Dereverb-Echo | `p257_326` | 5.94 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p257_326` |
| Mel-RoFormer-Dereverb-Echo | `p257_089` | 6.44 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p257_089` |
| Mel-RoFormer-Dereverb-Echo | `p257_100` | 10.11 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p257_100` |
| Mel-RoFormer-Dereverb-Echo | `p232_172` | 10.86 | mid | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p232_172` |
| Mel-RoFormer-Dereverb-Echo | `p257_199` | -3.09 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p257_199` |
| Mel-RoFormer-Dereverb-Echo | `p257_102` | 1.25 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p257_102` |
| Mel-RoFormer-Dereverb-Echo | `p232_019` | 2.05 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p232_019` |
| Mel-RoFormer-Dereverb-Echo | `p232_298` | 5.13 | poor | `04_reports/02_denoising/figures/_model_figs/mel-roformer-dereverb-echo/valentini/p232_298` |

## 五、缺哪些

无 —— 全部 84 个单元格产物齐备。

## 六、图说明

同 `01_separation` 侧。此处 `est` = 模型增强输出，`ref` = Valentini clean。

## 七、跨模型联络图

每个片段另出一张 **7 模型 + clean 参考（2×4）** 的声纹联络图，清单与读法见 `FIGURES_valentini_F2_sheets.md`：

```
figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models.png
```

统一显示带宽 **0–8 kHz**、跨面板**同一 dB 色标** → 可直接横向比较各模型的压制/保留行为。

## 八、跨模型联络图（原生采样率版）

每个片段另出一张**原生采样率**联络图（同 8 面板布局，不做重采样），用于查看 **mel 的 >8 kHz 真实内容** 与 **denoiser 的 8 kHz 断崖**。清单与口径见 `FIGURES_valentini_F2_sheets_native.md`：

```
figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models_native.png
```

各面板保持原生率、共享频率轴 **0–24 kHz**、跨面板同一 dB 色标；`n_fft`/`hop` 随采样率缩放，使各面板时间/频率分辨率一致。

## 九、跨模型联络图（双版合一）

每片段再出一张**双版合一**图：4 列 × 4 行，同一列上下两格为**同一模型**的「@16 kHz 对齐版 / 原生率版」两种读法。清单与口径见 `FIGURES_valentini_F2_sheets_both.md`：

```
figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models_both.png
```

16 个面板共用同一 dB 色标；两行的 y 轴各自口径（对齐版 0–8 kHz / 原生率版 0–24 kHz），**不可跨行比幅度**。

# Valentini 降噪 · 跨模型联络图（双版合一）

每个片段一张图，**同图内同时给出两种读法**，每个模型**上下相邻**：

```
figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models_both.png
```

## 版面

4 列 × 4 行 = 16 面板（8 个实体 × 2 个版本）：

| 行 | 内容 |
|---|---|
| 行 0 | Denoiser-DNS48 / DNS64 / Master64 / Mel-RoFormer-Denoise — **@16 kHz 对齐版** |
| 行 1 | 上面 4 个的 **原生率版** |
| 行 2 | Mel-Denoise-Aggr / Mel-Dereverb / Mel-Dereverb-Echo / ★ clean — **@16 kHz 对齐版** |
| 行 3 | 上面 4 个的 **原生率版** |

→ **同一列上下两格 = 同一个模型**，直接对照，不用来回翻两个文件。

## 两行的 y 轴刻意不同（各自口径）

- **@16 kHz 对齐版行**：y 轴 **0–8 kHz**。全面板重采样到 16 kHz，各面板 Δt≈32 ms / Δf≈15.6 Hz 一致 → 读「**同一频带内谁更接近 clean**」。
- **原生率行**：y 轴 **0–24 kHz**。各面板保持产物原生率（mel 22.05 kHz / denoiser 8 kHz / clean 24 kHz；青色虚线 = 各自 Nyquist），`n_fft`/`hop` 随率缩放使 Δt≈11.6 ms / Δf≈43.1 Hz 一致 → 读「**>8 kHz 怎么处理**」（mel 保真 vs denoiser 物理封顶）。

⚠️ 两行**不能跨行直接比幅度**：它们的分辨率参数与重采样口径不同。各自行内可横向比；列内**只能定性看带宽差异**。

**色标**：16 个面板**共用一个**（vmax = 全图最大峰，vmin = vmax−70 dB）。

## 联络图清单（双版合一）

| # | 片段 | 输入 SNR (dB) | 时长 (s) | 档 | 双版合一联络图 |
|---|---|---|---|---|---|
| 1 | `p232_021` | 11.92 | 8.51 | good | `p232_021_spectrogram_7models_both.png` |
| 2 | `p232_045` | 14.38 | 1.24 | good | `p232_045_spectrogram_7models_both.png` |
| 3 | `p232_020` | 16.23 | 3.62 | good | `p232_020_spectrogram_7models_both.png` |
| 4 | `p232_024` | 16.80 | 5.52 | good | `p232_024_spectrogram_7models_both.png` |
| 5 | `p257_326` | 5.94 | 1.74 | mid | `p257_326_spectrogram_7models_both.png` |
| 6 | `p257_089` | 6.44 | 2.89 | mid | `p257_089_spectrogram_7models_both.png` |
| 7 | `p257_100` | 10.11 | 1.47 | mid | `p257_100_spectrogram_7models_both.png` |
| 8 | `p232_172` | 10.86 | 2.02 | mid | `p232_172_spectrogram_7models_both.png` |
| 9 | `p257_199` | -3.09 | 4.22 | poor | `p257_199_spectrogram_7models_both.png` |
| 10 | `p257_102` | 1.25 | 2.59 | poor | `p257_102_spectrogram_7models_both.png` |
| 11 | `p232_019` | 2.05 | 6.74 | poor | `p232_019_spectrogram_7models_both.png` |
| 12 | `p232_298` | 5.13 | 1.60 | poor | `p232_298_spectrogram_7models_both.png` |

## 三个版本怎么选

| 文件后缀 | 用途 |
|---|---|
| `_spectrogram_7models.png` | **16 kHz 对齐版**：同频带内跨模型比保真度（最干净的可比口径） |
| `..._native.png` | **原生率版**：看 >8 kHz 的真实内容与 8 kHz 断崖 |
| `..._both.png` | **双版合一**：一张图两读法，做汇报/放论文附图最省版面 |

- `mel_roformer_dereverb_echo` 取 **`dry`（干声）** 支；★ = clean 参考面板。

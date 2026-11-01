# Valentini 降噪 · 跨模型声纹联络图（原生采样率版）

与 `FIGURES_valentini_F2_sheets.md`（16 kHz 统一率版）**同片段、同布局**（7 模型 + clean 参考 = 8 面板 2×4），区别是**不做重采样** —— 每个面板保持**产物原生采样率**：

```
figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models_native.png
```

## 这一版用来看什么

- **mel 系列 8 kHz 以上的真实内容**（原生 44.1 kHz，Nyquist 22.05 kHz）
- **denoiser 系列的 8 kHz 断崖**（原生 16 kHz，Nyquist 8 kHz）—— 面板 8 kHz 以上为空白，那是**物理上限**；青色虚线标出该面板 Nyquist
- clean 参考原生 48 kHz（Nyquist 24 kHz），作标尺

## 口径（与 16 kHz 版的唯一差别 + 一个防混淆处理）

1. **不重采样**：各面板按原生率做 STFT → 原生带宽完整保留。
2. **共享频率显示轴 0–24 kHz**（= 最大原生 Nyquist）→ 各面板带宽差异**直接可见**。
3. **跨面板同一 dB 色标**（vmax = 图内最大峰，vmin = vmax−70 dB），同 16 kHz 版。
4. **防分辨率混淆**：`n_fft`/`hop` 按采样率缩放（基准：44.1 kHz 下 n_fft=1024 / hop=512），使各面板 **Δt≈11.6 ms、Δf≈43.1 Hz 完全一致**。否则 hop=512 在 16 kHz 是 32 ms、44.1 kHz 只有 11.6 ms，denoiser 面板会「看起来更糊」—— 那是**分辨率差异不是模型差异**（@16 kHz 版已踩过）。缩放后，面板间差异只剩「原生带宽」这一个变量。

## 联络图清单（原生率版）

| # | 片段 | 输入 SNR (dB) | 时长 (s) | 档 | 原生率联络图 |
|---|---|---|---|---|---|
| 1 | `p232_021` | 11.92 | 8.51 | good | `p232_021_spectrogram_7models_native.png` |
| 2 | `p232_045` | 14.38 | 1.24 | good | `p232_045_spectrogram_7models_native.png` |
| 3 | `p232_020` | 16.23 | 3.62 | good | `p232_020_spectrogram_7models_native.png` |
| 4 | `p232_024` | 16.80 | 5.52 | good | `p232_024_spectrogram_7models_native.png` |
| 5 | `p257_326` | 5.94 | 1.74 | mid | `p257_326_spectrogram_7models_native.png` |
| 6 | `p257_089` | 6.44 | 2.89 | mid | `p257_089_spectrogram_7models_native.png` |
| 7 | `p257_100` | 10.11 | 1.47 | mid | `p257_100_spectrogram_7models_native.png` |
| 8 | `p232_172` | 10.86 | 2.02 | mid | `p232_172_spectrogram_7models_native.png` |
| 9 | `p257_199` | -3.09 | 4.22 | poor | `p257_199_spectrogram_7models_native.png` |
| 10 | `p257_102` | 1.25 | 2.59 | poor | `p257_102_spectrogram_7models_native.png` |
| 11 | `p232_019` | 2.05 | 6.74 | poor | `p232_019_spectrogram_7models_native.png` |
| 12 | `p232_298` | 5.13 | 1.60 | poor | `p232_298_spectrogram_7models_native.png` |

## 怎么读

- **看 mel 面板的 8–22 kHz 区**：是否还有真实内容 / 谐波，还是已接近底噪。
- **看 denoiser 面板的 8 kHz 边界**：边界上沿即断崖；边界以下为模型真实输出。
- **两版对照看**：16 kHz 版看「同一频带内谁更接近 clean」，原生率版看「超出 8 kHz 的部分各模型如何处理」。
- `mel_roformer_dereverb_echo` 取 **`dry`（干声）** 支；★ = clean 参考面板。

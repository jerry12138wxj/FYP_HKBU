# Valentini 降噪 · 跨模型声纹联络图（每片段 1 张）

每个片段一张：**7 个模型 + clean 参考 = 8 面板（2×4）**。

```
figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models.png
```

## 口径（三个「统一」，缺一个就没法跨模型直读）

1. **统一显示采样率 16 kHz**：所有面板（含 clean 参考）都重采样到 16 kHz 再算 STFT。denoiser 系列原生就是 16 kHz；mel 系列原生 44.1 kHz，此处做**降采样**（只丢 8 kHz 以上，**不制造样本**）。这样 `n_fft=1024 / hop=512` 在每个面板里对应**相同的时间与频率分辨率** —— 否则 hop=512 在 16 kHz 是 32 ms、在 44.1 kHz 只有 11.6 ms，denoiser 面板会「看起来更糊」，那是**分辨率差异，不是模型差异**。16 kHz 也正是本项目降噪评测的主口径。
2. **统一显示带宽 0–8 kHz**：= 16 kHz 的 Nyquist。mel 系列 8 kHz 以上的**真实**内容不在本图讨论 —— 否则是拿 mel 的 >8k 去比 denoiser 的**不存在区**（对应板 2 的 T5.6 结论）。
3. **跨面板同一 dB 色标**：以该图 8 个面板的最大峰为 `vmax`、`vmax−70 dB` 为 `vmin`。若改为逐面板归一，安静段与语音段会被拉成同亮度，跨模型判读即失效。

`mel_roformer_dereverb_echo` 取 **`dry`（干声）** 支；★ = clean 参考面板。
标题里的「原生 %d Hz」是该模型产物的**原始**采样率（图上显示前已统一到 16 kHz）。

## 联络图清单

| # | 片段 | 输入 SNR (dB) | 时长 (s) | 档 | 联络图文件 |
|---|---|---|---|---|---|
| 1 | `p232_021` | 11.92 | 8.51 | good | `p232_021_spectrogram_7models.png` |
| 2 | `p232_045` | 14.38 | 1.24 | good | `p232_045_spectrogram_7models.png` |
| 3 | `p232_020` | 16.23 | 3.62 | good | `p232_020_spectrogram_7models.png` |
| 4 | `p232_024` | 16.80 | 5.52 | good | `p232_024_spectrogram_7models.png` |
| 5 | `p257_326` | 5.94 | 1.74 | mid | `p257_326_spectrogram_7models.png` |
| 6 | `p257_089` | 6.44 | 2.89 | mid | `p257_089_spectrogram_7models.png` |
| 7 | `p257_100` | 10.11 | 1.47 | mid | `p257_100_spectrogram_7models.png` |
| 8 | `p232_172` | 10.86 | 2.02 | mid | `p232_172_spectrogram_7models.png` |
| 9 | `p257_199` | -3.09 | 4.22 | poor | `p257_199_spectrogram_7models.png` |
| 10 | `p257_102` | 1.25 | 2.59 | poor | `p257_102_spectrogram_7models.png` |
| 11 | `p232_019` | 2.05 | 6.74 | poor | `p232_019_spectrogram_7models.png` |
| 12 | `p232_298` | 5.13 | 1.60 | poor | `p232_298_spectrogram_7models.png` |

## 怎么读

- **横看一行**：同一频段里，哪个模型的能量块最接近 ★ clean 参考那一格。
- **denoiser 三兄弟**（dns48 / dns64 / master64）常在**静音/纯噪段**透出低频底噪、语音段收紧 —— 与其「自适应噪声门控」的既有结论一致。
- **mel 四兄弟**接近恒等映射，语音段形态与参考基本一致（`level_ratio` 0.96~1.00）。
- **同一片段内对比**最干净：8 个面板同片段、同采样率、同窗、同色标、同频带，变量只有模型。
- 若要看 **mel 的 8 kHz 以上真实行为**（或 denoiser 的 8 kHz 断崖），本图刻意不覆盖，需另出「原生采样率」版。

# 降噪模型 · 逐 output 分析图集

- 图集格式同 `01_separation` 侧
- 产物根目录：`figures/_model_figs/`（A1 隔离）
- 探针：Valentini `p232_001`（1.74 s，与 `tools/_probe_stage0_gate.py` 一致）
- 参考信号：`Valentini/clean_testset_wav/p232_001.wav`
- 窗长档位：128, 512, 1024, 2048
- 产物数：7

## 目录结构

```
figures/_model_figs/<model_slug>/p232_001/fig*.png
```

## 产物清单

| 模型 | 增强输出 | 参考 |
|---|---|---|
| denoiser-dns48 | `03_outputs/denoiser-dns48/stage0_gate/denoiser_dns48/out.wav` | `02_databases/Valentini/clean_testset_wav/p232_001.wav` |
| denoiser-dns64 | `03_outputs/denoiser-dns64/stage0_gate/denoiser_dns64/out.wav` | `02_databases/Valentini/clean_testset_wav/p232_001.wav` |
| denoiser-master64 | `03_outputs/denoiser-master64/stage0_gate/denoiser_master64/out.wav` | `02_databases/Valentini/clean_testset_wav/p232_001.wav` |
| mel-roformer-denoise | `03_outputs/Mel-RoFormer-Denoise/stage0_gate/mel_roformer_denoise/out.wav` | `02_databases/Valentini/clean_testset_wav/p232_001.wav` |
| mel-roformer-denoise-aggr | `03_outputs/Mel-RoFormer-Denoise/stage0_gate/mel_roformer_denoise_aggr/out.wav` | `02_databases/Valentini/clean_testset_wav/p232_001.wav` |
| mel-roformer-dereverb | `03_outputs/Mel-RoFormer-Dereverb/stage0_gate/mel_roformer_dereverb/out.wav` | `02_databases/Valentini/clean_testset_wav/p232_001.wav` |
| mel-roformer-dereverb-echo | `03_outputs/Mel-RoFormer-Dereverb-Echo/stage0_gate/mel_roformer_dereverb_echo/out.wav` | `02_databases/Valentini/clean_testset_wav/p232_001.wav` |

## 图说明

同 `01_separation` 侧；其中 `fig3/fig6` 的 `est` = 增强输出，`ref` = clean 参考。

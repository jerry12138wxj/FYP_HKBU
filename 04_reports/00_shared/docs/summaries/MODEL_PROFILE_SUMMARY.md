# 数据摘要 · 模型本体画像（22 个模型/权重）

> **机器生成 · 禁止手改** ｜ 生成日 2026-09-26 ｜ 交付物 **D11 / T7.3**（模型画像表 D1 的论文取值版）
>
> 数字全部读自下列机器可读文件（正文无手填数值）：
> - `04_reports/00_shared/data/model_analysis/model_profile.csv`
> - `04_reports/00_shared/data/model_analysis/thop_crosscheck.json`
> - `04_reports/00_shared/data/model_analysis/stage0_gate.json`
>
> 重建：`python tools/_build_summaries.py --only model` ｜ 校验：`python tools/_build_summaries.py --verify`
>
> 详解（机理 / 原因 / 决策过程，本表不复述）：`00_shared/docs/MODEL_PROFILE_2026-09-22.md`


---

## 1. 口径三要素（引用本表必须一并声明）

| 项 | 取值 / 说明 |
|:---|:---|
| 生成日 | `2026-09-26`（重建即刷新） |
| 输入构造 | **44.1 kHz / 立体声 / 10 s**（统一合成，不取自数据集） |
| 参数量 | `sum(p.numel())`，取自模型实例，**非**配置声明值 |
| FLOPs | `torch.utils.flop_counter.FlopCounterMode`，**口径 = 2×MACs** |
| 时延 | 预热 2 次后取 **5 次中位数**，CUDA 前后各同步 |
| 峰值显存 | `torch.cuda.max_memory_allocated()` |
| 设备 | RTX 4070 Laptop **8 GiB**（sm_89） |
| 隔离 | **每模型一独立子进程**（22 个同进程会显存耗尽） |

> ⚠️ **FLOPs 是下界，不是等价比较**：`FlopCounterMode` 只统计 torch 调度的算子（conv / linear / matmul / norm）；`torch.stft` 与融合的 `scaled_dot_product_attention` **不计入**。
> 因此跨架构比较**必须配合实测时延**。


覆盖度取自 CSV 字段 `flops_coverage`，实测取值域：['no torch ops dispatched (analytic/classical)', 'torch-dispatch (conv/linear/matmul/norm only)']。


---

## 2. 全表（22 行，保持 CSV 行序以便逐一对齐）

| model_key | 模型 | 组 | 组说明 | 参数量(M) | 权重(MB) | MACs(G) | FLOPs(G) | 时延(s) | RTF | 峰值显存(MB) | thop(G) | 偏差(%) | 状态 |
|:---|:---|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| oracle | IRM/IBM Oracle | analytic | 解析 / 经典基线 | 0.0 | — | 0.0 | 0.0 | 0.000 | 0.0000 | — | — | — | PASS |
| rpca | RPCA (Inexact-ALM) | analytic | 解析 / 经典基线 | 0.0 | — | 0.0 | 0.0 | 82.530 | 8.2530 | — | — | — | PASS |
| umx | Open-Unmix (umxhq) | 4-stem | 四轨分离 | 35.6 | — | 14.3 | 14.3 | 0.200 | 0.0200 | 1227.9 | — | — | PASS |
| mdx | MDX-Net (mdx_extra) | 4-stem | 四轨分离 | 334.5 | — | 777.2 | 777.2 | 0.737 | 0.0737 | 1912.8 | — | — | PASS |
| convtasnet | Conv-TasNet (musdb18) | 4-stem | 四轨分离 | 13.4 | — | 1171.7 | 1171.7 | 1.522 | 0.1522 | 606.6 | — | — | PASS |
| mmdenselstm | MMDenseLSTM (musdb18) | 4-stem | 四轨分离 | 5.5 | — | 294.5 | 294.5 | 0.333 | 0.0333 | 643.0 | — | — | PASS |
| bsroformer_l12 | BS-RoFormer L12 (ep_317, vocals) | 1-target | 单目标（人声） | 159.8 | — | 43480.9 | 43480.9 | 4.521 | 0.4521 | 3394.3 | — | — | PASS |
| bsroformer_l6 | BS-RoFormer L6 (ep_937, vocals+other) | 2-target | 双目标 | 98.2 | — | 14975.2 | 14975.2 | 2.170 | 0.2170 | 2087.4 | — | — | PASS |
| bsrnn | BSRNN (oBSRNN, vocals) | 1-target | 单目标（人声） | 40.8 | — | 955.5 | 955.5 | 1.081 | 0.1081 | 1675.0 | 3428.8 | 258.86 | PASS |
| bsrnn_all | BSRNN (oBSRNN, 4-stem) | 4-stem | 四轨分离 | 164.1 | — | 3891.3 | 3891.3 | 5.733 | 0.5733 | 2637.4 | 4596.9 | — | PASS |
| bsrnn_large | BSRNN large (vocals) | 1-target | 单目标（人声） | 36.4 | — | 276.8 | 276.8 | 0.629 | 0.0629 | 1657.4 | 2972.8 | 973.93 | PASS |
| bsrnn_large_all | BSRNN large (4-stem) | 4-stem | 四轨分离 | 146.7 | — | 1126.9 | 1126.9 | 2.949 | 0.2949 | 2567.9 | 3985.2 | — | PASS |
| bsrnn_simo | BSRNN SIMO (4-stem) | 4-stem | 四轨分离 | 108.7 | — | 1540.1 | 1540.1 | 1.210 | 0.1210 | 2483.0 | 4978.7 | 223.27 | PASS |
| demucs | Demucs (htdemucs) | 4-stem | 四轨分离 | 42.0 | — | 508.1 | 508.1 | 0.275 | 0.0275 | 599.7 | — | — | PASS |
| dprnn | DPRNN (自训, 4-stem) | 4-stem | 四轨分离 | 3.7 | — | 30.6 | 30.6 | 0.103 | 0.0103 | 579.7 | — | — | PASS |
| mel_roformer_denoise | Mel-RoFormer-Denoise (aufr33) | denoise | 降噪（板 2） | 228.2 | 913.1 | 4030.5 | 4030.5 | 0.980 | 0.0980 | 2011.2 | — | — | PASS |
| mel_roformer_denoise_aggr | Mel-RoFormer-Denoise (aggr) | denoise | 降噪（板 2） | 228.2 | 913.1 | 4030.5 | 4030.5 | 0.973 | 0.0973 | 2011.2 | — | — | PASS |
| mel_roformer_dereverb | Dereverb-Mel-RoFormer | dereverb | 去混响 / 去回声（板 2） | 228.2 | 913.1 | 4030.5 | 4030.5 | 0.981 | 0.0981 | 2011.2 | — | — | PASS |
| mel_roformer_dereverb_echo | Dereverb-Echo-Mel-RoFormer | dereverb | 去混响 / 去回声（板 2） | 208.9 | 836.0 | 3447.1 | 3447.1 | 1.018 | 0.1018 | 1869.2 | — | — | PASS |
| denoiser_dns48 | denoiser dns48 (16 kHz) | denoise | 降噪（板 2） | 18.9 | 75.5 | 39.1 | 39.1 | 0.085 | 0.0084 | 233.3 | — | — | PASS |
| denoiser_dns64 | denoiser dns64 (16 kHz) | denoise | 降噪（板 2） | 33.5 | 134.1 | 69.0 | 69.0 | 0.126 | 0.0126 | 343.2 | — | — | PASS |
| denoiser_master64 | denoiser master64 (16 kHz) | denoise | 降噪（板 2） | 33.5 | 134.1 | 69.0 | 69.0 | 0.127 | 0.0127 | 343.2 | — | — | PASS |

---

## 3. 分组计数（读自 CSV 的 `group` 列）

| 组 | 组说明 | 模型数 |
|:---|:---|---:|
| 1-target | 单目标（人声） | 3 |
| 2-target | 双目标 | 1 |
| 4-stem | 四轨分离 | 9 |
| analytic | 解析 / 经典基线 | 2 |
| denoise | 降噪（板 2） | 5 |
| dereverb | 去混响 / 去回声（板 2） | 2 |

---

## 4. FLOPs 独立第二口径（thop 交叉验证）

- 容差：**5.0 %** ｜ 单位：`thop_G = 2*MACs` ｜ 覆盖 **22** 个模型
- thop 能给出可比数值的：**3** 个 —— 其中在容差内 **0** 个、**超容差 3** 个（`bsrnn`、`bsrnn_large`、`bsrnn_simo`）；**无法用 thop 复核**：**19** 个
- ⚠️ 超容差**不是数值矛盾，是算子覆盖不同**（`备注` 列可见：thop 只看到单网/少了一维）。故 FLOPs 跨架构比较以「**本列下界 + 实测时延**」为准，thop 仅作参考。

| model_key | thop(G) | 偏差(%) | 备注 |
|:---|---:|---:|:---|
| bsrnn | 3428.8 | 258.86 | BSRNN @ 1,C,T; thop=2xMACs  [FLAG: dev>5% -> count coverage differs] |
| bsrnn_all | 4596.9 | — | BSRNN @ 1,C,T; thop=2xMACs; AGGREGATED loader (4 nets) -> thop saw 1 n |
| bsrnn_large | 2972.8 | 973.93 | BSRNN @ 1,C,T; thop=2xMACs  [FLAG: dev>5% -> count coverage differs] |
| bsrnn_large_all | 3985.2 | — | BSRNN @ 1,C,T; thop=2xMACs; AGGREGATED loader (4 nets) -> thop saw 1 n |
| bsrnn_simo | 4978.7 | 223.27 | BSRNN @ 1,C,T; thop=2xMACs  [FLAG: dev>5% -> count coverage differs] |
| bsroformer_l12 | — | — | thop cannot profile this model (AssertionError:stereo needs to be set  |
| bsroformer_l6 | — | — | thop cannot profile this model (AssertionError:stereo needs to be set  |
| convtasnet | — | — | thop cannot profile this model (ValueError:Not support 2 dimension inp |
| demucs | — | — | thop cannot profile this model (NotImplementedError:Call `apply_model` |
| denoiser_dns48 | — | — | thop cannot profile this model (RuntimeError:Input type (torch.FloatTe |
| denoiser_dns64 | — | — | thop cannot profile this model (RuntimeError:Input type (torch.FloatTe |
| denoiser_master64 | — | — | thop cannot profile this model (RuntimeError:Input type (torch.FloatTe |
| dprnn | — | — | thop cannot profile this model (RuntimeError:Calculated padded input s |
| mdx | — | — | thop cannot profile this model (NotImplementedError:Call `apply_model` |
| mel_roformer_denoise | — | — | thop cannot profile this model (AssertionError:stereo needs to be set  |
| mel_roformer_denoise_aggr | — | — | thop cannot profile this model (AssertionError:stereo needs to be set  |
| mel_roformer_dereverb | — | — | thop cannot profile this model (AssertionError:stereo needs to be set  |
| mel_roformer_dereverb_echo | — | — | thop cannot profile this model (AssertionError:stereo needs to be set  |
| mmdenselstm | — | — | thop cannot profile this model (AssertionError:input is expected 4D in |
| oracle | — | — | no nn.Module (analytic/classical) - thop N/A by construction |
| rpca | — | — | no nn.Module (analytic/classical) - thop N/A by construction |
| umx | — | — | thop cannot profile this model (ValueError:not enough values to unpack |

---

## 5. 板 2 门禁（stage0：加载 + 前向 + 探针）

| 模型 | 状态 | 参数量 | load(s) | forward(s) | ΔSI-SDR(dB) | `peak`（门禁自报） |
|:---|:---:|---:|---:|---:|---:|---:|
| denoiser_dns48 | PASS | 18867937 | 0.18 | 0.360 | 2.15 | 0.5027 |
| denoiser_dns64 | PASS | 33533569 | 0.29 | 0.035 | 1.69 | 0.5100 |
| denoiser_master64 | PASS | 33533569 | 0.31 | 0.029 | 0.15 | 0.5202 |
| mel_roformer_denoise | PASS | 228202852 | 1.53 | 0.534 | 9.88 | 0.5002 |
| mel_roformer_denoise_aggr | PASS | 228202852 | 1.97 | 0.167 | 9.67 | 0.5026 |
| mel_roformer_dereverb | PASS | 228202852 | 1.78 | 0.156 | 3.59 | 0.5073 |
| mel_roformer_dereverb_echo | PASS | 208880476 | 1.76 | 0.323 | 3.60 | 0.5078 |

> 门禁生成时间：`2026-09-22 23:15:05` ｜ 设备：`cuda`


---

## 6. 复现

```bash
python tools/_build_summaries.py --only model   # 重建本表
```


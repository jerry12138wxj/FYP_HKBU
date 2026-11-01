# 模型库加载 + 优秀模型清单 + Valentini SDR 对比

> 2026-10-20 更新。范围：用户指定 5 个「模型」的加载核实 + 分离/降噪优秀模型清单 + Valentini spectrogram 与 SDR 对比（前 100 条 → 已扩展全量 824 条）。

## 一、用户指定的 5 个「模型」——加载核实结果

⚠️ 其中有 3 个名字需要先纠正（不是独立模型）：

| 用户写的 | 实际是什么 | 加载状态 |
|---|---|---|
| Valentini | **数据集**（`02_databases/Valentini`），不是模型 | 已存在（clean/noisy 各 824 条，48 kHz） |
| demus mdx_q | demucs 的 **mdx_q**（量化 MDX 4 模型 bag） | ✅ **已加载并归档**（见下） |
| demus mdx_extra_q | demucs 的 **mdx_extra_q**（量化 extra MDX） | ✅ **已加载并归档**（见下） |
| mdx demus | **mdx**（MDX-Net 4 模型 bag）/ htdemucs | ✅ mdx 已归档并验证；htdemucs 已在库 |
| Wiener filter | **Open-Unmix 的 multichannel Wiener 后处理**（非独立模型） | ✅ 已含在 umxhq（`openunmix.predict` 的 `wiener_win_len`） |

### mdx 归档（本轮新增）
- 权重：`01_models/_weights/MDX-Net/mdx/`（4 个 `.th`，共 ~675 MB）
- 定义：`mdx.yaml`（`models: ['0d19c1c6','7ecf8ec1','c511e2ab','7d865c68']` + weights 4×4 + segment 44）
- 验证：`get_model('mdx', repo=Path('01_models/_weights/MDX-Net/mdx'))` → `BagOfModels` ✅
- 注意：PyTorch 2.6 需 `torch.load(weights_only=False)`（benchmark 已处理，同款）

### mdx_q / mdx_extra_q 的 blocker —— ✅ 已解决（纯 Python 绕过 MSVC，无需装 6 GB 编译器）
- 原 blocker：`diffq.bitpack` 是 Cython 扩展，`pip install diffq` 需要 MSVC 编译，本机无编译器。
- 解法：**不装 MSVC** —— diffq 只有 `bitpack` 一个 C 扩展，其余全纯 Python。
  把 `diffq/` 纯 Python 包复制进 site-packages，并自写 `bitpack.py`（numpy 位交错，全程 uint64 防 float64 精度丢失）。
  ⚠️ 坑：`torch_pack` 与 `bitpack` 存储格式不同（2 维 int16 vs 3 维 int64），必须按 `bitpack.pyx` 精确重写，不能互替。
- 归档：`01_models/_weights/MDX-Net/{mdx_q,mdx_extra_q}/`（各 4 个 `.th` + yaml），工具 `tools/_archive_mdx_quant.py`。
- 验证：mdx_q **345,460,200** 参数 / mdx_extra_q **334,543,632** 参数，dequantize 后全 float32，远程+本地加载均通过。
- 加载需 `torch.load(weights_only=False)`（同 mdx，benchmark 已处理）。

## 二、优秀模型清单

### 分离（SDR_vocals 中位数，museval 3 均衡片段，按 vocals 降序）

| 排名 | 模型 | SDR_vocals | RTF | 定位 |
|---|---|---|---|---|
| 1 | Oracle-IRM | 10.03 | 0.007 | 解析上界（需 GT 掩码，不可实时部署） |
| 2 | BS-RoFormer L12 | 9.69 | 0.494 | **精度最优（可部署）** |
| 3 | oBSRNN (4ckpt) | 9.17 | 0.418 | 精度次优 |
| 4 | oBSRNN-SIMO | 8.65 | 0.191 | 单目标快速版 |
| 5 | BSRNN-large (4ckpt) | 8.28 | 0.321 | 精度/成本均衡 |
| 6 | MDX-Net | 7.97 | 0.137 | 频谱掩码派 |
| 7 | Demucs (htdemucs) | 7.11 | **0.028** | **实时最优（级联默认）** |
| 8 | Open-Unmix | 6.05 | 0.059 | 经典频谱基线 |
| 9 | MMDenseLSTM | 5.60 | 0.082 | 历史基线 |
| 10 | Conv-TasNet | 5.00 | 0.176 | 时域端到端基线 |
| 11 | DPRNN（自训 4-stem） | −2.18 | 0.031 | 自训失败，弃 |

### 降噪（Valentini ALL，n=824，按 ΔPESQ 降序）

| 排名 | 模型 | ΔPESQ | ΔSI-SDR | ΔSTOI | 定位 |
|---|---|---|---|---|---|
| 1 | denoiser **master64** | **+0.963** | +9.49 | +0.017 | **PESQ 最优** |
| 2 | denoiser dns64 | +0.601 | +9.64 | +0.007 | 均衡 |
| 3 | denoiser dns48 | +0.551 | **+9.86** | +0.005 | **SI-SDR 最优** |
| 4 | Mel-RoFormer-Denoise (aggr) | +0.256 | +8.16 | +0.005 | 子带 Transformer |
| 5 | Mel-RoFormer-Denoise (aufr33) | +0.239 | +6.65 | +0.004 | 子带 Transformer |

## 三、Valentini 前 100 条 spectrogram + SDR 对比

产物目录：`04_reports/02_denoising/figures/valentini_snr_compare/`
- `snr00/ snr05/ snr10/ snr15/`：每对 clean↑ noisy↓ 并排图（各 25 张，共 100）
- `SDR_summary.json`：分档 + 整体统计

**口径**：SDR(noisy vs clean) = 10·log10( Σclean² / Σ(noisy−clean)² )，数值上等于输入 SNR。能量对齐：clean 与 noisy 共用 clean 峰值为 0 dB 参考，同一色标 −80~0 dB。

**结果**：

| SNR 档 | n | mean SDR | min | max |
|---|---|---|---|---|
| 0 dB | 25 | 0.79 | −0.73 | 2.05 |
| 5 dB | 25 | 5.98 | 4.42 | 7.01 |
| 10 dB | 25 | 11.15 | 9.91 | 11.98 |
| 15 dB | 25 | 15.96 | 14.38 | 16.95 |
| **整体** | **100** | **8.47** | **−0.73** | **16.95** |

> 说明：实测 SNR 略高于名义档位（如 10 dB 档实测 11.15）——Valentini 的 noisy 是按目标 SNR 混合但含能量校准偏差，属正常；本表用**实测值**，不修数。

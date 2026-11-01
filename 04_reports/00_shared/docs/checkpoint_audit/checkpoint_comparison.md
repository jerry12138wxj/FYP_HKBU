# Checkpoint 对比与优劣分析

> 审计日期：2026-10-30 ｜ 范围：`01_models/` 全部 22 个模型条目
> 本地权重：**57 个文件 / 11.49 GB**，**全部实算 SHA256**（`checkpoint_inventory.csv` 的 `sha256` 列）
> 未下载权重：**4 个**，`sha256` 列留空，`size_check` 明确写 `not downloaded`
> 证据路径全部可复查；无法离线核实的字段一律写 `unverified`

## 0. 全模型推荐总表

| 模型 | 本地有几个 ckpt | 推荐用哪个 | 判定依据（不是"感觉"） |
|---|---|---|---|
| BS-RoFormer-L12 | 1 | `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | 官方 MSST 预训练清单 Vocal models 表列名；且是本机唯一 L12 权重 |
| BS-RoFormer-L6 | 1 | `model_bs_roformer_ep_937_sdr_10.5309.ckpt` | 官方清单 Single stem models 表列名（标注为 other，实测输出 vocals+other） |
| BSRNN | 9（3 变体） | **`simo-bsrnn-opt/separator.ckpt`** | README 原话："we encourage to consider this variant if achieving maximum performance is the goal" |
| Demucs | 1 | `955717e8-8726e21a.th` | README line 222："`htdemucs` … **Default model**" |
| MDX-Net | 12（4 家族） | **有官方推荐的只有 `mdx`**（track A 冠军）；本项目实际用 `mdx_extra` 4 个 ensemble（无推荐标记，但精度更高） | demucs README line 228 明写 `mdx` 是 MDX 挑战 track A 冠军 |
| Conv-TasNet | 6（3 变体） | `8sec_L64/model/best.pth` | 只有"最长 segment + 最宽通道"这一条可辩护理由；官方 SDR 表**不区分变体** → 变体排序无法验证 |
| MMDenseLSTM | 8（4 目标 ×2） | 4 个 `paper/model/<target>/best.pth` 组合使用 | 官方只发"paper"一套预设，无变体可选 |
| Open-Unmix | 4 | 4 个 `.pth` 组合使用 | 每目标一个网络，缺一不可 |
| DPRNN | 2 | `dprnn_musdb/best.pt` | 官方**无音乐权重**，本机唯一来源是自训；best 优于 last |
| denoiser（3 个模型） | 3 | 评测用 `dns64`；追求 PESQ 用 `master64`（须声明 in-domain） | 官方无 default 标志（`get_model()` 无兜底分支），只能按训练集选 |
| Mel-RoFormer-Denoise | 2 | `..._aggr_sdr_27.9768.ckpt` | 本机实测 aggr 在全部 SNR 档位优于 normal（+8.16 vs +6.65 dB SI-SDR） |
| Mel-RoFormer-Dereverb | 1 | `dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt` | 官方清单唯一 dereverb 条目 |
| Mel-RoFormer-Dereverb-Echo | 1 | `dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt` | 官方清单唯一 deecho 条目 |
| Oracle-IRM / RPCA | 0 | — | 解析算法，无权重 |
| RPCA+DRNN / Pac-HuBERT-SEP | 0 | — | 官方从未公开代码与权重 |

---

## 1. BS-RoFormer（L12 / L6）

### 对比表

| 维度 | ep_317（L12） | ep_937（L6） | *ep_3005 MelBand（未下载）* | *PolarFormer（未下载）* |
|---|---|---|---|---|
| 官方列出的指标 | SDR **vocals 10.87** | SDR **other 6.85** | SDR vocals 9.67 | SDR vocals **11.00** |
| 指标口径 | Multisong Dataset（mvsep quality checker），非 MUSDB18 | 同左 | 同左 | 同左 |
| 本机实测（3 片段中位） | vocals 10.00（museval）/ SI-SDR 11.10 | vocals+other 12.63 / SI-SDR 12.13 | — | — |
| 参数量 | 159.758 M | 98.195 M | unverified | unverified |
| 文件大小 | 639,331,213 B（609.7 MB） | 393,068,365 B（374.9 MB） | 未下载 | 未下载 |
| 本机时延(10 s) / RTF | 4.5208 s / **0.452** | 2.1702 s / **0.217** | — | — |
| 训练数据 | MUSDB18-HQ + 额外数据（精确配比 unverified） | 同左 | unverified | unverified |
| 许可证 | MSST 仓库 MIT；**权重本身未单独声明** | 同左 | unverified | unverified |
| 输出语义 | `vocals`（单目标） | **实测 = mixture−drums−bass**，不是 yaml 写的 `other` | vocals/other | vocals/other |
| 部署友好度 | 未验证（本项目零导出） | 未验证 | — | — |
| 可复现性 | 训练框架公开（MSST），该 ckpt 的完整训练配置**未公开** | 同左 | — | — |
| 官方支持度 | 官方清单收录；训练者为社区（viperx），经官方 release 分发 | 同左 | 官方清单收录 | 官方清单收录（v1.0.20 release） |

### 推荐

**L12 用 ep_317，L6 用 ep_937** —— 各自只有一个本机权重，没有选择空间。这两个 ckpt 都出现在官方 `docs/pretrained_models.md` 的表里，属于"官方清单收录"，但它们**不是论文作者的权重**，而是 UVR 社区（viperx）训练、由 ZFTurbo 官方 release 分发。

### 优劣

**ep_317（L12）**
- 优点：vocals SDR 全场最高一档（本机 10.00 dB）；单目标，输出语义干净
- 缺点：609.7 MB + 159.8 M 参数，本机 RTF 0.452，接近实时但**在 8 GiB 卡上峰值 3394 MB**，级联时不能与别的模型并存；RTF 靠 GPU，CPU 上 10.97（完全不可实时）
- 适用：只要人声、有 GPU
- 不适用：CPU 实时、显存 <4 GB、需要 4 轨

**ep_937（L6）**
- 优点：374.9 MB、RTF 0.217，比 L12 轻一半且更快
- 缺点：**语义陷阱** —— yaml 写 `target_instrument: other`，实测输出是 `vocals+other`。直接与 MUSDB 的纯 `other` 对比会得出 0.83 dB 的"模型失效"误判（实测 vocals+other 上是 12.13 dB）
- 适用：需要"人声+伴奏残差"的场景
- 不适用：需要严格 4-stem 拆分的任何定量对比

> ⚠️ 社区权重标注：这两个 ckpt 由社区训练。**引用时必须写"权重由 viperx 训练，经 ZFTurbo MSST 分发，非论文作者原始权重"**。

---

## 2. BSRNN（opt / large / SIMO）

### 对比表

| 维度 | bsrnn-opt | bsrnn-large | **simo-bsrnn-opt** |
|---|---|---|---|
| 官方指标（MUSDB18-HQ test，chunk SDR） | 9.81 / 9.85 / 10.31 / 6.31，avg **9.07** | 9.5 / 7.8 / 10.3 / 6.3，avg **8.5**（`large (patience=30)` 行） | **10.66 / 9.73 / 10.98 / 7.78，avg 9.79** |
| 指标口径 | chunk SDR = 1 s 窗中位 → 再按曲中位（museval） | 同左 | 同左 |
| 结构 | 4 个单目标 ckpt 聚合 | 4 个单目标 ckpt 聚合 | **1 个 4 输出模型** |
| 本地文件数 / 总大小 | 4 / 1884 MiB | 4 / 1682 MiB | 1 / **1248 MiB** |
| 参数量（官方/本机测） | 40.777 M 单目标 / 164.119 M 四轨 | 36.417 M / 146.656 M | 108.728 M |
| 本机时延(10 s) / RTF | 1.0814 s 单目标 / 5.7328 s 四轨 → RTF 0.108 / 0.573 | 0.6294 / 2.9494 s → 0.063 / 0.295 | 1.2105 s → **0.121** |
| 训练数据 | MUSDB18-HQ（100 首） | 同左 | 同左 |
| 许可证 | bsrnn 仓库 MIT；Zenodo 记录许可证 **unverified** | 同左 | 同左 |
| 官方支持度 | 官方默认 `model_dir`（README line 111） | 官方发布，无推荐标记 | README 明确"追求最高性能请选它" |

### 推荐

**`simo-bsrnn-opt/separator.ckpt`**。理由有三条，都可复查：
1. 官方 README 原话推荐（"we encourage to consider this variant if achieving maximum performance is the goal"）；
2. 官方指标最高（avg 9.79 vs 9.07 vs 8.5）；
3. **工程上更省**：单模型 108.7 M / 1248 MiB，比 opt 的 164.1 M / 1884 MiB 少 34% 参数、少 34% 磁盘，且 4 轨一次前向 RTF 0.121，比 opt 的 0.573 快 4.7 倍。

### 优劣

**simo-bsrnn-opt**
- 优点：精度最高、显存与参数最省、单次前向出 4 轨
- 缺点：⚠️ **state_dict 按位置对齐** —— ckpt 里 `hyper_parameters.targets = ['vocals','bass','drums','other']`，若按别的顺序构造模型，4 个 masker 会**静默互换**（不报错、能出声、指标全错）。本项目已用 `ckpt_targets()` 从 ckpt 读取顺序并强制校验
- 适用：追求精度的离线批处理、有 GPU
- 不适用：需要逐目标单独调参的场景（单目标模型更灵活）

**bsrnn-opt**
- 优点：官方默认路径，文档与示例最完整；单目标模型可只加载需要的 1/4
- 缺点：4 个 ckpt 聚合时 RTF 0.573，比 SIMO 慢 4.7 倍；参数最多
- 适用：复现官方 baseline、按目标裁剪部署
- 不适用：实时四轨

**bsrnn-large**
- 优点：单目标 RTF 0.063，最轻快
- 缺点：官方指标最低（avg 8.5）；Zenodo 上 `bsrnn-large.zip` 对应 `docs/analysis.md` 哪一行**无法验证**
- 适用：算力受限、只需单轨
- 不适用：要最高精度

---

## 3. Demucs（htdemucs）

### 对比表

| 维度 | `955717e8-8726e21a.th`（本机） | *htdemucs_ft（未下载）* | *htdemucs_6s（未下载）* |
|---|---|---|---|
| 官方定位 | **README line 222：Default model** | fine-tuned 版，慢 4 倍，"might be a bit better" | 6 轨版（加 piano/guitar）|
| 官方指标 | Multisong avg **9.16**（bass 11.76 / drums 10.88 / vocals 8.24 / other 5.74）；README 对比表 HT Demucs f.t. = 9.0 | 官方仅给 f.t. 的 9.0，**单模型 9.16 与 f.t. 的关系未说明** | bass 11.22 / drums 10.22 / vocals 8.05，other/piano/guitar 为 `---` |
| 本机实测（3 片段中位） | 四轨均值 8.11 / vocals 7.11 | — | — |
| 参数量 / 大小 | 41.984 M / 84,141,911 B（80.2 MB） | unverified | unverified |
| 本机时延(10 s) / RTF | 0.2749 s / **0.0277** | — | — |
| 训练数据 | **MusDB + 800 songs** | 同上（README line 224） | 同上 |
| 许可证 | **MIT**（本地 LICENSE 文件首行确认） | MIT | MIT |
| 完整性自证 | 文件名后缀 `8726e21a` == 实算 SHA256 前 8 位 ✅ | — | — |

> 另注：本机 HF 缓存 `~/.cache/huggingface/hub/models--adefossez--HTDemucs/` 还存了一份 `955717e8.safetensors`（84,025,440 B），与 `_weights` 里的 `.th`（84,141,911 B）是**同一权重的两种序列化**，字节不同属正常。

### 推荐

**`955717e8-8726e21a.th`**。这是官方 README 明写的默认模型，也是 MSST 官方清单里 HTDemucs4 一行对应的权重。没有理由换。

### 优劣

- 优点：**RTF 0.0277，全场最快**；单模型直接出 4 轨；MIT 许可最干净；80 MB 体积最小；文件名自带 SHA256 前缀，可自证完整性
- 缺点：精度不是第一（四轨均值 8.11，低于 BSRNN-SIMO 9.27）；**other 轨 5.49 明显偏弱**；CPU 上非确定性（同输入两次 ±0.1~0.3 dB），报单曲数字必须标注波动
- 适用：实时/低延迟部署、嵌入端侧、需要干净许可证
- 不适用：追求最高 SDR、需要 6 轨（要用 htdemucs_6s）

---

## 4. MDX-Net 家族（12 个 ckpt）

### 对比表

| 家族 | 文件数 | 单文件大小 | 合计 | 本机实测（museval 1 s 窗，10 s 片段，RTX 4070） | 官方说明 |
|---|---|---|---|---|---|
| `mdx_extra` | 4 | 167,391,595 ×2 / 167,399,275 ×2 B（各 159.6 MiB） | **639 MiB** | vocals 8.52 / drums 6.15 / bass 21.23 / other 8.88 | 4 个 MDX 挑战 submission 权重，需 ensemble |
| `mdx` | 4 | 169.8 / 160.1 / 169.8 / 159.6 MiB | 659 MiB | 项目未单独测（demucs 另一权重族，仅参考） | demucs 内置的 MDX 权重族 |
| `mdx_q` | 4 | 44.7 / 55.5 / 56.9 / 42.3 MiB | 199 MiB | 3 段 ×10 s 测 8.80 dB | **官方：quantized，smaller but maybe a bit less accurate** |
| `mdx_extra_q` | 4 | 36.7 / 37.1 / 37.6 / 48.4 MiB | **160 MiB** | **8.37 dB（比 mdx_extra 8.96 低 0.59）** | 同左 |

- 参数量（`mdx_extra` 4 个合计）：**334.544 M**，全场最多
- 本机时延(10 s) / RTF：0.7373 s / **0.134**（4 个 ensemble 合计）
- 训练数据：MUSDB18（mdx 为 MUSDB HQ 冠军方案；`mdx_extra` 具体配比 unverified）
- 许可证：`mdx-net` 及 3 个 submission 仓库均 **MIT**（本地 LICENSE 文件确认）
- 部署友好度：**唯一有官方 ONNX 包的模型** —— `01_models/_weights/MDX-Net/onnx_A.zip`（110,359,032 B）。但本项目**从未解压验证**其与 `.th` 的数值一致性 → 一致性 unverified
- 官方支持度：Meta demucs 包内维护；MDX 挑战已结束

### 推荐

按"官方推荐"的严格定义（见 `checkpoint_audit_report.md` §3），**唯一有推荐依据的是 `mdx` 家族**：demucs README line 228 明写 *"`mdx`: trained only on MusDB HQ, **winning model on track A at the MDX challenge**"*（优先级 P3：竞赛最佳）。`mdx_extra` 是 4 个 submission 权重的 ensemble，**README 没有给它任何推荐标记**。

但工程上本项目用的是 `mdx_extra`（4 ckpt 整套），因为它在 4 轨上的实测精度更高（8.96 dB）。这两个选择要分开说：
- **要"官方背书"** → 用 `mdx`（track A 冠军）
- **要精度** → 用 `mdx_extra`，但论文里必须写"本项目选用 ensemble，无官方推荐标记"

**不推荐量化版**：官方明说 less accurate，本机实测也确实低 0.59 dB。

### 优劣

**mdx_extra（4 ckpt ensemble）**
- 优点：bass 轨 21.23 dB 是全场最高一档；有官方 ONNX 包，是唯一"看起来能上非 PyTorch 运行时"的模型
- 缺点：334.5 M 参数最大；4 个模型串行，显存与延迟叠加；**torch ≥2.6 需 `weights_only=False`** 才能加载（安全性与可移植性都受影响）；单个 ckpt 不能单独用
- 适用：离线高质量分离、需要 bass 精度、需要 ONNX 路线
- 不适用：端侧、低显存、需要单模型

**mdx_q / mdx_extra_q（量化）**
- 优点：总体积从 640 MB 降到 168~209 MB，适合分发
- 缺点：精度掉 0.59 dB（实测）；依赖纯 Python 的 `diffq` 包，环境更脆
- 适用：带宽/存储受限的分发场景
- 不适用：追求精度的评测对比

---

## 5. 早期与基线模型（Conv-TasNet / MMDenseLSTM / Open-Unmix / DPRNN）

### 对比表

| 维度 | Conv-TasNet | MMDenseLSTM | Open-Unmix | DPRNN |
|---|---|---|---|---|
| 本地 ckpt | 6（3 变体 × best/last） | 8（4 目标 × best/last） | 4（每目标 1 个） | 2（best/last，**自训**） |
| 官方指标（MUSDB18 test，museval 中位） | bass 5.95 / drums 6.11 / other 3.78 / vocals 5.59 / **avg 5.36** | 4.80 / 6.22 / 4.43 / 6.87 / **avg 5.58** | 5.02 / 6.06 / 4.00 / 6.14 / **avg 5.30** | **无官方音乐权重** |
| 本机实测 | vocals 4.73 / drums 2.05 / bass 17.30 / other 5.58 | 7.02 / 2.37 / 17.13 / 7.83 | 四轨均值 6.65（历史产物） | 四轨均值 **−1.72**（负） |
| 参数量 | 13.395 M | 5.487 M（4 目标合计） | 35.577 M | 3.686 M |
| 大小 | 27.5~54.0 MB/个 | 5.81 MB/个 | 35.6 MB/个 | best 14.8 MB / last 44.4 MB |
| 本机时延(10 s) / RTF | 1.5221 s / 0.152 | 0.3331 s / 0.033 | 0.2 s / 0.020 | 0.103 s / 0.010 |
| 训练数据 | MUSDB18 train（100 首） | 同左 | MUSDB18 | MUSDB18-HQ，本机 31900 step |
| 许可证 | 原仓库 MIT；**镜像仓库无 LICENSE 文件** | **镜像仓库无 LICENSE 文件** | repo MIT；**umxhq 权重许可未声明**（umxl 才明确 CC BY-NC-SA 4.0） | Apache-2.0（代码）；权重为本项目所有 |
| 官方支持度 | 社区镜像（tky823） | 社区镜像（tky823） | 官方 sigsep | 自训，无官方支持 |

### 推荐

- **Conv-TasNet**：`8sec_L64/model/best.pth`。唯一可辩护的理由是"最长 segment + 最宽通道"，但**官方 SDR 表只给一个 Conv-TasNet 数字（5.36），不区分 3 个变体 → 哪个变体最好无法验证**。若要严谨，应把 3 个变体都跑一遍再排序。
- **MMDenseLSTM**：4 个 `paper/model/<target>/best.pth`，套用官方唯一预设，无选择空间。
- **Open-Unmix**：4 个 `.pth` 必须成套；它是基线参考实现，不是竞品。
- **DPRNN**：`best.pt`。官方只发语音权重（wsj0-mix / librispeech），**没有 MUSDB18 音乐权重**，本机权重是自训产物，指标为负，**只能作负面证据**。

### 优劣

**Conv-TasNet**：纯时域、13.4 M 最小巧；但 other 轨官方 3.78 dB、本机 5.58（口径不同），是最弱一档；镜像仓库无 LICENSE 是真实法务风险。
**MMDenseLSTM**：5.49 M 参数最少、RTF 0.033 很快，但官方 avg 5.58 偏低；需 `ParallelMMDenseLSTM` + `TimeDomainWrapper` 才能正确加载，容易踩形状坑。
**Open-Unmix**：最稳的基线（MIT、官方维护、代码干净），但精度就是基线水平。
**DPRNN**：RTF 0.010 最快，但四轨 SDR 全为负；`last.pt` 44.4 MB（含优化器状态）只用于续训，评测用 `best.pt`。

> ⚠️ 社区/镜像权重标注：Conv-TasNet、MMDenseLSTM 的权重由 **tky823 社区仓库**转换并分发，**非原作者发布的权重**。引用需注明。

---

## 6. 降噪器（dns48 / dns64 / master64）

### 对比表

| 维度 | dns48 | dns64 | master64 | *valentini_nc（未下载）* |
|---|---|---|---|---|
| 官方定位 | "real time H=48, trained on DNS" | "real time H=64, trained on DNS" | "real time H=64, **trained on DNS and Valentini**" | "H=64, trained on Valentini, **non causal**" |
| 官方指标 | README 无指标表 → **unverified** | 同左 | 同左 | 同左 |
| **本机实测**（Valentini 824 条，16 kHz，逐条配对差中位） | ΔSI-SDR **+9.86** / ΔPESQ **+0.551** | +9.64 / +0.601 | +9.49 / **+0.963** | — |
| 参数量 | 18.868 M | 33.534 M | 33.534 M | unverified |
| 大小 | 75,478,395 B（72 MB） | 134,140,945 B（128 MB） | 134,140,945 B（128 MB） | 未下载 |
| 本机时延(10 s) / RTF | 0.0845 s / **0.0085** | 0.1263 s / 0.0126 | 0.1269 s / 0.0127 | — |
| 许可证 | **CC-BY-NC 4.0（禁止商用）** | 同左 | 同左 | 同左 |
| 完整性自证 | 文件名后缀 == SHA256 前 16 位 ✅ | ✅ | ✅ | — |

### 推荐

**评测用 `dns64`，报 PESQ 用 `master64`（必须同时标注 in-domain 问题）**。

理由：官方**没有默认模型**（`get_model()` 里 `--dns48/--dns64/--master64` 是并列分支，无兜底 → 不传参就加载失败），所以只能按训练集选。`master64` 的 CLI help 明写训练集含 Valentini，而我们恰好在 Valentini 上评测 → **它在自己见过的数据上考了 +0.963 PESQ，这个数字不能当作泛化能力**。`dns64` 训练集不含 Valentini，是公平口径。

### 优劣

**dns48**：最小最快（RTF 0.0085），SI-SDR 改善最高（+9.86），PESQ 最低（+0.551）。适合极限轻量。
**dns64**：公平口径下的最佳折中（+9.64 SI-SDR / +0.601 PESQ）。**推荐作为主对比对象**。
**master64**：PESQ 最高（+0.963）但属 in-domain，**任何跨模型对比都必须并列 dns48/dns64 以暴露偏置**。
**共同缺点**：**CC-BY-NC 4.0 —— 禁止商用**。这是全项目最严的许可证，任何"产品化"表述都不能用这三个权重。

> ⚠️ `valentini_nc-93fc4337.th` 是官方提供的第 4 个 checkpoint（非因果、Valentini 训练），本项目**没有下载**。若论文要讨论"非因果上界"，这是缺失的一环。

---

## 7. Mel-RoFormer 家族（denoise ×2 / dereverb / dereverb-echo）

### 对比表

| 维度 | denoise（normal） | denoise（aggr） | dereverb（anvuew） | dereverb-echo（Sucial） |
|---|---|---|---|---|
| 官方指标 | MSST 表 denoise 行标 `---`（不给 SDR） | 同左 | MSST 表标 `---`；文件名 19.1729 未在文档中解释 | **SDR 10.01** |
| **本机实测**（Valentini 824，16 kHz） | ΔSI-SDR **+6.65** / ΔPESQ +0.239 | **+8.16** / **+0.256** | 负结果（去混响中位 +0.044） | — |
| 参数量 | 228.203 M | 228.203 M | 228.203 M | 208.88 M |
| 大小 | 913,097,300 B（871 MB） | 913,097,300 B（871 MB） | 913,107,578 B（871 MB） | 835,997,896 B（797 MB） |
| 本机时延(10 s) / RTF | 0.9802 s / 0.098 | 0.9732 s / 0.097 | 0.9809 s / 0.098 | 1.0182 s / 0.102 |
| 训练数据 | unverified | unverified | unverified | unverified |
| 许可证 | MSST 仓库 MIT；**训练者未单独声明权重许可** | 同左 | 同左（HF 仓库许可 unverified） | 同左 |
| 输出轨 | `enhanced` | `enhanced` | `dry` | **`dry` / `other`（2 stem，无 `enhanced`）** |

### 推荐

- **denoise 选 aggr**：全部 SNR 档位都优于 normal（ALL +8.16 vs +6.65 dB；<5 dB 档 +12.14 vs +8.60），代价是同样的 871 MB / RTF 0.097。官方清单把两者并列、**没有推荐标记**，所以这个结论来自本机实测而非官方背书。
- **dereverb / dereverb-echo**：各只有一个 ckpt，无选择空间。

### 优劣

**denoise-aggr**
- 优点：本机最强神经降噪器（+8.16 dB SI-SDR / +0.256 PESQ），44.1 kHz 立体声原生，不需降采样
- 缺点：871 MB / 228 M 参数，RTF 0.097（比 dns48 慢 11 倍）；**本机实测 PESQ 仍低于 dns48/dns64**（+0.256 vs +0.551/+0.601）——SI-SDR 与 PESQ 在这里不同向，必须分别报
- 适用：音乐域降噪（44.1 kHz）
- 不适用：语音 PESQ 优先、显存 <2 GB

**dereverb（anvuew）**
- 优点：唯一可用的去混响权重
- 缺点：**本机实测是负结果**（中位 +0.044）；文件名里的 19.1729 在官方文档中没有任何解释，不能当 SDR 引用
- 适用：仅作为"去混响未达标"的负面证据

**dereverb-echo（Sucial）**
- 优点：官方给了 SDR 10.01（唯一有明确数字的 Mel-RoFormer）
- 缺点：**2-stem 模型，键是 `dry`/`other`，没有 `enhanced`** —— 按 `enhanced` 取会直接失败，必须走兜底逻辑
- 适用：去回声场景

> ⚠️ **社区权重标注（强制）**：以上 4 个 Mel-RoFormer 权重**全部为社区训练**（aufr33 / anvuew / SUC-DriverOld），由 ZFTurbo 官方 release 或 HuggingFace 分发，**不是 Mel-Band RoFormer 论文作者的权重**。论文引用必须写"非官方权重，由 XXX 训练，经 ZFTurbo MSST 分发"。

---

## 8. 无 checkpoint 的模型（4 个）

| 模型 | 状态 | 证据 |
|---|---|---|
| **Oracle-IRM** | 无数重，解析计算（IRM/IBM） | `01_models/separation/README.md#Oracle-IRM`："权重：无（解析算法，零参数）" |
| **RPCA** | 无权重，迭代求解（Inexact-ALM） | 同上 #RPCA；输出"稀疏分量"**无天然 stem 归属** |
| **RPCA+DRNN** | 官方**从未公开代码或权重** | `MODEL_PROVISIONING_REPORT.md#3.2`；已降级为"相关工作" |
| **Pac-HuBERT-SEP** | MERL **未放出代码与权重** | `MODEL_REGISTRY.md#2.2` |

这 4 个不存在"选哪个 checkpoint"的问题。前两个是算法，后两个是**无法验证的空缺** —— 报告里必须写成"官方未公开"，不能写成"我们没找到"。

---

## 9. 跨模型横向提醒

1. **指标不可直接横比**：本文件里同时出现三种口径 ——
   - `Multisong Dataset`（MSST 表，mvsep 质检）→ BS-RoFormer / Mel-RoFormer 那一列
   - `MUSDB18-HQ test, chunk SDR`（1 s 窗中位 → 曲中位，museval）→ BSRNN
   - `MUSDB18 test, median-of-median SDR`（tky823 表）→ Conv-TasNet / MMDenseLSTM / UMX
   **同一个模型在不同口径下能差 2 dB 以上**（例：MMDenseLSTM 官方 5.58 vs 本机 3 片段 6.27）。跨行比较只能用同一列。
2. **本机实测一律是"3 个均衡片段 / 10 s"或"Valentini 824 条"**，与官方全测试集不同口径，不能混排。
3. **只有 Demucs 与 3 个 denoiser 的文件名自带 SHA256 前缀**，可与实算值自证（4/4 通过）。其余权重的完整性只能靠"大小 + 本次实算 hash"两者留档，**没有官方 hash 可比对**。

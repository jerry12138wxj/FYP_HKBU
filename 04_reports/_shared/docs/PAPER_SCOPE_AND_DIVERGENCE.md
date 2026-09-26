# 口径与差异说明（论文 T8.3 · 服务 D12 图包 / D13 答辩）

> **机器生成 · 禁止手改** ｜ 生成脚本 `tools/_build_paper_scope.py` ｜ 生成日期 `2026-09-26`
> 重建：`python tools/_build_paper_scope.py` ｜ 校验：`python tools/_build_paper_scope.py --verify`
> 用途（**T8.3 DoD**）：**挡掉「为什么和参考表不一样」的提问** —— 论文正文 / 答辩 / 复现者共用同一份口径声明。
> 除「参考表」列（外部提供，出处见 §6）外，本文件**全部数值由脚本从源产物读出或重算**。

## 0. 一句话（论文与口播可直接用）

> **中文**：本报告全部数值是**本机复现口径**下的实测结果，口径三要素（数据集 / 片段 / 指标定义）随每张图表声明；与参考表或原文数值的差异来自**实现版本、数据子集、评价口径**三处，已逐条登记并附复核命令 —— 我们选择**把差异写清楚**，而不是硬凑数字。

> **English**: Every figure and table reports a **locally reproduced** measurement with its three protocol elements (dataset / clip / metric definition) declared inline. Deviations from the reference table or the original papers are attributed to **implementation version, data subset, and evaluation protocol**, itemised in §2 and §3, and each is reproducible from the commands listed in §6.

---

## 1. 口径三要素（全局，按图组继承）

`53` 张论文图分属 9 个口径组；**图注必须连同本组的一行一起复制**，不得只抄标题句。

| 组 | 名称 | 板块 | 图数 | 数据集 | 片段 | 指标定义 |
|:---|:---|:---|---:|---|---|---|
| `G-ARCH` | 架构原理图 | 板 1 | 14 | N/A（结构示意，不含实验数据） | N/A | 框内 shape / 参数量取自 `graph_*.json` 溯源；成本口径见模型画像摘要 |
| `G-PROFILE` | 模型画像图 | 板 1 | 2 | 统一**合成**输入（不取自数据集） | 10 s / 44.1 kHz / 立体声 | 参数量 `sum(numel)`；FLOPs = 2×MACs **下界**；时延 5 次中位数 |
| `G-ACC` | 分离精度图 | 板 1 | 5 | MUSDB18-HQ **train** 抽段 | 3 首 × 10 s | `museval.metrics.bss_eval` SDR（窗 88200 / hop 66150，逐帧 nanmedian） |
| `G-COST` | 实机成本图 | 板 1 | 7 | MUSDB18-HQ **test** 50 首 | 整曲 | wall time / RTF / SDR 均值；**单轨模型（1:50）的 SDR 不可与四轨（4:50）直接比** |
| `G-SPEC` | 信号级频谱图 | 板 1 | 6 | MUSDB18-HQ train 抽段 | 见各图注（默认 10 s） | STFT 幅度（dB）；窗长对比图用 win 1024 vs 128 |
| `G-REV` | 混响 / 回声退化图 | 板 1 | 3 | MUSDB18-HQ train 抽段 + AIR/合成 RIR | 3 首 × 10 s | ΔSDR(dB) = 湿 − 干；**T60 为导出口径 44.1 kHz**（非源 48 kHz） |
| `G-DN` | 板 2 降噪结果图 | 板 2 | 13 | `valentini`（真实含噪，有 clean 参考）+ `synth`（干净语音 + 合成瞬态噪声） | 整条 utterance（valentini 824 条 / synth 800 条），16 kHz 口径 | SI-SDR(dB) / PESQ / STOI / LSD；`hf_ratio` = >4 kHz 能量占比 |
| `G-CAS` | 板 1×2 级联图 | 板 1 × 板 2 | 2 | MUSDB18-HQ test Top-10 曲 × DNS freesound 噪声池（逐声道独立加噪） | 10 曲 × 4 SNR × 20 s | ΔSDR(dB) = 该链路 − L0；GT = 干 stem；museval bss_eval（与板 1 主表同源） |
| `G-S4` | 阶段 4 一页汇总 | 板 1 | 1 | 同 G-REV（混响 + 回声两组实验汇总） | 3 首 × 10 s | ΔSDR(dB)；曲线为 6 模型均值，大厅档 `bsrnn_all` n=1 已标注不参与排名 |

> 本表由 `tools/_export_paper_figures.py` 的 `GROUPS` **直接继承**（同源），非重抄 —— 改口径只需改那一处。
>
> **「板块」列是主题归属，与 §4.1 的 `board` 计数口径不同**：级联 2 张主题跨两板、输出时编入板 2 目录（故 §4.1 记板 2 为 13 + 2 = 15 张）。两处都不是「数错了」。

---

## 2. 与参考表的差异说明（板 1 · 逐行核对）

下表「参考表」列来自用户提供的参考表（登记于 `FYP_ROADMAP_2026-09-22.md` §7、`MODEL_PROFILE_2026-09-22.md` §5，**本项目不重算**）；「本机」列由脚本从 `model_runs_median.json` / `model_profile.csv` **重算**，并逐格比对登记值。

| 差异项 | 参考表 | 本机（重算） | 差异主因（按贡献排序） | 核对 |
|:---|---:|---:|---|:---:|
| Demucs 参数量 | 128 M | 41.98 M | 参考表是 **原版 Demucs(v1)**，我们用的是 **HTDemucs** | ✅ |
| Demucs SDR | 6.03 dB | 8.11 dB | 口径不同：参考表为整曲、单模型对比池；**我们为 3 均衡片段中位数、12 模型池** | ✅ |
| DPRNN-TasNet | 6.01 dB | -1.72 dB | 我们的是**自训 5 h 权重**（官方只发语音权重），欠训练，非同一物 | ✅ |
| Conv-TasNet / MMDenseLSTM / Open-Unmix | 5.7 / 6.0 / 5.3 | 5.93 / 6.27 / 6.65 | 片段选择与评价口径不同（我们排除了"能量陷阱"片段） | ✅ |
| RPCA+DRNN | 5.80 dB | 无产出 | 论文未公开代码，无法复现（既有审计结论） | ✅ |


**三条通用差异（任何一行都可以归到这三条）**：

1. **子集不同** —— 本表 `train`（in-domain）/ 参考表 `test`；
2. **实现版本不同** —— HTDemucs ≠ 原版 Demucs(v1)；自训 DPRNN ≠ 官方权重；
3. **评价口径不同** —— mono、2 s 窗、3 个能量均衡片段的中位数 vs 参考表的整曲 / 其他池。

**✅ 核对结果**：参考表登记值与源数据**逐格一致**（容差 0.005），无 WARN。

---

## 3. 引用前必读：口径坑清单（三块看板合并）

共 **18** 条 = 板 1 **7** + 板 2 **6** + 级联 **5**（来源：`_build_dashboards.py` §6 / `_build_dashboards_t72.py` §8 / 同文件级联 §6；条数由脚本交叉计数，搬漏即 FAIL）。

### A · 指标定义（Metric semantics）（5 条）

| 坑 | 影响 | 引用时的一句话（可直接写进论文） | 来源 |
|:---|:---|:---|:---|
| 分析窗实际 **2 s / hop 1.5 s** | `evaluate()` 未传 `window`/`hop`，落到 museval 默认值；旧文档写「1 s 窗」**与实现不符**；实测 \|Δ\| 均值 0.267 dB | SDR 口径为 museval 签名默认窗（2 s 窗 / 1.5 s hop），非 1 s 窗；窗宽敏感性已量化为 \|Δ\| 均值 0.267 dB。 | 板 1 §6 |
| FLOPs = **下界** | `FlopCounterMode` 不计 `torch.stft` 与融合注意力；跨架构比较须配合实测时延 | FLOPs 为 2×MACs 下界（不含 STFT 与融合注意力），仅用于同架构量级比较。 | 板 1 §6 |
| **配对差 ≠ 中位数之差** | `*_improve` 列均为 med(out−in)；`med(out)−med(in)` 在非同分布时会**反号** | 所有改善量按逐条配对差取中位（med(out−in)），不是两个中位数相减。 | 板 2 §8 |
| PESQ 只支持 16 kHz | 非 16 kHz 一律不报（`pesq_applicable=false`），**不得当 0 用** | PESQ/STOI 定义域为 8/16 kHz；44.1 kHz 口径下为空是设计，不是缺测。 | 板 2 §8 |
| 采样率契约固定 `44.1k→16k→mono→44.1k` | `denoiser` 内部往返重采样；**引用 `hf_ratio` 必须注明口径**（16 kHz ≈0.207 / 44.1 kHz ≈0.035） | 报告任何 `hf_ratio` 必须注明口径；44.1 kHz 契约率含 denoiser 内部重采样代价。 | 板 2 §8 |


### B · 数据与子集（Data & subset）（6 条）

| 坑 | 影响 | 引用时的一句话（可直接写进论文） | 来源 |
|:---|:---|:---|:---|
| 主表子集 = MUSDB18-HQ `train` | in-domain，数字系统性偏乐观；与参考表（`test`）**不可逐格对齐** | 本表为同任务、同数据集族的**本机复现口径**，子集为 train（in-domain），非参考表的 test 口径。 | 板 1 §6 |
| 单轨模型不可与四轨 `avg4` 同轴 | BS-RoFormer / BSRNN-opt 只产 1~2 条轨，其 SDR 只覆盖目标轨 | `轨数` 列区分 `1:50` / `4:50`；两类 SDR 不在同一条轴上，禁止直接排名。 | 板 1 §6 |
| `dns_dev` 无 clean GT（`reference_mode=noref`） | fullref 列为 `null`，**不得当 0 用**；该集只能报电平行为量 | dns_dev 为无参考集，只报电平/频谱行为量，不报 SI-SDR / PESQ。 | 板 2 §8 |
| 分档键**同名不同义** | 真实集按**输入 SI-SDR 事后分档**；synth 按**真值 SNR**（−5/0→<5 dB，5/10→5–15 dB） | 分层键：真实集用事后输入 SI-SDR 分档，synth 用真值 SNR；跨集比较须先对齐键的语义。 | 板 2 §8 |
| 片段 >30 s 统一跳过 | dns_dev 867/921 —— **可比性优先于覆盖率**，各模型看同一批片段 | 所有模型在同一批片段上评比；超长片段统一跳过以保证配对比，代价是覆盖率。 | 板 2 §8 |
| 片段 **20 s**（非整曲） | 与 T4/T5 口径一致、匹配 museval 2 s 窗；与 §4 副表的整曲口径**不是一条轴** | 级联矩阵为 10 s/20 s 片段口径，与副表 test 集 50 首整曲不可混列。 | 级联 §6 |


### C · 实现与运行环境（Implementation & environment）（5 条）

| 坑 | 影响 | 引用时的一句话（可直接写进论文） | 来源 |
|:---|:---|:---|:---|
| RTF 受机器负载影响 | 同一模型两次可差 2×；只做量级参考，**排名请用整曲墙钟** | RTF 为单卡（RTX 4070 Laptop 8 GiB）实测、受负载影响，排名以整曲墙钟为准。 | 板 1 §6 |
| 音频必须 32-bit float WAV | 噪声脉冲性强，按功率匹配 SNR 后峰值冲高 → 写 PCM_16 会**静默削波** 30/40 格；但峰值大**不伤模型**（wrapper 按输入自身 mean/std 归一化再还原） | 级联实验全程 32-bit float 存储；峰值超 1.0 不影响模型（内部按输入统计量归一化）。 | 级联 §6 |
| 门禁判据 = **float32 重建逐位相同** | 拿 float32 存储值比 float64 精确和 → 纯量化（0.55 ulp）会被误判 FAIL | G2 门禁判据为 float32 位级重建一致性，而非 float64 数值相等。 | 级联 §6 |
| 计划书写的「BSRNN-opt」实为人声单轨（违反 R10） | 已改用 **`bsrnn_all`**（oBSRNN 4 ckpt 四轨）→ 文档与实现一度不一致，属**已修正的偏离** | 级联链路中的 BSRNN 指 `bsrnn_all`（oBSRNN 四轨），非人声单轨的 BSRNN-opt。 | 级联 §6 |
| 沙箱**无法创建脱离进程** | `nohup &` / `cmd start` 被拒，后台任务随会话结束被杀 → 主跑改用**逐格 JSONL 增量落盘 + resume** | 长跑任务采用逐格 JSONL 增量落盘，中断可幂等续跑（全格结果可逐格追溯）。 | 级联 §6 |


### D · 局限与负结果（Limits & negative results）（2 条）

| 坑 | 影响 | 引用时的一句话（可直接写进论文） | 来源 |
|:---|:---|:---|:---|
| DPRNN 是**自训 5 h** 的负面对照 | 官方只发语音权重，本机无法复现论文值 → 其 −1.72 dB 不构成对论文的否定 | DPRNN 为本机自训 5 h 的欠训练对照，非官方权重，其数字不可与论文值等同看待。 | 板 1 §6 |
| RPCA 不出四轨均值 | 稀疏分量无天然 stem 归属，只能报区间；**不进主表排名** | RPCA 属解析方法，无 stem 归属，只报区间与耗时，不参与 SDR 排名。 | 板 1 §6 |


---

## 4. 已知取舍与缺口（照报，不美化）

### 4.1 图纸产出

- 成品图 **53 张**（板 1 38 / 板 2 15），目标 **300 dpi**；判据按**印刷宽度**定义 —— 单栏 3.35 in = **1005 px**、双栏 7.00 in = **2100 px**。
- **单栏达标 53/53（缺口 0）**；其中 **41 张**同时满足双栏宽度，其余 12 张**按单栏排版使用**。

| 实际 dpi | 张数 | 占比 |
|:---|---:|---:|
| 300 dpi | 31 | 58% |
| 150 dpi | 14 | 26% |
| 140 dpi | 8 | 15% |

> **低于 300 dpi 的图不是漏渲染**：其绘图脚本内 `savefig(dpi=...)` 写死，或属「不重跑」组（含 torch 推理，重跑会改写已归档数据）。它们**均满足单栏 300 dpi 等效宽度**，按**单栏**排版使用。

**「不重跑」清单（10 张 / 4 个脚本）** —— 复现命令栏不能骗人，故如实标缺口：

| 脚本 | 图数 |
|:---|---:|
| `_plot_denoise_spectral.py` | 4 |
| `_plot_denoise_spectrum_delta.py` | 4 |
| `compare_separation_methods.py` | 1 |
| `_denoise_diagnosis.py` | 1 |


### 4.2 实验口径上的取舍

| # | 取舍 | 处置（已在报告中显式声明） |
|:---|:---|:---|
| 1 | 主表跑在 `train` 子集（in-domain，偏乐观） | 副表另给 `test` 集 50 首整曲口径（只看耗时与规模），两表**不混列** |
| 2 | 分析窗落到 museval 默认 **2 s / hop 1.5 s**（文档曾写 1 s） | 已量化为 \|Δ\| 均值 0.267 dB；对齐其他论文需补 `window`/`hop` 后整表重跑 |
| 3 | BSRNN-SIMO 只跑 **14/50** 首（截断） | 报告中显式标注截断；四轨最优结论以 MDX-Net 为可用代表 |
| 4 | RPCA 无四轨产出 | 只报区间与耗时，不进排名（见 §3 · D 类） |
| 5 | 降噪**域外探针为负结果**（mel 对纯噪声近不抑制） | 按「互补失效」正面报告：两个模型族**有效域不同** |
| 6 | 级联**前置降噪为负结果** | 照报：带宽代价与净动作已分解，见 §5 Q3 |
| 7 | 门禁首轮 35 格 FAIL 系**语义误判**（非信号损坏） | 免重跑重判（`tools/_cascade_regate.py`）→ 全格 PASS；判据见 §5 Q3 |


### 4.3 规模与计数（可对账）

| 项 | 值 | 来源 |
|:---|---:|---|
| 降噪评测 cells | 16575 | `denoiser/data/denoise_manifest.json` |
| 降噪口径 A（44.1 kHz 契约率）行数 | 20 | `denoise_eval_44k.json` |
| 降噪口径 B（16 kHz）行数 | 40 | `denoise_eval_16k.json` |
| 级联门禁 | 90/90 PASS | `cascade_manifest.json` |
| 级联分离格 | 680/680 PASS | `cascade_eval.json` |
| 级联后置格 | 640 | `cascade_eval.json` |
| 门禁重判改动格数 | 35 | `cascade_eval.json` · regate |
| `hf_ratio_out`（16 kHz / 44.1 kHz，`denoiser_master64` · valentini · ALL） | 0.2088 / 0.0345 | `denoise_eval_16k.json` / `_44k.json` |

---

## 5. 答辩速答卡（Q → A）

**Q1. Demucs 本机 8.11 dB，参考表 6.03 dB —— 是不是做错了？**

→ 不是同一物：参考表是**原版 Demucs (v1)**，本机是 **HTDemucs**；且本表为 `train` 子集、3 个能量均衡片段的中位数。三条通用差异见 §2 —— 差异已写明，不硬凑。

**Q2. 降噪表里 PESQ / STOI 有的是空的？**

→ **PESQ 的定义域只有 8/16 kHz**，44.1 kHz 口径下不报是设计（`pesq_applicable=false`），**不能当 0 用**（§3 · A 类）。

**Q3. 前置降噪反而让 SDR 中位下降 3.99 dB，这是 bug 吗？**

→ 是**真实负结果**，且已做对照臂拆解：L1 前置降噪中位 ΔSDR **-3.993**，其中**仅限带代价** L1b **-0.894**，**净降噪动作 -3.214（占 80%）**（均读自 `cascade_eval.json` · `matrix.summary_all_cells`）；机理是降噪后 `V1den` 的 drums/bass/other 电平塌到 0.006~0.062（转录自 `docs/T6_CASCADE_DENOISE_BEFORE_SEPARATION.md` §机理），分离器**退化为恒等映射** —— 属**任务错配**。门禁 90/90 PASS、锚点 40/40 PASS、分离格 680/680。

**Q4. 为什么用 20 s 片段而不是整曲？**

→ 为匹配 museval 的 2 s 分析窗，并与 T4/T5 保持同一口径（**可比性优先于覆盖率**）；整曲口径另见 §4 副表，两表不混列（§3 · B 类）。

**Q5. FLOPs 和论文里的对不上？**

→ 本机 FLOPs = **2×MACs 下界**（`FlopCounterMode` 不计 `torch.stft` 与融合注意力），跨架构比较必须配合实测时延；同架构内排序仍有效（§3 · A 类）。

**Q6. 为什么有些图不是 300 dpi？**

→ 那 10 张属「不重跑」组（含 torch 推理）或脚本写死 dpi；它们**均满足单栏 300 dpi 等效宽度**，按单栏排版使用。清单与原因逐张登记（§4.1），未美化。

**Q7. 主表用 train 子集，是不是在作弊？**

→ **是 in-domain 口径，已主动交代**（§2 第 1 行 + §4.2 第 1 行）：它测的是「模型能否复现其训练分布」，测的不是泛化；泛化证据另由 `test` 集副表与 dns_dev 外部集给出。

---

## 6. 数字溯源（引用任何数字前，先看它在哪个文件）

| 数字 / 结论 | 源文件 | 生成工具 |
|:---|:---|:---|
| 分离主表（Average SDR 等） | `separation/data/comparison/model_runs_median.json` | `tools/bench_multisong.py` + `median_over_clips.py` |
| 参考表登记值 | `FYP_ROADMAP_2026-09-22.md` §7、`MODEL_PROFILE_2026-09-22.md` §5 | （外部提供，不重算） |
| 模型画像（参数量 / FLOPs / 时延） | `_shared/data/model_analysis/model_profile.csv` | `tools/_measure_model_profile.py` |
| 降噪评测（双口径） | `denoiser/data/denoise_eval_16k.json` / `_44k.json` | `tools/_denoise_eval.py` |
| dry/wet 旋钮 | `denoiser/data/denoise_drywet.json` | `tools/_denoise_drywet.py` |
| 域外探针 | `denoiser/data/denoise_ood_probe.json` | `tools/_denoise_ood_probe.py` |
| 级联矩阵 / 门禁 | `cascade/data/cascade_eval.json` / `cascade_manifest.json` | `tools/_cascade_experiment.py` |
| 门禁重判 | `cascade/data/cascade_eval.json` · regate | `tools/_cascade_regate.py` |
| 论文图清单（像素 / dpi / 复现脚本） | `_shared/figures/paper/paper_figures_manifest.json` | `tools/_export_paper_figures.py` |
| 四份数据摘要 | `_shared/docs/summaries/*.md` | `tools/_build_summaries.py` |
| 口径三要素（本文件 §1） | `tools/_export_paper_figures.py` · `GROUPS` | （继承，非重抄） |

> **解释器**：全部脚本须用 venv —— `C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe`


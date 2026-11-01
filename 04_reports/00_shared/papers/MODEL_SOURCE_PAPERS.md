# 模型来源论文 · 原文摘抄 · 原理图例

> 生成：2026-10-18 ｜ 覆盖：**18 个模型条目 → 14 个架构 → 12 篇论文**
> 全部 PDF 已落地 `04_reports/00_shared/papers/pdf/`；摘抄**逐字取自 PDF 文本层**（不是凭记忆转述），
> 图例按图注从 PDF **原图裁出**（`figs/`，300 dpi），未重绘、未臆造。
> 核对方式：`pdf/<模型名>.txt` 里 `Ctrl+F` 搜任意一句即可定位页码。

---

## 0. 口径与使用说明

| 项 | 规则 |
|---|---|
| 模型清单来源 | `01_models/MODEL_REGISTRY.md` + `01_models/separation/README.md` + `01_models/denoising/README.md` |
| 「原文摘抄」 | 英文原样，**保留原文拼写错误**（如 BSRNN 的 `explictly`、Mel-RoFormer 的 `In contract`），标 `[sic]` |
| 「原理图例」 | 按图注裁出的论文插图，标注 Figure 号与页码；`figs/` 下可直接嵌进论文 |
| 无图例的条目 | RPCA、Oracle-IRM、Open-Unmix —— 论文本身没有架构图，给 AI 生图提示词（§3） |
| 同篇多条目 | BSRNN ×3、BS-RoFormer ×2、Mel-RoFormer ×3 共用同一篇论文，不重复摘抄 |

> ⚠️ **引用前必读**：§2.4 列出 `MODEL_REGISTRY.md` 里 **5 处作者/出处登记错误**（已按 PDF 首页核对）。
> 论文正文引用请以本文件的作者名为准，并顺手把登记表改掉。
>
> **出处口径**：会议/期刊名以 arXiv 元数据 `comment`/`journal_ref` 与 PDF 首页为准；
> 元数据没有标注的（MMDenseLSTM、BSRNN）沿用项目登记，已在对应条目里打 ⚠ 标记。

---

## 1. 列表：模型 → 论文 → 原文摘抄 → 图例

### 1.1 Conv-TasNet（时域掩码开山）

| 项 | 内容 |
|---|---|
| 论文 | *Conv-TasNet: Surpassing Ideal Time–Frequency Magnitude Masking for Speech Separation* |
| 作者 | Yi Luo, Nima Mesgarani |
| 出处 | IEEE/ACM TASLP 27(8), 2019 ｜ **arXiv:1809.07454** |
| 本机条目 | `convtasnet`（13.395 M，四轨 5.93 dB） |
| 图例 | `figs/fig01_convtasnet.png`（原文 **Fig. 1**, p.3） |

**原文摘抄（Abstract）**

> "To address these shortcomings, we propose a fully-convolutional time-domain audio separation network (Conv-TasNet), a deep learning framework for end-to-end time-domain speech separation. Conv-TasNet uses a linear encoder to generate a representation of the speech waveform optimized for separating individual speakers. Speaker separation is achieved by applying a set of weighting functions (masks) to the encoder output."

> "The masks are found using a temporal convolutional network (TCN) consisting of stacked 1-D dilated convolutional blocks, which allows the network to model the long-term dependencies of the speech signal while maintaining a small model size."

---

### 1.2 DPRNN（长序列的 dual-path 解法）

| 项 | 内容 |
|---|---|
| 论文 | *Dual-Path RNN: Efficient Long Sequence Modeling for Time-Domain Single-Channel Speech Separation* |
| 作者 | Yi Luo, Zhuo Chen, **Takuya Yoshioka** |
| 出处 | ICASSP 2020 ｜ **arXiv:1910.06379** |
| 本机条目 | `dprnn`（3.686 M，**自训**，四轨 −1.72 dB，不参与排名） |
| 图例 | `figs/fig02_dprnn.png`（原文 **Fig. 1**, p.3） |

**原文摘抄（Abstract）**

> "In this paper, we propose dual-path recurrent neural network (DPRNN), a simple yet effective method for organizing RNN layers in a deep structure to model extremely long sequences. DPRNN splits the long sequential input into smaller chunks and applies intra- and inter-chunk operations iteratively, where the input length can be made proportional to the square root of the original sequence length in each operation."

---

### 1.3 MMDenseLSTM（多尺度卷积 + 多尺度 LSTM）

| 项 | 内容 |
|---|---|
| 论文 | *MMDenseLSTM: An Efficient Combination of Convolutional and Recurrent Neural Networks for Audio Source Separation* |
| 作者 | Naoya Takahashi, **Nabarun Goswami**, Yuki Mitsufuji |
| 出处 | IWAENC 2018 ｜ **arXiv:1805.02410**（⚠ arXiv 元数据未标会议，投稿前核实一次） |
| 本机条目 | `mmdenselstm`（5.487 M，四轨 6.27 dB） |
| 图例 | `figs/fig03_mmdenselstm.png`（原文 **Fig. 3**, p.3） |

**原文摘抄（Abstract）**

> "It was recently reported that a variant of CNN architecture called MMDenseNet was successfully employed to solve the ASS problem of estimating source amplitudes, and state-of-the-art results were obtained for DSD100 dataset. To further enhance MMDenseNet, here we propose a novel architecture that integrates long short-term memory (LSTM) in multiple scales with skip connections to efficiently model long-term structures within an audio context."

> "The number of parameters and processing time of the proposed model are significantly less than those for simple blending."

---

### 1.4 Open-Unmix（参考实现基线）

| 项 | 内容 |
|---|---|
| 论文 | *Open-Unmix - A Reference Implementation for Music Source Separation* |
| 作者 | Fabian-Robert Stöter, Stefan Uhlich, Antoine Liutkus, Yuki Mitsufuji |
| 出处 | JOSS 4(41):1667, 2019 ｜ **DOI 10.21105/joss.01667**（非 arXiv，已下载 `pdf/Open-Unmix.pdf`） |
| 本机条目 | `umx`（35.577 M，四轨 6.65 dB） |
| 图例 | **无架构图**（该文 Fig. 1 是 SDR 箱线图）→ 见 §3.3 提示词 |

**原文摘抄（Summary）**

> "Music source separation is the task of decomposing music into its constitutive components, e.g., yielding separated stems for the vocals, bass, and drums."

> "However, until now, no open-source implementation that achieves state-of-the-art results is available. Open-Unmix closes this gap by providing a reference implementation based on deep neural networks."

> ⚠️ JOSS 是**软件论文**，不含网络结构细节。写论文时若要描述 UMX 的「每目标一套 3 层 BiLSTM + FC + sigmoid 掩码 + Wiener 重建」，须引 UMX 官方文档/代码（`01_models/_third_party/DNN-based_source_separation`），不能挂在这篇 JOSS 上。

---

### 1.5 Demucs / htdemucs（时频双 U-Net + 跨域 Transformer）

| 项 | 内容 |
|---|---|
| 论文 | *Hybrid Transformers for Music Source Separation* |
| 作者 | Simon Rouard, Francisco Massa, Alexandre Défossez |
| 出处 | ICASSP 2023 ｜ **arXiv:2211.08553** |
| 本机条目 | `demucs`（41.984 M，四轨 8.11 dB，GPU RTF 0.03 全场最快） |
| 图例 | `figs/fig04_htdemucs.png`（原文 **Fig. 1**, p.3，含 (a)(b)(c)） |

**原文摘抄（Abstract）**

> "In this work, we introduce Hybrid Transformer Demucs (HT Demucs), an hybrid temporal/spectral bi-U-Net based on Hybrid Demucs [2], where the innermost layers are replaced by a cross-domain Transformer Encoder, using self-attention within one domain, and cross-attention across domains."

> "Using sparse attention kernels to extend its receptive field, and per source fine-tuning, we achieve state-of-the-art results on MUSDB with extra training data, with 9.20 dB of SDR."

---

### 1.6 MDX-Net / KUIELab-MDX-Net（时域 + 频域双流集成）

| 项 | 内容 |
|---|---|
| 论文 | *KUIELab-MDX-Net: A Two-Stream Neural Network for Music Demixing* |
| 作者 | Minseok Kim, Woosung Choi, Jaehwa Chung, Daewon Lee, Soonyoung Jung |
| 出处 | MDX Workshop @ ISMIR 2021 ｜ **arXiv:2111.12203** |
| 本机条目 | `mdx`（334.544 M，四轨 8.96 dB；mdx_extra = 4 个 submission 权重） |
| 图例 | `figs/fig05_mdxnet.png`（原文 **Fig. 2**, p.3） |

**原文摘抄（Summary）**

> "This paper proposes a two-stream neural network for music demixing, called KUIELab-MDX-Net, which shows a good balance of performance and required resources. The proposed model has a time-frequency branch and a time-domain branch, where each branch separates stems, respectively. It blends results from two streams to generate the final estimation."

> "KUIELab-MDX-Net took second place on leaderboard A and third place on leaderboard B in the Music Demixing Challenge at ISMIR 2021."

---

### 1.7 BSRNN（band-split 系列起点）— 对应 `bsrnn` / `bsrnn_large` / `bsrnn_simo`

| 项 | 内容 |
|---|---|
| 论文 | *Music Source Separation with Band-split RNN* |
| 作者 | Yi Luo, Jianwei Yu |
| 出处 | IEEE/ACM TASLP 2023 ｜ **arXiv:2209.15174** |
| 本机条目 | `bsrnn`(40.777 M) / `bsrnn_all` / `bsrnn_large` / `bsrnn_simo`（9.16 / 8.42 / **9.27** dB） |
| 图例 | `figs/fig06_bsrnn.png`（原文 **Fig. 1**, p.3，含 (A)(B)(C)(D)） |

**原文摘抄（Abstract）**

> "In this paper, we propose band-split RNN (BSRNN), a frequency-domain model that explictly [sic] splits the spectrogram of the mixture into subbands and perform interleaved band-level and sequence-level modeling."

> "The choices of the bandwidths of the subbands can be determined by a priori knowledge or expert knowledge on the characteristics of the target source in order to optimize the performance on a certain type of target musical instrument."

---

### 1.8 BS-RoFormer（band-split + 层次 Transformer + RoPE）— 对应 L12 / L6

| 项 | 内容 |
|---|---|
| 论文 | *Music Source Separation with Band-Split RoPE Transformer* |
| 作者 | Wei-Tsung Lu, Ju-Chiang Wang, **Qiuqiang Kong, Yun-Ning Hung** |
| 出处 | arXiv 2023（**arXiv:2309.02612**）；投稿 SDX'23 MSS 赛道并获第一名 |
| 本机条目 | `bsroformer_l12`（159.758 M，vocals 9.69）/ `bsroformer_l6`（98.195 M，vocals+other 10.06） |
| 图例 | `figs/fig07_bsroformer.png`（原文 **Fig. 1**, p.2） |

**原文摘抄（Abstract）**

> "BS-RoFormer relies on a band-split module to project the input complex spectrogram into subband-level representations, and then arranges a stack of hierarchical Transformers to model the inner-band as well as inter-band sequences for multi-band mask estimation. To facilitate training the model for MSS, we propose to use the Rotary Position Embedding (RoPE)."

> "Benchmarking a smaller version of BS-RoFormer on MUSDB18HQ, we achieve state-of-the-art result without extra training data, with 9.80 dB of average SDR."

---

### 1.9 Mel-RoFormer（把 band-split 换成 mel 投影）— 对应 Denoise / Dereverb / Dereverb-Echo

| 项 | 内容 |
|---|---|
| 论文 | *Mel-Band RoFormer for Music Source Separation* |
| 作者 | **Ju-Chiang Wang**, Wei-Tsung Lu, Minz Won |
| 出处 | ISMIR 2023 LBD/demo ｜ **arXiv:2310.01809** |
| 本机条目 | `mel_roformer_denoise` / `_aggr`（aufr33）、`mel_roformer_dereverb`（anvuew）、`mel_roformer_dereverb_echo`（Sucial）— **均为社区权重，非论文官方** |
| 图例 | `figs/fig08_melroformer_melband.png`（原文 **Fig. 1**, p.2，mel 频带映射）<br>⚠️ 该文**只有这一张原理图**，没有整体架构图（架构沿用前作 BS-RoFormer）→ 需要整图时用 `fig07` 并注明 |

**原文摘抄（Abstract）**

> "This model has achieved state-of-the-art performance, but the band-split scheme is defined empirically, without analytic supports from the literature. In this paper, we propose Mel-RoFormer, which adopts the Mel-band scheme that maps the frequency bins into overlapped subbands according to the mel scale."

> "In contract [sic], the band-split mapping in BSRNN and BS-RoFormer is non-overlapping and designed based on heuristics. Using the MUSDB18HQ dataset for experiments, we demonstrate that Mel-RoFormer outperforms BS-RoFormer in the separation tasks of vocals, drums, and other stems."

---

### 1.10 Denoiser / Demucs-Denoiser（语音降噪，实时波形域）— 对应 dns48 / dns64 / master64

| 项 | 内容 |
|---|---|
| 论文 | *Real Time Speech Enhancement in the Waveform Domain* |
| 作者 | Alexandre Défossez, Gabriel Synnaeve, Yossi Adi |
| 出处 | Interspeech 2020 ｜ **arXiv:2006.12847** |
| 本机条目 | `denoiser_dns48`(18.868 M) / `denoiser_dns64`(33.534 M) / `denoiser_master64`(33.534 M)，16 kHz 单通道 |
| 图例 | `figs/fig09_denoiser.png`（原文 **Fig. 1**, p.2，(a) U-Net 总览 + (b) 编解码层细节） |

**原文摘抄（Abstract）**

> "We present a causal speech enhancement model working on the raw waveform that runs in real-time on a laptop CPU. The proposed model is based on an encoder-decoder architecture with skip-connections. It is optimized on both time and frequency domains, using multiple loss functions."

> "Empirical evidence shows that it is capable of removing various kinds of background noise including stationary and non-stationary noises, as well as room reverb."

---

### 1.11 Oracle-IRM（理论天花板，不是模型）

| 项 | 内容 |
|---|---|
| 出处 | 实现：`01_models/_third_party/sigsep-mus-oracle`；数据集：Rafii, Liutkus, Stöter, Mimilakis, Bittner, *MUSDB18*, 2017（DOI 10.5281/zenodo.1117372）；IRM 定义：Wang & Wang, IEEE/ACM TASLP 2014 |
| 本机条目 | `oracle`（0 参数，四轨 8.30 dB，理论上界） |
| 图例 | **无数值/架构图**（解析算法）→ 见 §3.2 提示词 |

**原理（无公开 PDF 可摘）**：理想比值掩码直接由 ground-truth 分量算得

$$ \mathrm{IRM}_i(f,t)=\frac{|S_i(f,t)|}{\sum_j |S_j(f,t)|},\qquad \hat{S}_i=\mathrm{IRM}_i \odot |X| $$

> ⚠️ **本条目没有原文摘抄**：Wang & Wang 2014 在 IEEE 付费墙内，本地无合法 PDF。
> 论文里引用时请写「定义见 Wang & Wang (2014)，本实现复用 sigsep 官方 oracle 代码」，**不要**套用别处的句子。

---

### 1.12 RPCA（低秩 + 稀疏分解）

| 项 | 内容 |
|---|---|
| 论文 | *Robust Principal Component Analysis?* |
| 作者 | Emmanuel J. Candès, Xiaodong Li, Yi Ma, John Wright |
| 出处 | J. ACM 58(3), 2011 ｜ **arXiv:0912.3599** |
| 本机条目 | `rpca`（0 参数，单次 10 s 需 82.5 s） |
| 图例 | **无架构图**（该文 Fig. 1 是相变图，Fig. 2-4 是视频/人脸实验）→ 见 §3.1 提示词 |

**原文摘抄（Abstract）**

> "Suppose we have a data matrix, which is the superposition of a low-rank component and a sparse component. Can we recover each component individually? We prove that under some suitable assumptions, it is possible to recover both the low-rank and the sparse components exactly by solving a very convenient convex program called Principal Component Pursuit; among all feasible decompositions, simply minimize a weighted combination of the nuclear norm and of the ℓ1 norm."

> ⚠️ 项目登记表还引了 Huang et al., ICASSP 2012（RPCA 用于歌声分离）与 Lin et al. 2010（ALM 求解器）。
> 这两篇未取得 PDF，**未做摘抄**；本文件引用的是 PCP 的数学出处（Candès 等）。

---

## 2. 读后总结

### 2.1 一句话谱系

```
            ┌── 时域 ────────── Conv-TasNet (2019) ──▶ DPRNN (2020)
  输入混合 ─┤
            ├── 频域 ────────── MMDenseLSTM (2018) ──▶ Open-Unmix (2019)
            │                        └──▶ BSRNN (2022) ──▶ BS-RoFormer (2023) ──▶ Mel-RoFormer (2023)
            │                                              ▲ band-split 前端 + 层次 Transformer + RoPE
            ├── 混合/集成 ──── Demucs htdemucs (2023)
            │                  MDX-Net (2021, 时域+频域双流 + mixer 融合)
            └── 解析基线 ────── RPCA / IRM-Oracle（零参数，划上下界）
```

**主线就一条**：*把「频谱切成合理的子带」比「换更大的网络」更值钱*。BSRNN 用经验固定子带 → BS-RoFormer 换成层次 Transformer + RoPE → Mel-RoFormer 把子带换成 mel 尺度，三代人只改这一处，SDR 从 9.16 走到 9.80。本项目实测精度前三（9.27 / 9.16 / 8.96）也正好落在这一支上。

### 2.2 逐个总结

| 模型 | 读后判断（本质 + 代价） |
|---|---|
| **Conv-TasNet** | 用可学习 1-D 卷积编码器替代 STFT，TCN（堆叠膨胀深度可分离卷积）估掩码，线性解码回波形。真正贡献是**把相位重建从问题里摘出去**；代价是编码器基函数不可解释、对采样率敏感。 |
| **DPRNN** | 把长序列切块，块内 BiRNN + 块间 BiRNN 交替，单次操作长度从 N 降到 √N。是注意力之前最优雅的长序列解法；但**串行 RNN 的并行度差**，训练慢——这正是本项目 8 GiB 单卡只能到 −1.72 dB 的根因。 |
| **MMDenseLSTM** | 多尺度 DenseNet 抓局部纹理、LSTM 抓跨帧依赖、U 形 skip 拼回。5.49 M 参数做到 6.27 dB，**参数效率最高**；但层深且串行，时延反而比同量级模型高。 |
| **Open-Unmix** | 每个 stem 一套独立网络（3 层 BiLSTM + FC + sigmoid）在幅度谱上出掩码，Wiener 滤波重建。**价值在「可复现的参考实现」，不在精度**；它的存在让后来所有模型有了统一的对照锚点。 |
| **Demucs htdemucs** | 时域、频域两条 bi-U-Net 并行，最内层换成跨域 Transformer（域内 self-attn、跨域 cross-attn）。41.98 M 单模型直接出 4 stem、GPU RTF 0.03，**工程性价比第一**；弱项是 `other`（5.49 dB）。 |
| **MDX-Net** | 时域流（Demucs）+ 频域流（TFC-TDF-U-Net）分别出 stem，再 mixer 融合。论文本身是个「资源友好」方案，**本机 8.96 dB 有相当部分来自 4 个 submission 权重的集成**，单模型横比时必须说明。 |
| **BSRNN** | 按先验带宽切子带，交错做帧方向 / band 方向 RNN，band merge 出掩码。**子带边界是手工 heuristic**，这是它唯一的软肋，也直接催生了后两篇。 |
| **BS-RoFormer** | 沿用 band-split 前端，序列建模换成 inner-band / inter-band 两级 Transformer，RoPE 编码位置。人声 9.69 dB 全场最高，**但 FLOPs 43,480 G 也是全场最高**——CPU RTF 10.97 完全不可实时，靠 GPU 才降到 0.49。 |
| **Mel-RoFormer** | 唯一改动：把「非重叠经验子带」换成「按 mel 尺度重叠投影」，低频密高频疏，贴合听觉分辨率。作者自证 vocals/drums/other 优于 BS-RoFormer。**注意本机三个变体全是社区权重**，只能证明「这个架构能降噪/去混响」，不能当作论文复现成绩。 |
| **Denoiser** | 波形域**因果** U-Net + skip，多分辨率 STFT 损失 + 时域 L1，专为笔记本 CPU 实时设计。18.87 M 的 dns48 在本项目门禁 SI-SDR 改善最高（+2.15 dB）——**小而专，胜过通用大模型**。 |
| **Oracle-IRM** | 用 ground-truth 算理想比值掩码，给所有模型划天花板（8.30 dB）。它证明：本项目最好的模型（9.27）**已经越过 IRM 上界**，说明「幅度掩码」本身不是瓶颈，相位与其它表示还有空间。 |
| **RPCA** | 幅度谱 = 低秩（伴奏重复结构）+ 稀疏（人声），PCP 凸松弛（核范数 + ℓ1）用 ALM 迭代求解。零训练、零参数、可解释；但 10 s 要 82.5 s，**慢三个数量级**，且稀疏分量没有天然 stem 归属。 |

### 2.3 对本项目的 5 条直接结论

1. **精度排序与谱系完全吻合**：band-split+Transformer（9.27 / 9.16）> 混合域集成（8.96 / 8.11）> 纯频域（6.65 / 6.27）> 纯时域（5.93）。写论文时这条「架构代际」比逐个报数字更有说服力。
2. **「能不能实时」是实现问题，不是架构属性**。BS-RoFormer L12 在 CPU 上 RTF 10.97（离线），装 CUDA 后 0.49（实时）——**22 倍**。论文里的 FLOPs 不能直接推实时性，必须附硬件。
3. **参数 ≠ 精度 ≠ 速度**。MMDenseLSTM 5.49 M 拿 6.27；MDX-Net 334 M 拿 8.96（还含集成）；Demucs 41.98 M 拿 8.11 且最快。三者不能用一个「模型大小」轴解释。
4. **DPRNN 的负分要归因到预算，不是架构**。原文在 WSJ0-2mix 上用 1/20 的模型即 SOTA；本项目 8 GiB + 5 h 只到 −1.72 dB。引用时必须写「自训、欠训练、不参与排名」，否则是错误结论。
5. **两块板不能混谈**。Denoiser 是 16 kHz 单通道**语音**模型，Mel-RoFormer 是 44.1 kHz 立体声**音乐**模型；且 `master64` 训练集含 Valentini → 测 Valentini 属 in-domain，必须同时报 dns48/dns64 对照。

### 2.4 论文登记表纠错（按 PDF 首页核对）

| 模型 | `MODEL_REGISTRY.md` / 模型卡写的 | 论文实际 | 建议 |
|---|---|---|---|
| MMDenseLSTM | Takahashi, Matsubara, Uehara. IEEE SPL 27, 2020 | **Takahashi, Goswami, Mitsufuji. IWAENC 2018**（arXiv:1805.02410） | 🔴 出处整条错，须改 |
| DPRNN | Luo, Chen, **Mesgarani** | Luo, Chen, **Yoshioka** | 🟠 第三作者错 |
| BS-RoFormer | Lu, Wang, **Jiang, Zhang** | Lu, Wang, **Kong, Hung** | 🟠 后两位错 |
| Mel-RoFormer | **Lu** et al. | **Wang**, Lu, Won | 🟠 首作者错 |
| Denoiser | 只写标题，无编号 | **arXiv:2006.12847** | 🟡 补编号 |
| Oracle-IRM | Wang & Wang, TASLP 2014 | 未取得原文（付费墙） | 🟡 引用前核实卷期 |

---

## 3. 无原理图例的条目 → AI 生图提示词

> 用法：直接喂给图像模型（Midjourney / DALL·E / SDXL）。**生成后必须人工核对标签**，
> 图上每个方块、箭头都要能对上 §1 的原文摘抄与 `01_models/_selfimpl` 的实现，否则不能用进论文。
> 通用风格尾缀已内置：`flat vector technical diagram, white background, thin black strokes, muted blue/orange palette, sans-serif labels, no 3D, no photorealism`。

### 3.1 RPCA（对应 §1.12）

```text
A flat vector technical diagram of Robust Principal Component Analysis decomposition.
Left: a large matrix labeled "M (mixture magnitude spectrogram)" drawn as a grid.
Two arrows split to: top-right "L (low-rank)" drawn as a grid with a few repeated identical
column patterns; bottom-right "S (sparse)" drawn as a mostly dark grid with a few bright
scattered cells. Between them a small formula box: "min ||L||_* + λ||S||_1  s.t. M = L + S".
Below, a loop arrow labeled "ALM iterations (SVT + soft-thresholding)".
Flat vector technical diagram, white background, thin black strokes, muted blue/orange
palette, sans-serif labels, no 3D, no photorealism, 16:9, high resolution.
```

### 3.2 Oracle-IRM（对应 §1.11）

```text
A flat vector technical diagram of an ideal ratio mask oracle for 4-stem music separation.
Top: one mixture spectrogram "X". Middle: four ground-truth stem spectrograms labeled
vocals / drums / bass / other, each arrow pointing into a block labeled "ratio mask
S_i / Σ_j S_j". Right: a multiply node "⊙" combining the mask with |X|, then a block
"iSTFT" producing four separated waveforms at the bottom. Include a small vertical dB
colorbar. Flat vector technical diagram, white background, thin black strokes, muted
blue/orange palette, sans-serif labels, no 3D, no photorealism, 16:9, high resolution.
```

### 3.3 Open-Unmix / UMX（对应 §1.4）

```text
A flat vector technical diagram of the Open-Unmix (UMX) architecture for one target stem.
Left: "mixture waveform" waveform icon → "STFT" block → "|X| log-magnitude" grid.
Then four parallel identical branches labeled vocals / drums / bass / other; inside each
branch: three stacked "BiLSTM (256)" blocks with forward/backward arrows → "FC + ReLU" →
"sigmoid" → "mask M_i". Right: multiply node "M_i ⊙ X", then "Wiener filter" block, then
"iSTFT" → separated waveform. Mark clearly that each target has its own network.
Flat vector technical diagram, white background, thin black strokes, muted blue/orange
palette, sans-serif labels, no 3D, no photorealism, 16:9, high resolution.
```

### 3.4 （可选）Mel-RoFormer 整图

原文只有 mel 映射图。若论文需要一张完整架构图，**优先复用 `figs/fig07_bsroformer.png`** 并注明
「Mel-RoFormer 沿用 BS-RoFormer 的层次 Transformer，仅将 band-split 换成 mel 投影」；
确需新图时用：

```text
A flat vector technical diagram of Mel-Band RoFormer: STFT → complex spectrogram →
"Mel-band projection (overlapped subbands, mel scale)" drawn as a fan of overlapping
horizontal bands grouping frequency bins → stack of "Transformer blocks (inner-band)"
alternating with "Transformer blocks (inter-band)" with a "RoPE" tag → "MLP mask head"
→ mask multiplied with the complex spectrogram → iSTFT → waveform. Show a small inset
of frequency bins mapped into overlapping mel bands.
Flat vector technical diagram, white background, thin black strokes, muted blue/orange
palette, sans-serif labels, no 3D, no photorealism, 16:9, high resolution.
```

---

## 4. 复现与核对

```bash
PY="C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe"
cd 04_reports/00_shared/papers

# 1) 重新抽取某篇论文的全文（带页码分隔）
$PY ../../../tools/_paper_extract.py text --pdf pdf/Conv-TasNet.pdf

# 2) 重新裁某张原理图（按图注定位）
$PY ../../../tools/_paper_fig.py --pdf pdf/MMDenseLSTM.pdf --page 3 \
    --caption "MMDenseLSTM architecture" --top-text "Fig. 2"

# 3) 查看某页整页渲染，人工确认图在哪
$PY ../../../tools/_paper_extract.py render --pdf pdf/BS-RoFormer.pdf --pages 2
```

> ⚖️ **版权**：`figs/` 下是从论文 PDF 直接裁出的插图，仅可用于本人学位论文的引用性说明
> （须在图注写明 "Reproduced from [作者, 论文, Fig. X]"）。**不要**上传到公开仓库或再发布。

---

### 文件清单

| 路径 | 内容 |
|---|---|
| `pdf/*.pdf` | 12 篇原始论文 |
| `pdf/*.txt` | 逐页纯文本（摘抄的可核查来源） |
| `figs/fig01..09_*.png` | 9 张从论文裁出的原理图（300 dpi） |
| `MODEL_SOURCE_PAPERS.md` | 本文件 |

# DRNN（RPCA-DRNN）无法运行的原因说明

生成时间：2026-10-30 · 批次 `rerun_20261030_2358`
对应模型：`01_models/MODEL_REGISTRY.md` 第 2 行 **RPCA+DRNN**（Lai & Wang 2022）

---

## 1 结论

**这个模型无法在本机运行 —— 不是环境问题、不是显存问题、不是缺依赖，
而是它从来没有公开过代码，也没有公开过任何权重。** 全世界没有任何一份可以下载的
RPCA-DRNN 实现。因此「跑这个模型」在物理上不成立，只能二选一：

- **A. 放弃**（推荐，与项目既有决策一致：降级为「相关工作」）；
- **B. 自研重写 + 自己训练**（可行，但那是「复现论文」而不是「运行模型」，且口径与现有四轨评测不可比）。

下面给出全部证据、方法拆解、以及与 DPRNN 的区别（这两个名字极易混淆）。

---

## 2 证据链（每条都可复核）

### 2.1 论文本身

| 项 | 值 |
|---|---|
| 标题 | RPCA-DRNN technique for monaural singing voice separation |
| 作者 | Wen-Hsing Lai, Siou-Lin Wang（国立高雄科技大学） |
| 期刊 | EURASIP Journal on Audio, Speech, and Music Processing, 2022(1):4 |
| DOI | 10.1186/s13636-022-00236-9 |
| 开放获取 | 是（CC BY 4.0），PDF 可直接下载 |

论文正文只有方法描述与实验结果，**全文没有任何代码仓库链接、项目主页或权重下载地址**。

### 2.2 补充材料只有音频，没有代码

Springer Nature 为该文挂了两个补充文件（figshare，DOI 10.6084/m9.figshare.19128688）：

| 文件 | 官方描述 | 实际内容 |
|---|---|---|
| Additional file 1 | *Separated accompaniment* | 分离后的**伴奏音频样例** |
| Additional file 2 | *Separated vocal* | 分离后的**人声音频样例** |

论文 5. Supplementary Information 一节原文即：
> "Additional file 1. Separated accompaniment. Additional file 2. Separated vocal."

即：作者只放出了**试听样例**，用于证明「我们确实分离出来了」，**没有放出复现所需的任何东西**。

### 2.3 GitHub 全站搜索为 0

```
GET https://api.github.com/search/repositories?q=RPCA-DRNN+in:name,description,readme
→ {"total_count": 0, "items": []}

GET https://api.github.com/search/repositories?q=%22RPCA%22+%22DRNN%22+singing
→ {"total_count": 0, "items": []}
```

两次查询均返回 `total_count = 0`：**不存在任何以此命名的公开仓库**，
连第三方复现都没有。这排除了「官方没放、但社区有人复现过」这条路。

### 2.4 权重不存在

论文没有发布模型文件的渠道（无 Zenodo、无 figshare 权重、无 Google Drive 链接）。
仓库不存在 → 权重自然也不存在。**没有任何 SHA256 可算**，初始化卡片无从建立。

---

## 3 论文方法到底是什么（决定「自研」要写多少东西）

论文的方法链是四段，缺一不可：

```
mixture (单声道)
  → ① RPCA 分解（低秩 L = 伴奏 / 稀疏 S = 人声）
  → ② 后处理：中值滤波 + 形态学 + 高通滤波
  → ③ 两路并行 stacked RNN（sRNN + mask layer），分别精修 S 和 L
  → ④ 两路输出相加，ISTFT 时用 S/L 的相位
```

关键点（都来自论文原文）：

| 维度 | 论文设定 |
|---|---|
| 输入 | **单声道**（monaural），2 源（singing / accompaniment） |
| 网络 | 两个**并行**的 stacked RNN（sRNN），带 mask 层，**联合优化** |
| 损失 | 同时约束「人声」与「伴奏」两路估计（联合优化） |
| 相位 | 不做相位估计，直接沿用 RPCA 稀疏/低秩分量的相位做 ISTFT |
| 训练数据 | MIR-1K（23 min 36 s）、ccMixter、MUSDB18（7 h 46 min 24 s） |
| 轻量版 | RPCA-DRNNl 只用 53 min 45 s 训练数据 |
| 硬件要求 | 论文明确写「至少一张 1080Ti 或更高」 |
| 数据增强 | 不用（这是论文的卖点之一） |

**注意第 1 行与第 4 行**：它是**单声道、两源**。而本项目主表是 **44.1 kHz 立体声、MUSDB 四轨**。
即使自研成功，它的 SDR 也**不能**与 Demucs / BSRNN / BS-RoFormer 放进同一张表比较 ——
参考信号不同（vocals vs accompaniment，不是 4 stem）、声道数不同、评测口径不同。
这正是 `MODEL_REGISTRY.md` §3 把它「降级为相关工作」的原因。

---

## 4 最容易搞混的一点：DRNN ≠ DPRNN

| | **DRNN（本次要的）** | **DPRNN（本项目已有的）** |
|---|---|---|
| 全称 | Deep Recurrent Neural Network（论文里叫 stacked RNN） | Dual-Path Recurrent Neural Network |
| 出处 | Lai & Wang 2022 | Luo et al. 2019 |
| 代码 | **不存在** | `01_models/_third_party/Dual-Path-RNN-Pytorch` ✅ |
| 权重 | **不存在** | 本项目**自训**：`01_models/_weights/dprnn_musdb/{best,last}.pt` ✅ |
| 任务 | 单声道 2 源 | MUSDB 4 轨 |
| 状态 | ⛔ 不可运行 | ✅ 已跑通，四轨均值 **−1.72 dB**（欠训练，不参与排名） |

如果你其实想要的是「能跑的循环网络分离模型」，**DPRNN 已经在跑了**，
产物在 `03_outputs/DPRNN/test/<song>/{vocals,drums,bass,other}.flac`，
训练脚本 `tools/train_dprnn_musdb.py`。但它有两个已知问题（见下）。

---

## 5 如果坚持要「自研复现」，需要付出什么

### 5.1 工作量

| 步骤 | 内容 | 预估 |
|---|---|---|
| 1 | RPCA + 后处理（中值滤波/形态学/高通） | **已完成**（`sep_rpca` + 本次 Octave 交叉验证），约 0.5 天补后处理 |
| 2 | 双路 sRNN + mask 层实现（论文未给层数/隐单元数细节，需自己试） | 1–2 天 |
| 3 | 数据管线：单声道 2 源（vocals vs mixture−vocals），MUSDB 重切 | 0.5 天 |
| 4 | 训练（MUSDB 7h46m 数据，1080Ti 级，无增强） | **6–12 h/次**，至少要跑 2–3 次调参 |
| 5 | 评测（2 源 BSSEval，与四轨表分开） | 0.5 天 |

合计 **3–5 天 + 20–30 GPU 小时**，且结果**无法与官方数字对照**（官方数字在 MIR-1K/ccMixter 上，
Supplement 只给音频不给分数表）→ 做出来也**无法证明复现正确**。

### 5.2 本机的两个硬约束

1. **显存 8 GiB**：论文要求 1080Ti（11 GiB）。sRNN 是序列模型，长序列 + 双路并行会吃显存；
   需要梯度累积 + 短片段（本项目 DPRNN 自训就是被 8 GiB 逼到 11.025 kHz + 小 batch，
   结果欠训练到 −1.72 dB）。
2. **训练不能被会话托管**：本项目的实测结论是「会话发起的后台进程在回合结束时被硬杀」，
   长训练必须由你双击 `.bat` 或走任务计划程序。

### 5.3 结论建议

**不建议自研**。理由不是「做不到」，而是「做出来不可信」：
无官方权重、无官方逐曲分数、口径还是单声道 2 源 —— 这三条叠加，产出的任何数字都无法答辩时自证。
维持既有决策：**在论文里作为相关工作引用一句**，与 Pac-HuBERT-SEP 同处理。

---

## 6 本次为了「尽可能跑」实际做了什么

| 尝试 | 结果 |
|---|---|
| 查论文补充材料清单 | 只有 2 个音频（Additional file 1/2），无代码无权重 |
| GitHub 仓库搜索（2 个查询） | `total_count = 0` |
| 查作者单位页面 | 无项目主页/代码链接（论文全文亦无） |
| 查是否有第三方复现 | 无（GitHub 0 结果，搜索引擎仅返回论文本身与聚合站） |
| 尝试建立初始化卡片 | 无法建立 —— 无权重文件，`SHA256` 无从计算 |

**因此本次没有产生 DRNN 的任何音频或指标** —— 不是失败，是源头没有可执行物。

---

## 7 唯一还能做的一件事（如果你要）

若你只是想「让 RPCA 这一支看起来完整」，可以做**RPCA + 后处理的纯古典版本**
（不加 DRNN，即论文 §2.1 的 RPCA + 中值滤波 + 形态学 + 高通），
这不需要训练、不需要权重、今天就能出音频。但它**不是 RPCA-DRNN**，
论文里它只是 DRNN 的输入，指标会明显低于论文最终结果。
要的话说一声，我按 30 s 统一口径给你补一版，并明确标注「RPCA+post-processing, 无 DRNN」。

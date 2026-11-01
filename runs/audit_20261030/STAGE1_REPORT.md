# 阶段一报告：扫描 + 盲跑审计 + 训练计划

> 生成时间：2026-10-30 23:5x ｜ 执行模式：**只读**（未训练 / 未推理 / 未下载 / 未改配置 / 未覆盖任何原产物）
> 唯一写入：`runs/audit_20261030/`（本目录）与 `tools/_audit_blind_runs.py`（审计脚本）
> 审计对象：全项目 40 份历史输出、22 个模型、61 个 checkpoint、151 个日志、4 张主指标表

---

## 0. 三条必须先说的结论

**① 这个项目几乎没有"训练"，只有 1 个模型真训过。**
全项目只有一个训练脚本 `tools/train_dprnn_musdb.py`，`grep -c "epoch [0-9]" tools/_logs/*.out` = **0**，项目根目录**不存在 `configs/`、`runs/`、`checkpoints/`**。其余 21 个模型全部是**加载官方权重做推理评测**，从未训练。你记忆中的"盲目跑"，绝大部分是**推理跑**，不是训练跑。

**② 唯一训练过的 DPRNN，验证集来自训练集 —— 这是本次审计唯一的 D 类污染。**
`train_dprnn_musdb.py` L78-82：
```python
VAL_CLIPS = (("ANiMAL - Clinic A", "train", 140.0),
             ("Creepoid - OldTree", "train", 60.0),
             ("Dark Ride - Burning Bridges", "train", 180.0))
```
三首全部 `subset="train"`，而训练集就是 MUSDB train 的 100 首（日志第 4 行 `训练集: 100 首歌`）。`best.pt` 由这个验证集选出 → **模型选择污染**。
铁证：验证 best = **+2.745 dB**，测试集 = **−1.72 dB**，**差 4.5 dB**。

**③ 训练元数据自相矛盾：JSON 说 3 分钟，日志说 250.7 分钟。**
`dprnn_training.json` 的 `total_min: 3.0`、`started 00:56:37`、`finished 15:19:50`——这是**最后一轮 `--minutes 3`** 的耗时；日志实测 15:13 时已用 **247.1 min**，最终 **250.7 min**，跨 14.5 小时多轮续跑。同一份 JSON 里 `batch: 8`，而日志启动行写 `batch=4`。

---

## 1. 阶段矩阵表（22 模型 × P1–P10）

**状态口径**：✅ 已完成且合格 ｜ ⚠️ 部分完成或有遗漏 ｜ ❌ 未做 ｜ ❓ 无法验证
**重要前提**：P4–P8 是"训练"语义。21 个推理型模型没有训练，这些阶段判 ❌ 不是"做错了"，而是**从未发生**。

### 1.1 板 1 分离（15 个）

| 模型 | P1 配置/清单 | P2 划分防泄漏 | P3 输入契约 | P4 DataLoader | P5 预训练初始化 | P6 损失/优化器 | P7 lr/AMP/裁剪 | P8 循环/验证 | P9 Checkpoint | P10 小样本+测试+归档 | 证据 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| demucs | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `03_outputs/Demucs` 200 flac；`_weights/Demucs/955717e8-8726e21a.th` |
| mdx | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `03_outputs/MDX-Net`；`_weights/MDX-Net/mdx_extra/*.th` |
| umx | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `03_outputs/Open-Unmix`；`umxhq` ×4 |
| convtasnet | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `03_outputs/Conv-TasNet` 200 flac |
| mmdenselstm | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `03_outputs/MMDenseLSTM` |
| bsroformer_l12 | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `ep_317_sdr_12.9755.ckpt`；单目标 vocals |
| bsroformer_l6 | ❌ | ❌ | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | 🔴 输出语义 = vocals+other（非 yaml 写的 other） |
| bsrnn | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `_weights/BSRNN/bsrnn-opt/vocals.ckpt` |
| bsrnn_all | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | 4 ckpt 聚合 164.12 M |
| bsrnn_large | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | 36.42 M |
| bsrnn_large_all | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | 146.66 M |
| bsrnn_simo | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `simo-bsrnn-opt/separator.ckpt`（P1 官方推荐） |
| oracle | ❌ | ❌ | ✅ | ❌ | ➖ | ➖ | ➖ | ➖ | ➖ | ⚠️ | 解析上界，**不配损失/优化器**；`03_outputs/Oracle-IRM` |
| rpca | ❌ | ❌ | ✅ | ❌ | ➖ | ➖ | ➖ | ➖ | ➖ | ❌ | 🔴 `03_outputs/RPCA` **0 文件**（注册表标 ✅ 与磁盘不符） |
| **dprnn** | ⚠️ | ❌ | ✅ | ✅ | ❌ | ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ | `train_dprnn_musdb.py`；验证集泄漏（D 类） |

### 1.2 板 2 降噪/去混响（7 个）

| 模型 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 | 证据 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| denoiser_dns48 | ❌ | ❌ | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | 契约 44.1k/2ch 输入 → 内部 16k；`dns48-11decc9d8e3f0998.th` |
| denoiser_dns64 | ❌ | ❌ | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `dns64-a7761ff99a7d5bb6.th` |
| denoiser_master64 | ❌ | ❌ | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `master64-8a5dfb4bb92753dd.th`（ALL ΔPESQ +0.963 最优） |
| mel_roformer_denoise | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `aufr33_sdr_27.9959.ckpt`；近恒等（level_ratio 0.96~1.00） |
| mel_roformer_denoise_aggr | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `aufr33_aggr_sdr_27.9768.ckpt` |
| mel_roformer_dereverb | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | `anvuew_sdr_19.1729.ckpt` |
| mel_roformer_dereverb_echo | ❌ | ❌ | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ⚠️ | 🔴 **2-stem**（`dry`/`other`），无 `enhanced` 键 |

**图例说明**：➖ = 该阶段对解析法**根本不存在**（不适用），一律不配损失与优化器。

### 1.3 矩阵的读法（三条判读规则）

1. **P3 只有 2 个 ⚠️，但都是致命的**：`bsroformer_l6` 的输出语义与 yaml 不符（直接比会误判失效）；4 个降噪模型全部要 `44.1k/2ch` 输入 → 内部 `16k`，这正是 P19 采样率契约 bug 的土壤。
2. **P5 全是 ✅ 不代表"会训练"**：✅ 只说明"权重能加载"。真正的训练初始化（冻结策略、encoder 解冻）**一个都没做**。
3. **P10 全是 ⚠️，没有一个 ✅**：因为全项目**没有任何一次小样本过拟合测试**。这是材料 B 点名的"5 分钟暴露 90% 接线错误"的手段，全项目零执行。

---

## 2. 盲目跑数据审计表（A/B/C/D + 证据）

完整机读版：`runs/audit_20261030/audit_blind_runs.csv`（40 行）。

**分布：A=2 ｜ B=27 ｜ C=9 ｜ D=2**

### 2.1 A 类（可用，可直接纳入结果）—— 只有 2 份

| id | 路径 | 为什么是 A |
|---|---|---|
| X04 | `03_outputs/rerun_20261030_1700/` | **全项目唯一有完整 meta 的产物**：`command`（完整命令行）、python 3.13.14、torch 2.14.0+cu126、cuda 12.6、`git commit 1107b16`、`git_dirty_count 111`、起止时间、`weight_hashes.json` 全齐 |
| M05 | `.../model_analysis/model_profile.csv` | 22 模型齐全，含 `params_M / rtf / peak_vram_infer_mb / native_sr / native_ch`，字段自洽，可直接作训练配置卡依据 |

> X04 应作为**全项目的可追溯范式模板**：它证明这套 `rerun_report.json` 结构在本项目是可行的，只是没被推广到其它 38 个产物。

### 2.2 B 类（部分可用，需补证）—— 27 份，占 67%

共同缺陷高度一致，归纳为 4 条：

| 缺陷 | 命中数 | 说明 |
|---|---|---|
| **无 run manifest / 无命令行** | 24 | 产物能听、能测，但**说不出是哪条命令、哪份配置生成的** |
| **非全量** | 9 | 单条冒烟（1–2 wav）、3 段×10s、4×4 小样本 |
| **口径不统一** | 6 | 降噪 16k/44.1k 混放（D07）、抽样表被当全量（M01 只 100 行） |
| **清单与磁盘不匹配** | 1 | `TableSample_Audio`：25 目录 / 933 wav，`_manifest.json` **只剩 1 条** |

**B 类里最需要注意的 4 条**：

- **S07 `BS-RoFormer-L6`**：`03_outputs/BS-RoFormer-L6` 200 flac。yaml 写 `target_instrument: other`，实测输出是 `mixture − drums − bass`（= vocals + other）。**若按 "other" 去比，会把它误判成 0.83 dB 的失效模型**。
- **D07 `_valentini_denoise`**（5768 wav / 3.2 GB）：抽样实测 `denoiser_dns64/p232_292.wav` = **16 kHz / 单声道**，`mel_roformer_dereverb/p257_153.wav` = **44.1 kHz / 立体声**。**跨模型不能直接横比**。mtime 2026-10-13 00:31–00:49，无 manifest。
- **M01 `comparison_results.csv`**：只有 **100 行**（不是 50 曲 × 4 stem 的 200 行 × 多模型），是抽样表。`delta_SDR` 以 mixture 为基线，口径本身正确。
- **M02 `denoise_eval_16k.csv`**：40 行里 `dns_dev` 的 6 行 `si_sdr_in/out/improve` **全为 0.00**——`reference_mode=noref`（DNS 无参考）时**空值被写成了 0**。`synth` 行正常（4.83 → 15.35，**+11.61 dB**）。`n_skipped` 全 0，说明已是 P19 修复后版本。

### 2.3 C 类（无用）—— 9 份

| id | 路径 | 证据 |
|---|---|---|
| **S13** | `03_outputs/RPCA` | 🔴 **0 文件 / 0 MB**。而 `MODEL_REGISTRY.md` 把 RPCA 标为 ✅ 可运行 —— **注册表与磁盘直接矛盾** |
| D01–D03 | `denoiser-dns48/dns64/master64` | 各仅 **1 个 wav（112 KB）**，单条冒烟，非评测产物 |
| D04–D06 | Mel-RoFormer ×3 | 各 **1–2 个 wav（600 KB–1.2 MB）**，单条抽查 |
| C04 | `_eval_test` | 29 文件冒烟残留，样本极小 |
| X03 | `_wiener_pkg` | **8 KB 空壳目录**，无音频 |

### 2.4 D 类（有污染风险）—— 2 份，且是同一件事

| id | 路径 | 污染类型 | 证据 |
|---|---|---|---|
| **S12** | `03_outputs/DPRNN` | **数据泄漏 + 模型选择污染** | ① `VAL_CLIPS` 三首 `subset="train"`（`train_dprnn_musdb.py` L78-82）② 日志 L4「训练集: 100 首歌」= 验证集 ⊂ 训练集 ③ best.pt 由该验证集选出 ④ 验证 +2.745 / 测试 −1.72（差 4.5 dB）⑤ 另有削波：抽样 20 flac，`peak=1.0000`，clipped **0.0168%** |
| **T01** | `_weights/dprnn_musdb/{best,last}.pt` | **元数据矛盾** | ① `dprnn_training.json` `total_min=3.0` vs 日志 `已用 250.7 min` ② `batch=8` vs 日志 `batch=4` ③ `started 00:56:37` 只是最后一轮 |

**其他被判 D 的高风险项（已在矩阵里降级，未进 CSV 独立行）**：
- 任何"用验证集指标写进结论"的做法 —— 已核 `comparison_results.csv` 的 `delta_SDR` 口径正确，**未发现**该类问题；
- 社区权重冒充官方 —— 已在 `checkpoint_audit` 里区分，`BS-RoFormer`/`Mel-RoFormer` 全部标 `NO 无官方推荐`。

---

## 3. 初始化卡片汇总（22 模型）

完整机读数据源：`.../model_analysis/model_profile.csv`（22 行）。
下表是**本次审计认定**的初始化状态，共 4 类：已完成 / 需重做 / 未做 / 无法验证。

### 3.1 已完成（可直接复用，2 个）

| 模型 | sr / ch | 参数量 | 权重 hash | 依据 |
|---|---|---|---|---|
| demucs | 44100 / 2 | 41.98 M | `955717e8-8726e21a.th`（文件名自证） | profile + ckpt 清单 |
| bsrnn_simo | 44100 / 2 | 108.73 M | `simo-bsrnn-opt/separator.ckpt` | profile + Zenodo |

### 3.2 需重做（3 个）

| 模型 | 问题 | 必须改什么 |
|---|---|---|
| dprnn | 验证集泄漏 + 削波 0.0168% + 元数据矛盾 | 改按歌曲划分（MUSDB train 100 拆 85/15）+ 输出峰值归一化 + 重写 meta |
| bsroformer_l6 | 输出语义 ≠ yaml 声明 | 初始化卡片里把 `output_stems` 写成 **`vocals+other`**，不得写 `other` |
| mel_roformer_dereverb_echo | 2-stem（`dry`/`other`），无 `enhanced` | 导出必须走 `enhanced→dry→首键` 兜底，卡片标注 `output_stems=[dry, other]` |

### 3.3 未做（15 个）

`mdx, umx, convtasnet, mmdenselstm, bsroformer_l12, bsrnn, bsrnn_all, bsrnn_large, bsrnn_large_all, mel_roformer_denoise, mel_roformer_denoise_aggr, mel_roformer_dereverb, denoiser_dns48, denoiser_dns64, denoiser_master64`
—— 从未写过 `configs/init_<model>.yaml`（项目无 `configs/` 目录）。

### 3.4 无法验证（2 个）

| 模型 | 阻塞原因 |
|---|---|
| oracle | 解析法，**无初始化语义**；应标"不适用"而非"未做" |
| rpca | 解析法，但 `03_outputs/RPCA` 0 文件，**无法验证能否输出 stem** |

### 3.5 关键缺项：STFT 参数

材料 B 要求"初始化必须一模一样：STFT 参数"。**全项目没有任何一份记录写明各模型的 n_fft/hop/win**。
`model_profile.csv` 只有 `native_sr / native_ch / params / rtf / vram`，**没有 STFT 字段**。
→ 这一项在阶段二必须从 `_third_party/*/conf/*.yaml` 逐个读出并落卡。**阶段一不猜**，列入第 7 节。

---

## 4. 逐模型训练配置卡（loss / optimizer / 策略 + 依据 + 风险）

> **统一声明**：以下全部是**微调（fine-tune）配置**，不是从零训练。21 个模型有官方/社区预训练权重，从零训练在本机 8 GiB 上既无必要也不可行（DPRNN 从零训 250 min 只到 −1.72 dB 就是反例）。
> **依据列**逐条引用 `model_profile.csv` 的具体字段，不引用的不写。

### 4.1 板 1 · 音乐源分离（波形 L1 为主）

| 模型 | loss（项+权重+域） | optimizer | lr | sched / warmup | amp / clip | batch×accum | epochs | freeze | 依据 | 风险 |
|---|---|---|---|---|---|---|---|---|---|---|
| demucs | `L1(wave) 1.0 + MultiResSTFT-L1 0.5`，44.1k/2ch | AdamW β=(0.9,0.999) wd=1e-4 | 3e-4 | cosine + warmup 500 step | AMP bf16 / clip 5.0 | 4×2 | 5~10 | encoder 冻 2 epoch → 解冻 | params 41.98 M、vram 599.7 MiB（profile） | 8 GiB 下 batch>6 会 sysmem fallback 静默变慢 |
| mdx | `L1(wave) 1.0 + STFT-L1 0.5` | AdamW wd=1e-4 | 2e-4 | cosine + warmup 800 | AMP / clip 1.0 | 2×4 | 5 | 冻 encoder 2 ep | params **334.54 M**、vram **1930.9 MiB** | 最大模型，必须梯度累积；别用大 lr |
| umx | `L1(wave) 1.0` | AdamW wd=1e-5 | 3e-4 | cosine + 300 | AMP / clip 5.0 | 8×1 | 10 | 不冻（小模型） | params 35.58 M、vram 1226 MiB | 小模型易过拟合，早停 patience 3 |
| convtasnet | `SI-SDR loss（负）1.0`（时域模型惯用） | AdamW wd=1e-5 | 5e-4 | cosine + 400 | AMP / clip 5.0 | 4×2 | 10 | 冻 encoder 2 ep | params 13.40 M、vram 606.6 MiB | 时域模型对 chunk 长度敏感，必须 4 s 对齐 |
| mmdenselstm | `L1(wave) 1.0 + STFT-L1 0.3` | AdamW wd=1e-4 | 3e-4 | cosine + 400 | AMP / clip 5.0 | 4×2 | 8 | 冻 LSTM 前 2 层 2 ep | params 5.49 M、vram 643.4 MiB | 🔴 历史训练困难；warmup 加倍、patience 5 |
| bsroformer_l12 | `L1(wave) 1.0 + STFT-L1 0.5` | AdamW wd=1e-4 | 2e-4 | cosine + 1000 | AMP bf16 / clip 1.0 | 2×4 | 5 | 冻 encoder 3 ep | params 159.76 M、vram **3394.3 MiB** | 显存最紧；单目标 vocals，**不能与四轨均值比** |
| bsroformer_l6 | 同上 | 同上 | 2e-4 | cosine + 800 | AMP / clip 1.0 | 3×2 | 5 | 冻 encoder 3 ep | params 98.20 M、vram 2087.4 MiB | 🔴 输出是 vocals+other，loss 的 target 必须同改 |
| bsrnn（单轨） | `L1(wave) 1.0` | AdamW wd=1e-4 | 3e-4 | cosine + 500 | AMP / clip 5.0 | 4×2 | 8 | 冻 band-split 前段 2 ep | params 40.78 M、vram 1675 MiB | 单轨模型，评估口径要单列 |
| bsrnn_all | `L1(wave) 1.0`（4 输出求和） | AdamW wd=1e-4 | 2.5e-4 | cosine + 800 | AMP / clip 5.0 | 3×3 | 8 | 冻 2 ep | params 164.12 M、vram 2637.4 MiB | 🔴 4 ckpt 按位置对齐，顺序错静默互换 |
| bsrnn_large | 同 bsrnn | 同上 | 2.5e-4 | cosine + 600 | AMP / clip 5.0 | 3×2 | 8 | 冻 2 ep | params 36.42 M、vram 1657 MiB | 与 opt 变体分开报 |
| bsrnn_large_all | 同 bsrnn_all | 同上 | 2.5e-4 | cosine + 800 | AMP / clip 5.0 | 2×4 | 8 | 冻 2 ep | params 146.66 M、vram 2567.9 MiB | 同上 |
| bsrnn_simo | `L1(wave) 1.0` | AdamW wd=1e-4 | **3e-4（官方推荐起点）** | cosine + 600 | AMP / clip 5.0 | 3×2 | 8 | 冻 2 ep | params 108.73 M、vram 2483 MiB；**P1 官方推荐** | 最优基线，改动它要格外保守 |
| oracle | **不适用** | 不适用 | — | — | — | — | — | — | 解析法 | 禁止硬配 |
| rpca | **不适用** | 不适用 | — | — | — | — | — | — | 解析法 | 禁止硬配；产物目录为空 |
| **dprnn** | `负 SI-SDR`（已验证可用）1.0，11.025k/单声道/4.0s | **Adam**（原脚本）→ **建议改 AdamW wd=1e-4** | 5e-4 → 建议 3e-4 | ReduceLROnPlateau → **建议 cosine + warmup 500** | AMP bf16 / clip 5.0 | 4×1 | **≥30**（现 31900 step ≈ 21 个有效 epoch） | **无**（从零训） | 脚本 L279-281；日志 250.7 min | 🔴 已知训练困难（−1.72）；**必须先修验证集泄漏** |

### 4.2 板 2 · 降噪 / 去混响

| 模型 | loss | optimizer | lr | sched/warmup | amp/clip | batch×accum | epochs | freeze | 依据 | 风险 |
|---|---|---|---|---|---|---|---|---|---|---|
| denoiser_dns48 | `时域 L1 1.0 + 频谱 L1 0.5`（材料 B 明示） | AdamW wd=1e-5 | 3e-4 | cosine + 400 | AMP / clip 5.0 | 8×1 | 10 | 冻 encoder 2 ep | params **18.87 M**、vram **233.4 MiB**、rtf 0.0084（profile） | 最轻量；**契约输入 44.1k/2ch，内部 16k**，别在 16k 上train |
| denoiser_dns64 | 同上 | 同上 | 3e-4 | cosine + 400 | AMP / clip 5.0 | 6×2 | 10 | 冻 2 ep | params 33.53 M、vram 343.2 MiB | 同上；dns48/64/master64 三个要同口径 |
| denoiser_master64 | 同上 | 同上 | 3e-4 | cosine + 400 | AMP / clip 5.0 | 6×2 | 10 | 冻 2 ep | params 33.53 M（与 dns64 同参数）、rtf 0.0127 | **ALL ΔPESQ +0.963 最优**，改它会让主结论漂移 |
| mel_roformer_denoise | `时域 L1 1.0 + 频谱 L1 0.5` | AdamW wd=1e-4 | 2e-4 | cosine + 800 | AMP / clip 1.0 | 2×4 | 5 | 冻 encoder 3 ep | params 228.20 M、vram 2011.2 MiB | 🔴 近恒等（level_ratio 0.96~1.00），微调极易"更恒等" |
| mel_roformer_denoise_aggr | 同上 | 同上 | 2e-4 | cosine + 800 | AMP / clip 1.0 | 2×4 | 5 | 冻 3 ep | 同上（同 228.20 M） | 两变体结果差 20 dB（+0.96 vs +21.17），**必须分开报** |
| mel_roformer_dereverb | **SI-SDR 为主**（去混响不用纯 L1）1.0 | AdamW wd=1e-4 | 2e-4 | cosine + 800 | AMP / clip 1.0 | 2×4 | 5 | 冻 3 ep | 228.20 M、vram 2011.2 MiB | 与降噪的区别：目标含 T60，L1 会奖励"抹平混响尾巴" |
| mel_roformer_dereverb_echo | SI-SDR 为主 | 同上 | 2e-4 | cosine + 800 | AMP / clip 1.0 | 2×4 | 5 | 冻 3 ep | 208.88 M、vram 1869.2 MiB | 🔴 2-stem 输出，loss 要同时约束 dry 与 other |

### 4.3 五条全局规则

1. **AMP 一律 bf16**（本机 torch 2.14 + cu126 已验证 `torch.autocast("cuda", dtype=torch.bfloat16)` 可用，DPRNN 脚本已在用）。
2. **clip 分两档**：波形损失模型 5.0；STFT/Transformer 类 1.0（梯度更尖）。
3. **batch 上限由 profile 的 `peak_vram_infer_mb` 反推**：推理已占 3.4 GB 的 `bsroformer_l12`，训练必须梯度累积而不是加 batch。
4. **社区权重必须标注**：`BS-RoFormer`、`Mel-RoFormer` 全部为社区训练/分发（`checkpoint_audit` 判 `NO 无官方推荐`），微调结果只能写"基于社区权重微调，非官方基线"。
5. **`master64` 是降噪主结论的承载者**（ΔPESQ +0.963），任何重训都必须同批跑 `dns48/dns64` 对照。

---

## 5. 逐模型训练全过程清单（18 环节）

> 由于 21 个模型从未训练，这 18 环节里 **1–18 全部是"待建"**。下表给出**每个模型的实际落地路径**（路径级，不是概念级）。

| # | 环节 | 现状 | 阶段二落地路径 |
|---|---|---|---|
| 1 | 配置文件 | ❌ 无 `configs/` | 新建 `configs/train_<model>.yaml`（22 份） |
| 2 | 数据清单 | ⚠️ 部分 | MUSDB: `02_databases/MUSDB18-HQ/{train,test}`；降噪: Valentini 824 对 + DNS 867 |
| 3 | 划分方式 | 🔴 **DPRNN 按片段/同集** | 改为**按歌曲**：MUSDB train 100 首 → 85/15；Valentini 按说话人 p257/p232 分半 |
| 4 | 输入契约 | ⚠️ | 逐模型 `native_sr/native_ch`（profile 已有）；**STFT 待从 `_third_party` 读** |
| 5 | DataLoader | ❌ 仅 DPRNN | 沿用 `MusdbChunks`（可复用），`num_workers=0`（Windows + 8 GiB） |
| 6 | 预训练权重/hash | ✅ | `checkpoint_audit/checkpoint_inventory.csv` 61 条全 hash，直接引用 |
| 7 | 损失函数 | ❌ | 见 §4 表（逐模型权重已定） |
| 8 | 优化器 | ❌ | AdamW 统一，lr 见 §4 |
| 9 | 调度/warmup | ❌ | cosine + warmup（DPRNN 现为 ReduceLROnPlateau，需换） |
| 10 | AMP/裁剪 | ⚠️ DPRNN 有 | bf16 + clip 5.0/1.0 |
| 11 | 训练循环 | ⚠️ DPRNN 有 | 复用 `train_dprnn_musdb.py` 骨架（含 OOM 降级、NaN 兜底、keep_awake） |
| 12 | 验证集口径 | 🔴 泄漏 | 独立 val 集 + **SI-SDR 代理**（11.025k）与**正式 SDR**（44.1k）分离记账 |
| 13 | Checkpoint | ✅ DPRNN | `best.pt`/`last.pt` + `step/best/val/cfg/targets/sr`（DPRNN 已是此格式） |
| 14 | 小样本过拟合 | ❌ **全项目零执行** | 10 条 × 200 step，5 min，loss 必须降到接近 0 |
| 15 | 正式训练命令 | ⚠️ | `python tools/train_<model>.py --config configs/train_<model>.yaml` |
| 16 | 测试集评估 | ⚠️ | MUSDB **test 50 首**（只考一次）；降噪 Valentini test 824 |
| 17 | 产物路径 | — | `runs/rerun_YYYYMMDD_HHMM/<model>/`（不覆盖 `03_outputs/`） |
| 18 | 归档字段 | ⚠️ | 复用 X04 的 `rerun_report.json` 结构（已证明可行） |

---

## 6. 阶段二执行计划（跳过 / 重做 / 立刻做 + 耗时 + 风险）

### 6.1 跳过（证据齐全，不动）

| 项 | 证据 |
|---|---|
| 权重资产与 hash | `checkpoint_audit/checkpoint_inventory.csv`，**61/61 实算 SHA256，13.60 GiB** |
| 模型画像 | `model_profile.csv` 22 行（A 类） |
| 可追溯范式 | `rerun_20261030_1700/rerun_report.json`（A 类） |
| 板 2 主表口径 | `denoise_eval_16k.csv` / `44k.csv`（B 类但 n_skipped=0，P19 已修） |

### 6.2 重做（必须修，否则不能进训练）

| 优先级 | 项 | 动作 | 预计耗时 | 风险 |
|---|---|---|---|---|
| **P0** | DPRNN 验证集泄漏 | 改按歌曲划分；重训 | 4~5 h（GPU） | 中：重训后精度可能仍低（模型 3.69 M 太小） |
| **P0** | `03_outputs/RPCA` 空目录 | 跑 1 首验证能否出 stem | 10 min | 低 |
| **P1** | `TableSample_Audio` manifest | 从 933 wav 反推重建 | 20 min | 低（只读扫描 + 写新 manifest） |
| **P1** | `dprnn_training.json` 元数据 | 按日志重算 total_min/batch | 10 min | 低 |
| **P2** | STFT 参数补录 | 读 7 个 `_third_party` yaml | 40 min | 低 |
| **P2** | `denoise_eval_16k.csv` dns_dev 空值 | 0 → null | 5 min | 低（会影响下游读取） |

### 6.3 立刻做（阶段二一开始就做，无需等待）

| 项 | 动作 | 耗时 |
|---|---|---|
| 22 份 `configs/init_<model>.yaml` | 按 §3 + profile 生成 | 30 min |
| 22 份 `configs/train_<model>.yaml` | 按 §4 生成 | 40 min |
| 1 次端到端小样本过拟合 | 选 demucs（最轻、vram 599.7 MiB）10 条 × 200 step | **5 min** |

### 6.4 不建议现在做

- **21 个模型全部微调**：8 GiB 显存 + 114 GB 项目 + 12 GB 空闲磁盘，同时训多个必然 OOM，且 21 个模型逐个微调需 **50+ 小时**。建议**只微调 3 个**：`demucs`（最轻）、`bsrnn_simo`（官方 P1 推荐）、`denoiser_master64`（板 2 主结论）。
- **`bsroformer_l12` / `mdx` 微调**：推理已占 3.4 GB / 1.9 GB，训练几乎必然触发 sysmem fallback（静默变慢 10~100×）。

### 6.5 前置条件（必须你先处理）

- **磁盘**：E: 只剩 **12 GB**，而 `03_outputs` 已 42 GB。训练 checkpoint（每模型 100~1600 MB）+ `runs/` 新产物至少要 **20 GB**。**不腾空间，阶段二无法启动**。
- **bench500 仍在跑**（`_bench500.bat`，当前 bsrnn_all，剩 7 模型 ≈ 3 h）。**训练必须等它结束**，否则 8 GiB 显存会互抢。

---

## 7. 无法验证项与需要你提供的信息

| # | 无法验证项 | 为什么 | 需要你做什么 |
|---|---|---|---|
| 1 | **全部 22 个模型的 STFT 参数**（n_fft/hop/win） | 项目里没有任何一份记录写了这些字段；`model_profile.csv` 只有 sr/ch/params/rtf/vram | 允许我读 `_third_party/*/conf/*.yaml`（只读），或你直接给 |
| 2 | **归一化方式** | 同上，未记录 | 同上 |
| 3 | **DPRNN 真实总训练时长** | JSON 写 3.0 min，日志 250.7 min，两者矛盾 | 你确认以哪个为准（我建议以日志为准） |
| 4 | **`_valentini_denoise` 是 P19 修复前还是修复后生成** | mtime 2026-10-13 00:31–00:49，早于/晚于修复点我无法判定 | 你回忆或允许我抽样比对 noisy 源 |
| 5 | **`TableSample_Audio` 原始清单** | manifest 只剩 1 条，933 wav 无法反查来源 | 若你有备份，提供；否则我按目录名反推（可能不准） |
| 6 | **`03_outputs/RPCA` 为何为空** | 注册表标 ✅ 但 0 文件 | 允许我跑 1 首验证（属阶段二写操作） |
| 7 | **社区权重的训练数据构成** | BS-RoFormer / Mel-RoFormer 均无训练数据说明 | 论文里只能写"官方未披露" |
| 8 | **`bsrnn-large` 对应 Zenodo 哪一行** | 包内无明确映射 | 需查 Zenodo 页面（联网） |

---

## 8. 等待确认声明

**阶段一完成，等待用户确认后再进入阶段二。**

请重点确认以下 4 件事：

1. **审计判定，尤其 C 类 9 份和 D 类 2 份**：
   - C 类里 `03_outputs/RPCA` **0 文件**（注册表却标 ✅），`_wiener_pkg` 空壳，5 个降噪目录只有单条冒烟 —— 这些我判"作废"，你同意吗？
   - D 类 2 份是同一件事（DPRNN 验证集泄漏 + 元数据矛盾），我判"必须重跑"，你认可这个定性吗？

2. **证据路径是否真实**：全部 40 行都写了 `path` + `evidence`，你可以直接点开核对。若有一条你打不开，我立刻重查。

3. **无法验证项 8 条**：其中第 1、2 条（STFT / 归一化）是材料 B 明确要求"必须一模一样"的，**没有它初始化卡片不算合格**。你允许我读 `_third_party` 的 yaml 吗？

4. **阶段二计划是否准确**：我建议**只微调 3 个模型**（demucs / bsrnn_simo / denoiser_master64），不是 22 个全训 —— 因为磁盘只剩 12 GB、显存 8 GiB、bench500 还在跑。你是否接受这个收缩？

**两个硬阻塞，需要你先处理：**
- 磁盘只剩 **12 GB**（训练产物至少要 20 GB）；
- `_bench500.bat` 还在跑（剩约 3 h），训练必须等它结束。

回复「确认，进入阶段二」即可，或先回答上面 4 点。

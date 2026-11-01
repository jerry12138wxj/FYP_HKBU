# 模型训练计划（22 个模型 · 18 环节）

生成时间：2026-10-30
依据：材料 A（训练全流程 18 环节）+ 材料 B（HTDemucs 三条毁结果风险 / 初始化必须一模一样 / lr 3e-4 / 冻 encoder 2 epoch / best.pt 评估 / 10 条 200 步过拟合测试）
配套文件：`configs/init_<model>.yaml` × 22、`configs/train_<model>.yaml` × 22

---

## 0 一句话结论

**22 个模型里，20 个有可用权重、2 个是解析方法；但整个项目历史上从未完成过一次「按 18 环节走完」的训练。**
本次已经把所有「训练前必须固定下来的东西」落成可执行的 YAML 文件（共 44 份），
并跑通了第一个小样本过拟合测试（demucs，PASS）。
真正需要重训的只有 **DPRNN**（唯一被证实存在验证集泄漏）。

---

## 1 模型分组与训练必要性

| 组 | 模型 | 任务 | 权重状态 | 是否需要训练 | 理由 |
|---|---|---|---|---|---|
| 解析/古典 | `oracle` | 分离 | 无参数 | ❌ 不适用 | IRM/IBM 掩码，需要 GT |
| 解析/古典 | `rpca` | 分离 | 无参数 | ❌ 不适用 | 凸优化 IALM 迭代，无学习参数 |
| 4 轨分离 | `umx` `mdx` `convtasnet` `mmdenselstm` `demucs` `dprnn` `bsrnn_all` `bsrnn_large_all` `bsrnn_simo` | 分离 | 官方（dprnn 为自训） | ⚠️ 仅 dprnn | 其余官方权重已达论文水平，重训无收益 |
| 单轨分离 | `bsroformer_l12` `bsroformer_l6` `bsrnn` `bsrnn_large` | 分离 | 社区/官方 | ❌ 不重训 | 单目标模型，重训需重切参考信号 |
| 降噪 | `mel_roformer_denoise` `mel_roformer_denoise_aggr` `denoiser_dns48` `denoiser_dns64` `denoiser_master64` | 降噪 | 官方/社区 | ⚠️ 仅 master64 可选 | 见 §6 |
| 去混响 | `mel_roformer_dereverb` `mel_roformer_dereverb_echo` | 去混响 | 社区 | ❌ 不重训 | 去混响已是负结果（ΔSDR +0.044），重训救不回来 |

**结论：真正要开机训练的只有 `dprnn`（必修）+ `denoiser_master64`（可选）。**
其余 20 个模型的 `init_*.yaml` 是「冻结现状、可复现」的档案，不是训练任务。

---

## 2 18 环节 → 10 阶段映射

| 阶段 | 环节 | 交付物 / 判据 |
|---|---|---|
| **P1 配置** | ① config.yaml（菜谱） | `configs/init_<m>.yaml` + `configs/train_<m>.yaml`（本次生成 44 份） |
| **P2 清单** | ② manifest（点名册） | `model_inventory.csv`（22 行）+ `checkpoint_inventory.csv`（61 ckpt）+ 数据 manifest |
| **P3 划分** | ③ 按歌曲划分 train/val/test（防泄漏） | 校验 `set(train_songs) ∩ set(val_songs) == ∅` |
| **P4 输入契约** | ④ 对齐 sr/声道/segment | `init_*.yaml#audio_contract` + `#stft` |
| **P5 DataLoader** | ⑤ Dataset/DataLoader（备菜上菜） | 随机 offset 取样、能量门控（MUSDB 前 30 s 常静音） |
| **P6 初始化** | ⑥ 预训练权重初始化（给起点） | `init_*.yaml#weights`，sha256 已实算 |
| **P7 冻结** | ⑦ 冻结 encoder 再解冻 | 前 2 epoch 冻 encoder，之后解冻 |
| **P8 损失** | ⑧ 损失函数（打分老师） | `train_*.yaml#loss` |
| **P9 优化器** | ⑨ 优化器 + ⑩ 学习率/调度 + ⑪ AMP + ⑫ 梯度裁剪 | `train_*.yaml#optim/#schedule/#amp` |
| **P10 评估与归档** | ⑬ 训练循环 ⑭ 验证集 ⑮ checkpoint ⑯ 小样本过拟合 ⑰ 测试集评估 ⑱ 归档复现 | `train_*.yaml#checkpoint/#overfit_test/#commands/#archive_fields` |

---

## 3 逐模型阶段判定（✅ 有证据 / ⚠️ 部分 / ❌ 缺失 / n/a 不适用）

判定口径：**✅ = 本机存在可执行文件或可核验记录；❌ = 从未发生（不是做错，是没做）**。

| 模型 | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 | 证据 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle | ✅ | ✅ | n/a | ✅ | n/a | n/a | n/a | n/a | n/a | ⚠️ | `init_oracle.yaml`；解析无训练 |
| rpca | ✅ | ✅ | n/a | ✅ | n/a | n/a | n/a | n/a | n/a | ✅ | 本次实跑 2 首 + Octave 交叉验证（133.7 dB 一致） |
| umx | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | 权重 4 个 sha256 已验；无训练脚本 |
| mdx | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ckpt kwargs: HDemucs nfft 4096 segment 112 |
| convtasnet | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | pth args: kernel 20 stride 10 n_basis 256 |
| mmdenselstm | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | pth args: n_fft 4096 hop 1024 bands 3 段 |
| bsroformer_l12 | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | yaml: dim 512 depth 12 hop 441 |
| bsroformer_l6 | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | yaml: dim 384 hop 512；输出=vocals+other |
| bsrnn / _all | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ckpt hyper_parameters 实读 |
| bsrnn_large / _all | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | 同上，attn_enc_dim=0 |
| bsrnn_simo | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | targets=[vocals,bass,drums,other] |
| demucs | ✅ | ✅ | ❌ | ✅ | ⚠️ | ✅ | ❌ | ✅ | ✅ | ✅ | 过拟合测试 PASS（见 §7） |
| **dprnn** | ✅ | ✅ | **❌ 泄漏** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ⚠️ | `train_dprnn_musdb.py` L78-82 VAL_CLIPS 全在 train |
| mel_roformer_denoise | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | yaml: dim 384 depth 6 target dry |
| mel_roformer_denoise_aggr | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | 同架构，激进 ckpt |
| mel_roformer_dereverb | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | instruments=[noreverb,reverb] |
| mel_roformer_dereverb_echo | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | **2-stem**：dim 256 depth 8 |
| denoiser_dns48/64/master64 | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | 16 kHz 单声道，波形域无 STFT |

> **统一说明**：P8 ⚠️ 是因为「损失函数只写在 YAML 里，没有对应的训练代码入口」；
> P9 ❌ 是因为除 DPRNN 外没有任何模型有 optimizer state；
> P10 ❌ 是因为除本次 demucs 探针外，全项目没有任何一次小样本过拟合记录。

---

## 4 损失函数与优化器规则（逐模型已落到 `train_*.yaml`）

### 4.1 三条硬规则

1. **分离（频域）**：波形 L1 + 多分辨率 STFT（512/1024/2048，hop=0.25·n）。
2. **分离（时域：convtasnet / dprnn）**：SI-SDR 为主 + 波形 L1 辅助（避免音量耦合）。
3. **降噪**：时域 L1 + 频域 L1（同一 STFT 口径）；**去混响**：SI-SDR 为主 + 频域 L1 辅助。
4. **Oracle / RPCA**：`not_applicable` —— 不硬配损失与优化器（任务书要求）。

### 4.2 优化器与显存策略

| 条件 | lr | warmup | batch | 梯度累积 | 依据 |
|---|---|---|---|---|---|
| 默认 | 3e-4 | 500 | 8 | 1 | 材料 B：微调从 3e-4 起 |
| 参数 > 40 M | 3e-4 | 1000 | 4 | 2 | 8 GiB 显存实测 |
| 参数 ≥ 150 M | 3e-4 | 1000 | 2 | 4 | `bsrnn_all` 峰值 2637 MB、`bsroformer_l12` 3394 MB |
| 难训（dprnn/convtasnet/mmdenselstm） | 1e-4 | 2000 | 8 | 1 | DPRNN 实跑欠训练到 −1.72 dB |

全部用 **AdamW**（weight_decay 0.01）+ **余弦退火**（min_lr 5%）+ **梯度裁剪 5.0** + **bf16 AMP**。
> ⚠️ DPRNN 的原始训练用的是 Adam + 无 AMP（`train_dprnn_musdb.py` 现状），改 AdamW 需重跑对照，
> 因此 DPRNN 重训时**保持原优化器不变**，只修划分 —— 一次只改一个变量。

### 4.3 冻结策略（材料 B 的「先别动地基」）

- 对所有 deep 模型：**前 2 epoch 冻结 encoder / 前端 STFT 之后的第一级卷积块**，第 3 epoch 解冻。
- 已在 `init_*.yaml#freeze` 写明 `epochs_frozen: 2` 与需冻结的模块层级。
- **注意**：本项目的 20 个模型都是「加载官方权重做推理」，从未进入过训练循环，
  所以这条策略**从未被执行过一次**（P7 全 ❌）。

---

## 5 数据划分（P3，最危险的一环）

### 5.1 正确做法（已写入全部 20 份 train yaml）

```
train : MUSDB18-HQ train 的 90 首（100 首里整首留出 10 首）
valid : 那 10 首留出歌（整首，不切片）
test  : MUSDB18-HQ test 的 50 首 —— 只在最后考一次
```

**绝对不要用 test 当验证集**：那与 DPRNN 的「用 train 当 valid」是同一类错误，只是方向相反。
一旦 test 参与选模型，最终报的测试指标就是虚高的。
断言：`set(train_songs) & set(valid_songs) == ∅` 且 `set(valid_songs) & set(test_songs) == ∅`。

### 5.2 本项目已发生的错误（DPRNN）

`tools/train_dprnn_musdb.py` L78-82：

```python
VAL_CLIPS = (
    ("ANiMAL - Clinic A", "train", 140.0),
    ("Creepoid - OldTree", "train", 60.0),
    ...
)
```

三个验证片段**全部 `subset="train"`**，而训练集就是 MUSDB train 100 首 → **验证集是训练集的子集**。
后果铁证：验证 SI-SDR **+2.745 dB**，测试四轨均值 **−1.72 dB**，差 4.5 dB。
`best.pt` 是在被污染的验证集上选的，等于用训练数据选模型。

**修复**：验证片段改成 `subset="test"` 的整首留出（或 train 内整首留出 10 首），
并加断言 `set(train_songs) & set(val_songs) == set()`。

---

## 6 训练顺序与门禁

```
P1–P4（配置/清单/划分/契约）   ← 已完成（44 份 YAML）
  ↓ 门禁：所有 init yaml 的 sha256 状态必须是 verified / n/a
P5–P7（DataLoader/初始化/冻结） ← 待写训练入口（当前只有 dprnn 有）
  ↓ 门禁：小样本过拟合测试 PASS
P8–P9（损失/优化器）           ← 已定义在 train yaml
  ↓ 门禁：200 步内 loss 降到 <10%
P10（评估/归档）               ← 每模型跑 benchmark + 写 archive
```

**当前唯一可立即开机的训练任务 = DPRNN 重训（修划分）**。
其余模型的训练入口需要新写（每个架构一套），预估 0.5–1 天/模型，**不建议全做** ——
理由：官方权重已经能跑出论文级指标，重训只会更差（8 GiB 显存 + 单卡）。

---

## 7 小样本过拟合测试结果（P10 的第一个 ✅）

| 项 | 值 |
|---|---|
| 模型 | `demucs`（htdemucs，41.984 M 参数） |
| 数据 | MUSDB train 前 10 首，各取前 4 s，44.1 kHz 立体声 |
| 步数 / batch | 200 / 2 |
| 优化器 | AdamW lr 3e-4 + OneCycle |
| 损失 | L1 波形 + 0.5 × 多分辨率 STFT |
| 耗时 | **68.7 s**（0.343 s/step，单卡 4070 Laptop） |
| 显存峰值 | **5450 MB**（推理只需 599.7 MB → 训练是 9.1×） |
| 首次 loss（step 1） | 0.02014 |
| 全量评估 loss（200 步后） | **0.00175** |
| 下降比例 | **91.31%** → **PASS**（判据：>90%） |
| 参数量自检 | 实测 41,984,456 vs 画像 41.984 M → **偏差 0.000%** |

产物：`D:\FYP_HKBU_runs\rerun_20261030_2358\overfit\{probe.log, probe_result.json}`

**这次测试暴露的一个真实问题**：训练步时 loss 在 0.002–0.024 之间抖动（单 batch 方差大），
只有「全量 10 条评估」才能看出真实收敛。→ **正式训练必须用全量验证集算 best，不能用单 batch 训练 loss。**

---

## 8 正式训练的前置条件（客观约束）

| 约束 | 现状 | 影响 |
|---|---|---|
| 磁盘 | E: 仅剩 **11.5 GB**（12.4 GB 备份包已移至 `D:\FYP_backup`） | 训练产物**必须**写 `D:\FYP_HKBU_runs\` |
| 显存 | 8 GiB（4070 Laptop） | demucs 训练已占 5.45 GB；大模型必须梯度累积 |
| 后台进程 | 会话发起的后台进程在回合结束被硬杀 | 长训练必须**双击 .bat** 或任务计划程序 |
| 时长 | DPRNN 重训 4–5 h（原 250.7 min/31,900 step） | 需要你确认后再开机 |

---

## 9 复现命令（每个模型都有）

```bash
# 1) 生成/校验全部配置（幂等，可重复跑）
python tools/_gen_training_configs.py

# 2) 小样本过拟合测试（5 分钟内）
python tools/_overfit_probe.py --model demucs --items 10 --steps 200

# 3) 正式训练（以 dprnn 为例，需先修 VAL_CLIPS）
python tools/train_dprnn_musdb.py --steps 31900

# 4) 测试集评估（只考一次）
python tools/benchmark_model_universal.py --model dprnn --subset test --duration 30

# 5) RPCA（解析模型，无训练）
python tools/benchmark_model_universal.py --model rpca --subset test --duration 30 --out-tag run
```

---

## 10 归档字段（每个模型的 `archive_fields` 已写入 train yaml）

`model, config_sha256, weight_init_sha256, git_commit, dataset_manifest_sha256, seed, steps,
best_valid_loss, test_metrics, command, started_at, finished_at`

> 归档要求：**同一目录下必须同时有**可跑的 config、可核的权重 hash、可查的命令行。
> 本次审计发现 24 份历史产物三样都缺 —— 这是「无法追溯」的根因。

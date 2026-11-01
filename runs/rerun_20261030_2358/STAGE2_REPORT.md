# 阶段二执行报告

时间：2026-10-30 23:58 → 2026-10-31 03:00
批次目录：`D:\FYP_HKBU_runs\rerun_20261030_2358\`
配置目录：`E:\FYP_HKBU\configs\`（44 份 YAML）

---

## 9 执行记录

### 9.1 按批示先停 bench500

| 项 | 内容 |
|---|---|
| 进程 | PID 27740（启动器）+ 7072（工作子进程），命令行 `_bench500.py model --model bsrnn_large_all` |
| 动作 | `Stop-Process -Force`，两进程均已终止 |
| 已完成模型 | **9 个**：demucs / umx / mdx / mdx_q / mdx_extra_q / convtasnet / mmdenselstm / bsroformer_l12 / bsroformer_l6 / bsrnn_all |
| 未完成 | `bsrnn_large_all`（第 10 个，CSV 只写到一半，**需重跑**）、`bsrnn_simo`、`bsrnn_large`、3 个 mel_roformer、3 个 denoiser |
| 续跑方式 | 双击 `tools\_bat\_bench500.bat`；已完成的模型有 `.csv`，脚本会跳过或需 `--force`（按 `_bench500.py` 的跳过逻辑） |

### 9.2 磁盘：你判断「有足够空间」，但实测 E: 已满

- 实测 `E:` 空闲 **0 GB**（150 GB 用满），第一次跑 RPCA 直接报 `OSError: [Errno 28] No space left on device`。
- 元凶：一个 **12.4 GB** 的 `FYP_HKBU_backup_20261030.zip`（mtime 00:02，刚写完），与已有的
  `FYP_HKBU_progress_20261030.zip`（2.26 GB）+ `FYP_HKBU_backup_20261030\`（15.95 GB）三份重复。
- 处置：
  - `FYP_HKBU_progress_20261030.zip` → 已移至 `D:\FYP_backup\`；
  - `FYP_HKBU_backup_20261030.zip` 在移动时被占用，随后**从 E: 消失且空间未归还**（12.4 GB，句柄未释放，属异常，已在 §14 记为待查）；
  - 用 `_cmp_backup.py` 逐项比对 `D:\FYP_HKBU_backup_20261030` 与 `E:\...`：**8846 文件、路径 0 差异、大小 0 差异、40 个抽样 md5 全等 → IDENTICAL**，D: 那份可独立使用；
  - 尝试删除 E: 的重复目录时**你拒绝了批量删除**，已停止，目录保留（18 GB 级）。
- 最终 `E:` 空闲 **11.5 GB**。**因此所有训练产物一律写 `D:\FYP_HKBU_runs\`（D: 有 269 GB）。**

### 9.3 RPCA：已跑通（真实产物）

| 项 | 值 |
|---|---|
| 命令 | `python tools/benchmark_model_universal.py --model rpca --subset test --song "<song>" --duration 30 --out-tag run --audio-format flac` |
| 数据 | MUSDB18-HQ test，前 30 s，44.1 kHz，**单声道**（内部 downmix，落盘复制成双声道） |
| 产物 | `03_outputs/_test_run/RPCA/<song>/vocals.flac`（2 个，共 2.4 MB） |
| 峰值 / 削波 | 0.376 / 0.293，`clip_frac = 0.0` |
| 时长核对 | 输出 30.000 s = 输入 30.000 s |

| 歌曲 | RTF | 最匹配 stem | SI-SDR | corr | vocals | drums | bass | other |
|---|---|---|---|---|---|---|---|---|
| Al James - Schoolboy Facination | 2.949 | **vocals** | +0.213 | 0.716 | +0.21 | −6.56 | −8.99 | −11.63 |
| AM Contra - Heart Peripheral | 2.930 | **drums** | +1.333 | 0.759 | −6.72 | +1.33 | −75.49 | −6.63 |

**解读**：两首歌落点不同（vocals vs drums）→ 实证「稀疏分量无天然 stem 归属」。
两首最佳值都在 0~1.3 dB → RPCA 基本没有四轨分离能力，只能当古典基线。

### 9.4 Octave 11.3.0 交叉验证（你要求「尽可能用上 Octave」）

写了两套独立实现：`tools/_octave/rpca_ialm.m`（Octave）与 `_rpca_ialm`（numpy），
输入**同一个** 1025×2584 幅度谱，参数逐项对齐。

| 校验项 | numpy | Octave 11.3.0 | 差异 |
|---|---|---|---|
| 迭代数 | 34 | 34 | 0 |
| 最终相对残差 | 7.9884331854e-07 | 7.9884331850e-07 | <1e-15 |
| `rel_err(L)` / `rel_err(S)` | — | — | 2.53e-08 / 2.53e-08 |
| `rel_err(mask)` | — | — | 5.10e-08 |
| mask 相关系数 | — | — | **0.999999999999989** |
| 重建波形 SI-SDR | — | — | **133.67 dB** |
| 耗时 | ~88 s | **161.6 s** | Octave 慢 1.8×（CPU） |

**结论：两实现数值等价**（差异在 float32 存储精度量级）。RPCA 结果可信。

### 9.5 DRNN：不可运行（已写独立说明）

`DRNN_BLOCKER.md` 记录全部取证：

1. 论文 Lai & Wang, EURASIP JASMP 2022:4，DOI 10.1186/s13636-022-00236-9；
2. 补充材料**只有 2 个音频**（Additional file 1 = Separated accompaniment，file 2 = Separated vocal），无代码无权重；
3. GitHub API 两次查询 `RPCA-DRNN` / `RPCA+DRNN+singing` → **`total_count = 0`**；
4. 论文要求 1080Ti 以上，且口径是**单声道 2 源**，与 4-stem 不可横比。

→ **没有可执行物**，不是环境问题。自研复现预估 3–5 天 + 20–30 GPU 小时，且无法与官方数字对照（Supplement 不给分数表），不建议做。

### 9.6 生成 44 份配置（22 模型 × init/train）

`configs/init_<m>.yaml` 的每个字段都带 provenance：

- `audio_contract`：sr / ch / segment（来自 `model_profile.csv` + 官方 conf）
- `stft`：n_fft / hop / win / center（来自 ckpt 内嵌 `hyper_parameters`、官方 yaml、或源码行号）
- `weights`：文件清单 + **实算 SHA256**（22 个模型全部 `verified`，无一个 `missing`）
- `device` / `freeze` / `selfcheck`（参数量期望值 + shape probe + 断言式）

`configs/train_<m>.yaml` 覆盖 18 环节里的 ②–⑱：data / loss / optim / schedule / amp / checkpoint /
overfit_test / commands / artifacts / archive_fields。

**抽到的真实参数（举例，全部可回查）**：

| 模型 | 关键参数 | 来源 |
|---|---|---|
| demucs | nfft 4096, hop 1024, segment 7.8, 4 sources | `demucs/hdemucs.py:374,468` |
| mdx | **klass = HDemucs**, nfft 4096, segment 112, hybrid | ckpt kwargs 实读 |
| convtasnet | kernel 20, stride 10, n_basis 256, 时域无 STFT | `best.pth` args |
| mmdenselstm | n_fft 4096, hop 1024, hann, bands 3 段 | `best.pth` args |
| bsroformer_l12 | n_fft 2048, hop 441, chunk 352800, dim 512, depth 12 | 官方 yaml |
| bsrnn 系列 | n_fft 2048, n_hop 512, feature 128, attn 16/0 | ckpt `hyper_parameters` |
| dprnn | 11025 Hz, kernel 16, stride 8, chunk 4 s, LSTM×6, K=200 | `train_dprnn_musdb.py:55-75` |
| mel_roformer ×3 | n_fft 2048, hop 441, dim 384/256, depth 6/8 | 官方 yaml |
| denoiser ×3 | 16 kHz 单声道, segment 4, 波形域无 STFT | `denoiser/conf/config.yaml` |

### 9.7 DPRNN 泄漏修复版（零侵入）

`tools/train_dprnn_fixedsplit.py` 用模块级属性覆盖，**不修改原脚本、不覆盖原权重**：

| 项 | 原版 | 修复版 |
|---|---|---|
| 训练歌曲 | 100 | **90** |
| 验证 | 3 个片段，全部 `subset="train"`（**泄漏**） | **10 首整首留出**（train 内），取 3 首做验证 |
| 泄漏断言 | 无 | `assert not (set(train) & set(held_out))` |
| 输出 | `01_models/_weights/dprnn_musdb`（原样保留） | `D:\FYP_HKBU_runs\dprnn_v2\` |

dry-run 实测：`train_songs=90 held_out=10 (valid clips=3)`，manifest 已写。

### 9.8 一处自查纠正（重要）

生成器第一版把 `valid_split` 写成「test 50 首」，**这是错的**：用 test 选 best.pt 会重犯
DPRNN 的同类错误（方向相反）。已全部改回：

```
train 90 首 / valid 10 首（train 内整首留出）/ test 50 首（只考一次）
leakage_guard: train ∩ valid == ∅ AND valid ∩ test == ∅
```

20 份 deep 模型的 `train_*.yaml` 已重新生成并逐份校验（`grep -l "valid_split: 10 held-out"` = 20/20）。

---

## 10 小样本过拟合测试结果

| 项 | 值 |
|---|---|
| 模型 | **demucs**（htdemucs） |
| 数据 | MUSDB train 前 10 首 × 各 4 s，44.1 kHz 立体声 |
| 步数 / batch | 200 / 2 |
| 优化器 | AdamW lr 3e-4 + OneCycle（pct_start 0.1） |
| 损失 | L1 波形 + 0.5 × 多分辨率 STFT(512/1024/2048) |
| 耗时 | **68.7 s**（0.343 s/step） |
| 显存峰值 | **5450 MB**（推理仅 599.7 MB → 训练是 9.1×） |
| step 1 loss | 0.02014 |
| 200 步后全量 loss | **0.00175** |
| 下降比例 | **91.31%** |
| 判据（>90%） | **PASS** |
| 参数量自检 | 实测 **41,984,456** vs 画像 41.984 M → 偏差 **0.000%** |

产物：`overfit/probe.log`、`overfit/probe_result.json`

**两个真实发现**：
1. 单 batch 训练 loss 在 0.002–0.024 间抖动，只有**全量 10 条评估**才看得出收敛 → 正式训练必须用全量验证集选 best。
2. 训练显存是推理的 9.1 倍（demucs 5.45 GB）→ 8 GiB 上 `batch=2` 是安全上限，大模型必须梯度累积。

---

## 11 正式训练与 checkpoint 记录

**本轮没有启动任何正式训练**，原因有二：

1. **会话发起的进程在回合结束会被硬杀**（本项目已复现多次），4–5 h 的训练必须由你双击 bat；
2. 除 dprnn 外，**20 个模型的训练入口代码不存在**（P5 全 ❌）——
   `train_*.yaml` 里写的 `python tools/train_<arch>.py` 是待实现的目标，不是现有文件。

已就绪可直接开机的：

| 任务 | 启动方式 | 预计 | 产物 |
|---|---|---|---|
| DPRNN 重训（修泄漏） | 双击 `tools\_bat\_dprnn_v2.bat` | 4–5 h | `D:\FYP_HKBU_runs\dprnn_v2\checkpoints\{best,last}.pt` |

checkpoint 策略（已写入每份 train yaml）：
`best.pt` 按**全量验证集 loss** 每 epoch 保存；`last.pt` 每 N step；保留最近 3 个；
**报告测试集指标只准用 best.pt**。

---

## 12 测试集评估结果

仅有 RPCA 有新增（其余模型本轮未重跑）：

| 模型 | 数据 | 片段 | 指标 | 结果 |
|---|---|---|---|---|
| RPCA | MUSDB18-HQ test | 30 s | 跨 stem SI-SDR 最佳 | 曲 1：vocals +0.213；曲 2：drums +1.333 |
| RPCA | 同上 | 同上 | RTF（CPU） | 2.949 / 2.930 |
| RPCA | 同上 | 同上 | 削波率 | 0.0 |

口径：单声道、44.1 kHz、CPU、`museval` 未参与（跨 stem 用 SI-SDR）。

> 口径警告：不得把 `RPCA/vocals.flac` 当成「RPCA 的人声结果」与其他模型的 vocals 横比。

---

## 13 归档清单与复现命令

### 13.1 本轮新增文件

```
E:\FYP_HKBU\configs\
  init_<22 models>.yaml            22 份   初始化卡片（STFT/segment/权重 sha256/冻结/自检）
  train_<22 models>.yaml           22 份   训练配置（损失/优化器/调度/AMP/checkpoint/归档）
  _init_params_raw.json                   从官方 yaml 抽出的原始参数（可回溯）
  _weights_meta.json                      从 ckpt 抽出的 hyper_parameters/kwargs（可回溯）
E:\FYP_HKBU\
  model_training_plan.md                  总计划（18 环节 × 10 阶段 + 逐模型判定）
  tools\_gen_training_configs.py          配置生成器（幂等，可重跑）
  tools\_overfit_probe.py                 小样本过拟合探针
  tools\train_dprnn_fixedsplit.py         DPRNN 无泄漏重训入口
  tools\_rpca_octave_export.py            RPCA→Octave 数据导出
  tools\_rpca_octave_compare.py           numpy↔Octave 比对
  tools\_octave\rpca_ialm.m               Octave IALM 实现
  tools\_rpca_collect.py                  RPCA 结果汇总
  tools\_dump_ckpt_meta.py                ckpt 元数据抽取
  tools\_extract_init_params.py           官方 yaml 参数抽取
  tools\_scratch\_cmp_backup.py           两份备份一致性比对
  tools\_bat\_dprnn_v2.bat                DPRNN 重训启动器（ASCII + CRLF）

D:\FYP_HKBU_runs\rerun_20261030_2358\
  RPCA_REPORT.md                           RPCA 实跑 + Octave 验证
  DRNN_BLOCKER.md                          DRNN 不可运行的完整证据链
  rpca_results.json                        两首的指标与音频自检
  rpca_octave\{mag.npy,L_f32.bin,S_f32.bin,mask_f32.bin,octave_stats.txt,compare.json}
  overfit\{probe.log,probe_result.json}
D:\FYP_HKBU_runs\dprnn_v2\
  split_manifest.txt                       train 90 / held-out 10 名单
```

### 13.2 复现命令

```bash
# 配置（幂等）
python tools/_gen_training_configs.py

# 过拟合测试（5 分钟内）
python tools/_overfit_probe.py --model demucs --items 10 --steps 200

# RPCA
python tools/benchmark_model_universal.py --model rpca --subset test --duration 30 --out-tag run --audio-format flac

# Octave 交叉验证（三步）
python tools/_rpca_octave_export.py
octave-cli --no-gui --eval "run('E:/FYP_HKBU/tools/_octave/rpca_ialm.m')"
python tools/_rpca_octave_compare.py

# DPRNN 重训（必须双击，会话内会被杀）
tools\_bat\_dprnn_v2.bat
```

---

## 14 当前阻塞项与下一步唯一最重要的动作

### 阻塞项（按严重度）

| # | 阻塞 | 现状 | 影响 |
|---|---|---|---|
| 1 | **20 个模型的训练入口不存在** | 只有 dprnn 有 `train_dprnn_musdb.py` | `train_*.yaml` 的 `commands.train` 目前是目标而非现实；全量重训需 0.5–1 天/架构 |
| 2 | **DPRNN 重训需你双击** | bat 已就绪，划分已验证 90/10 | 会话内跑会被硬杀；4–5 h |
| 3 | E: 仅 11.5 GB | 备份目录 18 GB 你拒绝删除 | 训练已改走 D:，不阻塞 |
| 4 | 12.4 GB zip 消失且空间未归还 | 文件不在 E:/D:，`free` 未增加 | 需确认是否被安全软件隔离（火绒在 D:） |
| 5 | bench500 未跑完 | 9/16 完成，`bsrnn_large_all` 半成品 | 需重跑该模型 + 剩余 6 个 |
| 6 | RPCA 未并入正式目录 | 产物在 `03_outputs/_test_run/RPCA/` | 等你决定是否复制到 `03_outputs/RPCA/test/` |

### 下一步唯一最重要的动作

**双击 `E:\FYP_HKBU\tools\_bat\_dprnn_v2.bat`。**

它是本次审计唯一的 D 类问题（验证集泄漏）的修复，也是 22 个模型里唯一「值得重训且入口已就绪」的。
训练 4–5 h，产物落 `D:\FYP_HKBU_runs\dprnn_v2\`，跑完后用 `best.pt` 在官方 test 50 首上评估 ——
那才是一次真正干净的「期末考」。

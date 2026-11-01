# 模型 Checkpoint 资产审计报告

> 项目：HKBU FYP · 音乐源分离 + 语音降噪
> 审计日期：2026-10-30 ｜ 审计方式：**只读**（未移动、未删除、未改名任何权重）
> 产物目录：`04_reports/00_shared/docs/checkpoint_audit/`

---

## 0. 一句话结论

**18 个有权重的模型里，只有 4 组权重能拿出"官方推荐"的书面依据；6 组是社区训练、经官方渠道分发的权重；1 组（DPRNN）是自训。原先缺失的 4 个 checkpoint 已于 2026-10-30 全部补齐，现在 61 个本地权重全部实算 SHA256（13.60 GiB），其中 5 个能用"文件名内嵌 hash"自证（新增的 `valentini_nc-93fc4337.th` 也自证），其余 56 个没有任何官方 hash 可比对。**

> **变更记录（2026-10-30 21:30）** —— 本次按用户要求执行 D4「全部下载」，以下 4 个此前标 `not downloaded` 的 checkpoint 已落盘并实算哈希。**只增不改**：原有 57 条的哈希、体积、判定一字未动。
>
> | checkpoint | 落盘路径 | 字节数 | SHA256 前 16 位 | 自证 |
> |---|---|---|---|---|
> | `model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt` | `_weights/BS-RoFormer/` | 1,007,816,988 | `21b9d0958e35b8eb` | 否 |
> | `MelBandRoformer_KJ.ckpt`（清单名 `MelBandRoformer.ckpt (KimberleyJensen)`） | `_weights/BS-RoFormer/` | 913,106,900 | `87201f4d31afb5bc` | 否 |
> | `model_bs_polarformer_float16.ckpt` | `_weights/BS-RoFormer/` | 102,410,301 | `fc8b72c3beb92caa` | 否 |
> | `valentini_nc-93fc4337.th` | `_weights/denoiser/` | 243,263,941 | `93fc4337fb425758` | **是**（文件名后缀 `93fc4337` = 实算前缀） |
>
> 连带修改：`checkpoint_inventory.csv` 4 行补 `sha256/size_bytes/size_mb/size_check/note`；`_sha256_local.csv` 由 56 行增至 60 行（+1 个 `onnx_A.zip` 共 61）；本文 §0/§1/§2 的计数同步更新。**这 4 个权重的"官方推荐"判定不变，仍为 `NO`** —— 下载不等于获得推荐依据，三份 Mel/Polar 权重至今没有任何 README 或 CLI 把它们写成默认。

---

## 1. 审计方法（可复查）

| 步骤 | 做法 | 证据 |
|---|---|---|
| ① 建清单 | 读 `MODEL_REGISTRY.md`、两个板块 `README.md`、`tools/benchmark_model_universal.py::REGISTRY`、`tools/_denoise_registry.py`，再对 `01_models/separation/` 与 `denoising/` 实际目录逐一核对 | `model_inventory.csv`（22 行） |
| ② 查权重 | `find 01_models/_weights` 全量枚举，按扩展名筛 `.ckpt/.th/.pth/.pt/.onnx` | 60 个 + `onnx_A.zip` = **61** |
| ③ 算 hash | 逐文件流式 SHA256（16 MB 块），记录字节数 | `_sha256_local.csv`（60 行 + 1 个 zip） |
| ④ 找官方口径 | 读各上游仓库 README / `docs/pretrained_models.md` / `LICENSE` / `pretrained.py` | 见 `checkpoint_inventory.csv` 的 `evidence_path` 列 |
| ⑤ 查下载缓存 | `~/.cache/huggingface/hub/` 与项目内 `torch/hub/checkpoints` | HF 缓存有 `models--adefossez--HTDemucs` |
| ⑥ 合并 | `tools/_audit_checkpoints.py` 把实测 hash/大小 与人工整理的元数据 join | 重跑即重建两份 CSV |

> 说明：第 ⑤ 步查到的 HF 缓存里是 `955717e8.safetensors`（84,025,440 B），与 `_weights` 里的 `.th`（84,141,911 B）**是同一权重的两种序列化**。两者不是重复下载错误，是两条不同的分发通道。

---

## 2. 覆盖率与完整性

| 检查项 | 结果 |
|---|---|
| 本地 checkpoint 文件 | **61 个**（60 个权重 + 1 个 `onnx_A.zip`） |
| 总体积 | **13.60 GiB**（60 个权重） + 105 MiB（ONNX 包，110,359,032 B） |
| 已实算 SHA256 | **61 / 61** |
| 清单覆盖 | 磁盘文件 **100% 出现在 `checkpoint_inventory.csv`**（程序化校验，缺失 0） |
| 与官方声明大小比对 | **0 处不一致**（BS-RoFormer 两个 ckpt 声明 639,331,213 / 393,068,365 B，实测完全一致） |
| 可用文件名自证 hash | **5 / 61**：`955717e8-8726e21a.th`、`dns48-11decc9d8e3f0998.th`、`dns64-a7761ff99a7d5bb6.th`、`master64-8a5dfb4bb92753dd.th`、`valentini_nc-93fc4337.th` —— 文件名后缀与实算 SHA256 前 8/16 位**逐一吻合** |
| 内容重复的权重 | **0 组**（60 个文件的 hash 两两不同；`bsrnn-opt` 的 `bass/drums/other/vocals` 虽同名但内容不同） |
| 未下载的 checkpoint | **0 个**（2026-10-30 已补齐此前缺失的 4 个；`sha256` 列 61/61 非空） |

---

## 3. "官方推荐"判定（严格按 4 级优先级）

判定标准（用户给定）：P1 = README/模型卡明写 recommended/best/default；P2 = 官方 CLI 默认模型；P3 = 官方排行榜/竞赛最佳提交；P4 = 论文主结果权重。**四者皆无 → "无官方推荐，仅有可用权重"。**

### 3.1 有官方推荐的（仅 4 组）

| 模型 | checkpoint | 判定 | 依据原文 |
|---|---|---|---|
| Demucs | `955717e8-8726e21a.th` | **P1** | README line 222：`htdemucs` … **Default model**；line 57：`htdemucs model now used by default` |
| BSRNN | `simo-bsrnn-opt/separator.ckpt` | **P1** | README：*"we encourage to consider this variant **if achieving maximum performance is the goal**"* |
| BSRNN | `bsrnn-opt/{vocals,drums,bass,other}.ckpt` | **P2** | README line 111：`model_dir` (default: `bsrnn-opt`) |
| MDX-Net | `mdx/{4 个}.th` | **P3** | demucs README line 228：`mdx`: … **winning model on track A at the MDX challenge** |

### 3.2 无官方推荐、但列入官方清单的（7 组）

这些权重的出处完全正当（官方 release / 官方 Zenodo / 官方 HuggingFace），但**清单里没有任何 recommended/best/default 标记**，因此按判定规则**不能写成"官方推荐"**：

| 模型 | 权重 | 官方渠道 | 正确表述 |
|---|---|---|---|
| BS-RoFormer-L12 | `ep_317_sdr_12.9755` | TRvlvr/model_repo release（MSST 官方清单引用） | 社区训练（viperx），官方清单收录，**无推荐标记** |
| BS-RoFormer-L6 | `ep_937_sdr_10.5309` | 同上 | 同上 |
| BSRNN | `bsrnn-large/{4 个}.ckpt` | Zenodo 17516442 | 官方发布，**无推荐标记** |
| Mel-RoFormer-Denoise | `..._sdr_27.9959` / `..._aggr_27.9768` | MSST release v.1.0.7 | 社区训练（aufr33），官方 release 分发，**无推荐标记** |
| Mel-RoFormer-Dereverb | `..._anvuew_sdr_19.1729` | HuggingFace（anvuew） | 社区训练，**无推荐标记** |
| Mel-RoFormer-Dereverb-Echo | `..._sdr_10.0169` | HuggingFace（Sucial） | 社区训练，**无推荐标记** |
| MDX-Net | `mdx_extra/{4 个}.th` | demucs 模型包 | 4-submission ensemble，**无推荐标记** |

### 3.3 明确被"降级"的（4 个量化 ckpt）

`mdx_q` / `mdx_extra_q` 共 8 个文件，官方 README 原文：*"mdx_q is the quantized model, **smaller but maybe a bit less accurate**"* → 这是**负面表述**，不是推荐。本项目实测印证：`mdx_extra_q` 8.37 dB vs `mdx_extra` 8.96 dB（−0.59）。

### 3.4 无任何官方推荐的（Early / baseline）

Conv-TasNet（3 变体）、MMDenseLSTM、Open-Unmix、denoiser（3 个）—— 官方都是"给几个权重，不排序"。denoiser 尤其明显：`get_model()` 里 `--dns48/--dns64/--master64/--valentini_nc` 是**并列分支，且没有兜底**，不传参数直接加载失败，**根本不存在默认模型**。

---

## 4. 分类结论

### 4.1 有官方 checkpoint（13 个模型）

BSRNN（3 变体）、Demucs、MDX-Net（4 家族）、Conv-TasNet、MMDenseLSTM、Open-Unmix、denoiser（3 个）、Mel-RoFormer（3 个）—— 全部本地已有，且下载完整（大小校验 0 差异）。

### 4.2 只有社区权重（2 个模型 / 6 个 checkpoint）

- **BS-RoFormer-L12 / L6**：`ep_317`、`ep_937` 由 **viperx** 训练
- **Mel-RoFormer-Denoise / Dereverb / Dereverb-Echo**：由 **aufr33 / anvuew / SUC-DriverOld** 训练

> ⚠️ **非官方，引用需注明**。论文里必须写"权重由 XXX 训练，经 ZFTurbo MSST / HuggingFace 分发，非论文作者原始权重"。这 6 个权重是本项目分离与降噪两条主线的核心，**这个标注不是可选项**。

### 4.3 自训权重（1 个模型）

**DPRNN**：官方仓库只发 `wsj0-mix` / `librispeech`（语音分离）权重，**没有 MUSDB18 音乐权重**。本机 `best.pt` / `last.pt` 全部来自 `tools/train_dprnn_musdb.py`（31900 step）。
- 指标四轨全为负（−1.72 dB），**只能作"端到端时域方法在 8 GiB 单卡上欠训练"的负面证据**
- 引用时必须标"自训，非官方发布"

### 4.4 没有 checkpoint（4 个模型）

| 模型 | 原因 |
|---|---|
| Oracle-IRM | 解析法，零参数 |
| RPCA | 迭代算法（Inexact-ALM），零参数 |
| RPCA+DRNN | 论文（Lai & Wang 2022）**从未公开代码与权重** |
| Pac-HuBERT-SEP | MERL **未放出代码与权重** |

后两个必须写成"官方未公开"，**不能写成"我们没找到"**。

### 4.5 官方提供但此前缺失（1 个，已于 2026-10-30 补齐）

| checkpoint | 状态 | 影响 |
|---|---|---|
| `valentini_nc-93fc4337.th` | **已下载**（243,263,941 B，SHA256 `93fc4337fb425758…`，文件名后缀自证） | 这是 denoiser 官方唯一的**非因果**模型。此前缺它就没有"非因果上界 / 离线场景天花板"的对照；现已具备，但**尚未纳入任何评测表**，要用需单独跑一轮 |

---

## 5. 许可证风险

| 等级 | 模型 / 权重 | 许可证 | 风险说明 |
|---|---|---|---|
| 🔴 **高** | **denoiser 全部 3 个 ckpt** | **CC-BY-NC 4.0（Attribution-NonCommercial）** | **禁止商用**。本地 `LICENSE` 文件首行即为该协议。任何"可部署 / 可产品化 / 落地"的表述若涉及这三个权重，都属于误述。降噪主线的最强结果（+9.49~+9.86 dB）恰好全落在这里 |
| 🟠 中 | Conv-TasNet、MMDenseLSTM | 原仓库 MIT，但**镜像仓库 `DNN-based_source_separation` 没有 LICENSE 文件** | 权重是社区镜像转换的，**许可证处于真空状态**。论文只能写"代码 MIT，权重许可未声明" |
| 🟠 中 | BS-RoFormer（2）、Mel-RoFormer（4） | 分发仓库 MIT，**权重本身无单独声明** | 社区训练的权重挂在 MIT 框架下，但训练者未声明权重许可。商用前必须逐个联系或不使用 |
| 🟠 中 | BSRNN（9 个文件） | 仓库 `LICENSE.txt` = MIT，但**Zenodo 记录的许可证未在本地留档** → unverified | 数据集本身（MUSDB18）也是"学术研究用途"，叠加限制 |
| 🟡 低 | Open-Unmix（4） | 仓库 MIT；**`umxhq` 权重许可未声明** | 注意区分：README line 86 说 `umxl` 才是默认模型且权重为 **CC BY-NC-SA 4.0**；本项目用的是 `umxhq`，不是 `umxl` |
| 🟢 干净 | Demucs、MDX-Net 家族、mdx-net submissions | **MIT**（本地 LICENSE 文件确认） | 全项目许可证最干净的一组 |
| 🟢 自有 | DPRNN（自训） | 代码 Apache-2.0，权重归本项目 | 无第三方限制 |

**结论**：若论文/答辩出现"可用于产品"的表述，**必须把 denoiser 三个权重排除在外**；降噪章应改为"研究用途，权重为 CC-BY-NC 4.0"。

---

## 6. 无法验证项（明确写出，不编造）

| # | 项目 | 为什么无法验证 |
|---|---|---|
| 1 | **56 个权重的官方 SHA256** | 除 Demucs、3 个 denoiser 与新增的 `valentini_nc` 外，官方均未发布 hash。本次只能建立"本地基线"（下次重下可对比），**不能证明与官方原件一致** |
| 2 | **Zenodo 17516442 的许可证** | 记录页未在本地留档，离线无法读取 → BSRNN 权重的法律状态为 `unverified` |
| 3 | **`bsrnn-large.zip` 对应 `docs/analysis.md` 哪一行** | README 未说明；`analysis.md` 里 `large` 有两行（9.2 / 9.5 vocals），无法判定发布的是哪一个 |
| 4 | **Mel-RoFormer 权重文件名里的数字含义** | `sdr_19.1729`、`sdr_10.0169`、`sdr_27.9959` 在 MSST 文档中**无解释**，不能当作 SDR 引用 |
| 5 | **denoiser 的官方指标** | README **没有任何指标表**，`--no_pesq` 只是开关。论文数字无法在本地核实 |
| 6 | **各权重的训练数据构成** | 只有 Demucs（"MusDB + 800 songs"）与 BSRNN（MUSDB18-HQ 100 首）在 README 明确写出；其余全部 `unverified` |
| 7 | **`onnx_A.zip` 与 PyTorch 权重的一致性** | 从未解压、从未做过导出前后数值比对 |
| 8 | **`mdx_extra` 4 个 ckpt 各对应哪个 submission** | demucs 只给 hash 文件名，无 submission 映射表 |
| 9 | **所有模型的导出/部署可行性** | 本项目**零导出产物**（无 ONNX / TorchScript / TFLite），全部为 `未验证` |

---

## 7. 建议动作（按优先级）

| # | 动作 | 理由 | 验收标准 |
|---|---|---|---|
| 1 | **在论文里修正 6 个社区权重的表述** | BS-RoFormer ×2 + Mel-RoFormer ×4 是本项目主结果的核心，目前文档只在板块 README 里小字标注 | 正文/图表脚注出现"非官方权重，由 XXX 训练" |
| 2 | ~~**补下 `valentini_nc-93fc4337.th`**~~ ✅ **2026-10-30 已完成** | 官方唯一非因果 denoiser，缺失导致"离线天花板"无法讨论 | 已落 `_weights/denoiser/`，243,263,941 B，SHA256 `93fc4337…`；库存表该行已从 `not downloaded` 变为有 hash |
| 3 | **把 denoiser 的 CC-BY-NC 写进降噪章的限制节** | 这是全项目唯一"禁止商用"的许可证，且承载最强结果 | `02_denoising/docs/` 出现明确许可证声明 |
| 4 | **把 61 条 SHA256 并入复现链** | 目前 `reproduce.py --check` 只校验文件存在，不校验内容 | `reproduce.py --check` 增加 hash 比对，或新增 `verify_weights.py` |
| 5 | **验证 `onnx_A.zip` 与 PyTorch 权重的一致性** | 这是唯一"看起来能上非 PyTorch 运行时"的路线，也是阶段 8（导出部署）最省力的起点 | 同输入下 ORT 与 PyTorch 输出 max\|Δ\| ≤ 1e-4 |
| 6 | **Conv-TasNet 三变体补齐排序** | 官方 SDR 表不区分变体，当前"选 8sec_L64"缺少依据 | 3 变体同片段跑完，得到可排序的 SDR |

---

## 8. 产物清单

| 文件 | 内容 | 行数 |
|---|---|---|
| `model_inventory.csv` | 22 个模型：任务 / 仓库 / commit / 配置 / 采样率 / 声道 / 输出轨 / 证据路径 | 22 |
| `checkpoint_inventory.csv` | 61 条 checkpoint：来源 / URL / SHA256 / 大小 / 训练数据 / 指标 / 许可证 / 推荐判定 / 证据路径 | 61 |
| `checkpoint_comparison.md` | 逐模型对比表 + 推荐 + 优劣（9 节） | — |
| `_sha256_local.csv` | 60 个文件的实算 hash（原始记录，供复核；+1 个 `onnx_A.zip` 共 61） | 60 |
| `checkpoint_audit_report.md` | 本文件 | — |

复现命令：

```bash
PY="C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe"

# 1) 重算全部本地 hash（约 20 秒，11.5 GB）
$PY -X utf8 tools/_audit_checkpoints.py   # 若 _sha256_local.csv 已存在则直接复用
# 2) 重建两份清单 + 覆盖率校验
$PY -X utf8 tools/_audit_checkpoints.py
```

> 脚本末尾会打印三项自检：`size MISMATCH`（应为 0）、`local weight files not described`（应为 0）、以及每个文件是否被清单覆盖。本次结果：**0 / 0 / 全覆盖**。

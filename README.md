# FYP_HKBU — 实时音乐源分离 / 深度降噪

香港浸会大学 FYP ｜ **板 1**：音乐源分离（MUSDB18-HQ 四轨）｜ **板 2**：语音降噪（DNS-Challenge / Valentini-Botinhao）；
两者再串成 **级联**（先降噪再分离）端到端实验。

交付日期 **2026-10-27** ｜ 文档版本 **2026-09-27** ｜ 目录结构：**2026-09-23 三级重组（板块 → 模型）**

---

## ⓪ 只想复现一张图 / 一个产物？（30 秒上手）

```bash
PY="C:/Users/jerry/.workbuddy/binaries/python/envs/fyp_audio/Scripts/python.exe"

$PY tools/reproduce.py --check                     # 复现链自检：脚本在否 / 产物在否 / 53 论文图全覆盖
$PY tools/reproduce.py --list                      # 全部复现目标（28 个，标出轻量 / 重跑）
$PY tools/reproduce.py --figure fig-arch-demucs    # ★ 复现任意一张论文图（按 53 图 id）
$PY tools/reproduce.py --run report.dashboards     # 复现某产物家族（三块看板）
$PY tools/reproduce.py --all-report                # 重建全部报告产物（**不跑推理**）
```

**完整清单（图 → 命令 → 产物落点）见 `04_reports/_shared/docs/REPRODUCE.md`（自动生成，`--verify` 可逐字节校验）。**
含 GPU 推理的目标默认锁死，需显式 `--force-heavy` 才会跑。

---

## ① 五大模块（顶层只有这 5 项）

```
E:\FYP_HKBU\
│
├── 01_models\          ① 模型 —— 先按**板块**，再按**模型**
│   ├── separation\          板 1：14 个模型目录（RPCA / Oracle-IRM / Conv-TasNet / DPRNN /
│   │                        MMDenseLSTM / Open-Unmix / Demucs / MDX-Net / BS-RoFormer-L6/L12 /
│   │                        BSRNN-opt / BSRNN-large / BSRNN-SIMO）+ README.md（模型卡）
│   ├── denoising\           板 2：6 个模型目录（denoiser-dns48 / dns64 / master64 /
│   │                        Mel-RoFormer-Denoise / -Dereverb / -Dereverb-Echo）+ README.md
│   ├── _third_party\        官方 / 社区仓库共享层（各模型 `code\` 是指向此处的目录联接）
│   ├── _weights\            ★ 权重的唯一物理落点（其他地方的 `weights\` 都是链接）
│   ├── _selfimpl\           自研算法索引（RPCA / NMF / ICA / HPSS / Oracle 掩码）
│   ├── MODEL_REGISTRY.md    指定模型在位状态 / 可运行性 / 精度总表
│   └── README.md
│
├── 02_databases\       ② 数据（只读）
│   ├── MUSDB18-HQ\         train(100) / test(50) / _smoketest
│   ├── DNS-Challenge\      clean / noise / dev_testset / impulse_responses（60248 条 RIR）
│   └── Valentini\          板 2 降噪评测集（824 noisy + 824 clean 配对，48 kHz 单声道）
│
├── 03_outputs\         ③ 产物 —— 每个模型一个独立文件夹
│   ├── <模型名>\
│   │   ├── test\            MUSDB18 test 50 首整曲分离结果（每首一个子目录）
│   │   └── stage0_gate\     阶段 0 门禁单文件输出（仅板 2 模型有）
│   ├── _cascade\           级联实验中间产物
│   └── _reverb\            混响 / 回声实验中间产物
│
├── 04_reports\         ④ 报告 —— **按板块分文件夹**，每板块下再分 `docs / figures / data / html`
│   ├── separation\         板 1 · 分离（阶段 1-4）
│   ├── denoiser\           板 2 · 降噪 + 去混响 / 去回声（阶段 5-7）
│   ├── cascade\            级联实验（阶段 6-7）
│   ├── _shared\            跨板块共用（总纲、模型画像、14 张架构图、论文图包、口径章节）
│   └── slides\             答辩材料（阶段 8）
│
└── tools\              ⑤ 工具
    ├── *.py                110 个脚本（唯一路径入口 `paths.py`；一键复现入口 `reproduce.py`）
    ├── _bat\               Task Scheduler 启动器（长任务防会话硬杀）
    ├── _logs\              运行日志（124 项）
    └── _scratch\           临时与缓存（.cache = TORCH_HOME / HF_HOME）
```

### 模块职责速查

| 模块 | 放什么 | 不放什么 |
|---|---|---|
| `01_models` | 模型代码、权重、模型卡、注册表 | 运行产物、报告 |
| `02_databases` | 原始数据集（只读） | 分离结果 |
| `03_outputs` | **每个模型自己的 stem wav** | 跨模型汇总、图表 |
| `04_reports` | 报告文档、**全部图表**、**全部数据 json/csv** | 大体积 wav |
| `tools` | 脚本、日志、缓存、批处理启动器 | 任何交付物 |

---

## ② 交付物索引（阶段 1–8）

| 阶段 | 交付物 | 落点 | 复现目标 |
|:-:|:--|:--|:--|
| 1-2 | 模型本体画像（参数量 / FLOPs / 时延） | `_shared/data/model_analysis/model_profile.csv` | `profile.measure` |
| 2 | **14 张架构原理图** + 画像图 | `_shared/figures/model_arch/arch_*.png` | `arch.figures` |
| 3 | 分离精度主表（MD + 300 dpi 重绘） | `separation/docs/MEDIAN_TABLE_REDRAWN.md` | `sep.table` |
| 3 | 中位条形 / 逐轨 / Pareto 三图 | `separation/figures/comparison/fig_median_*.png` | `sep.median_figs` |
| 3 | 5 张信号级频谱 / 波形面板 | `separation/figures/audio_analysis/fig*.png` | `sep.panels` |
| 4 | 实机成本 7 图（耗时 / RTF / Pareto） | `separation/figures/figs_time/fig*.png` | `cost.figures` |
| 4 | 混响 / 回声退化 + RIR + 一页汇总图 | `separation/figures/comparison/fig_reverb_*.png` 等 | `reverb.figures` / `stage4.summary` |
| 4 | 阶段 4 结论 | `separation/docs/STAGE4_SUMMARY.md` | — |
| 5 | 降噪双口径评测（16k / 44.1k，16575 格） | `denoiser/data/denoise_eval_*.json` | 🔒 `denoise.eval` |
| 5 | 降噪结果 4 图（抑制 / 合成增益 / 域反转 / dry-wet） | `denoiser/figures/fig_denoise_*.png` | `denoise.figures` |
| 5 | 采样率契约 bug 复盘 / 域外探针 | `denoiser/docs/P19_*.md`、`T5_7_*.md` | 🔒 `denoise.ood` |
| 6 | 级联 ΔSDR 主矩阵 + 净动作分解 | `cascade/figures/fig_cascade_*.png` | `cascade.figures` |
| 6 | 级联结论（**负结果照报**） | `cascade/docs/T6_CASCADE_DENOISE_BEFORE_SEPARATION.md` | 🔒 `cascade.eval` |
| 7 | **三块自包含离线看板** | `_shared/html/*.html`、`denoiser/html/`、`cascade/html/` | `report.dashboards` |
| 7 | 4 份数据摘要（数字零手填） | `_shared/docs/summaries/*.md` | `report.summaries` |
| 8 | **53 张论文图** + 清单 + 两板图注 | `_shared/figures/paper/` | `paper.figures` |
| 8 | 口径与差异说明章节 | `_shared/docs/PAPER_SCOPE_AND_DIVERGENCE.md` | `paper.scope` |
| 8 | 答辩 slides（24 页离线 HTML） | `slides/defense_slides.html` | `report.slides` |
| 8 | **本复现指南** | `_shared/docs/REPRODUCE.md` | `--readme` |

> 🔒 = 含 GPU 推理，跑一次数小时；已归档结果**不重跑**，只做判据与图注复核。

---

## ③ 模型文件夹里的 `weights/` 是什么

**不是拷贝，是链接。** 为了让「一个模型一个文件夹」成立，同时不把权重复制一遍：

| 权重形态 | 链接方式 | 特性 |
|---|---|---|
| 目录（如 `BSRNN/bsrnn-large/`） | NTFS **目录联接**（`mklink /J`） | 秒级、零拷贝、无需管理员权限 |
| 单个文件（如 `model_bs_roformer_ep_317_*.ckpt`） | NTFS **硬链接**（`mklink /H`） | 同一 inode，`-rw-r--r-- 2`；删任一侧都不丢数据 |

因此：**物理落点始终唯一（`01_models/_weights/`），脚本不需要改任何权重路径。**

---

## ④ 报告按板块归档

| 文件夹 | 归属 | 覆盖的计划阶段 |
|---|---|---|
| `04_reports/separation/` | 板 1 · 分离 | 阶段 1-4：模型画像、14 张架构图、频谱面板、混响鲁棒性 |
| `04_reports/denoiser/` | 板 2 · 降噪 | 阶段 5-7：降噪双口径评测、去混响、去回声 |
| `04_reports/cascade/` | 级联 | 阶段 6-7：分离输出 → 降噪输入 |
| `04_reports/_shared/` | 跨板块 | 总纲、模型画像、架构图数据、论文图包、口径章节 |
| `04_reports/slides/` | 答辩 | 阶段 8 |

每个板块下固定四类子目录：`docs/`（md 报告）、`figures/`（png）、`data/`（json/csv）、`html/`（自包含看板）。

---

## ⑤ 路径中枢（唯一真理源）

**所有脚本不再自己拼路径**，统一从 `tools/paths.py` 取：

```python
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths
_paths.setup_env()                       # 自动设 TORCH_HOME / HF_HOME / MPLCONFIGDIR

_paths.THIRD_PARTY, _paths.WEIGHTS, _paths.MUSDB18_ROOT, _paths.DNS_ROOT, _paths.VALENTINI_ROOT
_paths.OUTPUTS, _paths.REPORTS
_paths.board_dir("denoiser")             # 04_reports/denoiser
_paths.board_sub("separation", "figures")
_paths.model_dir("BS-RoFormer-L12")      # 01_models/separation/BS-RoFormer-L12
_paths.out_dir("Demucs")                 # 03_outputs/Demucs
_paths.LOGS, _paths.SCRATCH, _paths.BAT_DIR
```

**旧名兼容**：`DOCS / HTML / FIGURES / DATA` 四个常量现在一律指向 **板 1（separation）**；
板 2 用 `DEN_DOCS / DEN_FIGURES / DEN_DATA / DEN_HTML`，共用资产用 `SHR_*`。
**以后目录再调整，只改 `tools/paths.py` 一个文件。**

---

## ⑥ 常用命令

```bash
PY="C:/Users/jerry/.workbuddy/binaries/python/envs/fyp_audio/Scripts/python.exe"

# —— 自检（先跑这两个，确认结构没坏）——
$PY tools/paths.py                              # 路径中枢自检
$PY tools/selfcheck_project.py                  # 模块 / 模型 / 数据集全量自检
$PY tools/reproduce.py --check                  # 复现链自检（脚本 / 产物 / 53 图覆盖）

# —— 复现（轻量，不跑推理）——
$PY tools/reproduce.py --figure fig-arch-demucs # 任意一张论文图
$PY tools/reproduce.py --all-report             # 重建全部报告产物

# —— 单产线（等价于 --run <目标>）——
$PY tools/_measure_model_profile.py             # 模型画像 → model_profile.csv
$PY tools/_extract_model_graph.py --models all  # 抓真实层级树 → graph_*.json
$PY tools/_plot_model_arch.py                   # 渲染 14 张架构图
$PY tools/_build_dashboards.py --only all       # 三块看板（一个入口建三块）
$PY tools/_build_summaries.py --verify          # 4 份摘要（重建并与磁盘比对）
$PY tools/_export_paper_figures.py --board 1 render   # 论文图包（板 1）
$PY tools/_build_paper_scope.py --verify        # 口径与差异说明章节
$PY tools/_build_slides.py --verify             # 答辩 slides

# —— 人耳聆听页（双击也行）——
start_listen.bat          # → http://127.0.0.1:8123/04_reports/separation/html/listen_compare.html
```

> ⚠️ 解释器**只能用 venv**（`fyp_audio`）。WorkBuddy 默认的 `python` 指向系统 3.13.12，没有 numpy，
> 子进程会秒退 `ModuleNotFoundError`，外层看起来像「推理失败」，实则根本没跑起来。

> ⚠️ 长任务（数小时~数天）**必须走 `schtasks`**，不能靠后台任务：Agent 会话结束会 `TerminateProcess`
> 硬杀子进程，`finally` 不执行、锁残留。启动器模板见 `tools/_bat/_sweep_launch.bat`。

---

## ⑦ 目录变更史

### 2026-09-23（第三次重组）：模型改为「板块 → 模型」

| 变更 | 从 | 到 |
|---|---|---|
| 模型按板块分组 | `01_models/<模型>/` | `01_models/<板块>/<模型>/`（板块 = `separation` / `denoising`） |
| 移除冗余层 | `<模型>/weights/`（只是链接） | 权重统一在 `01_models/_weights/` |
| 合并模型卡 | `<模型>/README.md` | 并入 `01_models/<板块>/README.md` + `model_profile.csv` |

### 2026-09-23（第二次重组）

| 变更 | 从 | 到 |
|---|---|---|
| 杂项模块撤销 | `05_misc/logs/` · `scratch/` · `*.bat` | `tools/_logs/` · `tools/_scratch/` · `tools/_bat/` |
| 报告改为按板块 | `04_reports/{docs,figures,data,html}/` | `04_reports/{separation,denoiser,cascade,_shared}/{...}/` |
| 产物按模型独立 | `03_outputs/_test_run/<模型>/` | `03_outputs/<模型>/test/` |
| 移出项目 | `05_misc/lyrics-game/`（501 MB）等 | `E:\FYP_HKBU_evicted\`（同盘 `mv`，非删除） |

> 逆向清单见 `04_reports/_shared/docs/RESTRUCTURE_2026-09-23.md` 与机器可读的 `_restructure_manifest.json`。

### 2026-09-23 事故记录（磁盘）

根目录 `.git` 曾积累 **76,427 个不可达松散对象 = 57 GB**（成因：「`git add .` 之后从未 commit」），
把 47 GB 数据集与 21 GB 推理产物全塞进对象库，导致 E 盘可用空间归零、所有脚本写入失败（ENOSPC）。
`git prune --expire=now` 已回收全部 57 GB，`.gitignore` 已补防复发规则。

---

## ⑧ 环境铁律（答辩与交接都要知道）

1. **解释器唯一**：只用 `fyp_audio` venv；版本冻结记录见 `requirements-frozen-2026-09-23.txt`。
2. **脚本只从 `paths.py` 取路径**，自己拼字面量会在目录调整时静默失效。
3. **长任务走 Task Scheduler**，绝不依赖 Agent 后台任务。
4. **图上每个数字都能追到源文件**：产物 → `04_reports/**/data/**` → 生成脚本（见 `REPRODUCE.md` §3）。
5. **负结果照报**：级联实验的负结论（前置降噪使分离变差）与去混响负结果都写进报告，不做美化。

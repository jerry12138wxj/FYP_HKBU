# REPRODUCE — 全链路复现指南（T8.5，自动生成，勿手改）

> 本文件由 `tools/reproduce.py --readme` 生成，`--verify` 可逐字节校验。
> 目标：**按本文件能复跑任一图 / 任一报告产物**。所有命令与产物路径均取自脚本本身，非手抄。

## 0. 环境（唯一解释器）

```bash
PY="C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe"
$PY tools/paths.py                 # 路径中枢自检
$PY tools/selfcheck_project.py     # 模块 / 模型 / 数据集自检
$PY tools/reproduce.py --check     # 复现链自检（脚本在否 / 产物在否 / 53 图全覆盖）
```

⚠️ **只能用上面的 venv**（`fyp_audio`）。系统 `python` 无 numpy，子进程会秒退，外层看起来像「推理失败」。
⚠️ **长任务（数小时~数天）必须走 Task Scheduler**（`tools/_bat/_sweep_launch.bat`），后台任务会随 Agent 会话结束被硬杀。

## 1. 复现任意一张论文图

```bash
$PY tools/reproduce.py --figure <论文图 id>        # 例：--figure fig-arch-demucs
```

全部 **53** 张论文图 → 复现归属如下（`脚本` 列即该图的生成脚本；`🔒` 表示该图源脚本含推理/重算，**已归档不再重跑**，只做 300 dpi 判据与图注）：

| 图 id | 板 | 标题 | 组 | dpi 达标 | 复现归属 |
|:--|:-:|:--|:--|:-:|:--|
| `fig-acc-bars` | 1 | 分模型 SDR 中位条形图 | G-ACC | ✓单栏 | `sep.median_figs` |
| `fig-acc-dsdr` | 1 | 与基线对照的 ΔSDR | G-ACC | ✓单栏 | 🔒 不重跑 · `compare_separation_methods.py` |
| `fig-acc-main-table` | 1 | 分离精度主表（重绘） | G-ACC | ✓单栏 | `sep.table` |
| `fig-acc-pareto` | 1 | 精度—速度 Pareto | G-ACC | ✓单栏 | `sep.median_figs` |
| `fig-acc-per-stem` | 1 | 逐轨 SDR 中位 | G-ACC | ✓单栏 | `sep.median_figs` |
| `fig-arch-bsrnn` | 1 | BSRNN（oBSRNN） | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-bsroformer` | 1 | BS-RoFormer | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-convtasnet` | 1 | Conv-TasNet（时域分离） | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-demucs` | 1 | Demucs v4 / HTDemucs | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-denoiser` | 1 | denoiser（板 2） | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-dereverb` | 1 | Mel-Band-RoFormer-Dereverb (anvuew) | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-dereverb-echo` | 1 | Mel-Band-RoFormer-Dereverb-Echo (sucial) | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-dprnn` | 1 | DPRNN（自训） | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-irm` | 1 | IRM / IBM Oracle 结构（解析基线） | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-mdx` | 1 | MDX-Net (KUIELAB mdx_extra) | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-melden` | 1 | Mel-Band-RoFormer-Denoise (aufr33) | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-mmdenselstm` | 1 | MMDenseLSTM | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-rpca` | 1 | RPCA (Inexact-ALM) 流程 | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-arch-umx` | 1 | Open-Unmix (umxhq) | G-ARCH | ✓单栏 | `arch.figures` |
| `fig-cost-cumulative` | 1 | 累计耗时 | G-COST | ✓单栏 | `cost.figures` |
| `fig-cost-dist` | 1 | 耗时分布 | G-COST | ✓单栏 | `cost.figures` |
| `fig-cost-panels` | 1 | 成本多面板对比 | G-COST | ✓单栏 | `cost.figures` |
| `fig-cost-pareto` | 1 | 速度—精度 Pareto | G-COST | ✓单栏 | `cost.figures` |
| `fig-cost-rtf` | 1 | 逐曲 RTF | G-COST | ✓单栏 | `cost.figures` |
| `fig-cost-time-per-song` | 1 | 逐曲推理耗时 | G-COST | ✓单栏 | `cost.figures` |
| `fig-cost-vs-acc` | 1 | 耗时 vs 精度 | G-COST | ✓单栏 | `cost.figures` |
| `fig-echo-degradation` | 1 | 回声延迟/增益 → ΔSDR 退化曲线 | G-REV | ✓单栏 | `reverb.figures` |
| `fig-profile-params-flops` | 1 | 参数量 / FLOPs 对比 | G-PROFILE | ✓单栏 | `profile.figures` |
| `fig-profile-pareto` | 1 | 成本—容量 Pareto | G-PROFILE | ✓单栏 | `profile.figures` |
| `fig-rev-degradation` | 1 | 混响 T60 → ΔSDR 退化曲线 | G-REV | ✓单栏 | `reverb.figures` |
| `fig-rev-rir-t60` | 1 | RIR 本体与 T60 估计（已剔直达声） | G-REV | ✓单栏 | `reverb.figures` |
| `fig-spec-mixture` | 1 | 混音时频谱 | G-SPEC | ✓单栏 | `sep.panels` |
| `fig-spec-sr` | 1 | 采样率对比波形 | G-SPEC | ✓单栏 | `sep.panels` |
| `fig-spec-vocals` | 1 | 人声轨时频谱 | G-SPEC | ✓单栏 | `sep.panels` |
| `fig-spec-waveform` | 1 | 波形：混音 vs 人声 | G-SPEC | ✓单栏 | `sep.panels` |
| `fig-spec-win1024` | 1 | 窗长对比：win 1024 | G-SPEC | ✓单栏 | `sep.panels` |
| `fig-spec-win128` | 1 | 窗长对比：win 128 | G-SPEC | ✓单栏 | `sep.panels` |
| `fig-stage4-summary` | 1 | 阶段 4 答辩一页图 | G-S4 | ✓单栏 | `stage4.summary` |
| `fig-cas-decomposition` | 2 | 级联净动作分解（L1 vs L1b vs L1−L1b） | G-CAS | ✓单栏 | `cascade.figures` |
| `fig-cas-delta-matrix` | 2 | 级联 ΔSDR 主矩阵（4 SNR × 4 模型 × 6 链路） | G-CAS | ✓单栏 | `cascade.figures` |
| `fig-dn-domain-reversal` | 2 | 噪声域反转（真实噪声 vs 合成噪声） | G-DN | ✓单栏 | `denoise.figures` |
| `fig-dn-drywet` | 2 | dry/wet 强度旋钮曲线 | G-DN | ✓单栏 | `denoise.figures` |
| `fig-dn-dspec-master64-syn` | 2 | 平均谱差：master64 × synth | G-DN | ✓单栏 | 🔒 不重跑 · `_plot_denoise_spectrum_delta.py` |
| `fig-dn-dspec-master64-val` | 2 | 平均谱差：master64 × valentini | G-DN | ✓单栏 | 🔒 不重跑 · `_plot_denoise_spectrum_delta.py` |
| `fig-dn-dspec-mel-syn` | 2 | 平均谱差：mel-roformer × synth | G-DN | ✓单栏 | 🔒 不重跑 · `_plot_denoise_spectrum_delta.py` |
| `fig-dn-dspec-mel-val` | 2 | 平均谱差：mel-roformer × valentini | G-DN | ✓单栏 | 🔒 不重跑 · `_plot_denoise_spectrum_delta.py` |
| `fig-dn-metric-divergence` | 2 | 三指标分歧诊断 | G-DN | ✓单栏 | 🔒 不重跑 · `_denoise_diagnosis.py` |
| `fig-dn-spec-master64-syn` | 2 | 频谱前后对比：master64 × synth | G-DN | ✓单栏 | 🔒 不重跑 · `_plot_denoise_spectral.py` |
| `fig-dn-spec-master64-val` | 2 | 频谱前后对比：master64 × valentini | G-DN | ✓单栏 | 🔒 不重跑 · `_plot_denoise_spectral.py` |
| `fig-dn-spec-mel-syn` | 2 | 频谱前后对比：mel-roformer × synth | G-DN | ✓单栏 | 🔒 不重跑 · `_plot_denoise_spectral.py` |
| `fig-dn-spec-mel-val` | 2 | 频谱前后对比：mel-roformer × valentini | G-DN | ✓单栏 | 🔒 不重跑 · `_plot_denoise_spectral.py` |
| `fig-dn-suppression` | 2 | 降噪抑制量（按模型 / SNR 档） | G-DN | ✓单栏 | `denoise.figures` |
| `fig-dn-synth-gain` | 2 | 合成集增益（干净语音 + 瞬态噪声） | G-DN | ✓单栏 | `denoise.figures` |

## 2. 复现产物家族（一键）

| 目标 | 阶段 | 级别 | 说明 | 命令 |
|:--|:-:|:-:|:--|:--|
| `profile.measure` | 1 | 🔁 重测 | 模型本体画像（参数量 / FLOPs / 时延） | `$PY tools/reproduce.py --run profile.measure` |
| `sep.sweep` | 1 | 🔒 重跑 | MUSDB18 test 50 首整曲分离（song-major 全模型扫描） | `$PY tools/reproduce.py --run sep.sweep` |
| `sep.train.dprnn` | 1 | 🔒 重跑 | DPRNN 自训 MUSDB18 4-stem 权重（负面证据对照） | `$PY tools/reproduce.py --run sep.train.dprnn` |
| `arch.figures` | 2 | ✅ 重建 | 14 张架构原理图 | `$PY tools/reproduce.py --run arch.figures` |
| `arch.trace` | 2 | 🔁 重测 | 抓真实层级树（forward hook）→ graph_*.json | `$PY tools/reproduce.py --run arch.trace` |
| `profile.figures` | 2 | ✅ 重建 | 画像图：参数量/FLOPs 对比、成本—容量 Pareto | `$PY tools/reproduce.py --run profile.figures` |
| `sep.dsdr` | 3 | 🔒 重跑 | 与基线对照的 ΔSDR（脚本含 torch 重算 + 写死 dpi=150） | `$PY tools/reproduce.py --run sep.dsdr` |
| `sep.median_figs` | 3 | ✅ 重建 | 分模型 / 逐轨 / 精度-速度三张中位图 | `$PY tools/reproduce.py --run sep.median_figs` |
| `sep.panels` | 3 | ✅ 重建 | 3 首曲 × 4 张频谱面板（decomp / multimodel / mask / bands） | `$PY tools/reproduce.py --run sep.panels` |
| `sep.table` | 3 | ✅ 重建 | 分离精度主表（MD + 重绘 PNG，写死 300 dpi） | `$PY tools/reproduce.py --run sep.table` |
| `cost.figures` | 4 | ✅ 重建 | 7 张实机成本图（耗时 / RTF / 分布 / Pareto） | `$PY tools/reproduce.py --run cost.figures` |
| `reverb.eval` | 4 | 🔒 重跑 | 混响 / 回声退化实验 | `$PY tools/reproduce.py --run reverb.eval` |
| `reverb.figures` | 4 | ✅ 重建 | 混响 / RIR / 回声三张退化曲线图（含同批落盘的曲线 json） | `$PY tools/reproduce.py --run reverb.figures` |
| `sep.bench` | 4 | 🔒 重跑 | 10 首 × 30 s 实机时长基准（UMX vs HTDemucs） | `$PY tools/reproduce.py --run sep.bench` |
| `stage4.summary` | 4 | ✅ 重建 | 阶段 4 一页汇总图（含同批落盘的汇总 json） | `$PY tools/reproduce.py --run stage4.summary` |
| `denoise.diagnosis` | 5 | 🔒 重跑 | 三指标分歧诊断图（载入 _denoise_registry 推理） | `$PY tools/reproduce.py --run denoise.diagnosis` |
| `denoise.drywet` | 5 | 🔒 重跑 | dry/wet 强度旋钮扫描 | `$PY tools/reproduce.py --run denoise.drywet` |
| `denoise.eval` | 5 | 🔒 重跑 | 降噪双口径全量评测（16k / 44.1k） | `$PY tools/reproduce.py --run denoise.eval` |
| `denoise.figures` | 5 | ✅ 重建 | 降噪抑制 / 合成增益 / 域反转 / dry-wet / 分歧诊断 五张图 | `$PY tools/reproduce.py --run denoise.figures` |
| `denoise.ood` | 5 | 🔒 重跑 | 域外探针（直通 / 纯噪声，判 denoiser vs mel-roformer 有效域） | `$PY tools/reproduce.py --run denoise.ood` |
| `denoise.spectral` | 5 | 🔒 重跑 | 频谱前后对比 + 平均谱差（各 4 张，载入 registry 推理） | `$PY tools/reproduce.py --run denoise.spectral` |
| `cascade.eval` | 6 | 🔒 重跑 | 级联全量实验（640 分离格 + 40 锚点格，7 条链路） | `$PY tools/reproduce.py --run cascade.eval` |
| `cascade.figures` | 6 | ✅ 重建 | 级联 ΔSDR 主矩阵 + 净动作分解两张图 | `$PY tools/reproduce.py --run cascade.figures` |
| `report.dashboards` | 7 | ✅ 重建 | 三块自包含离线 HTML 看板（模型分析 / 降噪 / 级联） | `$PY tools/reproduce.py --run report.dashboards` |
| `report.summaries` | 7 | ✅ 重建 | 4 份数据摘要（数字全部从 CSV/JSON 生成） | `$PY tools/reproduce.py --run report.summaries` |
| `paper.figures` | 8 | ✅ 重建 | 53 张论文图（300 dpi 判据）+ 清单 + 两板图注 | `$PY tools/reproduce.py --run paper.figures` |
| `paper.scope` | 8 | ✅ 重建 | 口径与差异说明章节（含答辩速答卡） | `$PY tools/reproduce.py --run paper.scope` |
| `report.slides` | 8 | ✅ 重建 | 答辩 slides（24 页自包含离线 HTML） | `$PY tools/reproduce.py --run report.slides` |

**批量**：

```bash
$PY tools/reproduce.py --stage 7        # 跑某阶段全部「重建」目标
$PY tools/reproduce.py --all-report     # 跑全部「重建」目标（由归档数据确定性重画）
```

## 3. 产物落点（每个目标对应什么文件）

### `profile.measure` — 模型本体画像（参数量 / FLOPs / 时延）

- ⚠️ **重测目标**；执行需 `--force-heavy`。**重新测量**：22 个模型逐个测 5 次 ≈ 20 min；会改写 latency_s/rtf/load_s 等量测列，故不纳入 --all-report
- 脚本：`tools/_measure_model_profile.py`
- 产物：
  - `04_reports/_shared/data/model_analysis/model_profile.csv`（下限 1，当前 1）

### `sep.sweep` — MUSDB18 test 50 首整曲分离（song-major 全模型扫描）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。数小时~数天 GPU；必须走 Task Scheduler（tools/_bat/_sweep_launch.bat）
- 脚本：`tools/bench_musdb_test_songmajor.py --models all --songs all`
- 产物：
  - `03_outputs/*/test`（下限 8，当前 13）

### `sep.train.dprnn` — DPRNN 自训 MUSDB18 4-stem 权重（负面证据对照）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。GPU 训练数小时；官方只发语音权重，故自训仅作欠训练对照
- 脚本：`tools/train_dprnn_musdb.py`
- 产物：
  - `01_models/_weights/dprnn_musdb`（下限 1，当前 1）

### `arch.figures` — 14 张架构原理图

- 前置：`arch.trace`
- 脚本：`tools/_plot_model_arch.py`
- 产物：
  - `04_reports/_shared/figures/model_arch/arch_*.png`（下限 14，当前 14）

### `arch.trace` — 抓真实层级树（forward hook）→ graph_*.json

- ⚠️ **重测目标**；执行需 `--force-heavy`。**重新测量**：逐个载入模型做一次前向追踪（无音频推理）；是 14 张架构图的形状溯源，结果应确定，但耗时较长
- 脚本：`tools/_extract_model_graph.py --models all`
- 产物：
  - `04_reports/_shared/data/model_analysis/graph_*.json`（下限 8，当前 22）

### `profile.figures` — 画像图：参数量/FLOPs 对比、成本—容量 Pareto

- 前置：`profile.measure`
- 脚本：`tools/_plot_model_profile.py`
- 产物：
  - `04_reports/_shared/figures/model_arch/profile_*.png`（下限 2，当前 2）

### `sep.dsdr` — 与基线对照的 ΔSDR（脚本含 torch 重算 + 写死 dpi=150）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。重跑会触发重算并改写 comparison 数据 -> 为保已归档结果一致，默认不重跑
- 脚本：`tools/compare_separation_methods.py`
- 产物：
  - `04_reports/separation/figures/comparison/fig_compare_dsdr.png`（下限 1，当前 1）

### `sep.median_figs` — 分模型 / 逐轨 / 精度-速度三张中位图

- 脚本：`tools/plot_median_summary.py`
- 产物：
  - `04_reports/separation/figures/comparison/fig_median_*.png`（下限 3，当前 3）

### `sep.panels` — 3 首曲 × 4 张频谱面板（decomp / multimodel / mask / bands）

- 脚本：`tools/_make_spectrogram_panels.py`
- 产物：
  - `04_reports/separation/figures/spectrograms/panel_*.png`（下限 12，当前 12）
  - `04_reports/separation/data/comparison/panel_decomp_checks.json`（下限 1，当前 1）

### `sep.table` — 分离精度主表（MD + 重绘 PNG，写死 300 dpi）

- 脚本：`tools/_make_sdr_table.py`
- 产物：
  - `04_reports/separation/docs/MEDIAN_TABLE_REDRAWN.md`（下限 1，当前 1）
  - `04_reports/separation/figures/comparison/fig_avg_sdr_table.png`（下限 1，当前 1）

### `cost.figures` — 7 张实机成本图（耗时 / RTF / 分布 / Pareto）

- 脚本：`tools/plot_bench_10songs.py`
- 产物：
  - `04_reports/separation/data/comparison/figs_time/fig*.png`（下限 7，当前 7）

### `reverb.eval` — 混响 / 回声退化实验

- ⚠️ **重跑目标**；执行需 `--force-heavy`。
- 脚本：`tools/_reverb_experiment.py`、`tools/_echo_experiment.py`
- 产物：
  - `04_reports/separation/data/reverb/reverb_vs_sep.json`（下限 1，当前 1）
  - `04_reports/separation/data/reverb/echo_vs_sep.json`（下限 1，当前 1）

### `reverb.figures` — 混响 / RIR / 回声三张退化曲线图（含同批落盘的曲线 json）

- 脚本：`tools/_plot_rir.py`、`tools/_plot_reverb_curve.py`、`tools/_plot_echo_curve.py`
- 产物：
  - `04_reports/separation/figures/comparison/fig_reverb_degradation.png`（下限 1，当前 1）
  - `04_reports/separation/figures/comparison/fig_rir_t60.png`（下限 1，当前 1）
  - `04_reports/separation/figures/comparison/fig_echo_degradation.png`（下限 1，当前 1）
  - `04_reports/separation/data/reverb/reverb_degradation_curve.json`（下限 1，当前 1）
  - `04_reports/separation/data/reverb/echo_degradation_curve.json`（下限 1，当前 1）
  - `04_reports/separation/data/reverb/rir_figure_metrics.json`（下限 1，当前 1）

### `sep.bench` — 10 首 × 30 s 实机时长基准（UMX vs HTDemucs）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。CPU 单进程，分钟级；产出成本图的源 JSON
- 脚本：`tools/benchmark_models_10songs.py`
- 产物：
  - `04_reports/separation/data/comparison/bench_10songs.json`（下限 1，当前 1）

### `stage4.summary` — 阶段 4 一页汇总图（含同批落盘的汇总 json）

- 脚本：`tools/_plot_stage4_summary.py`
- 产物：
  - `04_reports/separation/figures/comparison/fig_stage4_summary.png`（下限 1，当前 1）
  - `04_reports/separation/data/reverb/stage4_summary.json`（下限 1，当前 1）

### `denoise.diagnosis` — 三指标分歧诊断图（载入 _denoise_registry 推理）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。避免与已归档结果分歧，默认不重跑
- 脚本：`tools/_denoise_diagnosis.py`
- 产物：
  - `04_reports/denoiser/figures/fig_denoise_metric_divergence.png`（下限 1，当前 1）

### `denoise.drywet` — dry/wet 强度旋钮扫描

- ⚠️ **重跑目标**；执行需 `--force-heavy`。需 GPU 推理多档 dry 混比
- 脚本：`tools/_denoise_drywet.py`
- 产物：
  - `04_reports/denoiser/data/denoise_drywet.json`（下限 1，当前 1）

### `denoise.eval` — 降噪双口径全量评测（16k / 44.1k）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。夜挂约 2 h GPU；16575 格逐格落盘
- 脚本：`tools/_denoise_eval.py`
- 产物：
  - `04_reports/denoiser/data/denoise_manifest.json`（下限 1，当前 1）

### `denoise.figures` — 降噪抑制 / 合成增益 / 域反转 / dry-wet / 分歧诊断 五张图

- 脚本：`tools/_plot_denoise.py`、`tools/_plot_denoise_drywet.py`
- 产物：
  - `04_reports/denoiser/figures/fig_denoise_suppression.png`（下限 1，当前 1）
  - `04_reports/denoiser/figures/fig_denoise_synth_gain.png`（下限 1，当前 1）
  - `04_reports/denoiser/figures/fig_denoise_noise_domain_reversal.png`（下限 1，当前 1）
  - `04_reports/denoiser/figures/fig_denoise_drywet.png`（下限 1，当前 1）
  - `04_reports/denoiser/figures/fig_denoise_metric_divergence.png`（下限 1，当前 1）

### `denoise.ood` — 域外探针（直通 / 纯噪声，判 denoiser vs mel-roformer 有效域）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。
- 脚本：`tools/_denoise_ood_probe.py`
- 产物：
  - `04_reports/denoiser/data/denoise_ood_probe.json`（下限 1，当前 1）

### `denoise.spectral` — 频谱前后对比 + 平均谱差（各 4 张，载入 registry 推理）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。脚本载入 _denoise_registry 做推理 -> 默认不重跑
- 脚本：`tools/_plot_denoise_spectral.py`、`tools/_plot_denoise_spectrum_delta.py`
- 产物：
  - `04_reports/denoiser/figures/denoise/t5_6_*_spectral.png`（下限 4，当前 4）
  - `04_reports/denoiser/figures/denoise/t5_6_*_delta_spectrum.png`（下限 4，当前 4）

### `cascade.eval` — 级联全量实验（640 分离格 + 40 锚点格，7 条链路）

- ⚠️ **重跑目标**；执行需 `--force-heavy`。夜挂约 4 h GPU；逐格 JSONL 可断点续跑
- 脚本：`tools/_cascade_experiment.py`
- 产物：
  - `04_reports/cascade/data/cascade_eval.json`（下限 1，当前 1）

### `cascade.figures` — 级联 ΔSDR 主矩阵 + 净动作分解两张图

- 前置：`cascade.eval`
- 脚本：`tools/_plot_cascade.py`
- 产物：
  - `04_reports/cascade/figures/fig_cascade_*.png`（下限 2，当前 2）

### `report.dashboards` — 三块自包含离线 HTML 看板（模型分析 / 降噪 / 级联）

- 脚本：`tools/_build_dashboards.py --only all`
- 产物：
  - `04_reports/_shared/html/model_analysis_dashboard.html`（下限 1，当前 1）
  - `04_reports/denoiser/html/denoise_dashboard.html`（下限 1，当前 1）
  - `04_reports/cascade/html/cascade_dashboard.html`（下限 1，当前 1）

### `report.summaries` — 4 份数据摘要（数字全部从 CSV/JSON 生成）

- 脚本：`tools/_build_summaries.py`
- 产物：
  - `04_reports/_shared/docs/summaries/MODEL_PROFILE_SUMMARY.md`（下限 1，当前 1）
  - `04_reports/_shared/docs/summaries/SEPARATION_SUMMARY.md`（下限 1，当前 1）
  - `04_reports/_shared/docs/summaries/DENOISE_SUMMARY.md`（下限 1，当前 1）
  - `04_reports/_shared/docs/summaries/CASCADE_SUMMARY.md`（下限 1，当前 1）

### `paper.figures` — 53 张论文图（300 dpi 判据）+ 清单 + 两板图注

- 说明：render 会**按 300 dpi 重渲染上游源图**再拷入图包（故也会touch arch_*/profile_*/fig_median_* 等，那些由图各自的 target 声明）；不重跑的 10 张只做 dpi 判据与图注
- 脚本：`tools/_export_paper_figures.py --board 1 render`、`tools/_export_paper_figures.py --board 2 render`、`tools/_export_paper_figures.py --board 1 captions`、`tools/_export_paper_figures.py --board 2 captions`
- 产物：
  - `04_reports/_shared/figures/paper/*.png`（下限 53，当前 53）
  - `04_reports/_shared/figures/paper/paper_figures_manifest.json`（下限 1，当前 1）
  - `04_reports/_shared/docs/PAPER_FIGURES_B1.md`（下限 1，当前 1）
  - `04_reports/_shared/docs/PAPER_FIGURES_B2.md`（下限 1，当前 1）

### `paper.scope` — 口径与差异说明章节（含答辩速答卡）

- 脚本：`tools/_build_paper_scope.py`
- 产物：
  - `04_reports/_shared/docs/PAPER_SCOPE_AND_DIVERGENCE.md`（下限 1，当前 1）

### `report.slides` — 答辩 slides（24 页自包含离线 HTML）

- 脚本：`tools/_build_slides.py`
- 产物：
  - `04_reports/slides/defense_slides.html`（下限 1，当前 1）

## 4. 重跑目标（默认锁死）

以下 **13** 个目标不是「由归档数据重建」——重测会改量测值、重跑含 GPU 推理 / 训练，`--run` 一律被拒绝；确认要执行时加 `--force-heavy`：

| 目标 | 级别 | 说明 | 备注 |
|:--|:-:|:--|:--|
| `arch.trace` | 🔁 重测 | 抓真实层级树（forward hook）→ graph_*.json | **重新测量**：逐个载入模型做一次前向追踪（无音频推理）；是 14 张架构图的形状溯源，结果应确定，但耗时较长 |
| `cascade.eval` | 🔒 重跑 | 级联全量实验（640 分离格 + 40 锚点格，7 条链路） | 夜挂约 4 h GPU；逐格 JSONL 可断点续跑 |
| `denoise.diagnosis` | 🔒 重跑 | 三指标分歧诊断图（载入 _denoise_registry 推理） | 避免与已归档结果分歧，默认不重跑 |
| `denoise.drywet` | 🔒 重跑 | dry/wet 强度旋钮扫描 | 需 GPU 推理多档 dry 混比 |
| `denoise.eval` | 🔒 重跑 | 降噪双口径全量评测（16k / 44.1k） | 夜挂约 2 h GPU；16575 格逐格落盘 |
| `denoise.ood` | 🔒 重跑 | 域外探针（直通 / 纯噪声，判 denoiser vs mel-roformer 有效域） |  |
| `denoise.spectral` | 🔒 重跑 | 频谱前后对比 + 平均谱差（各 4 张，载入 registry 推理） | 脚本载入 _denoise_registry 做推理 -> 默认不重跑 |
| `profile.measure` | 🔁 重测 | 模型本体画像（参数量 / FLOPs / 时延） | **重新测量**：22 个模型逐个测 5 次 ≈ 20 min；会改写 latency_s/rtf/load_s 等量测列，故不纳入 --all-report |
| `reverb.eval` | 🔒 重跑 | 混响 / 回声退化实验 |  |
| `sep.bench` | 🔒 重跑 | 10 首 × 30 s 实机时长基准（UMX vs HTDemucs） | CPU 单进程，分钟级；产出成本图的源 JSON |
| `sep.dsdr` | 🔒 重跑 | 与基线对照的 ΔSDR（脚本含 torch 重算 + 写死 dpi=150） | 重跑会触发重算并改写 comparison 数据 -> 为保已归档结果一致，默认不重跑 |
| `sep.sweep` | 🔒 重跑 | MUSDB18 test 50 首整曲分离（song-major 全模型扫描） | 数小时~数天 GPU；必须走 Task Scheduler（tools/_bat/_sweep_launch.bat） |
| `sep.train.dprnn` | 🔒 重跑 | DPRNN 自训 MUSDB18 4-stem 权重（负面证据对照） | GPU 训练数小时；官方只发语音权重，故自训仅作欠训练对照 |

## 5. 已知缺口（照报）

- **10 张论文图不重跑**（源脚本含推理或写死 dpi）：`fig-acc-dsdr`、`fig-dn-dspec-master64-syn`、`fig-dn-dspec-master64-val`、`fig-dn-dspec-mel-syn`、`fig-dn-dspec-mel-val`、`fig-dn-metric-divergence`、`fig-dn-spec-master64-syn`、`fig-dn-spec-master64-val`、`fig-dn-spec-mel-syn`、`fig-dn-spec-mel-val`。
- 其余 43 张可重跑；`paper.figures` 目标按 `--board 1/2 render` 重建。
- `--check` 会强制要求 **53/53 张图都有复现归属**，清单漂移即 FAIL。
- **重测 ≠ 重建**：`profile.measure` / `arch.trace` 会重新量测（含 `latency_s` 等计时列），其结果**本就不会逐字节相同**；故物理上仍读其产物的图（如画像图）只需保证**数据不变时逐字节一致**，不以「重测后也一致」为契约。

## 6. 复现边界（fresh clone 实测）

把 HEAD 导出到**不含本地数据树**的目录再跑 `--all-report`，以四级判定（逐字节 / 仅行尾 / 仅时间戳 / 仅计时）比对，结论：**10/15 个重建目标可逐字节复现**；下列目标**不可**，原因如下（实测证据见计划书 §9.13）：

| 目标 | 类别 | 原因 |
|:--|:--|:--|
| `arch.figures` | 🔒 需本地数据 | 渲染 01_models/_weights/** 的**本地**权重清单（文件名 + 体积） |
| `paper.figures` | ↳ 下游产物 | 把 arch.figures 的 12 张图镜像到 figures/paper/ |
| `report.dashboards` | ↳ 下游产物 | 内嵌 arch.figures 的 12 张架构图（base64） |
| `report.slides` | ↳ 下游产物 | 答辩 slides 内嵌架构图（base64） |
| `sep.panels` | 🔒 需本地数据 | 读 02_databases/MUSDB18-HQ/*.wav 与 03_outputs/<Model>/*.flac |

- **需本地数据**：生成时读 `01_models/` `02_databases/` `03_outputs/` 等未入库路径 —— 在完整工程机上照常逐字节复现，clone 机上会缺内容、`sep.panels` 直接 FAIL。
- **下游产物**：自身不读原始数据，但内嵌了上面的图，故随之变化。
- 另有 1 类**移植性缺陷**已在 T8.6 修复：生成器曾把**本机绝对路径**（`str(FIG)`）写进 JSON，换目录即变字节；现改为相对 `PROJECT_ROOT` 的 POSIX 路径。（实验日志类 JSON 中的原始绝对路径属**溯源记录**，有意保留。）

---

_重建目标 15 个 / 重测目标 2 个 / 重跑目标 11 个 / 论文图 53 张。_

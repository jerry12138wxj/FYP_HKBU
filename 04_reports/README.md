# ④ 报告模块

按**板块**分文件夹。板块名用**编号前缀**，便于排序、也让「谁属于谁」一眼可读：

| 现板块（编号式） | 旧板块名（2026-09-23 前） | 归属 | 计划阶段 |
|---|---|---|---|
| `00_shared/` | `_shared/` | 跨板块共用（总纲 / 画像 / 架构图 / 口径 / 复现指南） | 全阶段 |
| `01_separation/` | `separation/` | **板 1 · 分离** | 阶段 1-4（画像、架构图、频谱面板、混响鲁棒性） |
| `02_denoising/` | `denoiser/` | **板 2 · 降噪** | 阶段 5-7（降噪评测、去混响 / 去回声） |
| `03_cascade/` | `cascade/` | **级联**（板 2 收尾） | 阶段 6-7（分离 → 降噪串联） |
| `04_defense/` | `slides/` | 答辩材料 | 阶段 8 |

> 重命名由 `tools/_scratch/_patch_reorg_reports.py`（板块目录）+ `_patch_reorg_relpath.py`
> （REPORTS 相对路径）+ `_patch_reorg_docs.py`（文档 / 裸路径）+ `_patch_reorg_join.py`
> （`os.path.join` / `变量 / "路径"` 形态）四支补丁完成，全程字节级改写，残留自检 0。
> 命名以 `tools/paths.py` 为唯一入口：
> `SHARED` / `SEPARATION` / `DENOISER` / `CASCADE` / `SLIDES`。

## 各板块内容

### `00_shared/` —— 跨板块共用

总纲（计划 / 路线图 / 复盘 / 工作编年）、模型画像、架构图数据与成品、口径章节、复现指南。

- `docs/` —— `FYP_PLAN_2026-09-22.md`（主计划，含 §9 逐次记录）、`FYP_ROADMAP_2026-09-22.md`、
  `FYP_RETROSPECTIVE_2026-09-22.md`、`FYP_Audio_Setup_Guide.md`、`MODEL_PROFILE_2026-09-22.md`、
  `MODEL_DEPLOYMENT_2026-09-23.md`、`RESTRUCTURE_2026-09-23.md`、
  `PAPER_SCOPE_AND_DIVERGENCE.md`、`PAPER_FIGURES_B1.md`、`PAPER_FIGURES_B2.md`、
  `REPRODUCE.md`（由 `reproduce.py --readme` 自动生成）、`summaries/`（4 份数据摘要）、
  `MODEL_EVAL_SUMMARY_2026-10-23.docx` / `.pdf`（36 组模型评测总表的结果解读，12 页；
  由 `tools/_build_eval_report_doc.py` 从 `03_outputs/_eval` 现算生成）
- `figures/` —— `model_arch/`（16 项：14 张架构原理图 + 2 张基线）、`paper/`（54 项：53 张论文图 + 清单）、
  `plan/`、`_smoketest/`、`README.md`
- `data/` —— `model_analysis/`（画像 CSV / 图层 / 门禁 / thop 交叉验证）、
  `model_deploy_layout.json`、`model_deployment_audit.json`、`_reclassify_manifest.json`
- `figures/eval_report/` —— `fig1_sep_sdr.png`、`fig2_cascade_heatmap.png`、
  `fig3_cascade_rank.png`（评测总表解读配图，200 dpi）
- `html/` —— `model_analysis_dashboard.html`（模型分析看板）、
  `FYP_PLAN_FULL_2026-09-23.html` 与 `FYP_WORK_CHRONICLE_2026-09-23.html`（**陈旧快照，按原样保留**）、
  `_qa_audio_probe.html`、`_superseded/`

### `01_separation/` —— 板 1 · 分离

模型本体画像、14 张架构原理图、频谱面板、混响 / 去混响鲁棒性实验。

- `docs/` —— `MEDIAN_TABLE_REDRAWN.md`（300 dpi 重绘主表）、`STAGE4_SUMMARY.md`（阶段 4 小结）、
  `CODE_REVIEW_REPORT.md`、`DEMUCS_REPORT.md`、`MEDIAN_TABLE.md`、`MEDIAN_TABLE_TEST.md`、
  `METHOD_COMPARISON_REPORT.md`、`MODEL_PROVISIONING_REPORT.md`、`MODEL_RULE_AUDIT_2026-09-19.md`、
  `MUSDB18_TEST_SWEEP_2026-09-22.md`、`PROJECT_AUDIT_2026-09-19.md`
- `figures/` —— `audio_analysis`、`comparison`、`demucs`、`dprnn`、`figs_time`、`reverb`、
  `spectrograms`、`test_run`
- `data/` —— `comparison/`（主表口径、窗口探针、mixture 基线）、`reverb/`（RIR / 退化曲线 / 去混响诊断）、
  `dprnn_training.json`、`dprnn_training.bak-before-metafix.json`
- `html/` —— `METHOD_VISUAL_COMPARISON_1.3.html`、`RUNTIME_BENCH_PPT.html`、`listen_compare.html`、
  `test_run_dashboard.html`

### `02_denoising/` —— 板 2 · 降噪 / 去混响 / 去回声

降噪双口径评测（16k / 44.1k）、dry-wet 旋钮、域外探针、采样率契约 bug 复盘、去混响负结果。

- `docs/` —— `T5_DENOISE_STRATIFIED.md`（分层主表）、`T5_4_DNS_DEV_NOREF.md`、
  `T5_5_T5_6_DRYWET_AND_SPECTRA.md`、`T5_7_OOD_NOISE_NEGATIVE.md`、
  `T5_7_PASSTHROUGH_PROBE_CORRECTION.md`、`P19_SAMPLE_RATE_CONTRACT_BUG.md`、
  `DEREVERB_NEGATIVE_RESULT.md`
- `figures/` —— `fig_denoise_{suppression,synth_gain,metric_divergence,noise_domain_reversal,drywet}.png`、`denoise/`
- `data/` —— `denoise_eval_{16k,44k}.csv/.json`、`denoise_manifest.json`（+ 3 个 `.bak-*` 事故期备份）、
  `denoise_drywet.*`、`denoise_ood_probe.json`、`denoise_diagnosis.json`、`denoise_spectral_delta.json`、
  `denoise_probeA_paired.json`、`denoise_sr_bug_audit.json`、`synth_pairs_manifest.json`、`denoise/`
- `html/` —— `denoise_dashboard.html`（降噪看板）

### `03_cascade/` —— 级联实验

分离输出 → 降噪输入 的端到端结果（640 分离格 + 40 锚点）。

- `docs/` —— `T6_CASCADE_DENOISE_BEFORE_SEPARATION.md`
- `figures/` —— `fig_cascade_delta_matrix.png`、`fig_cascade_decomposition.png`、`cascade/`
- `data/` —— `cascade_eval.csv/.json`、`cascade_manifest.json`、`cascade_plan.json`、
  `cascade_eval.partial.jsonl`、`cascade/`
- `html/` —— `cascade_dashboard.html`（级联看板）

### `04_defense/` —— 答辩材料

- `defense_slides.html` —— 24 页自包含离线 HTML（论文图内嵌为 JPEG，零外部依赖，双击即开），
  由 `tools/_build_slides.py` 生成。

---

## 相关

- **过程留档** → `../05_step_reports/`（12 步流水线逐步汇报 + 总览）
- **一键复现** → `../tools/reproduce.py`（`--check` / `--readme` / `--manifest`）
- **路径入口** → `../tools/paths.py`

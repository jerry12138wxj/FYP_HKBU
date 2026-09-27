#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FYP_HKBU 全链路复现入口（T8.5）。

一条命令回答：**「要复现哪个产物 / 哪张论文图，该跑什么？」**

用法
----
    PY="C:/Users/jerry/.workbuddy/binaries/python/envs/fyp_audio/Scripts/python.exe"

    $PY tools/reproduce.py --list                 # 目标清单（按阶段，标出轻/重）
    $PY tools/reproduce.py --check                # 校验：脚本在否 / 产物在否 / 论文图全覆盖
    $PY tools/reproduce.py --manifest             # 机器可读清单（JSON）→ 交给核对脚本消费
    $PY tools/reproduce.py --figure fig-arch-demucs   # 复现某一张论文图（按 53 图 id）
    $PY tools/reproduce.py --figure fig-dn-metric-divergence --force-heavy
    $PY tools/reproduce.py --run report.dashboards    # 跑单个目标
    $PY tools/reproduce.py --stage 7              # 跑某阶段全部「轻量」目标
    $PY tools/reproduce.py --all-report           # 跑全部非推理目标（重建所有报告产物）
    $PY tools/reproduce.py --readme               # 生成 REPRODUCE.md
    $PY tools/reproduce.py --readme --verify      # 生成并与磁盘逐字节比对（只读，不写盘）

设计纪律
--------
1. **只登记、不臆造**：每个目标的 `scripts` 与 `outputs` 都对着真实脚本写；
   `--check` 会同时验证「脚本存在」与「产物 glob 命中数 ≥ 下限」。
2. **推理目标默认锁死**：含音频推理 / 模型训练的目标 `inference=True`，
   直接 `--run` 会被拒绝，须显式加 `--force-heavy`，避免误触发数小时重算。
3. **论文图全覆盖**：`--check` 会读 `paper_figures_manifest.json`，
   要求 53 张图的 `script` 都能映射到某个目标，否则 FAIL（防止清单漂移）。
4. **解释器用 `sys.executable`**：不写死路径，保证用哪个 venv 跑就用哪个 venv 复现。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

ROOT = _HERE.parent
REPORTS = ROOT / "04_reports"
PAPER_MANIFEST = REPORTS / "00_shared" / "figures" / "paper" / "paper_figures_manifest.json"
REPRO_DOC = REPORTS / "00_shared" / "docs" / "REPRODUCE.md"
# 统一绘图 rc：所有重建目标都按 300 dpi 出图 →
#  ① 满足论文插图判据；② 同一产物不再被两种 dpi 各写一次（消除顺序依赖）
MPLRC = ROOT / "tools" / "_scratch" / "mplrc_repro"
TARGET_DPI = 300

PY = sys.executable  # 用启用本脚本的同一 venv

LIGHT, MEASURE, HEAVY = "light", "measure", "heavy"


def T(name, stage, kind, what, scripts, outputs, *, inference=False,
      remeasure=False, note="", requires=()):
    """构造一个复现目标。

    scripts   可执行脚本清单（按顺序跑；均以 ROOT 为工作目录）
    outputs   ("相对路径 glob", 最少命中数) 列表
    requires  前置数据（人类可读，仅提示，不做强制检查）
    """
    level = HEAVY if inference else (MEASURE if remeasure else LIGHT)
    return dict(name=name, stage=stage, kind=kind, what=what, scripts=list(scripts),
                outputs=[tuple(o) for o in outputs], inference=inference,
                note=note, requires=list(requires),
                level=level, deterministic=(level == LIGHT))


# ------------------------------------------------------------------ 目标清单
TARGETS: list[dict] = [
    # ---------------- 阶段 1-2 · 模型画像与架构图 ----------------
    T("profile.measure", 1, "data", "模型本体画像（参数量 / FLOPs / 时延）",
      ["tools/_measure_model_profile.py"],
      [("04_reports/00_shared/data/model_analysis/model_profile.csv", 1)],
      remeasure=True,
      note="**重新测量**：22 个模型逐个测 5 次 ≈ 20 min；"
           "会改写 latency_s/rtf/load_s 等量测列，故不纳入 --all-report"),
    T("profile.figures", 2, "figure", "画像图：参数量/FLOPs 对比、成本—容量 Pareto",
      ["tools/_plot_model_profile.py"],
      [("04_reports/00_shared/figures/model_arch/profile_*.png", 2)],
      requires=("profile.measure",)),
    T("arch.trace", 2, "data", "抓真实层级树（forward hook）→ graph_*.json",
      ["tools/_extract_model_graph.py --models all"],
      [("04_reports/00_shared/data/model_analysis/graph_*.json", 8)],
      remeasure=True,
      note="**重新测量**：逐个载入模型做一次前向追踪（无音频推理）；"
           "是 14 张架构图的形状溯源，结果应确定，但耗时较长"),
    T("arch.figures", 2, "figure", "14 张架构原理图",
      ["tools/_plot_model_arch.py"],
      [("04_reports/00_shared/figures/model_arch/arch_*.png", 14)],
      requires=("arch.trace",)),

    # ---------------- 阶段 3 · 频谱面板与精度主表 ----------------
    T("sep.table", 3, "report", "分离精度主表（MD + 重绘 PNG，写死 300 dpi）",
      ["tools/_make_sdr_table.py"],
      [("04_reports/01_separation/docs/MEDIAN_TABLE_REDRAWN.md", 1),
       ("04_reports/01_separation/figures/comparison/fig_avg_sdr_table.png", 1)]),
    T("sep.median_figs", 3, "figure", "分模型 / 逐轨 / 精度-速度三张中位图",
      ["tools/plot_median_summary.py"],
      [("04_reports/01_separation/figures/comparison/fig_median_*.png", 3)]),
    T("sep.panels", 3, "figure", "3 首曲 × 4 张频谱面板（decomp / multimodel / mask / bands）",
      ["tools/_make_spectrogram_panels.py"],
      [("04_reports/01_separation/figures/spectrograms/panel_*.png", 12),
       ("04_reports/01_separation/data/comparison/panel_decomp_checks.json", 1)]),

    # ---------------- 阶段 4 · 成本 / 混响 / 回声 ----------------
    T("cost.figures", 4, "figure", "7 张实机成本图（耗时 / RTF / 分布 / Pareto）",
      ["tools/plot_bench_10songs.py"],
      [("04_reports/01_separation/data/comparison/figs_time/fig*.png", 7)]),
    T("reverb.figures", 4, "figure", "混响 / RIR / 回声三张退化曲线图（含同批落盘的曲线 json）",
      ["tools/_plot_rir.py", "tools/_plot_reverb_curve.py", "tools/_plot_echo_curve.py"],
      [("04_reports/01_separation/figures/comparison/fig_reverb_degradation.png", 1),
       ("04_reports/01_separation/figures/comparison/fig_rir_t60.png", 1),
       ("04_reports/01_separation/figures/comparison/fig_echo_degradation.png", 1),
       ("04_reports/01_separation/data/reverb/reverb_degradation_curve.json", 1),
       ("04_reports/01_separation/data/reverb/echo_degradation_curve.json", 1),
       ("04_reports/01_separation/data/reverb/rir_figure_metrics.json", 1)]),
    T("stage4.summary", 4, "figure", "阶段 4 一页汇总图（含同批落盘的汇总 json）",
      ["tools/_plot_stage4_summary.py"],
      [("04_reports/01_separation/figures/comparison/fig_stage4_summary.png", 1),
       ("04_reports/01_separation/data/reverb/stage4_summary.json", 1)]),

    # ---------------- 阶段 5 · 降噪结果图 ----------------
    T("denoise.figures", 5, "figure", "降噪抑制 / 合成增益 / 域反转 / dry-wet / 分歧诊断 五张图",
      ["tools/_plot_denoise.py", "tools/_plot_denoise_drywet.py"],
      [("04_reports/02_denoising/figures/fig_denoise_suppression.png", 1),
       ("04_reports/02_denoising/figures/fig_denoise_synth_gain.png", 1),
       ("04_reports/02_denoising/figures/fig_denoise_noise_domain_reversal.png", 1),
       ("04_reports/02_denoising/figures/fig_denoise_drywet.png", 1),
       ("04_reports/02_denoising/figures/fig_denoise_metric_divergence.png", 1)]),

    # ---------------- 阶段 6 · 级联图 ----------------
    T("cascade.figures", 6, "figure", "级联 ΔSDR 主矩阵 + 净动作分解两张图",
      ["tools/_plot_cascade.py"],
      [("04_reports/03_cascade/figures/fig_cascade_*.png", 2)],
      requires=("cascade.eval",)),

    # ---------------- 阶段 7 · 看板与摘要 ----------------
    T("report.dashboards", 7, "report", "三块自包含离线 HTML 看板（模型分析 / 降噪 / 级联）",
      ["tools/_build_dashboards.py --only all"],
      [("04_reports/00_shared/html/model_analysis_dashboard.html", 1),
       ("04_reports/02_denoising/html/denoise_dashboard.html", 1),
       ("04_reports/03_cascade/html/cascade_dashboard.html", 1)]),
    T("report.summaries", 7, "report", "4 份数据摘要（数字全部从 CSV/JSON 生成）",
      ["tools/_build_summaries.py"],
      [("04_reports/00_shared/docs/summaries/MODEL_PROFILE_SUMMARY.md", 1),
       ("04_reports/00_shared/docs/summaries/SEPARATION_SUMMARY.md", 1),
       ("04_reports/00_shared/docs/summaries/DENOISE_SUMMARY.md", 1),
       ("04_reports/00_shared/docs/summaries/CASCADE_SUMMARY.md", 1)]),

    # ---------------- 阶段 8 · 论文图包 / 口径章节 / slides ----------------
    T("paper.figures", 8, "report", "53 张论文图（300 dpi 判据）+ 清单 + 两板图注",
      ["tools/_export_paper_figures.py --board 1 render",
       "tools/_export_paper_figures.py --board 2 render",
       "tools/_export_paper_figures.py --board 1 captions",
       "tools/_export_paper_figures.py --board 2 captions"],
      [("04_reports/00_shared/figures/paper/*.png", 53),
       ("04_reports/00_shared/figures/paper/paper_figures_manifest.json", 1),
       ("04_reports/00_shared/docs/PAPER_FIGURES_B1.md", 1),
       ("04_reports/00_shared/docs/PAPER_FIGURES_B2.md", 1)],
      note="render 会**按 300 dpi 重渲染上游源图**再拷入图包（故也会touch arch_*/profile_*/fig_median_* 等，"
           "那些由图各自的 target 声明）；不重跑的 10 张只做 dpi 判据与图注"),
    T("paper.scope", 8, "report", "口径与差异说明章节（含答辩速答卡）",
      ["tools/_build_paper_scope.py"],
      [("04_reports/00_shared/docs/PAPER_SCOPE_AND_DIVERGENCE.md", 1)]),
    T("report.slides", 8, "report", "答辩 slides（24 页自包含离线 HTML）",
      ["tools/_build_slides.py"],
      [("04_reports/04_defense/defense_slides.html", 1)]),

    # ---------------- 重跑（推理 / 训练）：登记但默认锁死 ----------------
    T("sep.sweep", 1, "data", "MUSDB18 test 50 首整曲分离（song-major 全模型扫描）",
      ["tools/bench_musdb_test_songmajor.py --models all --songs all"],
      [("03_outputs/*/test", 8)], inference=True,
      note="数小时~数天 GPU；必须走 Task Scheduler（tools/_bat/_sweep_launch.bat）"),
    T("sep.bench", 4, "data", "10 首 × 30 s 实机时长基准（UMX vs HTDemucs）",
      ["tools/benchmark_models_10songs.py"],
      [("04_reports/01_separation/data/comparison/bench_10songs.json", 1)], inference=True,
      note="CPU 单进程，分钟级；产出成本图的源 JSON"),
    T("denoise.eval", 5, "data", "降噪双口径全量评测（16k / 44.1k）",
      ["tools/_denoise_eval.py"],
      [("04_reports/02_denoising/data/denoise_manifest.json", 1)], inference=True,
      note="夜挂约 2 h GPU；16575 格逐格落盘"),
    T("denoise.drywet", 5, "data", "dry/wet 强度旋钮扫描",
      ["tools/_denoise_drywet.py"],
      [("04_reports/02_denoising/data/denoise_drywet.json", 1)], inference=True,
      note="需 GPU 推理多档 dry 混比"),
    T("denoise.ood", 5, "data", "域外探针（直通 / 纯噪声，判 denoiser vs mel-roformer 有效域）",
      ["tools/_denoise_ood_probe.py"],
      [("04_reports/02_denoising/data/denoise_ood_probe.json", 1)], inference=True),
    T("sep.dsdr", 3, "figure", "与基线对照的 ΔSDR（脚本含 torch 重算 + 写死 dpi=150）",
      ["tools/compare_separation_methods.py"],
      [("04_reports/01_separation/figures/comparison/fig_compare_dsdr.png", 1)], inference=True,
      note="重跑会触发重算并改写 comparison 数据 -> 为保已归档结果一致，默认不重跑"),
    T("denoise.diagnosis", 5, "figure", "三指标分歧诊断图（载入 _denoise_registry 推理）",
      ["tools/_denoise_diagnosis.py"],
      [("04_reports/02_denoising/figures/fig_denoise_metric_divergence.png", 1)], inference=True,
      note="避免与已归档结果分歧，默认不重跑"),
    T("denoise.spectral", 5, "figure", "频谱前后对比 + 平均谱差（各 4 张，载入 registry 推理）",
      ["tools/_plot_denoise_spectral.py", "tools/_plot_denoise_spectrum_delta.py"],
      [("04_reports/02_denoising/figures/denoise/t5_6_*_spectral.png", 4),
       ("04_reports/02_denoising/figures/denoise/t5_6_*_delta_spectrum.png", 4)], inference=True,
      note="脚本载入 _denoise_registry 做推理 -> 默认不重跑"),
    T("cascade.eval", 6, "data", "级联全量实验（640 分离格 + 40 锚点格，7 条链路）",
      ["tools/_cascade_experiment.py"],
      [("04_reports/03_cascade/data/cascade_eval.json", 1)], inference=True,
      note="夜挂约 4 h GPU；逐格 JSONL 可断点续跑"),
    T("reverb.eval", 4, "data", "混响 / 回声退化实验",
      ["tools/_reverb_experiment.py", "tools/_echo_experiment.py"],
      [("04_reports/01_separation/data/reverb/reverb_vs_sep.json", 1),
       ("04_reports/01_separation/data/reverb/echo_vs_sep.json", 1)], inference=True),
    T("sep.train.dprnn", 1, "data", "DPRNN 自训 MUSDB18 4-stem 权重（负面证据对照）",
      ["tools/train_dprnn_musdb.py"],
      [("01_models/_weights/dprnn_musdb", 1)], inference=True,
      note="GPU 训练数小时；官方只发语音权重，故自训仅作欠训练对照"),
]

BY_NAME = {t["name"]: t for t in TARGETS}

# ------------------------------------------------------------------ 复现边界
# 「本机可复现」≠「clone 可复现」。下表是 T8.6 用**真 git clone（无本地数据树）**
# 跑 `--all-report` 后、以四级判定（逐字节 / 仅行尾 / 仅时间戳 / 仅计时）比对得到的结论。
# 证据与明细见计划书 §9.13。
#   data       = 生成时读 01_models/ 02_databases/ 03_outputs/ 等**未入库**路径
#   downstream = 自身不读原始数据，但内嵌了上面目标的图，故随之变化
CLONE_BOUNDARY = {
    "arch.figures": ("data", "渲染 01_models/_weights/** 的**本地**权重清单（文件名 + 体积）"),
    "sep.panels": ("data", "读 02_databases/MUSDB18-HQ/*.wav 与 03_outputs/<Model>/*.flac"),
    "report.dashboards": ("downstream", "内嵌 arch.figures 的 12 张架构图（base64）"),
    "paper.figures": ("downstream", "把 arch.figures 的 12 张图镜像到 figures/paper/"),
    "report.slides": ("downstream", "答辩 slides 内嵌架构图（base64）"),
}
CLONE_KIND = {"data": "🔒 需本地数据", "downstream": "↳ 下游产物"}


def _check_clone_boundary() -> list:
    """复现边界表自洽：键必须存在于 TARGETS，且必须是「重建」级目标。"""
    bad = []
    for name in sorted(CLONE_BOUNDARY):
        t = BY_NAME.get(name)
        if t is None:
            bad.append("边界表目标不存在: %s" % name)
        elif t["level"] != LIGHT:
            bad.append("边界表目标非重建级: %s(%s)" % (name, t["level"]))
    return bad



def _uscore(t: dict, *keys):
    return "".join(str(t[k]) for k in keys)


# ------------------------------------------------------------------ 校验
def _render_env() -> dict:
    """给子进程注入统一 matplotlibrc（savefig.dpi=300）。"""
    MPLRC.mkdir(parents=True, exist_ok=True)
    rc = MPLRC / "matplotlibrc"
    want = "savefig.dpi: %d\n" % TARGET_DPI
    if not rc.exists() or rc.read_text(encoding="utf-8") != want:
        rc.write_text(want, encoding="utf-8")
    return dict(os.environ, MATPLOTLIBRC=str(MPLRC))


def _glob_count(rel: str) -> int:
    return len(glob.glob(str(ROOT / rel)))


def load_figure_map() -> dict:
    """论文图 id -> {script, board, title, src, render}"""
    if not PAPER_MANIFEST.exists():
        return {}
    m = json.loads(PAPER_MANIFEST.read_text(encoding="utf-8"))
    return {f["id"]: f for f in m.get("figures", [])}


def _script_of(target: dict) -> list[str]:
    """目标引用到的脚本文件名（去掉参数、去掉 tools/ 前缀）。"""
    out = []
    for s in target["scripts"]:
        head = s.split()[0]
        out.append(Path(head).name)
    return out


def figure_owner(fig_id: str) -> dict | None:
    """某张论文图由哪个目标复现（按 FIGSET 的 script 反查）。"""
    rec = load_figure_map().get(fig_id)
    if not rec:
        return None
    scr = rec.get("script")
    for t in TARGETS:
        if scr in _script_of(t):
            return t
    return None


def check() -> int:
    print("=" * 78)
    print("FYP_HKBU 全链路复现性自检")
    print("=" * 78)
    npass = nfail = 0
    fails = []

    # 1 脚本存在
    for t in TARGETS:
        for s in t["scripts"]:
            head = s.split()[0]
            p = ROOT / head
            if p.exists():
                npass += 1
            else:
                nfail += 1
                fails.append("%-22s 脚本缺失: %s" % (t["name"], head))

    # 2 产物存在（light + measure；GPU 重跑目标本就可缺）
    for t in TARGETS:
        if t["level"] == HEAVY:
            continue
        for rel, need in t["outputs"]:
            got = _glob_count(rel)
            if got >= need:
                npass += 1
            else:
                nfail += 1
                fails.append("%-22s 产物不足: %s 期望>=%d 实得%d"
                             % (t["name"], rel, need, got))

    # 3 论文图全域覆盖（每张图的 script 都要有归属目标）
    figs = load_figure_map()
    if not figs:
        nfail += 1
        fails.append("paper_figures_manifest.json 缺失 → 无法验证论文图覆盖")
    else:
        orphans = [fid for fid in figs if figure_owner(fid) is None]
        if orphans:
            nfail += 1
            fails.append("论文图无归属目标 %d 张: %s"
                         % (len(orphans), ", ".join(sorted(orphans)[:8])))
        else:
            npass += 1
        # 3b 每张图的 src 文件必须真实存在（图包与源图一致性）
        miss_src = [fid for fid, r in figs.items()
                    if not (ROOT / "04_reports" / r["src"]).exists()]
        if miss_src:
            nfail += 1
            fails.append("论文图源文件缺失 %d 张: %s"
                         % (len(miss_src), ", ".join(sorted(miss_src)[:8])))
        else:
            npass += 1
        # 3c render=False 的图，其 script 必须确实是推理脚本（不得误标）
        INFER_SCRIPTS = {"_denoise_diagnosis.py",
                         "compare_separation_methods.py",
                         "_plot_denoise_spectral.py",
                         "_plot_denoise_spectrum_delta.py"}
        wrong = []
        for fid, r in figs.items():
            if not r.get("render", True) and r.get("script") not in INFER_SCRIPTS:
                wrong.append(fid)
            if r.get("render", True) and r.get("script") in INFER_SCRIPTS:
                wrong.append(fid)
        if wrong:
            nfail += 1
            fails.append("render 标记与脚本推理属性不符 %d 张: %s"
                         % (len(wrong), ", ".join(sorted(wrong)[:8])))
        else:
            npass += 1

    # 3d 复现边界表自洽（fresh clone 实测的边界必须指回真实的重建目标）
    bad_bd = _check_clone_boundary()
    if bad_bd:
        nfail += 1
        fails.append("复现边界表不自洽: " + "; ".join(bad_bd))
    else:
        npass += 1

    # 4 目标计数
    nl = sum(1 for t in TARGETS if t["level"] == LIGHT)
    nm = sum(1 for t in TARGETS if t["level"] == MEASURE)
    nheavy = sum(1 for t in TARGETS if t["level"] == HEAVY)
    print("目标总数 %d（重建 %d / 重测 %d / 重跑 %d）｜论文图 %d 张" %
          (len(TARGETS), nl, nm, nheavy, len(figs)))
    print("检查项：PASS %d / FAIL %d" % (npass, nfail))
    if fails:
        print("\n[FAIL] 明细：")
        for f in fails:
            print("  -", f)
    print("=" * 78)
    print("结果：", "全部通过 ✅" if nfail == 0 else "存在缺口 ❌")
    return 1 if nfail else 0


def do_manifest() -> int:
    print(json.dumps({
        "python": PY,
        "targets": [{
            "name": t["name"], "stage": t["stage"], "kind": t["kind"], "level": t["level"],
            "what": t["what"], "inference": t["inference"],
            "deterministic": t["deterministic"],
            "cmd": " ".join(['"%s"' % PY] + t["scripts"]),
            # scripts = 文件名（供「论文图→目标」反查）；cmds = 可直接执行的 argv 列表
            "scripts": _script_of(t),
            "cmds": [["%s" % PY, "-u"] + sc.split() for sc in t["scripts"]],
            "outputs": [{"glob": o, "min": n} for o, n in t["outputs"]],
            "figures": sorted(fid for fid in load_figure_map() if figure_owner(fid) is t),
        } for t in TARGETS],
        "clone_boundary": {k: {"kind": v[0], "why": v[1]}
                           for k, v in CLONE_BOUNDARY.items()},
        "n_targets": len(TARGETS),
        "n_figures": len(load_figure_map()),
    }, ensure_ascii=False, indent=1))
    return 0


def do_list() -> int:
    print("FYP_HKBU 复现目标清单（一条命令 = 一个产物家族）\n")
    cur = None
    for t in sorted(TARGETS, key=lambda x: (x["stage"], x["name"])):
        if t["stage"] != cur:
            cur = t["stage"]
            print("── 阶段 %s " % cur + "─" * 60)
        tag = {"light": "✅重建", "measure": "🔁重测", "heavy": "🔒重跑"}[t["level"]]
        print("  %-22s %s  %s" % (t["name"], tag, t["what"]))
        for sc in t["scripts"]:
            print('     "$PY" %s' % sc)
    print("\n提示：--figure <论文图id> 复现单图；--stage N 跑该阶段全部「重建」目标；"
          "重测/重跑目标需 --force-heavy。")
    return 0


def _run(t: dict) -> int:
    rc = 0
    for s in t["scripts"]:
        argv = ["%s" % PY, "-u"] + s.split()   # -u：子进程日志实时落盘，不留缓冲假象
        print("\n$", " ".join(argv))
        rc = subprocess.call(argv, cwd=str(ROOT), env=_render_env())
        if rc != 0:
            print("[FAIL] 上一步返回 %d，中止目标 %s" % (rc, t["name"]))
            return rc
    # 跑完即校验产物
    for rel, need in t["outputs"]:
        got = _glob_count(rel)
        mark = "OK " if got >= need else "BAD"
        print("  [%s] %-70s %d/%d" % (mark, rel, got, need))
        if got < need:
            rc = 3
    return rc


def run_target(t: dict, force_heavy: bool) -> int:
    if t["level"] != LIGHT and not force_heavy:
        kind = "重新测量" if t["level"] == MEASURE else "重跑（推理/训练）"
        print("[LOCKED] %s 是%s目标，未执行。" % (t["name"], kind))
        print("         %s" % t.get("note", ""))
        print("         确认要执行请加 --force-heavy。")
        return 2
    print("=" * 78)
    print("▶ %s ｜ %s" % (t["name"], t["what"]))
    print("=" * 78)
    return _run(t)


# ------------------------------------------------------------------ REPRODUCE.md
def build_readme() -> str:
    figs = load_figure_map()
    L = []
    A = L.append
    n_light = sum(1 for t in TARGETS if t["level"] == LIGHT)
    n_measure = sum(1 for t in TARGETS if t["level"] == MEASURE)
    n_heavy = sum(1 for t in TARGETS if t["level"] == HEAVY)
    A("# REPRODUCE — 全链路复现指南（T8.5，自动生成，勿手改）")
    A("")
    A("> 本文件由 `tools/reproduce.py --readme` 生成，`--verify` 可逐字节校验。")
    A("> 目标：**按本文件能复跑任一图 / 任一报告产物**。所有命令与产物路径均取自脚本本身，非手抄。")
    A("")
    A("## 0. 环境（唯一解释器）")
    A("")
    A("```bash")
    A('PY="%s"' % PY)
    A('$PY tools/paths.py                 # 路径中枢自检')
    A('$PY tools/selfcheck_project.py     # 模块 / 模型 / 数据集自检')
    A('$PY tools/reproduce.py --check     # 复现链自检（脚本在否 / 产物在否 / 53 图全覆盖）')
    A("```")
    A("")
    A("⚠️ **只能用上面的 venv**（`fyp_audio`）。系统 `python` 无 numpy，子进程会秒退，"
      "外层看起来像「推理失败」。")
    A("⚠️ **长任务（数小时~数天）必须走 Task Scheduler**（`tools/_bat/_sweep_launch.bat`），"
      "后台任务会随 Agent 会话结束被硬杀。")
    A("")
    A("## 1. 复现任意一张论文图")
    A("")
    A("```bash")
    A("$PY tools/reproduce.py --figure <论文图 id>        # 例：--figure fig-arch-demucs")
    A("```")
    A("")
    A("全部 **%d** 张论文图 → 复现归属如下（`脚本` 列即该图的生成脚本；"
      "`🔒` 表示该图源脚本含推理/重算，**已归档不再重跑**，只做 300 dpi 判据与图注）：" % len(figs))
    A("")
    A("| 图 id | 板 | 标题 | 组 | dpi 达标 | 复现归属 |")
    A("|:--|:-:|:--|:--|:-:|:--|")
    for fid in sorted(figs, key=lambda k: (figs[k]["board"], k)):
        r = figs[fid]
        own = figure_owner(fid)
        own_txt = ("🔒 `%s`" % own["name"]) if (own and own["inference"]) else \
                  ("`%s`" % own["name"] if own else "**未归属**")
        if not r.get("render", True):
            own_txt = "🔒 不重跑 · `%s`" % r.get("script", "")
        dpi = "✓单栏" if r.get("meets_300dpi") else "✗"
        A("| `%s` | %d | %s | %s | %s | %s |" %
          (fid, r["board"], r["title"], r["group"], dpi, own_txt))
    A("")
    A("## 2. 复现产物家族（一键）")
    A("")
    A("| 目标 | 阶段 | 级别 | 说明 | 命令 |")
    A("|:--|:-:|:-:|:--|:--|")
    for t in sorted(TARGETS, key=lambda x: (x["stage"], x["name"])):
        lvl = {"light": "✅ 重建", "measure": "🔁 重测", "heavy": "🔒 重跑"}[t["level"]]
        cmd = "$PY tools/reproduce.py --run %s" % t["name"]
        A("| `%s` | %d | %s | %s | `%s` |" %
          (t["name"], t["stage"], lvl, t["what"], cmd))
    A("")
    A("**批量**：")
    A("")
    A("```bash")
    A("$PY tools/reproduce.py --stage 7        # 跑某阶段全部「重建」目标")
    A("$PY tools/reproduce.py --all-report     # 跑全部「重建」目标（由归档数据确定性重画）")
    A("```")
    A("")
    A("## 3. 产物落点（每个目标对应什么文件）")
    A("")
    for t in sorted(TARGETS, key=lambda x: (x["stage"], x["name"])):
        A("### `%s` — %s" % (t["name"], t["what"]))
        A("")
        if t["requires"]:
            A("- 前置：%s" % "、".join("`%s`" % r for r in t["requires"]))
        if t["level"] != LIGHT:
            A("- ⚠️ **%s目标**；执行需 `--force-heavy`。%s"
              % ("重测" if t["level"] == MEASURE else "重跑", t.get("note", "")))
        elif t.get("note"):
            A("- 说明：%s" % t["note"])
        A("- 脚本：%s" % "、".join("`%s`" % s for s in t["scripts"]))
        A("- 产物：")
        for rel, need in t["outputs"]:
            got = _glob_count(rel)
            A("  - `%s`（下限 %d，当前 %d）" % (rel, need, got))
        A("")
    A("## 4. 重跑目标（默认锁死）")
    A("")
    A("以下 **%d** 个目标不是「由归档数据重建」——重测会改量测值、重跑含 GPU 推理 / 训练，"
      "`--run` 一律被拒绝；确认要执行时加 `--force-heavy`：" % (n_measure + n_heavy))
    A("")
    A("| 目标 | 级别 | 说明 | 备注 |")
    A("|:--|:-:|:--|:--|")
    for t in sorted(TARGETS, key=lambda x: x["name"]):
        if t["level"] != LIGHT:
            A("| `%s` | %s | %s | %s |"
              % (t["name"], {"measure": "🔁 重测", "heavy": "🔒 重跑"}[t["level"]],
                 t["what"], t.get("note", "—")))
    A("")
    A("## 5. 已知缺口（照报）")
    A("")
    render_false = sorted(fid for fid, r in figs.items() if not r.get("render", True))
    A("- **%d 张论文图不重跑**（源脚本含推理或写死 dpi）：%s。" %
      (len(render_false), "、".join("`%s`" % x for x in render_false)))
    A("- 其余 %d 张可重跑；`paper.figures` 目标按 `--board 1/2 render` 重建。" %
      (len(figs) - len(render_false)))
    A("- `--check` 会强制要求 **53/53 张图都有复现归属**，清单漂移即 FAIL。")
    A("- **重测 ≠ 重建**：`profile.measure` / `arch.trace` 会重新量测（含 `latency_s` 等计时列），"
      "其结果**本就不会逐字节相同**；故物理上仍读其产物的图（如画像图）只需保证"
      "**数据不变时逐字节一致**，不以「重测后也一致」为契约。")
    A("")
    A("## 6. 复现边界（fresh clone 实测）")
    A("")
    A("把 HEAD 导出到**不含本地数据树**的目录再跑 `--all-report`，以四级判定"
      "（逐字节 / 仅行尾 / 仅时间戳 / 仅计时）比对，结论：**%d/%d 个重建目标可逐字节复现**；"
      "下列目标**不可**，原因如下（实测证据见计划书 §9.13）："
      % (n_light - len(CLONE_BOUNDARY), n_light))
    A("")
    A("| 目标 | 类别 | 原因 |")
    A("|:--|:--|:--|")
    for _n in sorted(CLONE_BOUNDARY):
        _k, _w = CLONE_BOUNDARY[_n]
        A("| `%s` | %s | %s |" % (_n, CLONE_KIND.get(_k, _k), _w))
    A("")
    A("- **需本地数据**：生成时读 `01_models/` `02_databases/` `03_outputs/` 等未入库路径 —— "
      "在完整工程机上照常逐字节复现，clone 机上会缺内容、`sep.panels` 直接 FAIL。")
    A("- **下游产物**：自身不读原始数据，但内嵌了上面的图，故随之变化。")
    A("- 另有 1 类**移植性缺陷**已在 T8.6 修复：生成器曾把**本机绝对路径**"
      "（`str(FIG)`）写进 JSON，换目录即变字节；现改为相对 `PROJECT_ROOT` 的 POSIX 路径。"
      "（实验日志类 JSON 中的原始绝对路径属**溯源记录**，有意保留。）")
    A("")
    A("---")
    A("")
    A("_重建目标 %d 个 / 重测目标 %d 个 / 重跑目标 %d 个 / 论文图 %d 张。_" %
      (n_light, n_measure, n_heavy, len(figs)))
    return "\n".join(L) + "\n"


def do_readme(verify: bool) -> int:
    text = build_readme()
    if verify:
        if not REPRO_DOC.exists():
            print("[FAIL] 磁盘无 %s" % REPRO_DOC.relative_to(ROOT))
            return 1
        cur = REPRO_DOC.read_text(encoding="utf-8")
        if cur == text:
            print("[OK] REPRODUCE.md 与重建结果逐字节一致（%d 字符）" % len(text))
            return 0
        print("[FAIL] REPRODUCE.md 与重建结果不一致")
        a, b = cur.splitlines(), text.splitlines()
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else "<缺行>"
            y = b[i] if i < len(b) else "<缺行>"
            if x != y:
                print("  首个差异 第 %d 行:\n    磁盘: %s\n    重建: %s" % (i + 1, x[:120], y[:120]))
                break
        return 1
    REPRO_DOC.parent.mkdir(parents=True, exist_ok=True)
    REPRO_DOC.write_text(text, encoding="utf-8")
    print("[OK] 写出 %s（%d 行 / %d 字符）" %
          (REPRO_DOC.relative_to(ROOT), text.count("\n"), len(text)))
    return 0


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    # 行缓冲：重定向到文件时也能实时看到进度（否则「看起来卡死」）
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="FYP_HKBU 全链路复现入口（T8.5）")
    ap.add_argument("--list", action="store_true", help="列出全部目标")
    ap.add_argument("--check", action="store_true", help="校验复现链（脚本/产物/图覆盖）")
    ap.add_argument("--manifest", action="store_true", help="打印 JSON 清单")
    ap.add_argument("--figure", metavar="ID", help="复现指定论文图 id")
    ap.add_argument("--run", metavar="TARGET", help="运行指定目标")
    ap.add_argument("--stage", type=int, metavar="N", help="运行某阶段全部「重建」目标")
    ap.add_argument("--all-report", action="store_true",
                    help="运行全部「重建」目标（由归档数据确定性重画，不含重测/重跑）")
    ap.add_argument("--force-heavy", action="store_true", help="允许执行重跑（推理）目标")
    ap.add_argument("--readme", action="store_true", help="生成 REPRODUCE.md")
    ap.add_argument("--verify", action="store_true", help="配合 --readme：逐字节比对，不写盘")
    a = ap.parse_args(argv)

    if a.check:
        return check()
    if a.manifest:
        return do_manifest()
    if a.list:
        return do_list()
    if a.readme:
        return do_readme(a.verify)
    if a.figure:
        figs = load_figure_map()
        if a.figure not in figs:
            near = [k for k in figs if a.figure.split("-")[-1] in k][:6]
            print("[FAIL] 未知论文图 id: %s%s" %
                  (a.figure, ("；相近：%s" % ", ".join(near)) if near else ""))
            return 1
        t = figure_owner(a.figure)
        if t is None:
            print("[FAIL] 图 %s 没有归属目标（复现清单漂移）" % a.figure)
            return 1
        return run_target(t, a.force_heavy)
    if a.run:
        t = BY_NAME.get(a.run)
        if not t:
            print("[FAIL] 未知目标: %s（--list 查看）" % a.run)
            return 1
        return run_target(t, a.force_heavy)
    if a.stage is not None:
        ts = [t for t in TARGETS if t["stage"] == a.stage and t["level"] == LIGHT]
        if not ts:
            print("[FAIL] 阶段 %d 无轻量目标" % a.stage)
            return 1
        rc = 0
        for t in ts:
            rc |= run_target(t, a.force_heavy)
        return rc
    if a.all_report:
        rc = 0
        for t in sorted(TARGETS, key=lambda x: x["stage"]):
            if t["level"] == LIGHT:
                rc |= run_target(t, a.force_heavy)
        return rc
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""
================================================================================
 Valentini 全量降噪产物 · 逐模型图集 (F2 代表性子集)
--------------------------------------------------------------------------------
 背景
 ----
 `tools/_denoise_export_valentini.py` 已把 7 个降噪模型跑遍 Valentini 全量 824 条
 带噪片段, 产物落在 03_outputs/_valentini_denoise/<registry_key>/<clip>.wav。

 本脚本给这批【新产物】出图, 格式与 `tools/_make_model_figures.py` 完全一致
 (11 张图 + caption.json), 并放进同一棵产物树, 实现"和上面的图放在一起":

   04_reports/02_denoising/figures/_model_figs/<model_slug>/valentini/<clip_id>/fig*.png

 为什么不改 _make_model_figures.py
 ---------------------------------
 那个脚本 (801 行, 未纳入 git) 正在跑全量分离图集 (task 仍在运行中)。
 改它有截断风险且会与运行中的进程抢文件。故本脚本【import 复用】其
 make_figures / load_mono / assert_safe_target / DEN_MODELS 等, 零改动。

 范围 (用户 2026-10-13 拍板 F2)
 ------------------------------
 不是 824 条全出 (那要 824x7 = 5768 单元 / 63k 图 / ~19 GB),
 而是【按输入质量分层的 12 条代表片段】:
     good / mid / poor 三档各 4 条  ->  12 条 x 7 模型 = 84 单元 = 924 张图
 分层依据: 输入 SNR = 10*log10( sum(clean^2) / sum((noisy-clean)^2) )
           (Valentini 的 noisy 与 clean 逐样本对齐, 实测全 824 对等长)
 档内再按 SNR 四分位 x 时长 maximin 取 4 条, 兼顾 SNR 与时长两个维度。

 采样率口径
 ----------
 产物是【各模型原生格式】: mel_roformer_* -> 44100 Hz/2ch, denoiser_* -> 16000 Hz/1ch。
 故本脚本以 **产物自身采样率** 为对比率, 把 clean 参考重采样到同一率再出图
 (不把 16k 产物上采样到 44.1k 冒充原生 —— 与导出脚本口径一致)。
 片段时长 1.24~9.77 s, 均 < 30 s, 无需 30 s 截窗 (t_start 恒为 0)。

 用法
 ----
  python tools/_make_valentini_figures.py --pick          # 计算 12 条选择并落盘
  python tools/_make_valentini_figures.py --list          # 列单元 (12x7)
  python tools/_make_valentini_figures.py --all           # 出图 (可断点续跑)
  python tools/_make_valentini_figures.py --all --models A            # 只 mel 组
  python tools/_make_valentini_figures.py --all --clips p232_001,p232_005
  python tools/_make_valentini_figures.py --all --limit 2 # 冒烟: 每个模型前 2 条
  python tools/_make_valentini_figures.py --all --force   # 重画
================================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 复用主生成器: 出图函数 / 安全闸门 / 模型表 / 常量
import _make_model_figures as M  # noqa: E402

ROOT = M.ROOT
OUTPUTS = M.OUTPUTS
DEN_SUB = M.DEN_SUB
WIN_LENGTHS = M.WIN_LENGTHS
VAL = M.VAL
assert_safe_target = M.assert_safe_target
load_mono = M.load_mono
make_figures = M.make_figures
banner = M.banner

NOISY = VAL / "noisy_testset_wav"
CLEAN = VAL / "clean_testset_wav"
EXPORT_DIR = OUTPUTS / "_valentini_denoise"
EXPORT_MANIFEST = EXPORT_DIR / "manifest.json"

DOC_DEN = ROOT / "04_reports" / "02_denoising" / "docs"
SCRATCH = Path(__file__).resolve().parent / "_scratch"
SEL_JSON = SCRATCH / "valentini_f2_selection.json"
QUAL_JSON = SCRATCH / "valentini_quality_20261013.json"

PER_TIER = 4                      # 每档取几条
VAL_NS = "valentini"              # 产物树里的命名空间目录 (与探针 p232_001 同级)

# 展示名 (slug -> label)
DISPLAY = {
    "denoiser-dns48":             "Denoiser-DNS48",
    "denoiser-dns64":             "Denoiser-DNS64",
    "denoiser-master64":          "Denoiser-Master64",
    "mel-roformer-denoise":       "Mel-RoFormer-Denoise",
    "mel-roformer-denoise-aggr":  "Mel-RoFormer-Denoise-Aggr",
    "mel-roformer-dereverb":      "Mel-RoFormer-Dereverb",
    "mel-roformer-dereverb-echo": "Mel-RoFormer-Dereverb-Echo",
}
TIER_NAME = {0: "poor", 1: "mid", 2: "good"}
# (registry_key -> model_dir, registry_key, slug) 直接取自主脚本, 单一来源
KEY2SLUG = {prod: slug for _mdir, prod, slug in M.DEN_MODELS}


# ------------------------------------------------------------------ 工具 ----
def resolve_models(spec):
    """'A'/'B'/逗号分隔 slug 或 registry_key -> [registry_key]"""
    alias = {
        "A": ["mel_roformer_denoise", "mel_roformer_denoise_aggr",
              "mel_roformer_dereverb", "mel_roformer_dereverb_echo"],
        "B": ["denoiser_dns48", "denoiser_dns64", "denoiser_master64"],
    }
    valid = {prod for _m, prod, _s in M.DEN_MODELS}
    slug2key = {slug: prod for _m, prod, slug in M.DEN_MODELS}
    out = []
    for a in spec.split(","):
        a = a.strip()
        if not a:
            continue
        if a.upper() in alias:
            out += alias[a.upper()]
        elif a in valid:
            out.append(a)
        elif a in slug2key:
            out.append(slug2key[a])
        else:
            raise SystemExit("[FATAL] 未知模型: %s\n可用 slug: %s"
                             % (a, sorted(slug2key)))
    seen, uniq = set(), []
    for k in out:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq


def load_manifest():
    if EXPORT_MANIFEST.is_file():
        try:
            return json.loads(EXPORT_MANIFEST.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            pass
    return {"cells": {}}


# ------------------------------------------------------------- 片段选择 ----
def cmd_pick(args):
    """计算输入 SNR 分层 + 档内 maximin 取样, 写 SEL_JSON。"""
    clips = sorted(p.stem for p in NOISY.glob("*.wav")
                   if (CLEAN / p.name).is_file())
    print("Valentini 成对片段: %d" % len(clips))

    if QUAL_JSON.is_file():
        q = json.loads(QUAL_JSON.read_text(encoding="utf-8"))
        rows = q["rows"]
        print("复用已算好的质量表 %s" % QUAL_JSON.name)
    else:
        rows = []
        for i, cid in enumerate(clips, 1):
            n, sr = sf.read(str(NOISY / (cid + ".wav")),
                            dtype="float32", always_2d=True)
            cl, _ = sf.read(str(CLEAN / (cid + ".wav")),
                            dtype="float32", always_2d=True)
            n = n.mean(axis=1)
            cl = cl.mean(axis=1)
            L = min(len(n), len(cl))
            n, cl = n[:L], cl[:L]
            ec = float(np.sum(cl.astype(np.float64) ** 2))
            ee = float(np.sum((n - cl).astype(np.float64) ** 2))
            rows.append({
                "clip": cid,
                "snr_in": round(10 * np.log10((ec + 1e-12) / (ee + 1e-12)), 2),
                "dur": round(L / sr, 3),
            })
        q33, q67 = np.percentile([r["snr_in"] for r in rows], [33.333, 66.667])
        for r in rows:
            r["tier"] = 0 if r["snr_in"] < q33 else (1 if r["snr_in"] < q67 else 2)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        QUAL_JSON.write_text(json.dumps({"rows": rows, "q33": float(q33),
                                         "q67": float(q67)},
                                        ensure_ascii=False), encoding="utf-8")

    if "tier" not in rows[0]:
        q33, q67 = np.percentile([r["snr_in"] for r in rows], [33.333, 66.667])
        for r in rows:
            r["tier"] = 0 if r["snr_in"] < q33 else (1 if r["snr_in"] < q67 else 2)

    # ---- 档内 maximin: SNR 四分位保证质量覆盖, 时长 maximin 保证时长覆盖
    med_ld = float(np.median([np.log(r["dur"]) for r in rows]))
    by_tier = {0: [], 1: [], 2: []}
    for r in rows:
        by_tier[r["tier"]].append(r)

    chosen, seed_ld = [], [med_ld]
    for t in (2, 1, 0):                       # good -> mid -> poor
        sub = sorted(by_tier[t], key=lambda r: r["snr_in"])
        n = len(sub)
        for q in range(PER_TIER):
            lo = q * n // PER_TIER
            hi = max(lo + 1, (q + 1) * n // PER_TIER)
            window = sub[lo:hi]

            def score(r, _ref=tuple(seed_ld)):
                ld = np.log(r["dur"])
                return min(abs(ld - x) for x in _ref)

            best = max(window, key=lambda r: (score(r), r["snr_in"]))
            chosen.append(best)
            seed_ld.append(np.log(best["dur"]))

    chosen.sort(key=lambda r: (-r["tier"], r["snr_in"]))
    sel = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rule": ("输入 SNR 三分位分层, 每档 4 条; 档内按 SNR 四分位取窗, "
                 "窗内取时长 maximin (与已选 + 全局时长中位数距离最大)"),
        "metric": "SNR_in = 10log10(sum(clean^2)/sum((noisy-clean)^2)) dB",
        "clips": [{k: r[k] for k in ("clip", "snr_in", "dur", "tier")}
                  for r in chosen],
    }
    SCRATCH.mkdir(parents=True, exist_ok=True)
    SEL_JSON.write_text(json.dumps(sel, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    print("\n选定 %d 条 (good/mid/poor 各 %d):" % (len(chosen), PER_TIER))
    print("%-4s %-14s %8s %8s  %s" % ("#", "clip", "SNR_in", "dur(s)", "tier"))
    for i, r in enumerate(chosen, 1):
        print("%-4d %-14s %8.2f %8.2f  %s"
              % (i, r["clip"], r["snr_in"], r["dur"], TIER_NAME[r["tier"]]))
    print("\n[sel] %s" % SEL_JSON.relative_to(ROOT).as_posix())
    return 0


def load_selection(clips_arg=None):
    if clips_arg:
        return [{"clip": c.strip(), "snr_in": None, "dur": None, "tier": None}
                for c in clips_arg.split(",") if c.strip()]
    if not SEL_JSON.is_file():
        raise SystemExit("[FATAL] 缺少选择文件, 先跑 --pick: %s" % SEL_JSON)
    sel = json.loads(SEL_JSON.read_text(encoding="utf-8"))
    return sel["clips"]


# ------------------------------------------------------------------ 单元 ----
def val_units(keys, clips):
    """-> [(slug, key, clip_id, est_path, clean_path)]  (产物缺失则跳过)"""
    man = load_manifest()
    cells = man.get("cells", {})
    out = []
    for key in keys:
        slug = KEY2SLUG[key]
        for c in clips:
            cid = c["clip"]
            est = EXPORT_DIR / key / (cid + ".wav")
            if not est.is_file():
                continue
            out.append((slug, key, cid, est, CLEAN / (cid + ".wav"), c))
    return out


def do_val(slug, key, cid, est_p, clean_p, rec, force, man):
    outdir = DEN_SUB / slug / VAL_NS / cid
    marker = outdir / ".done"
    if marker.exists() and not force:
        return "skip"

    info = sf.info(str(est_p))
    sr = int(info.samplerate)
    nch = int(info.channels)
    cell = man.get("cells", {}).get("%s|%s" % (key, cid), {})
    target = cell.get("target", "enhanced")

    est = load_mono(est_p, sr, 0.0)
    ref = load_mono(clean_p, sr, 0.0)
    n = min(len(est), len(ref))
    est, ref = est[:n], ref[:n]

    snr = rec.get("snr_in")
    tier = TIER_NAME.get(rec.get("tier"), "?")
    est_label = "%s · %s" % (DISPLAY.get(slug, slug), target)
    ref_label = "clean reference (Valentini)"
    note = ("Valentini 全量降噪产物; 输入 noisy=%s.wav (输入SNR %s dB, %s 档, "
            "%.2fs); 产物原生 %d Hz / %d ch, clean 参考重采样到同一率; "
            "片段 < 30 s 不做截窗"
            % (cid, ("%.2f" % snr) if snr is not None else "-", tier,
               rec.get("dur") or (n / sr), sr, nch))
    make_figures(est, ref, sr, outdir,
                 est_label=est_label, ref_label=ref_label,
                 note=note, t_start=0.0)

    # 补写 caption 元数据
    cap_p = outdir / "caption.json"
    cap = json.loads(cap_p.read_text(encoding="utf-8"))
    cap.update({
        "source": "valentini_denoise_export",
        "model_key": key,
        "model_slug": slug,
        "model_label": DISPLAY.get(slug, slug),
        "target": target,
        "clip_id": cid,
        "input_snr_db": snr,
        "quality_tier": tier,
        "clip_dur_s": rec.get("dur"),
        "est_native_sr": sr,
        "est_native_ch": nch,
        "est_path": est_p.relative_to(ROOT).as_posix(),
        "ref_path": clean_p.relative_to(ROOT).as_posix(),
        "window_mode": "none (clip < 30 s, 不截窗)",
    })
    cap_p.write_text(json.dumps(cap, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    return "done"


# ------------------------------------------------------------------ 文档 ----
def write_docs(keys, clips, units):
    p = DOC_DEN / "FIGURES_valentini_F2.md"
    per = len(WIN_LENGTHS) + 7
    lines = [
        "# 降噪模型 · Valentini 全量产物图集（F2 代表性子集）",
        "",
        "## 一、这批图是什么",
        "",
        "- 来源：`tools/_denoise_export_valentini.py` 把 **7 个降噪模型** 跑遍 "
        "Valentini 全量 **824** 条带噪片段，产物落在 "
        "`03_outputs/_valentini_denoise/<模型>/<片段>.wav`。",
        "- 本批图只对其中 **%d 条代表片段** 出图（F2 口径，非全量 5768 单元）。"
        % len(clips),
        "- 出图格式与 `01_separation` 侧**完全一致**：每单元 **%d** 张图"
        "（fig1 / fig2 / fig3×2 / fig4×%d / fig5 / fig6×2）+ `caption.json`。"
        % (per, len(WIN_LENGTHS)),
        "- 与既有图**同树存放**（A1 隔离目录下新增 `valentini/` 命名空间）：",
        "",
        "```",
        "figures/_model_figs/<模型slug>/valentini/<片段id>/fig*.png",
        "```",
        "",
        "- 单元数：%d 条片段 × %d 模型 = **%d 单元 / %s 张图**"
        % (len(clips), len(keys), len(units), format(len(units) * per, ",")),
        "",
        "## 二、片段怎么选的（分层）",
        "",
        "输入质量指标（逐样本对齐，实测 824 对全部等长）：",
        "",
        "```",
        "SNR_in = 10 · log10( sum(clean²) / sum((noisy-clean)²) )   [dB]",
        "```",
        "",
        "按 SNR 三分位分档（poor / mid / good），每档再按 **SNR 四分位**取窗、"
        "窗内取 **时长 maximin** 的一条 → 每档 4 条，共 12 条，"
        "同时覆盖质量与时长两个维度。选择清单见 "
        "`tools/_scratch/valentini_f2_selection.json`。",
        "",
        "| # | 片段 | 输入 SNR (dB) | 时长 (s) | 档 |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(clips, 1):
        lines.append("| %d | `%s` | %s | %s | %s |"
                     % (i, c["clip"],
                        ("%.2f" % c["snr_in"]) if c.get("snr_in") is not None else "-",
                        ("%.2f" % c["dur"]) if c.get("dur") is not None else "-",
                        TIER_NAME.get(c.get("tier"), "-")))
    lines += [
        "",
        "## 三、模型与产物口径",
        "",
        "| 模型 | registry key | 原生采样率 | 增强目标 stem |",
        "|---|---|---|---|",
    ]
    for key in keys:
        slug = KEY2SLUG[key]
        rec = next((u for u in units if u[1] == key), None)
        sr_s = "-"
        if rec is not None:
            sr_s = "%d Hz / %d ch" % (sf.info(str(rec[3])).samplerate,
                                      sf.info(str(rec[3])).channels)
        tgt = "enhanced（单轨降噪/去混响）"
        if key == "mel_roformer_dereverb_echo":
            tgt = "dry（2-stem 的干声, 去混响残留）"
        lines.append("| %s | `%s` | %s | %s |"
                     % (DISPLAY.get(slug, slug), key, sr_s, tgt))
    lines += [
        "",
        "🔴 采样率口径：产物保存为**各模型原生格式**（mel_roformer \\* → 44100 Hz/2ch，"
        "denoiser \\* → 16000 Hz/1ch）。本批图以**产物自身采样率**为对比率，"
        "把 clean 参考重采样到同一率 —— 不把 16k 产物上采样到 44.1k 冒充原生。",
        "",
        "📌 与探针图的区别：`figures/_model_figs/<slug>/p232_001/` 是此前 "
        "`stage0_gate` 的 **1.74 s 探针**；本批 `.../valentini/p232_001/` 是 "
        "**全量导出的整段**（约 2–3 s）。同名不同源，看 `caption.json` 的 "
        "`source` 字段区分。",
        "",
        "## 四、单元清单",
        "",
        "| 模型 | 片段 | 输入SNR | 档 | 产物路径 |",
        "|---|---|---|---|---|",
    ]
    for slug, key, cid, est, clean, rec in units:
        lines.append("| %s | `%s` | %s | %s | `%s` |"
                     % (DISPLAY.get(slug, slug), cid,
                        ("%.2f" % rec["snr_in"]) if rec.get("snr_in") is not None else "-",
                        TIER_NAME.get(rec.get("tier"), "-"),
                        (DEN_SUB / slug / VAL_NS / cid).relative_to(ROOT).as_posix()))
    lines += [
        "",
        "## 五、缺哪些",
        "",
    ]
    man = load_manifest()
    cells = man.get("cells", {})
    missing = []
    for key in keys:
        for c in clips:
            if "%s|%s" % (key, c["clip"]) not in cells:
                missing.append("%s / %s" % (KEY2SLUG[key], c["clip"]))
    if missing:
        lines.append("以下单元格产物尚未导出（等 `_denoise_export_valentini.py` "
                     "跑完再补出图即可，本脚本可断点续跑）：")
        lines += ["", "```"] + missing + ["```"]
    else:
        lines.append("无 —— 全部 %d 个单元格产物齐备。" % (len(keys) * len(clips)))
    lines += [
        "",
        "## 六、图说明",
        "",
        "同 `01_separation` 侧。此处 `est` = 模型增强输出，`ref` = Valentini clean。",
        "",
    ]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ------------------------------------------------------- 跨模型联络图 ----
import matplotlib                    # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt      # noqa: E402
import librosa                       # noqa: E402
import librosa.display               # noqa: E402

# CJK 字体 (否则中文渲染成方框): 逐个候选探测, 找到就用
from matplotlib import font_manager as _fontmgr   # noqa: E402
_CJK_CAND = ["Microsoft YaHei", "SimHei", "DengXian", "Microsoft JhengHei",
             "SimSun", "Noto Sans CJK SC", "Source Han Sans SC",
             "Arial Unicode MS", "MS Gothic"]
_avail = {f.name for f in _fontmgr.fontManager.ttflist}
_CJK_PICK = next((n for n in _CJK_CAND if n in _avail), None)
if _CJK_PICK:
    matplotlib.rcParams["font.sans-serif"] = (
        [_CJK_PICK] + list(matplotlib.rcParams["font.sans-serif"]))
    matplotlib.rcParams["axes.unicode_minus"] = False

SHEET_SUB = DEN_SUB / "_cross_model_sheets"
N_FFT = 1024
HOP = 512
SR_DISPLAY = 16000                   # 统一显示采样率 (见下方口径说明)
DB_RANGE = 70.0                      # 色标动态范围 (dB)
FMAX_DISPLAY = SR_DISPLAY / 2.0      # = 8000 Hz


def _mag(y):
    return np.abs(librosa.stft(np.asarray(y, dtype=np.float32),
                               n_fft=N_FFT, hop_length=HOP))


def _panel_db(mag):
    return 20.0 * np.log10(mag + 1e-10)


def _to_display_rate(y, sr):
    """统一重采样到 SR_DISPLAY。只做降采样(44.1k/48k -> 16k), 不制造样本。"""
    if int(sr) == SR_DISPLAY:
        return y, int(sr)
    return (librosa.resample(np.asarray(y, dtype=np.float32),
                             orig_sr=int(sr), target_sr=SR_DISPLAY)
            .astype(np.float32), int(sr))


def make_sheet(clip, keys, man, force=False):
    """每个片段一张: 7 模型 est + clean 参考 = 8 面板 (2x4)。

    三个「统一」, 缺一个就没法跨模型直读:
      1. **统一显示采样率 16 kHz** —— 所有面板(含 clean 参考)都重采样到 16 kHz
         再算 STFT。denoiser 原生就是 16 kHz; mel 原生 44.1 kHz 这里做**降采样**
         (只丢 8 kHz 以上, 不制造样本)。这样 **n_fft/hop 在所有面板里对应相同的
         时间/频率分辨率** —— 否则 hop=512 在 16 kHz 是 32 ms、在 44.1 kHz 只有
         11.6 ms, denoiser 面板会「看起来更糊」, 那是分辨率差异不是模型差异。
         16 kHz 也正是本项目降噪评测的主口径。
      2. **统一显示带宽 0-8 kHz** —— = 16 kHz 的 Nyquist。mel 的 >8k 真实内容
         不在本图讨论 (否则是拿 mel 的 >8k 去比 denoiser 的不存在区; 见板 2 T5.6)。
      3. **跨面板同一 dB 色标** —— vmax = 本图最大峰, vmin = vmax - DB_RANGE。
         若逐面板归一, 安静段与语音段会被拉成同亮度, 跨模型判读即失效。
    """
    cid = clip["clip"]
    out = SHEET_SUB / ("%s_spectrogram_7models.png" % cid)
    if out.exists() and not force:
        return "skip"

    rows = []                    # (名称, target, y@16k, 原生sr)
    for key in keys:
        est_p = EXPORT_DIR / key / (cid + ".wav")
        if not est_p.is_file():
            continue
        y, sr = sf.read(str(est_p), dtype="float32", always_2d=True)
        y = y.mean(axis=1).astype(np.float32)
        y, sr_nat = _to_display_rate(y, sr)
        cell = man.get("cells", {}).get("%s|%s" % (key, cid), {})
        rows.append((DISPLAY.get(KEY2SLUG[key], key),
                     cell.get("target", "enhanced"), y, sr_nat))

    yc, src = sf.read(str(CLEAN / (cid + ".wav")), dtype="float32",
                      always_2d=True)
    yc = yc.mean(axis=1).astype(np.float32)
    yc, src_nat = _to_display_rate(yc, src)
    rows.append(("clean reference (Valentini)", "GT", yc, src_nat))

    mags = [_mag(r[2]) for r in rows]
    vmax = max(float(_panel_db(m).max()) for m in mags)
    vmin = vmax - DB_RANGE

    assert_safe_target(SHEET_SUB)
    SHEET_SUB.mkdir(parents=True, exist_ok=True)

    ncol = 4
    nrow = int(np.ceil(len(rows) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.3 * ncol, 3.4 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for ax in axes:
        ax.set_visible(False)

    img = None
    for i, ((name, tgt, y, sr_nat), mag) in enumerate(zip(rows, mags)):
        ax = axes[i]
        ax.set_visible(True)
        img = librosa.display.specshow(_panel_db(mag), sr=SR_DISPLAY,
                                       hop_length=HOP, x_axis="time",
                                       y_axis="hz", ax=ax, cmap="magma",
                                       vmin=vmin, vmax=vmax)
        ax.set_ylim(0, FMAX_DISPLAY)
        is_ref = name.startswith("clean")
        tag = "[%s | 原生 %d Hz]" % (tgt, sr_nat)
        ax.set_title("%s%s\n%s" % ("★ " if is_ref else "", name, tag),
                     fontsize=9)
        ax.set_ylabel("Hz" if i % ncol == 0 else "")
        if i < len(rows) - ncol:
            ax.set_xlabel("")

    snr = clip.get("snr_in")
    tier = TIER_NAME.get(clip.get("tier"), "?")
    fig.suptitle(
        "%s  |  输入 SNR %s dB (%s)  |  %.2f s  |  STFT n_fft=%d hop=%d @ %d Hz "
        "显示率  |  线性轴 0-%.1f kHz  |  色标 %.0f dB (跨面板同标尺)"
        % (cid, ("%.2f" % snr) if snr is not None else "-", tier,
           clip.get("dur") or 0.0, N_FFT, HOP, SR_DISPLAY,
           FMAX_DISPLAY / 1000.0, DB_RANGE), fontsize=10)
    fig.text(0.5, 0.004,
             "口径: 全面板统一重采样到 16 kHz (denoiser 原生率; mel 由 44.1 kHz "
             "降采样) -> 时间/频率分辨率一致, 面板间可直接比。"
             "显示带宽 0-8 kHz = 16 kHz 的 Nyquist; 8 kHz 以上不在本图讨论。",
             ha="center", fontsize=7.5, color="#555555")
    fig.subplots_adjust(top=0.85, bottom=0.10, hspace=0.45, wspace=0.12)
    if img is not None:
        cbar = fig.colorbar(img, ax=axes.tolist(), fraction=0.017, pad=0.01)
        cbar.set_label("dB", fontsize=8)
    fig.savefig(str(out), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "done"


def write_sheet_doc(keys, clips):
    p = DOC_DEN / "FIGURES_valentini_F2_sheets.md"
    lines = [
        "# Valentini 降噪 · 跨模型声纹联络图（每片段 1 张）",
        "",
        "每个片段一张：**7 个模型 + clean 参考 = 8 面板（2×4）**。",
        "",
        "```",
        "figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models.png",
        "```",
        "",
        "## 口径（三个「统一」，缺一个就没法跨模型直读）",
        "",
        "1. **统一显示采样率 16 kHz**：所有面板（含 clean 参考）都重采样到 16 kHz 再算 STFT。"
        "denoiser 系列原生就是 16 kHz；mel 系列原生 44.1 kHz，此处做**降采样**"
        "（只丢 8 kHz 以上，**不制造样本**）。"
        "这样 `n_fft=1024 / hop=512` 在每个面板里对应**相同的时间与频率分辨率** —— "
        "否则 hop=512 在 16 kHz 是 32 ms、在 44.1 kHz 只有 11.6 ms，denoiser 面板会"
        "「看起来更糊」，那是**分辨率差异，不是模型差异**。16 kHz 也正是本项目降噪评测的主口径。",
        "2. **统一显示带宽 0–8 kHz**：= 16 kHz 的 Nyquist。mel 系列 8 kHz 以上的**真实**内容"
        "不在本图讨论 —— 否则是拿 mel 的 >8k 去比 denoiser 的**不存在区**"
        "（对应板 2 的 T5.6 结论）。",
        "3. **跨面板同一 dB 色标**：以该图 8 个面板的最大峰为 `vmax`、`vmax−70 dB` 为 `vmin`。"
        "若改为逐面板归一，安静段与语音段会被拉成同亮度，跨模型判读即失效。",
        "",
        "`mel_roformer_dereverb_echo` 取 **`dry`（干声）** 支；★ = clean 参考面板。",
        "标题里的「原生 %d Hz」是该模型产物的**原始**采样率（图上显示前已统一到 16 kHz）。",
        "",
        "## 联络图清单",
        "",
        "| # | 片段 | 输入 SNR (dB) | 时长 (s) | 档 | 联络图文件 |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(clips, 1):
        fn = "%s_spectrogram_7models.png" % c["clip"]
        lines.append("| %d | `%s` | %s | %s | %s | `%s` |"
                     % (i, c["clip"],
                        ("%.2f" % c["snr_in"]) if c.get("snr_in") is not None else "-",
                        ("%.2f" % c["dur"]) if c.get("dur") is not None else "-",
                        TIER_NAME.get(c.get("tier"), "-"), fn))
    lines += [
        "",
        "## 怎么读",
        "",
        "- **横看一行**：同一频段里，哪个模型的能量块最接近 ★ clean 参考那一格。",
        "- **denoiser 三兄弟**（dns48 / dns64 / master64）常在**静音/纯噪段**透出低频底噪、"
        "语音段收紧 —— 与其「自适应噪声门控」的既有结论一致。",
        "- **mel 四兄弟**接近恒等映射，语音段形态与参考基本一致（`level_ratio` 0.96~1.00）。",
        "- **同一片段内对比**最干净：8 个面板同片段、同采样率、同窗、同色标、同频带，"
        "变量只有模型。",
        "- 若要看 **mel 的 8 kHz 以上真实行为**（或 denoiser 的 8 kHz 断崖），"
        "本图刻意不覆盖，需另出「原生采样率」版。",
        "",
    ]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _append_sheet_section_to_main_doc():
    p = DOC_DEN / "FIGURES_valentini_F2.md"
    if not p.is_file():
        return None
    txt = p.read_text(encoding="utf-8")
    marker = "## 七、跨模型联络图"
    if marker in txt:
        return p
    add = [
        "",
        marker,
        "",
        "每个片段另出一张 **7 模型 + clean 参考（2×4）** 的声纹联络图，"
        "清单与口径见 `FIGURES_valentini_F2_sheets.md`：",
        "",
        "```",
        "figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models.png",
        "```",
        "",
        "全面板**统一重采样到 16 kHz**（时间/频率分辨率一致）、统一显示带宽 "
        "**0–8 kHz**、跨面板**同一 dB 色标** → 可直接横向比较各模型的压制/保留行为。",
        "",
    ]
    p.write_text(txt + "\n".join(add), encoding="utf-8")
    return p


def cmd_sheet(args):
    keys = (resolve_models(args.models) if args.models
            else [prod for _m, prod, _s in M.DEN_MODELS])
    clips = load_selection(args.clips)
    if args.limit:
        clips = clips[:args.limit]
    man = load_manifest()
    banner("跨模型声纹联络图  模型 %d x 片段 %d   CJK字体=%s"
           % (len(keys), len(clips), _CJK_PICK or "(未找到, 中文会成方框)"))
    t0 = time.time()
    done = skipped = fail = 0
    for i, c in enumerate(clips, 1):
        try:
            r = make_sheet(c, keys, man, args.force)
        except SystemExit:
            raise
        except Exception as e:                              # noqa: BLE001
            print("[%3d/%d] %-40s FAIL  %s" % (i, len(clips), c["clip"], e))
            fail += 1
            continue
        done += (r == "done")
        skipped += (r == "skip")
        print("[%3d/%d] %-40s %-6s %5.1fs"
              % (i, len(clips), c["clip"], r, (time.time() - t0) / i))
    if clips:
        print("\n[doc] %s"
              % write_sheet_doc(keys, clips).relative_to(ROOT).as_posix())
        ap_ = _append_sheet_section_to_main_doc()
        if ap_:
            print("[doc] %s (追加 §七)" % ap_.relative_to(ROOT).as_posix())
    banner("联络图完成 done=%d skip=%d fail=%d  用时 %.1f min"
           % (done, skipped, fail, (time.time() - t0) / 60))
    return 0

# --------------------------------------------------- 跨模型联络图 · 原生率版 ----
# 与 @16 kHz 版同一批片段、同一 8 面板布局; 区别是【不做重采样】:
# 每个面板保持产物原生采样率 -> 原生带宽 (mel 22.05 kHz / denoiser 8 kHz /
# clean 24 kHz), 共享频率轴 0-24 kHz, 于是 denoiser 的 8 kHz 断崖与 mel 的
# >8 kHz 真实内容都直接可见。
#
# 分辨率口径: 为免重复 @16k 版修过的「分辨率混淆」, 这里把 n_fft/hop 按采样率
# 缩放 (基准 44.1 kHz: n_fft=1024, hop=512), 使各面板【时间与频率分辨率一致】:
#   Δt = hop/sr = 11.6 ms,  Δf = sr/n_fft = 43.1 Hz  (所有面板相同)
# 于是面板间差异只剩「原生带宽」这一个变量, 正是本图要看的。

SR_REF = 44100.0          # 分辨率基准 = 逐单元图的 n_fft=1024/hop=512 @44.1k
YMAX_NATIVE = 24000.0     # 共享频率显示上限 = 最大原生 Nyquist (clean 48k -> 24k)
NATIVE_TAG = "_native"


def _np_params(sr):
    """按采样率缩放 n_fft/hop, 保持 Δt=hop/sr 与 Δf=sr/n_fft 跨面板恒定。"""
    n_fft = max(256, int(round(N_FFT * sr / SR_REF)))
    hop = max(64, int(round(HOP * sr / SR_REF)))
    return n_fft, hop


def _stft_native(y, sr):
    n_fft, hop = _np_params(sr)
    mag = np.abs(librosa.stft(np.asarray(y, dtype=np.float32),
                              n_fft=n_fft, hop_length=hop))
    return mag, n_fft, hop


def make_sheet_native(clip, keys, man, force=False):
    """每个片段一张【原生采样率】8 面板联络图。

    与 `make_sheet` 的三点差别:
      1. **不重采样** —— 各面板按产物原生率做 STFT, 原生带宽完整保留。
      2. **共享频率显轴 0-24 kHz** —— = 最大原生 Nyquist (clean 48k), 于是各面板
         带宽差异直接可见; denoiser 面板 8 kHz 以上空白 = 物理上限 (青色虚线标
         该面板 Nyquist), 那道边就是 8 kHz 断崖。
      3. **n_fft/hop 随采样率缩放** —— 使 Δt=hop/sr 与 Δf=sr/n_fft 跨面板恒定
         (≈11.6 ms / ≈43.1 Hz), 免得 hop=512 在 16k=32ms、44.1k=11.6ms 造成
         「denoiser 更糊」的分辨率假象 (@16k 版已踩)。缩放后唯一变量 = 原生带宽。
    dB 色标仍跨面板统一 (vmax=图内最大峰, vmin=vmax-DB_RANGE)。
    """
    cid = clip["clip"]
    out = SHEET_SUB / ("%s_spectrogram_7models%s.png" % (cid, NATIVE_TAG))
    if out.exists() and not force:
        return "skip"

    rows = []                    # (名称, target, y@原生率, 原生sr)
    for key in keys:
        est_p = EXPORT_DIR / key / (cid + ".wav")
        if not est_p.is_file():
            continue
        y, sr = sf.read(str(est_p), dtype="float32", always_2d=True)
        y = y.mean(axis=1).astype(np.float32)
        cell = man.get("cells", {}).get("%s|%s" % (key, cid), {})
        rows.append((DISPLAY.get(KEY2SLUG[key], key),
                     cell.get("target", "enhanced"), y, int(sr)))

    yc, src = sf.read(str(CLEAN / (cid + ".wav")), dtype="float32",
                      always_2d=True)
    yc = yc.mean(axis=1).astype(np.float32)
    rows.append(("clean reference (Valentini)", "GT", yc, int(src)))

    stfts = [_stft_native(r[2], r[3]) for r in rows]
    mags = [s[0] for s in stfts]
    vmax = max(float(_panel_db(m).max()) for m in mags)
    vmin = vmax - DB_RANGE

    assert_safe_target(SHEET_SUB)
    SHEET_SUB.mkdir(parents=True, exist_ok=True)

    ncol = 4
    nrow = int(np.ceil(len(rows) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.3 * ncol, 3.4 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for ax in axes:
        ax.set_visible(False)

    img = None
    for i, ((name, tgt, y, sr_nat), (mag, n_fft, hop)) in enumerate(
            zip(rows, stfts)):
        ax = axes[i]
        ax.set_visible(True)
        img = librosa.display.specshow(_panel_db(mag), sr=sr_nat,
                                       hop_length=hop, n_fft=n_fft,
                                       x_axis="time", y_axis="hz", ax=ax,
                                       cmap="magma", vmin=vmin, vmax=vmax)
        ax.set_ylim(0, YMAX_NATIVE)
        ax.axhline(sr_nat / 2.0, color="cyan", lw=0.7, ls="--", alpha=0.85)
        is_ref = name.startswith("clean")
        tag = "[%s | 原生 %d Hz | Nyq %.1f kHz]" % (tgt, sr_nat, sr_nat / 2000.0)
        ax.set_title("%s%s\n%s" % ("★ " if is_ref else "", name, tag),
                     fontsize=9)
        ax.set_ylabel("Hz" if i % ncol == 0 else "")
        if i < len(rows) - ncol:
            ax.set_xlabel("")

    snr = clip.get("snr_in")
    tier = TIER_NAME.get(clip.get("tier"), "?")
    fig.suptitle(
        "%s  |  输入 SNR %s dB (%s)  |  %.2f s  |  原生采样率（不重采样）  |  "
        "n_fft/hop 按采样率缩放 → 跨面板 Δt=%.1f ms / Δf=%.1f Hz 一致  |  "
        "共享频率轴 0-%.1f kHz  |  色标 %.0f dB（跨面板同标尺）"
        % (cid, ("%.2f" % snr) if snr is not None else "-", tier,
           clip.get("dur") or 0.0, HOP / SR_REF * 1000.0,
           SR_REF / N_FFT, YMAX_NATIVE / 1000.0, DB_RANGE), fontsize=10)
    fig.text(0.5, 0.004,
             "口径: 每个面板保持【产物原生采样率】—— mel 22.05 kHz / denoiser 8 kHz / "
             "clean 24 kHz, 共享频率轴 0-24 kHz。denoiser 面板 8 kHz 以上为空白 = "
             "物理上限（青色虚线 = 该面板 Nyquist）, 那道边就是 8 kHz 断崖; "
             "mel 面板 8 kHz 以上是真实内容。为免分辨率混淆, n_fft/hop 随采样率缩放, "
             "使各面板时间/频率分辨率一致。",
             ha="center", fontsize=7.5, color="#555555")
    fig.subplots_adjust(top=0.85, bottom=0.10, hspace=0.45, wspace=0.12)
    if img is not None:
        cbar = fig.colorbar(img, ax=axes.tolist(), fraction=0.017, pad=0.01)
        cbar.set_label("dB", fontsize=8)
    fig.savefig(str(out), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "done"


def write_sheet_native_doc(keys, clips):
    p = DOC_DEN / "FIGURES_valentini_F2_sheets_native.md"
    lines = [
        "# Valentini 降噪 · 跨模型声纹联络图（原生采样率版）",
        "",
        "与 `FIGURES_valentini_F2_sheets.md`（16 kHz 统一率版）**同片段、同布局**"
        "（7 模型 + clean 参考 = 8 面板 2×4），区别是**不做重采样** —— "
        "每个面板保持**产物原生采样率**：",
        "",
        "```",
        "figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models_native.png",
        "```",
        "",
        "## 这一版用来看什么",
        "",
        "- **mel 系列 8 kHz 以上的真实内容**（原生 44.1 kHz，Nyquist 22.05 kHz）",
        "- **denoiser 系列的 8 kHz 断崖**（原生 16 kHz，Nyquist 8 kHz）—— "
        "面板 8 kHz 以上为空白，那是**物理上限**；青色虚线标出该面板 Nyquist",
        "- clean 参考原生 48 kHz（Nyquist 24 kHz），作标尺",
        "",
        "## 口径（与 16 kHz 版的唯一差别 + 一个防混淆处理）",
        "",
        "1. **不重采样**：各面板按原生率做 STFT → 原生带宽完整保留。",
        "2. **共享频率显示轴 0–24 kHz**（= 最大原生 Nyquist）→ 各面板带宽差异"
        "**直接可见**。",
        "3. **跨面板同一 dB 色标**（vmax = 图内最大峰，vmin = vmax−70 dB），"
        "同 16 kHz 版。",
        "4. **防分辨率混淆**：`n_fft`/`hop` 按采样率缩放（基准：44.1 kHz 下 "
        "n_fft=1024 / hop=512），使各面板 **Δt≈11.6 ms、Δf≈43.1 Hz 完全一致**。"
        "否则 hop=512 在 16 kHz 是 32 ms、44.1 kHz 只有 11.6 ms，denoiser 面板会"
        "「看起来更糊」—— 那是**分辨率差异不是模型差异**（@16 kHz 版已踩过）。"
        "缩放后，面板间差异只剩「原生带宽」这一个变量。",
        "",
        "## 联络图清单（原生率版）",
        "",
        "| # | 片段 | 输入 SNR (dB) | 时长 (s) | 档 | 原生率联络图 |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(clips, 1):
        fn = "%s_spectrogram_7models%s.png" % (c["clip"], NATIVE_TAG)
        lines.append("| %d | `%s` | %s | %s | %s | `%s` |"
                     % (i, c["clip"],
                        ("%.2f" % c["snr_in"]) if c.get("snr_in") is not None else "-",
                        ("%.2f" % c["dur"]) if c.get("dur") is not None else "-",
                        TIER_NAME.get(c.get("tier"), "-"), fn))
    lines += [
        "",
        "## 怎么读",
        "",
        "- **看 mel 面板的 8–22 kHz 区**：是否还有真实内容 / 谐波，还是已接近底噪。",
        "- **看 denoiser 面板的 8 kHz 边界**：边界上沿即断崖；边界以下为模型真实输出。",
        "- **两版对照看**：16 kHz 版看「同一频带内谁更接近 clean」，"
        "原生率版看「超出 8 kHz 的部分各模型如何处理」。",
        "- `mel_roformer_dereverb_echo` 取 **`dry`（干声）** 支；★ = clean 参考面板。",
        "",
    ]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _append_native_section_to_main_doc():
    p = DOC_DEN / "FIGURES_valentini_F2.md"
    if not p.is_file():
        return None
    txt = p.read_text(encoding="utf-8")
    marker = "## 八、跨模型联络图（原生采样率版）"
    if marker in txt:
        return p
    add = [
        "",
        marker,
        "",
        "每个片段另出一张**原生采样率**联络图（同 8 面板布局，不做重采样），"
        "用于查看 **mel 的 >8 kHz 真实内容** 与 **denoiser 的 8 kHz 断崖**。"
        "清单与口径见 `FIGURES_valentini_F2_sheets_native.md`：",
        "",
        "```",
        "figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models_native.png",
        "```",
        "",
        "各面板保持原生率、共享频率轴 **0–24 kHz**、跨面板同一 dB 色标；"
        "`n_fft`/`hop` 随采样率缩放，使各面板时间/频率分辨率一致。",
        "",
    ]
    p.write_text(txt + "\n".join(add), encoding="utf-8")
    return p


def cmd_sheet_native(args):
    keys = (resolve_models(args.models) if args.models
            else [prod for _m, prod, _s in M.DEN_MODELS])
    clips = load_selection(args.clips)
    if args.limit:
        clips = clips[:args.limit]
    man = load_manifest()
    banner("跨模型声纹联络图 · 原生率版  模型 %d x 片段 %d   CJK字体=%s"
           % (len(keys), len(clips), _CJK_PICK or "(未找到, 中文会成方框)"))
    t0 = time.time()
    done = skipped = fail = 0
    for i, c in enumerate(clips, 1):
        try:
            r = make_sheet_native(c, keys, man, args.force)
        except SystemExit:
            raise
        except Exception as e:                              # noqa: BLE001
            print("[%3d/%d] %-40s FAIL  %s" % (i, len(clips), c["clip"], e))
            fail += 1
            continue
        done += (r == "done")
        skipped += (r == "skip")
        print("[%3d/%d] %-40s %-6s %5.1fs"
              % (i, len(clips), c["clip"], r, (time.time() - t0) / i))
    if clips:
        print("\n[doc] %s"
              % write_sheet_native_doc(keys, clips).relative_to(ROOT).as_posix())
        ap_ = _append_native_section_to_main_doc()
        if ap_:
            print("[doc] %s (追加 §八)" % ap_.relative_to(ROOT).as_posix())
    banner("原生率联络图完成 done=%d skip=%d fail=%d  用时 %.1f min"
           % (done, skipped, fail, (time.time() - t0) / 60))
    return 0

# ------------------------------------- 跨模型联络图 · 双版合一 (16k + 原生率) ----
# 一张图里同时给出两种读法, 每个模型【上下相邻】:
#   上半组 (entity 1-4):  行0 = @16 kHz 对齐版  行1 = 原生率版
#   下半组 (entity 5-8):  行2 = @16 kHz 对齐版  行3 = 原生率版
# 同一列上下两格 = 同一个模型的两种读法 -> 直接对照, 不用来回翻文件。
#
# 两版的 y 轴刻意不同 (各自口径):
#   @16 kHz 行 -> 0-8 kHz (对齐版口径: 全面板重采样到 16 kHz, 只看同一频带)
#   原生率 行 -> 0-24 kHz (原生带宽: mel 22.05k / denoiser 8k / clean 24k)
# 色标仍【16 个面板共用一个】(vmax=全局最大峰, vmin=vmax-70 dB)。

BOTH_TAG = "_both"


def _collect_panels(clip, keys, man):
    """-> [(名称, target, y@原生率, 原生sr)] ; 末尾附 clean 参考。"""
    cid = clip["clip"]
    rows = []
    for key in keys:
        est_p = EXPORT_DIR / key / (cid + ".wav")
        if not est_p.is_file():
            continue
        y, sr = sf.read(str(est_p), dtype="float32", always_2d=True)
        y = y.mean(axis=1).astype(np.float32)
        cell = man.get("cells", {}).get("%s|%s" % (key, cid), {})
        rows.append((DISPLAY.get(KEY2SLUG[key], key),
                     cell.get("target", "enhanced"), y, int(sr)))
    yc, src = sf.read(str(CLEAN / (cid + ".wav")), dtype="float32",
                      always_2d=True)
    yc = yc.mean(axis=1).astype(np.float32)
    rows.append(("clean reference (Valentini)", "GT", yc, int(src)))
    return rows


def make_sheet_both(clip, keys, man, force=False):
    """每个片段一张【双版合一】联络图: 上=@16 kHz 对齐, 下=原生率, 同列同模型。"""
    cid = clip["clip"]
    out = SHEET_SUB / ("%s_spectrogram_7models%s.png" % (cid, BOTH_TAG))
    if out.exists() and not force:
        return "skip"

    rows = _collect_panels(clip, keys, man)
    n = len(rows)

    mags16, magsN = [], []
    for (_name, _tgt, y, sr_nat) in rows:
        y16, _ = _to_display_rate(y, sr_nat)
        mags16.append(_mag(y16))                      # 对齐版: 统一 16 kHz
        magsN.append(_stft_native(y, sr_nat)[0])      # 原生版: 原生率

    vmax = max(float(_panel_db(m).max()) for m in mags16 + magsN)
    vmin = vmax - DB_RANGE

    assert_safe_target(SHEET_SUB)
    SHEET_SUB.mkdir(parents=True, exist_ok=True)

    ncol = 4
    groups = [rows[i:i + ncol] for i in range(0, n, ncol)]
    nrow = len(groups) * 2                            # 每组 2 行 (对齐/原生)
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.3 * ncol, 2.55 * nrow))
    axes = np.atleast_2d(axes)

    img = None
    for gi, grp in enumerate(groups):
        for j, (name, tgt, y, sr_nat) in enumerate(grp):
            k = gi * ncol + j
            is_ref = name.startswith("clean")
            star = "★ " if is_ref else ""

            # ---------- 上: @16 kHz 对齐版 (0-8 kHz) ----------
            ax = axes[gi * 2, j]
            img = librosa.display.specshow(_panel_db(mags16[k]),
                                           sr=SR_DISPLAY, hop_length=HOP,
                                           x_axis="time", y_axis="hz", ax=ax,
                                           cmap="magma", vmin=vmin, vmax=vmax)
            ax.set_ylim(0, FMAX_DISPLAY)
            ax.set_title("%s%s\n〔16 kHz 对齐〕[%s]  0-%.0f kHz"
                         % (star, name, tgt, FMAX_DISPLAY / 1000.0), fontsize=8.5)
            ax.set_ylabel("Hz" if j == 0 else "")
            ax.set_xlabel("")
            # 时间轴与正下方原生率行完全相同 -> 刻度交给下面那行, 免得重复
            ax.tick_params(labelbottom=False)

            # ---------- 下: 原生率版 (0-24 kHz) ----------
            ax2 = axes[gi * 2 + 1, j]
            mag, n_fft, hop = _stft_native(y, sr_nat)
            img = librosa.display.specshow(_panel_db(mag), sr=sr_nat,
                                           hop_length=hop, n_fft=n_fft,
                                           x_axis="time", y_axis="hz", ax=ax2,
                                           cmap="magma", vmin=vmin, vmax=vmax)
            ax2.set_ylim(0, YMAX_NATIVE)
            ax2.axhline(sr_nat / 2.0, color="cyan", lw=0.7, ls="--", alpha=0.85)
            ax2.set_title("〔原生率 %d Hz · Nyq %.1f kHz〕[%s]"
                          % (sr_nat, sr_nat / 2000.0, tgt), fontsize=8.5)
            ax2.set_ylabel("Hz" if j == 0 else "")

    fig.subplots_adjust(top=0.885, bottom=0.085, hspace=0.72, wspace=0.13)

    # 组间分隔线 (只在两组之间画一条)
    for gi in range(len(groups) - 1):
        bb = axes[gi * 2 + 1, 0].get_position()
        yl = bb.y0 - 0.020
        fig.add_artist(plt.Line2D([0.02, 0.98], [yl, yl],
                                  transform=fig.transFigure,
                                  color="#888888", lw=1.0))

    snr = clip.get("snr_in")
    tier = TIER_NAME.get(clip.get("tier"), "?")
    fig.suptitle(
        "%s  |  输入 SNR %s dB (%s)  |  %.2f s  |  双版合一: 每列上=@16 kHz 对齐版 / "
        "下=原生率版  |  16 面板共用同一 dB 色标 (%.0f dB)"
        % (cid, ("%.2f" % snr) if snr is not None else "-", tier,
           clip.get("dur") or 0.0, DB_RANGE), fontsize=10, y=0.985)
    fig.text(0.5, 0.010,
             "口径: 上半版 (@16 kHz 对齐) 全面板重采样到 16 kHz, 各面板 Δt/Δf 一致, "
             "y 轴 0-8 kHz -> 读「同一频带内谁更接近 clean」; 下半版 (原生率) 各面板保持"
             "产物原生率 (mel 22.05k / denoiser 8k / clean 24k, 青虚线=各自 Nyquist), "
             "y 轴 0-24 kHz -> 读「>8 kHz 怎么处理」。两版行内各面板 Δt/Δf 已各自对齐 "
             "(对齐版 32 ms / 15.6 Hz; 原生率版 11.6 ms / 43.1 Hz), 故列内上下差异 = "
             "带宽与重采样口径, 不是分辨率。",
             ha="center", fontsize=7.5, color="#555555")

    cbar = fig.colorbar(img, ax=axes.ravel().tolist(), fraction=0.012, pad=0.008)
    cbar.set_label("dB", fontsize=8)
    fig.savefig(str(out), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "done"


def write_sheet_both_doc(keys, clips):
    p = DOC_DEN / "FIGURES_valentini_F2_sheets_both.md"
    lines = [
        "# Valentini 降噪 · 跨模型联络图（双版合一）",
        "",
        "每个片段一张图，**同图内同时给出两种读法**，每个模型**上下相邻**：",
        "",
        "```",
        "figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models_both.png",
        "```",
        "",
        "## 版面",
        "",
        "4 列 × 4 行 = 16 面板（8 个实体 × 2 个版本）：",
        "",
        "| 行 | 内容 |",
        "|---|---|",
        "| 行 0 | Denoiser-DNS48 / DNS64 / Master64 / Mel-RoFormer-Denoise — **@16 kHz 对齐版** |",
        "| 行 1 | 上面 4 个的 **原生率版** |",
        "| 行 2 | Mel-Denoise-Aggr / Mel-Dereverb / Mel-Dereverb-Echo / ★ clean — **@16 kHz 对齐版** |",
        "| 行 3 | 上面 4 个的 **原生率版** |",
        "",
        "→ **同一列上下两格 = 同一个模型**，直接对照，不用来回翻两个文件。",
        "",
        "## 两行的 y 轴刻意不同（各自口径）",
        "",
        "- **@16 kHz 对齐版行**：y 轴 **0–8 kHz**。全面板重采样到 16 kHz，"
        "各面板 Δt≈32 ms / Δf≈15.6 Hz 一致 → 读「**同一频带内谁更接近 clean**」。",
        "- **原生率行**：y 轴 **0–24 kHz**。各面板保持产物原生率"
        "（mel 22.05 kHz / denoiser 8 kHz / clean 24 kHz；青色虚线 = 各自 Nyquist），"
        "`n_fft`/`hop` 随率缩放使 Δt≈11.6 ms / Δf≈43.1 Hz 一致 → "
        "读「**>8 kHz 怎么处理**」（mel 保真 vs denoiser 物理封顶）。",
        "",
        "⚠️ 两行**不能跨行直接比幅度**：它们的分辨率参数与重采样口径不同。"
        "各自行内可横向比；列内**只能定性看带宽差异**。",
        "",
        "**色标**：16 个面板**共用一个**（vmax = 全图最大峰，vmin = vmax−70 dB）。",
        "",
        "## 联络图清单（双版合一）",
        "",
        "| # | 片段 | 输入 SNR (dB) | 时长 (s) | 档 | 双版合一联络图 |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(clips, 1):
        fn = "%s_spectrogram_7models%s.png" % (c["clip"], BOTH_TAG)
        lines.append("| %d | `%s` | %s | %s | %s | `%s` |"
                     % (i, c["clip"],
                        ("%.2f" % c["snr_in"]) if c.get("snr_in") is not None else "-",
                        ("%.2f" % c["dur"]) if c.get("dur") is not None else "-",
                        TIER_NAME.get(c.get("tier"), "-"), fn))
    lines += [
        "",
        "## 三个版本怎么选",
        "",
        "| 文件后缀 | 用途 |",
        "|---|---|",
        "| `_spectrogram_7models.png` | **16 kHz 对齐版**：同频带内跨模型比保真度（最干净的可比口径） |",
        "| `..._native.png` | **原生率版**：看 >8 kHz 的真实内容与 8 kHz 断崖 |",
        "| `..._both.png` | **双版合一**：一张图两读法，做汇报/放论文附图最省版面 |",
        "",
        "- `mel_roformer_dereverb_echo` 取 **`dry`（干声）** 支；★ = clean 参考面板。",
        "",
    ]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _append_both_section_to_main_doc():
    p = DOC_DEN / "FIGURES_valentini_F2.md"
    if not p.is_file():
        return None
    txt = p.read_text(encoding="utf-8")
    marker = "## 九、跨模型联络图（双版合一）"
    if marker in txt:
        return p
    add = [
        "",
        marker,
        "",
        "每片段再出一张**双版合一**图：4 列 × 4 行，同一列上下两格为**同一模型**的"
        "「@16 kHz 对齐版 / 原生率版」两种读法。清单与口径见 "
        "`FIGURES_valentini_F2_sheets_both.md`：",
        "",
        "```",
        "figures/_model_figs/_cross_model_sheets/<片段id>_spectrogram_7models_both.png",
        "```",
        "",
        "16 个面板共用同一 dB 色标；两行的 y 轴各自口径（对齐版 0–8 kHz / "
        "原生率版 0–24 kHz），**不可跨行比幅度**。",
        "",
    ]
    p.write_text(txt + "\n".join(add), encoding="utf-8")
    return p


def cmd_sheet_both(args):
    keys = (resolve_models(args.models) if args.models
            else [prod for _m, prod, _s in M.DEN_MODELS])
    clips = load_selection(args.clips)
    if args.limit:
        clips = clips[:args.limit]
    man = load_manifest()
    banner("跨模型声纹联络图 · 双版合一  模型 %d x 片段 %d   CJK字体=%s"
           % (len(keys), len(clips), _CJK_PICK or "(未找到, 中文会成方框)"))
    t0 = time.time()
    done = skipped = fail = 0
    for i, c in enumerate(clips, 1):
        try:
            r = make_sheet_both(c, keys, man, args.force)
        except SystemExit:
            raise
        except Exception as e:                              # noqa: BLE001
            print("[%3d/%d] %-40s FAIL  %s" % (i, len(clips), c["clip"], e))
            fail += 1
            continue
        done += (r == "done")
        skipped += (r == "skip")
        print("[%3d/%d] %-40s %-6s %5.1fs"
              % (i, len(clips), c["clip"], r, (time.time() - t0) / i))
    if clips:
        print("\n[doc] %s"
              % write_sheet_both_doc(keys, clips).relative_to(ROOT).as_posix())
        ap_ = _append_both_section_to_main_doc()
        if ap_:
            print("[doc] %s (追加 §九)" % ap_.relative_to(ROOT).as_posix())
    banner("双版合一联络图完成 done=%d skip=%d fail=%d  用时 %.1f min"
           % (done, skipped, fail, (time.time() - t0) / 60))
    return 0

# ------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", action="store_true", help="计算 12 条分层选择")
    ap.add_argument("--sheet", action="store_true", help="跨模型声纹联络图 (每片段 1 张)")
    ap.add_argument("--sheet-native", dest="sheet_native", action="store_true", help="联络图·原生采样率版 (看 >8k 与 8k 断崖)")
    ap.add_argument("--sheet-both", dest="sheet_both", action="store_true", help="联络图·双版合一 (上16k对齐/下原生率)")
    ap.add_argument("--list", action="store_true", help="列单元")
    ap.add_argument("--all", action="store_true", help="出图")
    ap.add_argument("--models", default=None, help="A/B 或逗号分隔 slug/key")
    ap.add_argument("--clips", default=None, help="逗号分隔片段id (覆盖 --pick 结果)")
    ap.add_argument("--limit", type=int, default=None, help="每个模型只做前 N 条")
    ap.add_argument("--force", action="store_true", help="忽略 .done 重画")
    a = ap.parse_args()

    if a.pick:
        return cmd_pick(a)

    if a.sheet:
        return cmd_sheet(a)

    if a.sheet_native:
        return cmd_sheet_native(a)

    if a.sheet_both:
        return cmd_sheet_both(a)

    keys = (resolve_models(a.models) if a.models
            else [prod for _m, prod, _s in M.DEN_MODELS])
    clips = load_selection(a.clips)
    if a.limit:
        clips = clips[:a.limit]

    units = val_units(keys, clips)
    per = len(WIN_LENGTHS) + 7

    if a.list or not a.all:
        print("Valentini 降噪图集 (F2)")
        print("模型 %d : %s" % (len(keys), [KEY2SLUG[k] for k in keys]))
        print("片段 %d : %s" % (len(clips), [c["clip"] for c in clips]))
        print("-" * 60)
        print("单元 %d  x 每单元 %d 图 = %s 图"
              % (len(units), per, format(len(units) * per, ",")))
        miss = len(keys) * len(clips) - len(units)
        if miss:
            print("⚠ 缺 %d 个单元格产物 (等导出脚本跑完, 重跑本脚本即可)" % miss)
        print("est. size 约 %.2f GB" % (len(units) * per * 298e3 / 1e9))
        print("输出根 : %s" % (DEN_SUB.relative_to(ROOT).as_posix()
                              + "/<slug>/" + VAL_NS + "/<clip>/"))
        return 0

    banner("Valentini 降噪图集 (F2)  单元 %d  x %d 图" % (len(units), per))
    man = load_manifest()
    t0 = time.time()
    done = skipped = fail = 0
    for i, (slug, key, cid, est, clean, rec) in enumerate(units, 1):
        tag = "%s/valentini/%s" % (slug, cid)
        try:
            r = do_val(slug, key, cid, est, clean, rec, a.force, man)
        except SystemExit:
            raise
        except Exception as e:                              # noqa: BLE001
            print("[%3d/%d] %-58s  FAIL  %s" % (i, len(units), tag[:58], e))
            fail += 1
            continue
        done += (r == "done")
        skipped += (r == "skip")
        el = time.time() - t0
        eta = (el / i) * (len(units) - i) / 60 if i else 0
        print("[%3d/%d] %-58s  %-8s %5.1fs  eta %5.1f min"
              % (i, len(units), tag[:58], r, el / i, eta))

    if units:
        print("\n[doc] %s" % write_docs(keys, clips, units).relative_to(ROOT).as_posix())
    banner("完成 done=%d skip=%d fail=%d  用时 %.1f min"
           % (done, skipped, fail, (time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""
================================================================================
 fig3_spectrogram_{est,ref} 的 **n_fft=2048 附加版**
--------------------------------------------------------------------------------
 背景 (用户 2026-10-13 要求)
 --------------------------
 用户在图集任务里认为 `fig3_spectrogram_ref` 的【频率细节】不够, 要求对同一批
 output 再做一份 **n_fft=2048** 版本。
 原 `fig3_*.png` = n_fft=1024 / hop=512 / y_axis="log" (见 _make_model_figures)。

 口径 (三条, 缺一不可)
 --------------------
 * **只加不减**: 产物名 `fig3_spectrogram_{est,ref}_nfft2048.png`,
   **绝不改动/覆盖** 原有 `fig3_spectrogram_{est,ref}.png`
   —— 原文件是 `_make_model_figures.py --all` 主任务的产物, 可能正在写。
 * **n_fft = 2048, hop = 1024** (= n_fft/2, 与 `fig4_spectrogram_win2048` 同档),
   y_axis = "log"。与原 fig3 唯一差别 = 频率分辨率翻倍 (43.1 Hz -> 21.5 Hz @44.1k)。
 * **跨单元同口径**: est / ref 用同一 n_fft/hop, 窗口口径沿用主脚本
   (WINDOW_MODE=energy, 默认), 故 est/ref 严格同窗可比。

 覆盖范围 (三套图集单元)
 ----------------------
   sep  板1 分离      figures/_model_figs/<Model>/<Song>/<stem>/
   den  板2 探针      figures/_model_figs/<slug>/p232_001/
   val  板2 Valentini figures/_model_figs/<slug>/valentini/<clip>/

 安全闸门
 --------
 * `assert_safe_target()` 复用主脚本 —— 拒绝写进受保护目录 (demucs/ 参照等)。
 * **只处理已存在 `.done` 的单元**: 主任务正在写的单元 (.done 未落) 一律不碰,
     避免半成品目录被写入 / caption.json 竞争。
 * **断点续跑**: 每单元写 `.done_nfft2048`; 已存在则 skip (--force 可重画)。
 * caption.json **尽力追加** (files 补 2 个新文件 + 加 "nfft2048" 小节); 失败不致命。

 运行
 ----
   python tools/_make_fig3_nfft2048.py --list                 # 只列可用单元
   python tools/_make_fig3_nfft2048.py --plan                 # 规模估算
   python tools/_make_fig3_nfft2048.py --all --scope all      # 全量 (三套)
   python tools/_make_fig3_nfft2048.py --all --scope sep      # 只板1
   python tools/_make_fig3_nfft2048.py --all --limit 5        # 冒烟
   python tools/_make_fig3_nfft2048.py --all --force          # 重画
================================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import _make_model_figures as M            # import 复用 (只读, 绝不改主脚本)

ROOT = M.ROOT
NFFT = 2048
HOP = NFFT // 2                             # = 1024, 与 fig4_spectrogram_win2048 同档
SFX = "_nfft2048"
MARK = ".done" + SFX


# ------------------------------------------------------------------ render ---
def _titles(est_label, ref_label, t_start):
    if t_start:
        est_label = "%s  [t_start=%.1fs]" % (est_label, t_start)
        ref_label = "%s  [t_start=%.1fs]" % (ref_label, t_start)
    return ("%s  |  log-freq (n_fft=%d)" % (est_label, NFFT),
            "%s  |  log-freq (n_fft=%d)" % (ref_label, NFFT))


def _update_caption(outdir, n, sr, t_start):
    """尽力把新增 2 个文件登记进 caption.json (失败只警告)。"""
    cp = outdir / "caption.json"
    try:
        cap = json.loads(cp.read_text(encoding="utf-8")) if cp.is_file() else {}
        added = sorted(p.name for p in outdir.glob("fig3*%s.png" % SFX))
        fl = list(cap.get("files", []))
        for x in added:
            if x not in fl:
                fl.append(x)
        cap["files"] = sorted(fl)
        cap["nfft2048"] = {
            "n_fft": NFFT, "hop_length": HOP, "y_axis": "log",
            "files": added,
            "duration_s": round(n / sr, 2),
            "t_start_s": round(t_start, 2),
            "window_mode": cap.get("window_mode"),
        }
        cp.write_text(json.dumps(cap, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    except Exception as e:                     # 绝不因 caption 失败而中断
        print("   [warn] caption 更新失败: %s" % e)


def render(est, ref, sr, outdir, est_label, ref_label, t_start=0.0, force=False):
    outdir = Path(outdir)
    M.assert_safe_target(outdir)               # A1 硬闸门
    if not outdir.is_dir():
        return "no-unit"
    if (outdir / MARK).exists() and not force:
        return "skip"
    n = min(len(est), len(ref)) if ref is not None else len(est)
    est = est[:n]
    ref = ref[:n] if ref is not None else None
    te, tr = _titles(est_label, ref_label, t_start)
    M.plot_spectrogram(est, sr, te,
                       outdir / ("fig3_spectrogram_est%s.png" % SFX),
                       n_fft=NFFT, hop_length=HOP, y_axis="log")
    if ref is not None:
        M.plot_spectrogram(ref, sr, tr,
                           outdir / ("fig3_spectrogram_ref%s.png" % SFX),
                           n_fft=NFFT, hop_length=HOP, y_axis="log")
    _update_caption(outdir, n, sr, t_start)
    (outdir / MARK).write_text("ok", encoding="utf-8")
    return "done"


# --------------------------------------------------------------- unit defs ---
def _unit_sep(model, song, stem, est_p, ref_p, mixed):
    """板1 一个单元 (sep)。loader 复刻 _make_model_figures.do_sep 的读法。"""
    outdir = M.SEP_SUB / M.slugify(model) / M.slugify(song) / M.slugify(stem)

    def load():
        anchor = ref_p if not mixed else (M.MUSDB_TEST / song / "vocals.wav")
        if anchor is not None and not Path(anchor).exists():
            anchor = None
        est, ref, t0, wnote = M.load_pair(est_p, anchor, M.SR_MUSDB,
                                         ref_anchor=not mixed)
        rl = "Ground-truth %s" % stem
        if mixed:
            rl = "GT vocals (NOT same target, shape ref only)"
        return est, ref, M.SR_MUSDB, t0, "%s · %s" % (model, stem), rl

    return ("sep", "%s/%s/%s" % (model, song, stem), outdir, load)


def _unit_den(slug):
    """板2 探针单元 (den): 固定 p232_001, 48 kHz 口径 (同 do_den)。"""
    return None                                 # 由 iter_units 内联构造


def _unit_val(dirp, cap):
    """板2 Valentini 单元 (val): 直接用 caption 里的 est/ref 路径与原生率。"""
    sr = cap.get("est_native_sr") or cap.get("sr") or M.SR_VAL
    est_p = ROOT / cap["est_path"]
    ref_p = (ROOT / cap["ref_path"]) if cap.get("ref_path") else None

    def load():
        est = M.load_mono(est_p, sr, 0.0)
        ref = M.load_mono(ref_p, sr, 0.0) if ref_p is not None else None
        return (est, ref, sr, 0.0,
                cap.get("est_label") or dirp.name,
                cap.get("ref_label") or "clean reference")

    return ("val", "%s/%s" % (dirp.parent.name, dirp.name), dirp, load)


def iter_units(scope="all", model=None, song=None):
    """-> [(kind, tag, outdir, load)]  (未过滤 .done; 过滤在 main 里做)"""
    out = []
    if scope in ("sep", "all"):
        for m in M.SEP_MODELS:
            if model and m != model:
                continue
            for (s, stem, est_p, ref_p, mixed) in M.sep_units(
                    m, [song] if song else None):
                out.append(_unit_sep(m, s, stem, est_p, ref_p, mixed))
    if scope in ("den", "all"):
        for (slug, est, noisy, clean) in M.den_units():
            if model and slug != model:
                continue
            outdir = M.DEN_SUB / slug / M.DEN_PROBE

            def load(est=est, clean=clean, slug=slug):
                return (M.load_mono(est, M.SR_VAL, 0.0),
                        M.load_mono(clean, M.SR_VAL, 0.0),
                        M.SR_VAL, 0.0,
                        "%s · enhanced" % slug,
                        "clean reference (Valentini %s)" % M.DEN_PROBE)

            out.append(("den", "%s/%s" % (slug, M.DEN_PROBE), outdir, load))
    if scope in ("val", "all"):
        for cp in sorted(M.DEN_SUB.glob("*/valentini/*/caption.json")):
            d = cp.parent
            if model and d.parent.name != model:
                continue
            try:
                cap = json.loads(cp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not cap.get("est_path"):
                continue
            out.append(_unit_val(d, cap))
    return out


# -------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="只列可用单元")
    ap.add_argument("--plan", action="store_true", help="规模估算")
    ap.add_argument("--all", action="store_true", help="全量")
    ap.add_argument("--sample", action="store_true", help="每模型首个单元")
    ap.add_argument("--scope", choices=["sep", "den", "val", "all"], default="all")
    ap.add_argument("--model", default=None, help="限定模型")
    ap.add_argument("--song", default=None, help="限定歌曲 (仅 sep)")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个 (冒烟)")
    ap.add_argument("--force", action="store_true", help="忽略 .done_nfft2048 重画")
    ap.add_argument("--window", choices=["first30", "energy"], default=None,
                    help="30s 窗口口径 (须与主任务一致; 默认 energy)")
    a = ap.parse_args()

    if a.window:
        M.WINDOW_MODE = a.window

    units = iter_units(a.scope, a.model, a.song)
    # 安全闸门: 只处理主任务已完成的单元 (.done 已落盘)
    ready = [u for u in units if (u[2] / ".done").is_file()]
    todo_cnt = {k: 0 for k in ("sep", "den", "val")}
    all_cnt = {k: 0 for k in ("sep", "den", "val")}
    for k, _t, _o, _l in units:
        all_cnt[k] += 1
    for k, _t, _o, _l in ready:
        todo_cnt[k] += 1
    pend = len(units) - len(ready)

    if a.list or a.plan:
        for k in ("sep", "den", "val"):
            print("%-4s  ready=%-5d / total=%-5d" % (k, todo_cnt[k], all_cnt[k]))
        print("-" * 48)
        print("ready units   : %d   (主任务已完成, 本脚本可处理)" % len(ready))
        print("pending units : %d   (主任务尚未完成 -> 跳过)" % pend)
        print("figs / unit   : 2  (fig3_est_nfft2048 + fig3_ref_nfft2048)")
        print("figs to write : %d" % (len(ready) * 2))
        print("n_fft / hop   : %d / %d" % (NFFT, HOP))
        print("marker        : %s" % MARK)
        print("window mode   : %s (sep/den 用; val 不截窗)" % M.WINDOW_MODE)
        return 0

    if not (a.all or a.sample):
        ap.print_help()
        return 2

    todo = ready
    if a.sample:
        seen, picked = set(), []
        for u in todo:
            if u[1] in seen:
                continue
            seen.add(u[1])
            picked.append(u)
        todo = picked
    if a.limit:
        todo = todo[:a.limit]

    print("=" * 78)
    print("fig3 n_fft=%d 附加版   待处理单元 %d  (每单元 2 图)  window=%s"
          % (NFFT, len(todo), M.WINDOW_MODE))
    print("=" * 78)
    t0 = time.time()
    done = skipped = failed = 0
    for i, (kind, tag, outdir, load) in enumerate(todo, 1):
        try:
            est, ref, sr, t_start, el, rl = load()
            r = render(est, ref, sr, outdir, el, rl, t_start, a.force)
        except SystemExit:
            raise
        except Exception as e:
            failed += 1
            print("[%4d/%d] %-56s  FAIL  %s" % (i, len(todo), tag[:56], e))
            continue
        done += (r == "done")
        skipped += (r == "skip")
        el_t = time.time() - t0
        eta = (el_t / i) * (len(todo) - i) / 60 if i else 0
        print("[%4d/%d] %-56s  %-6s %5.2fs  eta %5.1f min"
              % (i, len(todo), tag[:56], r, el_t / i, eta))

    print()
    print("=" * 78)
    print("完成  done=%d skipped=%d failed=%d  用时 %.1f min"
          % (done, skipped, failed, (time.time() - t0) / 60))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

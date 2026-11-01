# -*- coding: utf-8 -*-
"""
================================================================================
 fig3 n_fft=2048 附加版 —— 【独立模式】(不依赖主任务的 .done)
--------------------------------------------------------------------------------
 为什么需要这个脚本
 ------------------
 原 `_make_fig3_nfft2048.py` 有一条**安全闸门** (第 224-225 行):
     ready = [u for u in units if (u[2] / ".done").is_file()]
 即 "只处理主任务 `_make_model_figures.py --all` 已落 `.done` 的单元"。
 目的是避免与正在跑的主任务抢写 caption.json / 写进半成品目录。

 代价: **它的完成度被主任务封顶**, 永远追在主任务后面 -> "先完成任务二"做不到。

 本脚本把该闸门解除, 改为**直接从 03_outputs 的音频枚举全部 1600 个 sep 单元**
 (`M.sep_units()` 本来就不依赖 `.done`, 已实测返回 1600), 自己 mkdir,
 只出 2 张 nfft2048 图。

 安全性论证 (均已核对源码, 不是推断)
 ----------------------------------
 1. **不会被主任务删掉**: `_make_model_figures.py` 主流程**无任何删除操作**
    (`h.unlink()` 只在 `--cleanup-legacy-apply` 分支, `--all` 走不到);
    `make_figures` 只做 `outdir.mkdir(parents=True, exist_ok=True)`。
 2. **与主任务无文件名冲突**: 本脚本只写
    `fig3_spectrogram_{est,ref}_nfft2048.png`, 主任务写
    `fig3_spectrogram_{est,ref}.png` 等 11 个 -> 不重叠。
 3. **caption.json 绝不并发写**: 本脚本**完全不碰** caption.json, 改为每单元写
    `caption_nfft2048.json` (sidecar)。主任务跑完后用 `--merge-caption`
    一次性合并 (幂等, 可重复跑)。

 断点续跑
 --------
 沿用与原脚本**完全相同**的标记 `.done_nfft2048` -> 两者可互相接续, 不重复劳动。

 运行
 ----
   python tools/_make_fig3_nfft2048_indep.py --plan              # 规模估算
   python tools/_make_fig3_nfft2048_indep.py --all --scope sep   # 独立全量跑
   python tools/_make_fig3_nfft2048_indep.py --all --limit 5     # 冒烟
   python tools/_make_fig3_nfft2048_indep.py --merge-caption     # 主任务完成后合并
================================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import _make_model_figures as M                  # noqa: E402
import _make_fig3_nfft2048 as F                  # noqa: E402  (复用 render/unit 定义)

MARK = F.MARK                                    # ".done_nfft2048" (与原脚本共用)
SFX = F.SFX                                      # "_nfft2048"
SIDECAR = "caption_nfft2048.json"


# ------------------------------------------------------------ caption 旁路 ---
def _write_sidecar(outdir, n, sr, t_start):
    """独立模式专用: 绝不写 caption.json, 只写 sidecar -> 与主任务零竞争。

    由 F.render() 内部调用 (它按模块全局查 `_update_caption`, 故此处替换生效)。
    签名与原函数一致: (outdir, n, sr, t_start)。
    """
    try:
        outdir = Path(outdir)
        cap = {
            "n_fft": F.NFFT,
            "hop_length": F.HOP,
            "y_axis": "log",
            "files": sorted(p.name for p in outdir.glob("fig3*%s.png" % SFX)),
            "duration_s": round(n / sr, 2),
            "t_start_s": round(t_start, 2),
            "source": "indep",
            "note": "主任务跑完后用 --merge-caption 合并进 caption.json",
        }
        (outdir / SIDECAR).write_text(
            json.dumps(cap, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:                        # 绝不因 sidecar 失败而中断
        print("   [warn] sidecar 写失败: %s" % e)


F._update_caption = _write_sidecar                # 全局替换 -> render() 用它


# ------------------------------------------------------------------ plan ---
def cmd_plan(a) -> int:
    units = F.iter_units(a.scope, a.model, a.song)
    total, marked = Counter(), Counter()
    for kind, _tag, outdir, _load in units:
        total[kind] += 1
        if (outdir / MARK).is_file():
            marked[kind] += 1
    rem = sum(total.values()) - sum(marked.values())
    for k in ("sep", "den", "val"):
        if total[k]:
            print("%-4s  已做=%-5d / 共=%-5d   剩余=%d"
                  % (k, marked[k], total[k], total[k] - marked[k]))
    print("-" * 56)
    print("共 %d 单元, 已做 %d, **剩余 %d**" % (sum(total.values()),
                                              sum(marked.values()), rem))
    print("本模式不依赖主任务 .done -> 剩余部分本轮即可全部做完")
    print("每单元 2 图 -> 待写 %d 张 (n_fft=%d / hop=%d)" % (rem * 2, F.NFFT, F.HOP))
    print("参考速率 ~5 s/单元 -> 预计 %.1f min" % (rem * 5.0 / 60.0))
    return 0


# ------------------------------------------------------------------- run ---
def cmd_run(a) -> int:
    units = F.iter_units(a.scope, a.model, a.song)
    todo = [u for u in units
            if a.force or not (u[2] / MARK).is_file()]
    if a.limit:
        todo = todo[:a.limit]

    print("=" * 78)
    print("fig3 n_fft=%d 附加版 [独立模式]  待处理 %d 单元 (每单元 2 图)"
          % (F.NFFT, len(todo)))
    print("=" * 78)
    if not todo:
        print("没有待处理单元 (全部已带 %s)。" % MARK)
        return 0

    t0 = time.time()
    done = skipped = failed = 0
    for i, (kind, tag, outdir, load) in enumerate(todo, 1):
        try:
            outdir.mkdir(parents=True, exist_ok=True)     # 独立模式: 自己建目录
            est, ref, sr, t_start, el, rl = load()
            r = F.render(est, ref, sr, outdir, el, rl, t_start, a.force)
        except SystemExit:
            raise
        except Exception as e:
            failed += 1
            print("[%4d/%d] %-56s  FAIL  %s"
                  % (i, len(todo), tag[:56], e), flush=True)
            continue
        done += (r == "done")
        skipped += (r == "skip")
        el_t = time.time() - t0
        eta = (el_t / i) * (len(todo) - i) / 60 if i else 0
        print("[%4d/%d] %-56s  %-6s %5.2fs  eta %5.1f min"
              % (i, len(todo), tag[:56], r, el_t / i, eta), flush=True)

    print()
    print("=" * 78)
    print("完成  done=%d skipped=%d failed=%d  用时 %.1f min"
          % (done, skipped, failed, (time.time() - t0) / 60.0))
    print("=" * 78)
    return 0


# --------------------------------------------------------- merge-caption ---
def cmd_merge(a) -> int:
    """主任务跑完后, 把 sidecar 合并进 caption.json (幂等)。"""
    roots = [M.SEP_SUB, M.DEN_SUB]
    merged = missing = bad = 0
    for r in roots:
        if not r.is_dir():
            continue
        for sc in sorted(r.rglob(SIDECAR)):
            d = sc.parent
            cp = d / "caption.json"
            if not cp.is_file():
                missing += 1          # 主任务还没写到这个单元 -> 稍后再跑
                continue
            try:
                cap = json.loads(cp.read_text(encoding="utf-8"))
                scd = json.loads(sc.read_text(encoding="utf-8"))
            except Exception as e:
                print("  [warn] %s: %s" % (d, e))
                bad += 1
                continue
            fl = list(cap.get("files", []))
            for x in scd.get("files", []):
                if x not in fl:
                    fl.append(x)
            cap["files"] = sorted(fl)
            sec = dict(scd)
            sec.pop("source", None)
            sec.pop("note", None)
            cap["nfft2048"] = sec
            cp.write_text(json.dumps(cap, ensure_ascii=False, indent=2),
                          encoding="utf-8")
            merged += 1
    print("合并完成: merged=%d   caption.json 暂缺=%d   失败=%d"
          % (merged, missing, bad))
    if missing:
        print("(暂缺的单元 = 主任务尚未写完 -> 等主任务跑完后再跑一次本命令即可)")
    return 0


# ------------------------------------------------------------------ main ---
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="规模估算")
    ap.add_argument("--all", action="store_true", help="全量 (独立模式)")
    ap.add_argument("--scope", choices=["sep", "den", "val", "all"], default="all")
    ap.add_argument("--model", default=None, help="限定模型")
    ap.add_argument("--song", default=None, help="限定歌曲 (仅 sep)")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个 (冒烟)")
    ap.add_argument("--force", action="store_true", help="忽略 .done_nfft2048 重画")
    ap.add_argument("--merge-caption", dest="merge", action="store_true",
                    help="把 sidecar 合并进 caption.json (主任务跑完后用)")
    a = ap.parse_args()

    if a.merge:
        return cmd_merge(a)
    if a.plan:
        return cmd_plan(a)
    if not a.all:
        ap.print_help()
        return 2
    return cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())

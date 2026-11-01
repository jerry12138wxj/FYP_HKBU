# -*- coding: utf-8 -*-
"""
================================================================================
 驱动 _make_fig3_nfft2048.py 直到全部图集单元的 **n_fft=2048 附加版** 完成
--------------------------------------------------------------------------------
 与 `_run_figures_until_done.py` 同构（那是主图集任务的驱动），三点差别:
   * worker = tools/_make_fig3_nfft2048.py
   * 完成标记 = `.done_nfft2048`（与主任务的 `.done` 互不干扰）
   * 统计根 = 两个图集根（01_separation + 02_denoising）

 为什么也需要「被杀就重来」的外层循环
 ----------------------------------
 本项目实测：**由 agent 会话发起的后台进程会在该回合结束时被硬杀**
 （见 `tools/_bat/_denoise_full.bat` 顶部；2026-10-13 在分离图集任务上连续复现两次）。
 且 Ctrl-C 会打断整个控制台进程组 -> 故本驱动忽略 SIGINT，worker 另开进程组。
 所以本任务由用户**双击 bat**（脱离会话）运行；中途被打断也能续跑。

 幂等
 ----
 worker 每个单元写 `.done_nfft2048`；已完成的单元直接 skip。
 故：**随时可重复运行**，只补做缺的单元，不重复劳动。

 用法
 ----
   python tools/_run_fig3_2048_until_done.py            # 通常由 bat 调起
================================================================================
"""
from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "_make_fig3_nfft2048.py"
FIG_ROOTS = [
    ROOT / "04_reports" / "01_separation" / "figures" / "_model_figs",
    ROOT / "04_reports" / "02_denoising" / "figures" / "_model_figs",
]
MARK = ".done_nfft2048"
PLAN_TOTAL = 1691          # sep 1600 + den 7 + val 84
MAX_PASSES = 60


def count_done() -> int:
    n = 0
    for r in FIG_ROOTS:
        if r.is_dir():
            n += sum(1 for _ in r.rglob(MARK))
    return n


def main() -> int:
    if not SCRIPT.is_file():
        print("[driver] FATAL 找不到 %s" % SCRIPT, flush=True)
        return 2

    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        print("[driver] Ctrl-C 已屏蔽(要停请直接关闭本窗口)", flush=True)
    except Exception:
        pass

    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    for i in range(1, MAX_PASSES + 1):
        n0 = count_done()
        print("[driver] ===== pass %d start  done=%d/%d (%.1f%%) ====="
              % (i, n0, PLAN_TOTAL, 100.0 * n0 / PLAN_TOTAL), flush=True)
        t0 = time.time()
        try:
            rc = subprocess.call([sys.executable, "-X", "utf8", "-u", str(SCRIPT),
                                  "--all"], creationflags=flags)
        except KeyboardInterrupt:
            print("[driver] 收到 Ctrl-C，停止", flush=True)
            return 130
        n1 = count_done()
        print("[driver] pass %d exit=%s  done %d -> %d (+%d)  %.1f min"
              % (i, rc, n0, n1, n1 - n0, (time.time() - t0) / 60.0), flush=True)

        if n1 >= PLAN_TOTAL:
            print("[driver] 全部 %d 单元完成 ✓" % PLAN_TOTAL, flush=True)
            return 0
        if n1 == n0:
            print("[driver] 本轮零进展 -> 停 (done=%d/%d)。"
                  " 若主图集任务还没跑完, 等它跑完后再运行本驱动即可补齐剩余单元。"
                  % (n1, PLAN_TOTAL), flush=True)
            return 0 if n1 >= PLAN_TOTAL else 1

    print("[driver] 达到最大轮次 %d，done=%d/%d"
          % (MAX_PASSES, count_done(), PLAN_TOTAL), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

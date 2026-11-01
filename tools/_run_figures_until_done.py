# -*- coding: utf-8 -*-
"""
================================================================================
 驱动 _make_model_figures.py --all 直到全部分离图集单元完成
--------------------------------------------------------------------------------
 为什么要这个「外层循环」
 ----------------------
 `_make_model_figures.py --all` 本身可断点续跑（靠每单元末尾的 `.done`），但
 它有一个致命前提: **进程必须一直活着**。

 本项目实测（`tools/_bat/_denoise_full.bat` 顶部记录）:
   2026-09-21 测到、2026-09-23 复现 —— **由 agent 会话发起的后台进程，会在该
   回合结束时被硬杀**（无 traceback；进行中的单元留下半成品图、无 `.done`）。
   2026-10-13 在这个分离图集任务上**又连续复现两次**（01:10 与 02:13 各死一次）。

 所以本任务必须在**会话之外**运行（用户双击 bat / 任务计划程序）。而会话之外也
 可能被偶发事件打断（休眠、资源回收），故再加一层「**被杀就重来**」：
   每次 `--all` 跑完（或被杀）后重新统计 `.done`；只要还在增长就继续下一轮；
   某一轮完全没进展 = 已经跑完 -> 停。
 因为断点续跑靠 `.done`，重来**不会重复劳动**，只会重做被杀的那一个单元。

 用法
 ----
 通常由 `tools/_bat/_figures_full.bat` 调起；也可直接:
   python tools/_run_figures_until_done.py
================================================================================
"""
from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "_make_model_figures.py"
FIG_ROOT = ROOT / "04_reports" / "01_separation" / "figures" / "_model_figs"
PLAN_TOTAL = 1607                 # 全量计划的单元数（脚本头部会打印，用于进度显示）
MAX_PASSES = 60                   # 安全上限，别无限循环


def count_done() -> int:
    return sum(1 for _ in FIG_ROOT.rglob(".done"))


def main() -> int:
    if not SCRIPT.is_file():
        print("[driver] FATAL 找不到 %s" % SCRIPT, flush=True)
        return 2

    # 2026-10-13 事故: 在 bat 窗口按 Ctrl-C 会把**整个控制台进程组**都打断,
    # 连驱动一起杀掉(日志里只剩一个 ^C, 没有 pass 2 头) -> 剩余 1238 单元白停。
    # 修: 驱动忽略 SIGINT, 并让 worker 另开进程组 -> Ctrl-C 不再能打断本任务。
    # 要停就关掉那个 cmd 窗口(关窗会给全组发 CTRL_CLOSE_EVENT)。
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        print("[driver] Ctrl-C 已屏蔽(要停请直接关闭本窗口)", flush=True)
    except Exception:
        pass

    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    prev = -1
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
            # 一整轮没有任何新 .done -> 要么已完成，要么卡住（不再瞎转）
            print("[driver] 本轮零进展 -> 停（done=%d/%d）" % (n1, PLAN_TOTAL),
                  flush=True)
            return 1 if n1 < PLAN_TOTAL else 0
        prev = n1

    print("[driver] 达到最大轮次 %d，仍有 %d 单元未完成"
          % (MAX_PASSES, PLAN_TOTAL - count_done()), flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

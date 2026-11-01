"""bench500 finalizer: wait for the two open jobs, re-bench DPRNN, build the table.

Why this exists
---------------
The 500-segment comparison was produced while DPRNN still used the *leaked*
checkpoint.  The retrained model lives in a different directory, so simply
editing the old csv would mix two different weights under one name.  This
driver therefore:

  1. waits until both open jobs really finished (rpca 500/500 segments and the
     DPRNN retrain process exited),
  2. re-runs the 500 segments for the NEW checkpoint into `dprnn_v2.csv`
     (and `dprnn_v2_last.csv` for last.pt, kept out of the ranking so that one
     model cannot occupy two rows),
  3. builds the two-family comparison table.

Every step is idempotent: finished stages are skipped on re-run.

Usage:
    python tools/_bench500_finalize.py                    # wait up to 240 min
    python tools/_bench500_finalize.py --wait-minutes 0   # fail fast
    python tools/_bench500_finalize.py --skip-bench       # table only
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import paths as _paths  # noqa: E402

_paths.setup_env()

PY = sys.executable
BENCH = TOOLS / "_bench500.py"
TABLE = TOOLS / "_bench500_table.py"
OUT = _paths.PROJECT_ROOT / "baseline" / "bench500"
RESULTS = OUT / "results"
DPRNN_RUN = Path(r"D:\FYP_HKBU_runs\dprnn_v2")
N_SEG = 500
N_ROWS_4STEM = N_SEG * 4


def rows_of(p):
    if not p.is_file():
        return 0
    with open(p, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def seg_count(p):
    if not p.is_file():
        return 0
    with open(p, encoding="utf-8-sig", newline="") as f:
        return len({r["seg_id"] for r in csv.DictReader(f)})


def tail(p, n=4000):
    if not p.is_file():
        return ""
    with open(p, "rb") as f:
        try:
            f.seek(-n, os.SEEK_END)
        except OSError:
            f.seek(0)
        return f.read().decode("utf-8", "replace")


def status():
    rpca = seg_count(RESULTS / "rpca.csv")
    run_out = DPRNN_RUN / "run.out"
    exited = "exit code =" in tail(run_out)
    log = DPRNN_RUN / "train_dprnn_v2.log"
    stale = (not log.is_file()) or (time.time() - log.stat().st_mtime > 300)
    ck = DPRNN_RUN / "checkpoints" / "best.pt"
    return dict(rpca_seg=rpca, rpca_done=rpca >= N_SEG,
                dprnn_exited=exited, dprnn_log_stale=stale,
                dprnn_done=exited or (stale and ck.is_file()),
                dprnn_best=[str(ck), ck.stat().st_size if ck.is_file() else 0],
                dprnn_best_mtime=(time.strftime("%Y-%m-%d %H:%M:%S",
                                                time.localtime(ck.stat().st_mtime))
                                  if ck.is_file() else None))


def wait_ready(wait_minutes):
    t0 = time.time()
    limit = wait_minutes * 60
    while True:
        s = status()
        print("[%s] rpca=%d/%d dprnn_exited=%s log_stale=%s best=%s"
              % (time.strftime("%H:%M:%S"), s["rpca_seg"], N_SEG,
                 s["dprnn_exited"], s["dprnn_log_stale"], s["dprnn_best_mtime"]))
        if s["rpca_done"] and s["dprnn_done"]:
            return s
        if time.time() - t0 > limit:
            print("NOT_READY after %.0f min" % wait_minutes)
            return None
        time.sleep(60)


def last_only_dir(ckdir):
    """给 `last.pt` 造一个只放 last.pt 的目录。

    `_dprnn_loader.build("best.pt")` 在 best.pt 缺失时会回落到 last.pt，
    而 `load_dprnn()` 写死传 "best.pt"。所以想评 last.pt，只能换目录而不是换参数
    ——直接把 last.pt 单独放一处最稳（不复制 44 MB 就硬链接，失败再退回复制）。
    """
    d = ckdir.parent / "ckpt_last_only"
    d.mkdir(parents=True, exist_ok=True)
    src, dst = ckdir / "last.pt", d / "last.pt"
    if dst.is_file() and dst.stat().st_size == src.stat().st_size:
        return d
    try:
        if dst.exists():
            dst.unlink()
        os.link(src, dst)
        print("  hardlinked last.pt -> %s" % d)
    except OSError:
        shutil.copy2(src, dst)
        print("  copied last.pt -> %s" % d)
    return d


def bench(label, ckpt_dir, force=False):
    p = RESULTS / ("%s.csv" % label)
    if rows_of(p) >= N_ROWS_4STEM and not force:
        print("skip bench %s: already %d rows" % (label, rows_of(p)))
        return True
    env = dict(os.environ)
    env["FYP_DPRNN_CKPT_DIR"] = str(ckpt_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [PY, "-X", "utf8", "-u", str(BENCH), "model",
           "--model", "dprnn", "--label", label, "--force"]
    print("bench %s  ckpt_dir=%s" % (label, ckpt_dir))
    r = subprocess.run(cmd, cwd=str(_paths.PROJECT_ROOT), env=env)
    ok = r.returncode == 0 and rows_of(p) >= N_ROWS_4STEM
    print("  -> rc=%d rows=%d ok=%s" % (r.returncode, rows_of(p), ok))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-minutes", type=int, default=240)
    ap.add_argument("--skip-bench", action="store_true")
    ap.add_argument("--out-dir", default=r"D:\FYP_HKBU_runs\bench500_table")
    a = ap.parse_args()

    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    s = wait_ready(a.wait_minutes)
    report["status"] = s
    if s is None:
        report["result"] = "NOT_READY"
        p = Path(a.out_dir) if Path(a.out_dir).is_dir() else DPRNN_RUN
        (p / "BENCH500_STATUS.json").write_bytes(
            json.dumps(report, ensure_ascii=False, indent=1).encode("utf-8"))
        print("result: NOT_READY (jobs still running)")
        return 2

    if not a.skip_bench:
        ckdir = DPRNN_RUN / "checkpoints"
        ok1 = bench("dprnn_v2", ckdir)
        report["steps"].append({"stage": "bench_best", "ok": ok1})
        if (ckdir / "last.pt").is_file():
            # 注意：不能直接传 ckdir，否则 last 标签下跑的仍是 best.pt
            ok2 = bench("dprnn_v2_last", last_only_dir(ckdir))
            report["steps"].append({"stage": "bench_last", "ok": ok2})

    r = subprocess.run([PY, "-X", "utf8", "-u", str(TABLE), "--out-dir", a.out_dir],
                       cwd=str(_paths.PROJECT_ROOT))
    report["steps"].append({"stage": "table", "rc": r.returncode})
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    report["result"] = "OK" if r.returncode == 0 else "TABLE_FAILED"

    outdir = Path(a.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "BENCH500_STATUS.json").write_bytes(
        json.dumps(report, ensure_ascii=False, indent=1).encode("utf-8"))
    print("result: %s -> %s" % (report["result"], outdir))
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

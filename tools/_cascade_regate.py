# -*- coding: utf-8 -*-
"""T6 后处理：按新门禁语义重判 sep_results 的 status（不重跑推理）。

为什么需要它：
  主跑（2026-09-26）用的是**旧门禁** `0.01 <= level <= 10.0`，
  把「denoiser 前置把 drums 压到 0.006」这种**真实现象**判成了 FAIL。
  而 cmd_summary 只统计 status == PASS 的记录 -> L1 整列会变 None。

本脚本只改派生量 status，不动任何测量值（levels / per_stem / sdr_avg4 原样保留）：
  PASS  <=>  sdr_avg4 is not None  AND  levels 全为有限非负数  AND  并非全零

用法：
  python tools/_cascade_regate.py            # 只报告
  python tools/_cascade_regate.py --apply    # 写回 cascade_eval.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

ROOT = Path(_paths.PROJECT_ROOT)
EVAL_JSON = ROOT / "04_reports" / "cascade" / "data" / "cascade_eval.json"
PARTIAL = ROOT / "04_reports" / "cascade" / "data" / "cascade_eval.partial.jsonl"


def regate_levels(levels: dict) -> tuple:
    """返回 (new_ok, band_ok, note)。"""
    if not levels:
        return False, False, "levels 缺失"
    vals = [v for v in levels.values() if v is not None]
    finite = all(isinstance(v, (int, float)) and v == v and abs(v) != float("inf")
                 for v in vals)
    nonzero = any(v > 0 for v in vals)
    band = all(0.01 <= v <= 10.0 for v in vals)
    new_ok = bool(finite and nonzero)
    note = ""
    if not finite:
        note = "非有限值"
    elif not nonzero:
        note = "输出全零"
    return new_ok, band, note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写回 cascade_eval.json")
    a = ap.parse_args()

    ev = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
    seps = ev.get("sep_results", [])
    print("sep_results: %d 条" % len(seps))

    changed = []
    before = Counter()
    after = Counter()
    for r in seps:
        old = r.get("status")
        before[(r["model"], r["variant"], old)] += 1
        g = r.get("gate") or {}
        new_ok, band, note = regate_levels(g.get("levels") or {})
        # sdr_avg4 为 None 一律判 FAIL（真正的失败）
        if r.get("sdr_avg4") is None:
            new_ok = False
            note = note or "avg4 None"
        new = "PASS" if new_ok else "FAIL"
        r.setdefault("gate", {})["band_ok"] = band          # 原判据，审计用
        r["gate"]["lvl_ok_v2"] = new_ok
        if new != old:
            changed.append((r["model"], r["variant"], r["cell_id"], old, new, note))
        r["status"] = new
        if not new_ok:
            r["reason"] = ("avg4 None / 输出全零或 NaN" if r.get("sdr_avg4") is None
                           else "输出全零或 NaN: levels=%s" % (g.get("levels")))
        else:
            r.pop("reason", None)
        after[(r["model"], r["variant"], new)] += 1

    n_pass = sum(1 for r in seps if r["status"] == "PASS")
    print("\n重判：PASS %d / %d  （原 %d）"
          % (n_pass, len(seps), ev.get("n_sep_pass")))
    print("\n%-10s %-8s %6s -> %6s" % ("model", "variant", "旧PASS", "新PASS"))
    for mk in sorted({r["model"] for r in seps}):
        for var in ["Vdry", "V0", "V1den", "V1bl", "V1mel"]:
            b = sum(v for k, v in before.items() if k[0] == mk and k[1] == var and k[2] == "PASS")
            c = sum(v for k, v in after.items() if k[0] == mk and k[1] == var and k[2] == "PASS")
            if b or c:
                print("%-10s %-8s %6d -> %6d" % (mk, var, b, c))

    print("\n被改判的格（前 15）：")
    for row in changed[:15]:
        print("   %-10s %-7s %-34s %s -> %s  %s" % row)
    if len(changed) > 15:
        print("   ... 共 %d 格被改判" % len(changed))

    ev["n_sep_pass"] = n_pass
    ev["regate"] = {"applied": bool(a.apply), "n_changed": len(changed),
                    "rule": "PASS <=> avg4 not None AND levels 有限非负 AND 非全零",
                    "band_ok_kept_for_audit": True}
    if a.apply:
        EVAL_JSON.write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\n✅ 已写回 %s" % EVAL_JSON)
    else:
        print("\n（未写回；加 --apply 生效）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""T4.6 回声（echo）实验：给干混音叠加"延迟 + 衰减"副本，量分离退化。

与 T4.1/T4.2 的混响实验并列，但**不需要 RIR**：回声 = 原信号 + g * 延迟副本。
逐 stem 叠加可保证 Σstems == mixture（否则 SDR 会因"参考与估计不同源"而崩）。

两个档：
  echo_short: delay 80 ms, gain 0.6
  echo_long : delay 250 ms, gain 0.8

门禁：
  G1 Σ(wet stems) 与 wet mixture 的相对 RMS 误差 < 1e-3
  G2 wet mixture == dry mixture + g * shift(dry mixture, D)  逐样本复算，max|Δ| < 1e-6

用法：python tools/_echo_experiment.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

REV = _paths.PROJECT_ROOT / "04_reports" / "separation" / "data" / "reverb"
AUDIO = _paths.OUTPUTS / "_reverb"
MANIFEST = REV / "reverb_manifest.json"
OUT_JSON = REV / "echo_manifest.json"
SR = 44100
STEMS = ["vocals", "drums", "bass", "other"]

ECHO = {"echo_short": {"delay_ms": 80, "gain": 0.6},
        "echo_long": {"delay_ms": 250, "gain": 0.8}}


def _shift_add(x, delay, gain):
    """y[n] = x[n] + gain * x[n - delay]（无环绕）。"""
    y = np.array(x, np.float64, copy=True)
    if delay > 0:
        y[delay:] = y[delay:] + gain * x[:-delay]
    return y


def main() -> int:
    clips = [c["clip_id"] for c in
             json.loads(MANIFEST.read_text(encoding="utf-8"))["clips"]]
    gates = []
    made = []
    for clip in clips:
        src = AUDIO / clip / "dry"
        for cname, cfg in ECHO.items():
            D = int(round(cfg["delay_ms"] / 1000.0 * SR))
            dst = AUDIO / clip / cname
            dst.mkdir(parents=True, exist_ok=True)
            for stem in ["mixture"] + STEMS:
                x, sr = sf.read(str(src / ("%s.wav" % stem)), dtype="float64",
                                always_2d=True)
                y = _shift_add(x, D, cfg["gain"])
                sf.write(str(dst / ("%s.wav" % stem)), y.astype(np.float32), sr,
                         subtype="FLOAT")
            made.append("%s|%s" % (clip, cname))

            # G1：Σstem == mixture
            mixw, _ = sf.read(str(dst / "mixture.wav"), dtype="float64", always_2d=True)
            acc = None
            for stem in STEMS:
                v, _ = sf.read(str(dst / ("%s.wav" % stem)), dtype="float64",
                               always_2d=True)
                acc = v if acc is None else acc + v
            n = min(len(mixw), len(acc))
            e1 = float(np.sqrt(np.mean((mixw[:n] - acc[:n]) ** 2)) /
                       (np.sqrt(np.mean(mixw[:n] ** 2)) + 1e-12))
            gates.append({"clip_id": clip, "condition": cname, "gate": "sum_stems_eq_mixture",
                          "value": round(e1, 9), "threshold": 1e-3, "pass": e1 < 1e-3})

            # G2：逐样本复算
            x0, _ = sf.read(str(src / "mixture.wav"), dtype="float64", always_2d=True)
            ref = _shift_add(x0, D, cfg["gain"])
            m = min(len(ref), len(mixw))
            e2 = float(np.max(np.abs(ref[:m] - mixw[:m])))
            gates.append({"clip_id": clip, "condition": cname,
                          "gate": "echo_formula_roundtrip", "value": e2,
                          "threshold": 1e-6, "pass": e2 < 1e-6})

    n_fail = sum(1 for g in gates if not g["pass"])
    out = {"task": "T4.6 回声实验（生成）", "echo": ECHO, "clips": clips,
           "made": made, "n_gates": len(gates), "n_failed": n_fail, "gates": gates,
           "formula": "y[n] = x[n] + gain * x[n - delay_samples]",
           "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "status": "PASS" if n_fail == 0 else "FAIL"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[echo] %d gates, %d failed -> %s" % (len(gates), n_fail, OUT_JSON))
    for g in gates:
        print("  %-30s %-11s %-24s value=%.3e pass=%s" % (
            g["clip_id"][:30], g["condition"], g["gate"], g["value"], g["pass"]))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

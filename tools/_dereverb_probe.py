"""T4.x 去混响模型诊断探针（只读、不改产物）。

回答三个问题：
  Q1  echo 模型（num_stems=2）的两个 stem 各自 rms 是多少？信号到底在哪一支？
      dry+other 的和 ≈ 输入吗？（判断是"分工中的 dry=去混响"还是"别的东西"）
  Q2  anvuew 去混响模型喂【干信号】时近似恒等吗？（若把 dry 也大幅改动 → 模型在做别的事）
  Q3  同一段信号，【干】vs【湿】输入下，"dry" stem 的 rms 与 si_sdr(vs dry) 各是多少？

用法：
  python tools/_dereverb_probe.py <model_key> <clip_id> <cond>
  例：python tools/_dereverb_probe.py mel_roformer_dereverb_echo "Bobby Nobody - Stitch Up@172s" wet_small
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

TOOLS = Path(_paths.TOOLS)
sys.path.insert(0, str(TOOLS))
from _denoise_registry import REGISTRY  # noqa: E402

AUDIO_ROOT = _paths.OUTPUTS / "_reverb"


def _rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, np.float64) ** 2)))


def _si_sdr(est, ref):
    est = np.asarray(est, np.float64).ravel()
    ref = np.asarray(ref, np.float64).ravel()
    n = min(len(est), len(ref))
    est, ref = est[:n], ref[:n]
    a = np.dot(est, ref) / (np.dot(ref, ref) + 1e-12)
    tgt = a * ref
    e = est - tgt
    return float(10 * np.log10((np.sum(tgt ** 2) + 1e-12) / (np.sum(e ** 2) + 1e-12)))


def main() -> int:
    mk = sys.argv[1]
    clip_id = sys.argv[2]
    cond = sys.argv[3]
    run, load_s, info = REGISTRY[mk]["loader"]()
    print("[load] %s  %.1fs  n_stems=%s targets=%s sr=%s" % (
        info["label"], load_s, info["n_stems"], info["targets"], info["sample_rate"]))

    d = AUDIO_ROOT / clip_id / cond
    dry_path = AUDIO_ROOT / clip_id / "dry" / "vocals.wav"
    wet, _ = sf.read(str(d / "vocals.wav"), dtype="float32", always_2d=True)
    dry, _ = sf.read(str(dry_path), dtype="float32", always_2d=True)
    n = min(len(wet), len(dry))
    wet, dry = wet[:n], dry[:n]
    print("[in ] wet vocals rms=%.6f  dry vocals rms=%.6f  si(dry|wet)=%+.3f dB" % (
        _rms(wet), _rms(dry), _si_sdr(wet.mean(1), dry.mean(1))))

    for tag, sig in (("WET", wet), ("DRY", dry)):
        res = run(sig)
        print("  --- input=%s ---" % tag)
        rms_sum = 0.0
        k0 = None
        for k, v in res.items():
            r = _rms(v)
            rms_sum += r
            k0 = v if k0 is None else k0
            print("    stem %-10s rms=%.6f  si(vs dry)=%+.3f dB  si(vs wet)=%+.3f dB" % (
                k, r, _si_sdr(np.asarray(v).mean(1), dry.mean(1)),
                _si_sdr(np.asarray(v).mean(1), wet.mean(1))))
        # 若两支同形，验证和
        if len(res) >= 2:
            vals = [np.asarray(v) for v in res.values()]
            s = sum(vals)
            print("    sum(stems) rms=%.6f  si(sum vs input)=%+.3f dB" % (
                _rms(s), _si_sdr(s.mean(1), np.asarray(sig).mean(1))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

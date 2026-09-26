"""官方推理路径 vs 我们 loader 的对照探针（只读）。

动机：我们的 `_denoise_registry._make_mel_loader` 直接 `model(mix)` 对**整段**
音频做一次前向；而 ZFTurbo 官方 `inference.py` 走 `demix()` —— **分块
(chunk_size=352800≈8 s) + 重叠相加 + fade 窗**。mel_band_roformer 用时间轴
rotary 位置编码，训练长度 dim_t≈801 帧（≈8 s），整段 20 s 前向会外推出训练分布。

本脚本用官方 `bigshifts_wrapper`(bigshifts=1) 跑同一段湿人声，输出两支 stem 的
rms / si_sdr(vs dry) / si_sdr(vs wet)，与整段前向的结果对照，判断"近似直通/塌陷"
到底是模型域不匹配，还是我们的 loader 少了分块。

用法：
  python tools/_dereverb_official_probe.py <REGISTRY_KEY> <clip_id> <cond>
"""
from __future__ import annotations

import sys
from pathlib import Path

import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402

ROOT = _paths.PROJECT_ROOT
W = ROOT / "01_models" / "_weights"
ZF = ROOT / "01_models" / "_third_party" / "Music-Source-Separation-Training"
AUDIO_ROOT = _paths.OUTPUTS / "_reverb"
SR = 44100

CK = {
    "mel_roformer_dereverb": (
        "mel_roformer_dereverb", "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
        "dereverb_mel_band_roformer_anvuew.yaml"),
    "mel_roformer_dereverb_echo": (
        "mel_roformer_dereverb_echo", "dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt",
        "config_dereverb-echo_mel_band_roformer.yaml"),
    "mel_roformer_denoise": (
        "mel_roformer_denoise", "denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
        "model_mel_band_roformer_denoise.yaml"),
}


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
    key, clip_id, cond = sys.argv[1], sys.argv[2], sys.argv[3]
    folder, ckpt, yaml = CK[key]
    if str(ZF) not in sys.path:
        sys.path.insert(0, str(ZF))
    from utils.settings import get_model_from_config
    from utils.model_utils import bigshifts_wrapper

    model, config = get_model_from_config("mel_band_roformer", str(W / folder / yaml))
    sd = torch.load(str(W / folder / ckpt), map_location="cpu", weights_only=False)
    if isinstance(sd, dict) and "state_dict" in sd:
        sd = sd["state_dict"]
    model.load_state_dict(sd, strict=True)
    model.eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(dev)
    try:
        cs = int(config.inference["chunk_size"])
    except Exception:                                          # noqa: BLE001
        cs = int(config.audio["chunk_size"])
    print("[cfg] chunk_size=%d (%.2fs)  num_overlap=%s" % (
        cs, cs / SR, config.inference.get("num_overlap")))

    d = AUDIO_ROOT / clip_id / cond
    wet, _ = sf.read(str(d / "vocals.wav"), dtype="float32", always_2d=True)
    dry, _ = sf.read(str(AUDIO_ROOT / clip_id / "dry" / "vocals.wav"),
                     dtype="float32", always_2d=True)
    n = min(len(wet), len(dry))
    wet, dry = wet[:n], dry[:n]
    print("[in ] wet rms=%.6f  dry rms=%.6f  si(dry|wet)=%+.3f dB  (%.1fs)" % (
        _rms(wet), _rms(dry), _si_sdr(wet.mean(1), dry.mean(1)), n / SR))

    mix = wet.T.astype(np.float32)                             # (C, T)
    res = bigshifts_wrapper(config, model, mix, dev,
                            model_type="mel_band_roformer", pbar=False, bigshifts=1)
    if not isinstance(res, dict):
        res = {str(i): res[i] for i in range(len(res))}
    print("  --- OFFICIAL PATH (demix, chunked+overlap) ---")
    tot = None
    for k, v in res.items():
        v = np.asarray(v)
        if v.ndim == 2:
            v = v.T
        tot = v if tot is None else tot + v
        print("    stem %-10s rms=%.6f  si(vs dry)=%+.3f dB  si(vs wet)=%+.3f dB" % (
            k, _rms(v), _si_sdr(v.mean(1), dry.mean(1)), _si_sdr(v.mean(1), wet.mean(1))))
    if tot is not None and len(res) >= 2:
        print("    sum(stems) rms=%.6f  si(sum vs wet)=%+.3f dB" % (
            _rms(tot), _si_sdr(tot.mean(1), wet.mean(1))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

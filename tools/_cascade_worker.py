# -*- coding: utf-8 -*-
"""级联流水线的**单模型单发 worker** —— 一次只加载一个模型，跑完一个 job 就退出。

为什么是「单发 + 子进程」而不是「常驻 + 线程」（稳定性优先，速度其次）
------------------------------------------------------------------
1. **8 GiB 显存铁律**：同进程多模型必 OOM。本 worker 一个进程只驻留一个模型，
   跑完即退，CUDA 上下文随进程消失，显存立刻归还 —— 下一段（降噪）不会被拖住。
2. **模型崩溃无法拖垮 Web 服务**：worker 是独立子进程，分离/降噪模型内部
   一旦抛异常或卡死，服务器 `kill()` 掉它即可，服务本身永远活着。
3. **stdout 只放协议行**：loader（`load_mmdenselstm`、`_bsrnn_loader`、mel 等）
   会往 stdout 打调试信息。所以**在 import 任何重模块之前**把 `sys.stdout`
   换成 `sys.stderr`，协议行写到保存下来的原始 stdout 上 —— 协议永不被污染。

契约（与 `benchmark_model_universal` / `_denoise_registry` 完全一致）
------------------------------------------------------------------
`run_fn(mix)` 收 **(N, 2) float32 @ 44.1 kHz**，返回 `{target: (N,2)|(N,)}`。
- 分离模型（board=sep）→ 输出 `vocals/drums/bass/other` 等 stem。
- 降噪/去混响模型（board=den）→ 输出 `enhanced`（denoiser / mel-denoise）
  或 `dry`（dereverb / dereverb-echo）。
长输入走 `_chunked_infer.chunked_separate`（chunk 10 s / overlap 1 s），
把显存峰值钉在 10 s 档，而不是随输入长度线性涨。

用法
----
    python tools/_cascade_worker.py --board sep  --model demucs \
        --input noisy.wav --out-dir OUT --keep vocals
    python tools/_cascade_worker.py --board den  --model denoiser_master64 \
        --input vocals.wav --out-dir OUT --keep enhanced

输出（单行 JSON，写到原始 stdout）：{"event":"result", ...} 或 {"event":"error", ...}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

# ---- 1. 先把协议通道摘出来，再把 stdout 让给 loader 的自由打印 ----------------
_PROTO = sys.stdout
try:
    sys.stdout = sys.stderr
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

import benchmark_model_universal as BM  # noqa: E402
import _denoise_registry as DEN  # noqa: E402
from _chunked_infer import chunked_separate  # noqa: E402

SR = 44100
_UNSAFE = str.maketrans({"/": "_", "\\": "_", ":": "_", "*": "_",
                         "?": "_", '"': "_", "<": "_", ">": "_", "|": "_"})


def emit(obj) -> None:
    _PROTO.write(json.dumps(obj, ensure_ascii=False) + "\n")
    _PROTO.flush()


def safe_name(t: str) -> str:
    return t.translate(_UNSAFE)


def load_mix(path, max_seconds=None) -> np.ndarray:
    """读任意音频 -> (N, 2) float32 @ 44.1 kHz（立体声，缺声道复制）。"""
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if max_seconds:
        x = x[: int(float(max_seconds) * sr)]
    if sr != SR:
        import torch
        import torchaudio.functional as AF
        t = torch.as_tensor(np.ascontiguousarray(x.T))
        x = AF.resample(t, sr, SR).numpy().T
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    elif x.shape[1] > 2:
        x = x[:, :2]
    return np.ascontiguousarray(x, dtype=np.float32)


def _info_summary(info) -> dict:
    """各 loader 的 info 字段不统一，这里做归一（尽力而为）。"""
    info = info or {}
    params = info.get("params")
    if params is None and info.get("params_m") is not None:
        params = info["params_m"] * 1e6
    targets = info.get("targets") or info.get("sources") or []
    return {
        "params": params,
        "targets": sorted(str(t) for t in targets),
        "native_sr": info.get("native_sr") or info.get("sample_rate"),
        "kind": info.get("kind"),
        "repo": info.get("repo") or info.get("model"),
    }


def do_job(run_fn, inp, out_dir, keep, max_seconds, chunk_s, overlap_s) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mix = load_mix(inp, max_seconds)

    t0 = time.time()
    if len(mix) > chunk_s * SR:
        stems = chunked_separate(run_fn, mix, sr=SR, chunk_s=chunk_s, overlap_s=overlap_s)
        chunked, n_chunks = True, int(np.ceil(len(mix) / (chunk_s * SR)))
    else:
        stems = run_fn(mix)
        chunked, n_chunks = False, 1
    infer_s = time.time() - t0

    outs = []
    wanted = [k for k in keep if k in stems] or sorted(stems)
    for name in wanted:
        y = stems[name]
        if y.ndim == 1:
            y = np.stack([y, y], axis=-1)
        elif y.shape[1] == 1:
            y = np.repeat(y, 2, axis=1)
        n = min(len(y), len(mix))
        y = np.clip(y[:n], -1.0, 1.0).astype(np.float32)
        p = out_dir / (safe_name(name) + ".wav")
        sf.write(str(p), y, SR, subtype="PCM_16")
        outs.append({
            "target": name,
            "file": p.name,
            "frames": int(n),
            "dur_s": round(n / SR, 3),
            "mb": round(os.path.getsize(str(p)) / 1e6, 3),
            "rms": round(float(np.sqrt(np.mean(y ** 2))), 6),
            "peak": round(float(np.max(np.abs(y))) if n else 0.0, 5),
        })

    return {
        "in_s": round(len(mix) / SR, 3),
        "out_sr": SR,
        "infer_s": round(infer_s, 3),
        "chunked": chunked,
        "n_chunks": n_chunks,
        "chunk_s": chunk_s if chunked else None,
        "stems": outs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True, choices=["sep", "den"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--keep", nargs="*", default=[])
    ap.add_argument("--max-seconds", type=float, default=600.0)
    ap.add_argument("--chunk-s", type=float, default=10.0)
    ap.add_argument("--overlap-s", type=float, default=1.0)
    a = ap.parse_args()

    registry = BM.REGISTRY if a.board == "sep" else DEN.REGISTRY
    if a.model not in registry:
        emit({"event": "fatal", "error": "unknown model: %s (board=%s)" % (a.model, a.board)})
        return 2

    try:
        t0 = time.time()
        run_fn, _load_declared, info = registry[a.model]["loader"]()
        load_s = time.time() - t0
    except Exception as e:  # noqa: BLE001
        emit({"event": "fatal",
              "error": "%s: %s" % (type(e).__name__, e),
              "traceback": traceback.format_exc()[-2000:]})
        return 3

    summ = _info_summary(info)
    # 契约采样率必须显式读（P19 铁律）：denoiser 契约 44100，但原生 16000。
    summ["contract_sr"] = int(getattr(run_fn, "contract_sr", 44100))

    try:
        rec = do_job(run_fn, a.input, a.out_dir, a.keep,
                     a.max_seconds, a.chunk_s, a.overlap_s)
        rec.update({
            "event": "result",
            "model": a.model,
            "board": a.board,
            "label": registry[a.model].get("label", a.model),
            "load_s": round(load_s, 3),
            "info": summ,
        })
        emit(rec)
    except Exception as e:  # noqa: BLE001
        emit({"event": "error", "model": a.model,
              "error": "%s: %s" % (type(e).__name__, e),
              "traceback": traceback.format_exc()[-2000:]})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

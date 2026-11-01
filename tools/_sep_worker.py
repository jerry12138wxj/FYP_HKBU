# -*- coding: utf-8 -*-
"""分离模型的**单模型工作子进程** —— 一次只把一个模型放进显存。

为什么必须是子进程（不是线程）
----------------------------
1. 项目铁律：8 GiB 上**同进程多模型必 OOM**（13 个分离模型参数合计 ~1.18 G，
   光权重就 4.7 GB）。一个子进程只驻留一个模型，内核回收最干净。
2. **8 秒预算必须真的能中止**。线程无法被安全打断 —— torch 前向跑到一半
   没有取消点。进程可以 `kill()`，CUDA 上下文随进程一起消失，
   显存立刻归还，下一个模型不会被拖住。

🔴 stdout 只能放协议行
----------------------
实测：`load_mmdenselstm`、`load_bsroformer`、`_bsrnn_loader.load_bsrnn(progress=print)`
等 loader 会往 **stdout** 打调试信息（`[BSRNN] stub 替换: …`、`params=…`）。
父进程按行读 stdout 解析 JSON，被这些行污染就会直接抛
`JSONDecodeError: Expecting value: line 1 column 6`。

所以：**在 import 任何重模块之前**把 `sys.stdout` 换成 `sys.stderr`，
协议行写到保存下来的原始 stdout 上。这样 loader 随便打印，协议永不被污染。

协议（父进程 `_denoise_live_server.py` 通过 stdin/stdout 行协议驱动）
------------------------------------------------------------------
    父 -> 子   {"job_id": "...", "input": "<wav path>", "out_dir": "<dir>",
                "max_seconds": 30, "chunk_s": 10, "overlap_s": 1}
    子 -> 父   {"event":"ready",  "load_s":..., "params":..., "targets":[...]}
               {"event":"result", "job_id":..., "infer_s":..., "stems":[...]}
               {"event":"error",  "job_id":..., "error":..., "traceback":...}
               {"event":"fatal",  "error":...}          # 加载失败，进程退出

契约（与 `benchmark_model_universal` 完全一致）
---------------------------------------------
`run_fn(mix)` 收 **(N, 2) float32 @ 44.1 kHz**，返回 `{target: (N,2)|(N,)}`。
长输入走 `_chunked_infer.chunked_separate`（chunk 10 s / overlap 1 s）：
分块把显存峰值钉在 10 s 档（profile 实测最坏 3394 MB），而不是随输入长度线性涨。

用法
----
    python tools/_sep_worker.py --model demucs
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
except Exception:                                              # noqa: BLE001
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

# `benchmark_model_universal` 在 import 时就会摘掉 expandable_segments
# （那是 DPRNN 训练用的，会让推理期的 torch.istft 崩）——先于 torch 生效。
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

import benchmark_model_universal as BM  # noqa: E402
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
    """读任意音频 -> (N, 2) float32 @ 44.1 kHz。"""
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
    """各 loader 的 info 字段并不统一（见 benchmark_model_universal），这里做归一。

    demucs 给 `params_m` + `sources`；umx/mdx 连 targets 都没有；dprnn 给
    `native_sr`。所以 targets 只是**尽力而为**，权威 stem 名单以 RESULT 为准。
    """
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


def do_job(run_fn, job) -> dict:
    inp = job["input"]
    out_dir = Path(job["out_dir"])
    max_seconds = float(job.get("max_seconds") or 60.0)
    chunk_s = float(job.get("chunk_s") or 10.0)
    overlap_s = float(job.get("overlap_s") or 1.0)

    mix = load_mix(inp, max_seconds)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    if len(mix) > chunk_s * SR:
        stems = chunked_separate(run_fn, mix, sr=SR, chunk_s=chunk_s, overlap_s=overlap_s)
        chunked, n_chunks = True, int(np.ceil(len(mix) / (chunk_s * SR)))
    else:
        stems = run_fn(mix)
        chunked, n_chunks = False, 1
    infer_s = time.time() - t0

    outs = []
    for name in sorted(stems):
        y = BM._to_stereo(stems[name])                     # noqa: SLF001
        n = min(len(y), len(mix))
        y = np.clip(y[:n], -1.0, 1.0)
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
    ap.add_argument("--model", required=True)
    a = ap.parse_args()

    key = a.model
    if key not in BM.REGISTRY:
        emit({"event": "fatal", "error": "unknown model: %s" % key})
        return 2

    try:
        t0 = time.time()
        run_fn, _load_declared, info = BM.REGISTRY[key]["loader"]()
        load_s = time.time() - t0
    except Exception as e:                                     # noqa: BLE001
        emit({"event": "fatal",
              "error": "%s: %s" % (type(e).__name__, e),
              "traceback": traceback.format_exc()[-2000:]})
        return 3

    summ = _info_summary(info)
    emit({
        "event": "ready",
        "model": key,
        "load_s": round(load_s, 3),
        "label": BM.REGISTRY[key].get("label", key),
        **summ,
    })

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except Exception as e:                                 # noqa: BLE001
            emit({"event": "error", "job_id": None, "error": "bad job json: %s" % e})
            continue
        if job.get("cmd") == "quit":
            break
        jid = job.get("job_id")
        try:
            rec = do_job(run_fn, job)
            rec.update({"event": "result", "job_id": jid, "model": key})
            emit(rec)
        except Exception as e:                                 # noqa: BLE001
            emit({"event": "error", "job_id": jid,
                  "error": "%s: %s" % (type(e).__name__, e),
                  "traceback": traceback.format_exc()[-2000:]})
    return 0


if __name__ == "__main__":
    sys.exit(main())

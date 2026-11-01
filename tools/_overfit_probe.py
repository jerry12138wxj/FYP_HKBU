# -*- coding: utf-8 -*-
"""10-item / 200-step overfit probe -- the wiring check before any real training.

Material B rule: 10 clips + 200 steps exposes ~90% of wiring errors in <5 min.

Usage:
    python tools/_overfit_probe.py --model demucs --items 10 --steps 200
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()
import os  # noqa: E402

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

sys.path.insert(0, str(_paths.THIRD_PARTY / "demucs"))

OUT = Path(r"D:\FYP_HKBU_runs\rerun_20261030_2358\overfit")
CKPT = _paths.WEIGHTS / "Demucs" / "955717e8-8726e21a.th"


def load_clips(n, seg, sr=44100):
    root = _paths.MUSDB18_ROOT / "train"
    songs = sorted([p for p in root.iterdir() if p.is_dir()])[:n]
    clips, refs = [], []
    for s in songs:
        x, _ = sf.read(str(s / "mixture.wav"), frames=seg * sr, dtype="float32", always_2d=True)
        if x.shape[0] < seg * sr:
            continue
        clips.append(x.T)
        refs.append(np.stack([
            sf.read(str(s / f"{t}.wav"), frames=seg * sr, dtype="float32", always_2d=True)[0].T
            for t in ("drums", "bass", "other", "vocals")
        ]))
    return np.stack(clips), np.stack(refs)


def multires_stft_loss(est, ref, sizes=(512, 1024, 2048)):
    loss = 0.0
    for n in sizes:
        win = torch.hann_window(n, device=est.device)
        for x in (est, ref):
            pass
        E = torch.stft(est.reshape(-1, est.shape[-1]), n, n // 4, window=win,
                       return_complex=True, center=True)
        R = torch.stft(ref.reshape(-1, ref.shape[-1]), n, n // 4, window=win,
                       return_complex=True, center=True)
        loss = loss + F.l1_loss(E.abs(), R.abs())
    return loss / len(sizes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="demucs")
    ap.add_argument("--items", type=int, default=10)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--seg", type=float, default=4.0)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--lr", type=float, default=3e-4)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    log = open(OUT / "probe.log", "w", encoding="utf-8")

    def say(msg):
        print(msg)
        log.write(msg + "\n")
        log.flush()

    from demucs.states import load_model  # noqa: E402

    # torch 2.14 默认 weights_only=True，而 demucs.states.load_model 内部用
    # torch.load(path, 'cpu') 不带该参数 -> 会拒绝反序列化 HTDemucs 类。
    # 权重是本地官方发布文件（sha256 8726e21a...），这里显式放行。
    _orig_load = torch.load

    def _load(*a, **k):
        k.setdefault("weights_only", False)
        return _orig_load(*a, **k)

    torch.load = _load

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    say("device=%s torch=%s" % (dev, torch.__version__))
    model = load_model(str(CKPT)).to(dev)
    n_par = sum(p.numel() for p in model.parameters())
    say("params=%d (%.3f M) sources=%s" % (n_par, n_par / 1e6, model.sources))

    X, Y = load_clips(args.items, int(args.seg))
    say("clips=%s shape=%s refs=%s" % (X.shape, X.shape, Y.shape))
    X = torch.from_numpy(X).to(dev)
    Y = torch.from_numpy(Y).to(dev)
    order = [("drums", "bass", "other", "vocals").index(s) for s in model.sources]
    Y = Y[:, order]

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.steps,
                                                pct_start=0.1)
    model.train()
    hist = []
    t0 = time.time()
    step = 0
    while step < args.steps:
        idx = torch.randint(0, X.shape[0], (args.batch,), device=dev)
        xb, yb = X[idx], Y[idx]
        est = model(xb)
        if isinstance(est, (list, tuple)):
            est = est[0]
        l_wave = F.l1_loss(est, yb)
        l_spec = multires_stft_loss(est, yb)
        loss = l_wave + 0.5 * l_spec
        opt.zero_grad(set_to_none=True)
        loss.backward()
        gnorm = torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step()
        sched.step()
        step += 1
        if step == 1 or step % 10 == 0:
            rec = {"step": step, "loss": round(float(loss), 5),
                   "l_wave": round(float(l_wave), 5), "l_spec": round(float(l_spec), 5),
                   "grad_norm": round(float(gnorm), 3),
                   "vram_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1) if dev == "cuda" else 0}
            hist.append(rec)
            say(json.dumps(rec))
    elapsed = time.time() - t0

    model.eval()
    with torch.no_grad():
        est = model(X)
        if isinstance(est, (list, tuple)):
            est = est[0]
        final = float(F.l1_loss(est, Y))
    first = hist[0]["loss"]
    res = {
        "model": args.model, "device": dev, "params": n_par, "params_M": round(n_par / 1e6, 3),
        "items": int(X.shape[0]), "seg_s": args.seg, "steps": args.steps, "batch": args.batch,
        "lr": args.lr, "elapsed_s": round(elapsed, 1), "s_per_step": round(elapsed / args.steps, 3),
        "loss_first": first, "loss_last_logged": hist[-1]["loss"], "loss_eval_final": round(final, 5),
        "drop_ratio": round(1 - final / first, 4) if first else None,
        "max_vram_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1) if dev == "cuda" else 0,
        "history": hist,
        "pass_criterion": "final loss < 10% of first-10-step loss (drop_ratio > 0.9)",
        "passed": bool(final < 0.10 * first),
        "ckpt": str(CKPT), "ckpt_sha256_head": "8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4",
    }
    (OUT / "probe_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    say(json.dumps({k: v for k, v in res.items() if k != "history"}, ensure_ascii=False))
    log.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        Path(r"D:\FYP_HKBU_runs\rerun_20261030_2358\overfit").mkdir(parents=True, exist_ok=True)
        Path(r"D:\FYP_HKBU_runs\rerun_20261030_2358\overfit\probe_error.txt").write_text(
            traceback.format_exc(), encoding="utf-8")
        raise

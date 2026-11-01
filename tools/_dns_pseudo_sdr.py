# -*- coding: utf-8 -*-
"""在 DNS dev_testset 上用 pseudo-clean 参考计算 Method B'，以及模型间一致性。

口径
----
  ref  : pseudo-clean P_m = 模型 m 在 noisy 上的输出 (16 kHz mono)
  est  : noisy 原始信号 (48k -> 16k, 与 P_m 同长截断)
  指标 : museval BSSEval v4, win = hop = 16000 (1 s), 逐帧 nanmedian

  三种量:
    b_cons  ref = 多模型逐样本中位数 (共识), est = noisy
            -> DNS 上的"不分离下界" B'
    b_self  ref = P_m 自身, est = noisy
            -> 该模型改动了多少; 数值越大越接近恒等, 越不适合当参考
    agree   ref = 共识, est = P_m
            -> 各模型与共识的一致度 (参考无关的偏离度)

🔴 这不是 Method B。Method B 要求 ref 是真 clean; DNS dev_testset 没有 clean,
   这里用模型输出当参考, 全程标注 B' (pseudo-reference), 不得与 Valentini /
   MUSDB 的真 B 并列进同一张表。

🔴 增益
   落盘时按峰值归一化到 0.999 并把 gain 记进 _index.csv; 读回必须乘回 gain。

🔴 非有限帧
   静音帧 0/0 -> NaN 被 nanmedian 丢弃, 逐文件记录 n_nonfinite。

用法
----
  python tools/_dns_pseudo_sdr.py --limit 40 --jobs 4          # 冒烟
  python tools/_dns_pseudo_sdr.py --limit 300 --jobs 12        # 推荐
  python tools/_dns_pseudo_sdr.py                              # 全量 921
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

import museval  # noqa: E402

ROOT = _paths.PROJECT_ROOT
DNS = (ROOT / "02_databases" / "DNS-Challenge" / "dev_testset"
       / "datasets_fullband" / "dev_testset" / "noisy_testclips")
PSEUDO = ROOT / "baseline" / "dns_pseudo"
SR = 16000
WIN = HOP = 16000          # 1 s frames

# 子进程共享状态 (fork/spawn 后由 initializer 填充)
_CTX = {}


# ------------------------------------------------------------------ 工具
def load_index():
    p = PSEUDO / "_index.csv"
    if not p.is_file():
        raise SystemExit("[FATAL] run _dns_pseudo_clean.py first (no _index.csv)")
    d = {}
    for r in csv.DictReader(open(p, encoding="utf-8")):
        d.setdefault(r["model"], {})[r["clip"]] = r
    return d


def read_pseudo(kind, clip):
    r = _CTX["idx"][kind][clip]
    x, sr = sf.read(str(PSEUDO / kind / (clip + ".flac")), dtype="float32",
                    always_2d=True)
    if sr != SR:
        raise RuntimeError("unexpected sr %d" % sr)
    return (x[:, 0] * float(r["gain"])).astype(np.float32)


def read_noisy(clip):
    import torch
    import torchaudio.functional as AF
    x, sr = sf.read(str(DNS / (clip + ".wav")), dtype="float32", always_2d=True)
    m = x.mean(axis=1).astype(np.float32)
    if sr != 48000:
        m = AF.resample(torch.from_numpy(m)[None], sr, 48000)[0].numpy()
    return AF.resample(torch.from_numpy(m)[None], 48000, SR)[0].numpy().astype(
        np.float32)


def bss(ref, est):
    n = min(len(ref), len(est))
    r = np.ascontiguousarray(ref[:n]).reshape(1, -1, 1)
    e = np.ascontiguousarray(est[:n]).reshape(1, -1, 1)
    sdr, isr, sir, sar = museval.evaluate(r, e, win=WIN, hop=HOP, mode="v4")
    return np.asarray(sdr)[0], n


def fin(a):
    x = np.asarray(a, dtype=np.float64)
    nf = int(np.sum(~np.isfinite(x)))
    if not np.isfinite(x).any():
        return None, x.size, nf
    return float(np.nanmedian(x)), x.size, nf


def strat_sample(clips, n):
    """按片段时长排序后等距采样, 保证时长分布被覆盖。"""
    if not n or n >= len(clips):
        return list(clips)
    rows = sorted(((sf.info(str(DNS / (c + ".wav"))).duration, c) for c in clips))
    idx = np.linspace(0, len(rows) - 1, n).round().astype(int)
    return [rows[i][1] for i in idx]


# ------------------------------------------------------------------ 子进程
def _init(idx, models):
    _CTX["idx"] = idx
    _CTX["models"] = models


def _one(clip):
    """单个片段: 算 b_cons + 每模型 b_self / agree。返回行列表。"""
    models = _CTX["models"]
    idx = _CTX["idx"]
    rows = []
    try:
        noisy = read_noisy(clip)
        arrs = {m: read_pseudo(m, clip) for m in models}
        n = min([len(noisy)] + [len(v) for v in arrs.values()])
        cons = np.median(np.stack([v[:n] for v in arrs.values()], axis=0),
                         axis=0).astype(np.float32)

        def add(kind, key, ref, est, lvl):
            sdr, nn = bss(ref, est)
            v, nfrm, nnon = fin(sdr)
            rows.append({
                "kind": kind, "model": key, "clip": clip,
                "sdr_db": "" if v is None else round(v, 4),
                "n_frames": nfrm, "n_nonfinite": nnon,
                "dur_s": round(nn / float(SR), 3), "level_ratio": lvl,
                "est": "noisy(48k->16k)" if kind in ("b_self", "b_cons")
                else "pseudo:" + key,
                "ref": "pseudo:_consensus" if "cons" in kind else "pseudo:" + key,
                "win_samples": WIN, "hop_samples": HOP, "sample_rate": SR,
                "tool": "museval.bss_eval/v4",
                "tool_version": getattr(museval, "__version__", "?"),
                "n_models_in_consensus": len(models),
            })

        add("b_cons", "_consensus", cons, noisy, "")
        for m in models:
            lvl = idx[m][clip].get("level_ratio", "")
            add("b_self", m, arrs[m], noisy, lvl)
            add("agree", m, cons, arrs[m], lvl)
    except Exception as e:                                 # noqa: BLE001
        rows.append({"kind": "error", "model": "-", "clip": clip,
                     "sdr_db": "", "n_frames": "", "n_nonfinite": "",
                     "dur_s": "", "level_ratio": "", "est": "", "ref": "",
                     "win_samples": "", "hop_samples": "", "sample_rate": "",
                     "tool": "%s: %s" % (type(e).__name__, e),
                     "tool_version": traceback.format_exc()[-300:],
                     "n_models_in_consensus": ""})
    return rows


# ------------------------------------------------------------------ 主流程
def cmd_run(a):
    idx = load_index()
    models = (sorted(idx) if a.models == "all"
              else [m.strip() for m in a.models.split(",") if m.strip()])
    models = [m for m in models if m in idx]
    if not models:
        raise SystemExit("[FATAL] no model with exported output")

    common = None
    for m in models:
        s = set(idx[m])
        common = s if common is None else (common & s)
    clips = strat_sample(sorted(common), a.limit)

    print("=" * 78)
    print("DNS B' | models=%d | clips=%d | win=%d hop=%d @ %d Hz | jobs=%d"
          % (len(models), len(clips), WIN, HOP, SR, a.jobs))
    print("models: %s" % models)
    print("=" * 78)
    sys.stdout.flush()

    t0 = time.time()
    allrows = []
    if a.jobs <= 1:
        _init(idx, models)
        for i, c in enumerate(clips):
            allrows.extend(_one(c))
            if (i + 1) % 10 == 0:
                el = time.time() - t0
                print("  [%4d/%4d] %.1f s  %.2f s/clip  eta %.0f s"
                      % (i + 1, len(clips), el, el / (i + 1),
                         el / (i + 1) * (len(clips) - i - 1)))
                sys.stdout.flush()
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=a.jobs, initializer=_init,
                                 initargs=(idx, models)) as ex:
            for i, r in enumerate(ex.map(_one, clips, chunksize=4)):
                allrows.extend(r)
                if (i + 1) % 25 == 0:
                    el = time.time() - t0
                    print("  [%4d/%4d] %.1f s  %.2f s/clip  eta %.0f s"
                          % (i + 1, len(clips), el, el / (i + 1),
                             el / (i + 1) * (len(clips) - i - 1)))
                    sys.stdout.flush()

    errs = [r for r in allrows if r["kind"] == "error"]
    outp = PSEUDO / "b_prime.csv"
    cols = ["kind", "model", "clip", "sdr_db", "n_frames", "n_nonfinite",
            "dur_s", "level_ratio", "est", "ref", "win_samples", "hop_samples",
            "sample_rate", "tool", "tool_version", "n_models_in_consensus"]
    with open(outp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(allrows)

    print("\n[out] %s  rows=%d  errors=%d  wall=%.1f s"
          % (outp.relative_to(ROOT).as_posix(), len(allrows), len(errs),
             time.time() - t0))
    for e in errs[:3]:
        print("  ERR %-40s %s" % (e["clip"][:40], e["tool"][:120]))
    summarize(outp, len(clips))
    return 0


def summarize(path, n_clips):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    print("\nclips=%d  (stratified by duration)" % n_clips)
    for kind, title in (("b_cons", "B' (ref=consensus, est=noisy)"),
                        ("b_self", "B'_m (ref=model m, est=noisy)"),
                        ("agree", "agreement (ref=consensus, est=model m)")):
        agg = {}
        for r in rows:
            if r["kind"] != kind or r["sdr_db"] == "":
                continue
            agg.setdefault(r["model"], []).append(float(r["sdr_db"]))
        if not agg:
            continue
        print("\n[%s]" % title)
        print("  %-26s %5s %9s %9s %9s %9s" % ("model", "n", "median", "mean",
                                               "p10", "p90"))
        order = sorted(agg.items(), key=lambda kv: -np.median(kv[1]))
        for m, v in order:
            v = np.array(v)
            print("  %-26s %5d %9.3f %9.3f %9.3f %9.3f"
                  % (m, v.size, np.median(v), v.mean(),
                     np.percentile(v, 10), np.percentile(v, 90)))


def main():
    ap = argparse.ArgumentParser(description="DNS pseudo-reference B'")
    ap.add_argument("--models", default="all")
    ap.add_argument("--limit", type=int, default=None,
                    help="stratified subsample size (default: all 921)")
    ap.add_argument("--jobs", type=int, default=1,
                    help="⚠️ 保持 1: 本机沙箱会杀掉 ProcessPool 子进程 "
                         "(BrokenProcessPool); 只有脱离沙箱时才可 >1")
    a = ap.parse_args()
    return cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""在 DNS-Challenge dev_testset (921 条, 48k mono) 上跑全部降噪模型, 产出 pseudo-clean.

为什么需要这一步
----------------
DNS dev_testset 只有 noisy, 没有任何 clean 参考 -> baseline 的 Method B
(est=mixture, ref=clean) 在这个子集上**无定义**。D1 决策选 b:
用降噪模型的全量输出当"pseudo-clean"(伪参考), 使 B 可以在 DNS 上计算,
但必须全程标注为 B' (pseudo-reference), 不能与 Valentini/MUSDB 的真 B 并列。

输出
----
  baseline/dns_pseudo/<model>/<clip_id>.flac     16 kHz mono, PCM_16
  baseline/dns_pseudo/<model>/_manifest.json     逐条元数据
  baseline/dns_pseudo/_index.csv                 汇总索引

为什么统一存 16 kHz 单声道
--------------------------
  * mel_roformer 原生 44.1k 立体声, 全量存 float32 = 18.6 GB/模型 (磁盘不允许)。
  * 16 kHz 是板 2 的评测主口径 (PESQ 只支持 8/16 kHz), 也是各模型的公共分母。
  * 原生采样率/声道逐条记进 manifest, 不做隐瞒。
  * 16k -> 44.1k -> 16k 往返不引入 >8 kHz 能量, 回采误差远低于 -60 dB;
    与 48k->16k->48k 的 31 dB (永久丢失 8-24k) 性质不同。

🔴 采样率契约 (P19)
-------------------
  run_fn 恒收 (N,2) @ run_fn.contract_sr (=44100)。必须先把 48k 源重采样到
  contract_sr 再叠双声道, 否则 denoiser 内部二次降采样 -> 音频加速 2.76 倍。

🔴 长音频分段
-------------
  DNS 单条最长 77.5 s, 是 Valentini (最长 9.8 s) 的 8 倍。8 GiB 显存下整段前向
  有 OOM 风险, 因此默认按 30 s / 0.5 s 交叠分段推理, 交叠区线性交叉淡化。

用法
----
  python tools/_dns_pseudo_clean.py --plan
  python tools/_dns_pseudo_clean.py --models denoiser_master64 --limit 3    # 冒烟
  python tools/_dns_pseudo_clean.py --models denoiser_master64              # 单模型全量
  python tools/_dns_pseudo_clean.py --all                                   # 8 模型 x 921
"""
from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

import _denoise_registry as REG  # noqa: E402

ROOT = _paths.PROJECT_ROOT
DNS = (ROOT / "02_databases" / "DNS-Challenge" / "dev_testset"
       / "datasets_fullband" / "dev_testset" / "noisy_testclips")
OUT = ROOT / "baseline" / "dns_pseudo"
INDEX = OUT / "_index.csv"

SR_IN = 48000          # DNS 源采样率 (实测 921/921 全 48k mono)
SR_OUT = 16000         # 统一落盘率
SUB = "PCM_16"         # FLAC 位深


# ------------------------------------------------------------------ 音频工具
def resample(x, sr_in, sr_out):
    """时域重采样。x 可为 (N,) 或 (N,C)；torchaudio 要求时间维在最后。"""
    x = np.asarray(x, dtype=np.float32)
    if sr_in == sr_out:
        return x
    import torch
    import torchaudio.functional as AF
    t = torch.from_numpy(np.ascontiguousarray(x))
    if t.ndim == 1:
        y = AF.resample(t[None], sr_in, sr_out)[0]
    else:
        y = AF.resample(t.T, sr_in, sr_out).T
    return y.numpy().astype(np.float32)


def read_mono48(path):
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    m = x.mean(axis=1).astype(np.float32)
    if sr != SR_IN:
        m = resample(m, sr, SR_IN)
    return m, sr


def enhance_chunked(run_fn, info, mono48, chunk_s, overlap_s):
    """分段推理 + 交叠交叉淡化。返回 (N,2) @ 契约率的拼接结果。"""
    csr = int(getattr(run_fn, "contract_sr", 44100))
    x = resample(mono48, SR_IN, csr)
    n = len(x)
    if chunk_s <= 0 or n <= int(chunk_s * csr):
        d = run_fn(np.stack([x, x], axis=-1))
        return _pick(d)

    L = int(chunk_s * csr)
    O = int(overlap_s * csr)
    step = max(1, L - O)
    acc = None
    wsum = np.zeros(n, dtype=np.float64)
    start = 0
    while start < n:
        end = min(n, start + L)
        seg = x[start:end]
        d = run_fn(np.stack([seg, seg], axis=-1))
        y = _pick(d)
        # 模型可能返回少 2 个样本 (denoiser 已知行为)
        m = min(len(y), end - start)
        y = y[:m]
        w = np.ones(m, dtype=np.float64)
        if start > 0:                       # 左端淡入
            k = min(O, m)
            w[:k] = np.linspace(0.0, 1.0, k, endpoint=False)
        if end < n:                         # 右端淡出
            k = min(O, m)
            w[m - k:] = np.minimum(w[m - k:], np.linspace(1.0, 0.0, k,
                                                          endpoint=False))
        if acc is None:
            acc = np.zeros((n, y.shape[1]), dtype=np.float64)
        acc[start:start + m] += y.astype(np.float64) * w[:, None]
        wsum[start:start + m] += w
        if end >= n:
            break
        start += step
    wsum[wsum <= 0] = 1.0
    return (acc / wsum[:, None]).astype(np.float32)


def _pick(d):
    """目标键三选一: enhanced / dry / 首键 (dereverb-echo 是 2-stem 且无 enhanced)。"""
    if "enhanced" in d:
        tgt = "enhanced"
    elif "dry" in d:
        tgt = "dry"
    else:
        tgt = next(iter(d))
    return np.asarray(d[tgt], dtype=np.float32)


def to_disk_format(est, csr):
    """契约率输出 -> SR_OUT 单声道。"""
    m = est.mean(axis=1) if est.ndim == 2 else est
    return resample(m, csr, SR_OUT)


def list_clips(limit=None, start=0, end=None):
    rows = sorted(DNS.glob("*.wav"))
    rows = rows[start:end] if end is not None else rows[start:]
    return rows[:limit] if limit else rows


# ------------------------------------------------------------------ manifest
def man_path(key):
    return OUT / key / "_manifest.json"


def load_man(key):
    p = man_path(key)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            pass
    return {"model": key, "cells": {}}


def save_man(key, man):
    p = man_path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    man["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    p.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")


def write_index():
    """把 8 个模型的 manifest 汇总成一张 CSV。"""
    rows = []
    for key in sorted(REG.REGISTRY):
        p = man_path(key)
        if not p.is_file():
            continue
        man = json.loads(p.read_text(encoding="utf-8"))
        for cid, c in sorted(man.get("cells", {}).items()):
            if not c.get("ok"):
                continue
            # 只收录磁盘上真实存在的文件: 被中断/删除的半成品不得进入索引
            if not (ROOT / c.get("out", "")).is_file():
                continue
            rows.append({
                "model": key, "clip": cid,
                "dur_s": c.get("dur_s"), "sr_native": c.get("sr_native"),
                "ch_native": c.get("ch_native"), "sr_out": SR_OUT,
                "target": c.get("target"),
                "rms_in": c.get("rms_in"), "rms_out": c.get("rms_out"),
                "level_ratio": c.get("level_ratio"),
                "peak_raw": c.get("peak_raw"), "gain": c.get("gain"),
                "out": c.get("out"),
            })
    if not rows:
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["model", "clip", "dur_s", "sr_native", "ch_native", "sr_out",
            "target", "rms_in", "rms_out", "level_ratio", "peak_raw", "gain",
            "out"]
    with open(INDEX, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ------------------------------------------------------------------ 主流程
def resolve_keys(spec):
    if not spec or spec == "all":
        return list(REG.REGISTRY)
    keys = [k.strip() for k in spec.split(",") if k.strip()]
    bad = [k for k in keys if k not in REG.REGISTRY]
    if bad:
        raise SystemExit("[FATAL] unknown model key: %s\navailable: %s"
                         % (bad, list(REG.REGISTRY)))
    return keys


def cmd_plan(a):
    clips = list_clips(a.limit, a.start, a.end)
    keys = resolve_keys(a.models)
    print("DNS dev_testset clips : %d" % len(clips))
    print("models                : %d -> %s" % (len(keys), keys))
    print("total forwards        : %d" % (len(clips) * len(keys)))
    print("out root              : %s" % OUT.relative_to(ROOT).as_posix())
    print("disk format           : %d Hz mono %s (native sr/ch kept in manifest)"
          % (SR_OUT, SUB))
    return 0


def cmd_run(a):
    keys = resolve_keys(a.models)
    clips = list_clips(a.limit, a.start, a.end)
    if not clips:
        raise SystemExit("[FATAL] no clips selected")
    OUT.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("DNS pseudo-clean export | models %d | clips %d | force=%s"
          % (len(keys), len(clips), a.force))
    print("=" * 78)

    t_all = time.time()
    for mk in keys:
        t0 = time.time()
        man = load_man(mk)
        cells = man.setdefault("cells", {})
        done = {k for k, v in cells.items() if v.get("ok")}

        try:
            run_fn, load_s, info = REG.REGISTRY[mk]["loader"]()
            label = REG.REGISTRY[mk].get("label", mk)
        except Exception as e:                             # noqa: BLE001
            print("[FAIL-LOAD] %-26s %s" % (mk, e))
            traceback.print_exc()
            continue

        csr = int(getattr(run_fn, "contract_sr", 44100))
        nat_sr = int(info.get("sample_rate", csr))
        nat_ch = int(info.get("channels", 2))
        print("\n-- %-26s load=%.1fs  native %s Hz / %s ch  contract=%s  dev=%s"
              % (mk, load_s, nat_sr, nat_ch, csr, info.get("device")))
        print("   %s" % label)

        n_ok = n_skip = n_err = 0
        for p in clips:
            cid = p.stem
            outp = OUT / mk / (cid + ".flac")
            if cid in done and outp.is_file() and not a.force:
                n_skip += 1
                continue
            try:
                mono48, _ = read_mono48(p)
                est44 = enhance_chunked(run_fn, info, mono48, a.chunk_s,
                                        a.overlap_s)
                y = to_disk_format(est44, csr)
                outp.parent.mkdir(parents=True, exist_ok=True)
                # 🔴 削波防护: 模型输出真实峰值可达 1.23 (16k 重采样后 1.28), 直接
                # 写 PCM_16 会削掉 0.2~4% 的样本 -> SDR 被系统性压低。
                # SDR 对全局增益不变, 因此按峰值归一化到 0.999 并把增益记进
                # manifest, 读回时乘回。16-bit 量化噪声约 -89 dBFS, 远低于有效范围。
                peak = float(np.abs(y).max()) if y.size else 0.0
                gain = (0.999 / peak) if peak > 0.999 else 1.0
                sf.write(str(outp), y * gain, SR_OUT, subtype=SUB)
                r_in = float(np.sqrt(np.mean(mono48.astype(np.float64) ** 2)))
                r_out = float(np.sqrt(np.mean(y.astype(np.float64) ** 2)))
                cells[cid] = {
                    "model": mk, "clip": cid, "ok": True,
                    "out": outp.relative_to(ROOT).as_posix(),
                    "dur_s": round(len(y) / float(SR_OUT), 3),
                    "sr_native": nat_sr, "ch_native": nat_ch,
                    "target": "enhanced", "sr_out": SR_OUT,
                    "rms_in": round(r_in, 6), "rms_out": round(r_out, 6),
                    "level_ratio": round(r_out / (r_in + 1e-12), 4),
                    "peak_raw": round(peak, 4), "gain": round(gain, 6),
                }
                n_ok += 1
            except Exception as e:                          # noqa: BLE001
                cells[cid] = {
                    "model": mk, "clip": cid, "ok": False,
                    "error": "%s: %s" % (type(e).__name__, e),
                    "traceback": traceback.format_exc()[-1000:],
                }
                n_err += 1
                print("   FAIL %-44s %s: %s" % (cid[:44], type(e).__name__, e))
            n = n_ok + n_err
            if n and n % 40 == 0:
                save_man(mk, man)
                el = time.time() - t0
                print("   [%4d] ok=%d skip=%d err=%d  %.1f s  %.2f s/条  eta %.0f s"
                      % (n, n_ok, n_skip, n_err, el, el / max(1, n),
                         el / max(1, n) * (len(clips) - n)))
                sys.stdout.flush()

        man["clip_count"] = len(clips)
        man["sr_out"] = SR_OUT
        save_man(mk, man)
        print("   => ok=%d skip=%d err=%d  wall=%.1f s" % (n_ok, n_skip, n_err,
                                                           time.time() - t0))
        sys.stdout.flush()

        run_fn = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:                                   # noqa: BLE001
            pass

    n = write_index()
    print("\n[index] %s  rows=%d" % (INDEX.relative_to(ROOT).as_posix(), n))
    print("[total] %.1f s" % (time.time() - t_all))
    return 0


def main():
    ap = argparse.ArgumentParser(description="DNS dev_testset pseudo-clean export")
    ap.add_argument("--models", default="all",
                    help="all / comma separated registry keys")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--chunk-s", type=float, default=30.0,
                    help="inference chunk length in seconds (0 = whole clip)")
    ap.add_argument("--overlap-s", type=float, default=0.5)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()
    return cmd_plan(a) if a.plan else cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""在【全量 Valentini 带噪集】上跑全部降噪模型, 并把增强音频落盘。

背景
----
`03_outputs/` 里的降噪目录此前只有 1 个 stage0_gate 探针 (p232_001, 1.74 s),
没有逐条输出 -> 降噪板无法出图对比。本脚本补齐这一步。

数据
----
  valentini : 02_databases/Valentini/noisy_testset_wav/*.wav   (824 条, 48 kHz mono)
              配对 clean:  .../clean_testset_wav/<同名>.wav

模型 (来自 `_denoise_registry.REGISTRY`, 7 个权重 / 6 种架构)
-----------------------------------------------------------
  A 组 (mel_roformer, 44.1 kHz 立体声契约)
    mel_roformer_denoise / _aggr / mel_roformer_dereverb / _dereverb_echo
  B 组 (denoiser, 16 kHz 单声道原生)
    denoiser_dns48 / dns64 / master64

输出
----
  03_outputs/_valentini_denoise/<registry_key>/<clip_id>.wav
  03_outputs/_valentini_denoise/manifest.json

  🔴 保存为**各模型原生**格式 (info["sample_rate"] / info["channels"]):
       mel_roformer_*  -> 44100 Hz, 2ch
       denoiser_*      -> 16000 Hz, 1ch
     不统一成 44.1k, 免得把 denoiser 的 16k 输出上采样 2.76x 后当"原生"存。

🔴 采样率契约 (P19 铁律)
------------------------
  run_fn 假定输入已在 `run_fn.contract_sr` (=44100)。必须先把 48k 源
  重采样到契约率再叠双声道, 否则 denoiser 内部会二次降采样 -> 音频加速 2.76x。

可续跑: 输出已存在则跳过 (除非 --force)。

用法
----
  python tools/_denoise_export_valentini.py --plan
  python tools/_denoise_export_valentini.py --models B --limit 3     # 冒烟
  python tools/_denoise_export_valentini.py --models A               # mel 全量
  python tools/_denoise_export_valentini.py --all                    # 7 模型 x 824
"""
from __future__ import annotations

import argparse
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
VAL = ROOT / "02_databases" / "Valentini"
NOISY = VAL / "noisy_testset_wav"
CLEAN = VAL / "clean_testset_wav"
OUT = ROOT / "03_outputs" / "_valentini_denoise"
MANIFEST = OUT / "manifest.json"

SR_IN = 48000                      # Valentini 源采样率 (实测全 48k mono)

TOOL_ALIAS = {
    "A": ["mel_roformer_denoise", "mel_roformer_denoise_aggr",
          "mel_roformer_dereverb", "mel_roformer_dereverb_echo"],
    "B": ["denoiser_dns48", "denoiser_dns64", "denoiser_master64"],
}


# ------------------------------------------------------------------ 音频工具
def resample(x, sr_in, sr_out):
    """时域重采样。x 可为 (N,) 或 (N, C)；AF.resample 要求时间维在最后。"""
    x = np.asarray(x, dtype=np.float32)
    if sr_in == sr_out:
        return x
    import torch
    import torchaudio.functional as AF
    t = torch.from_numpy(np.ascontiguousarray(x))
    if t.ndim == 1:
        y = AF.resample(t[None], sr_in, sr_out)[0]
    else:
        y = AF.resample(t.T, sr_in, sr_out).T          # (N,C)->(C,N)->resample->(N,C)
    return y.numpy().astype(np.float32)


def list_clips(limit=None):
    """返回 [(clip_id, noisy_path, clean_path)]，已排序、成对校验。"""
    rows = []
    for p in sorted(NOISY.glob("*.wav")):
        c = CLEAN / p.name
        if c.is_file():
            rows.append((p.stem, p, c))
    return rows[:limit] if limit else rows


def enhance(run_fn, info, noisy_path):
    """跑一条片段，返回 (est, sr_out, ch_out) —— 取模型原生格式。"""
    x, sr = sf.read(str(noisy_path), dtype="float32", always_2d=True)
    mono = x.mean(axis=1).astype(np.float32)
    if sr != SR_IN:
        mono = resample(mono, sr, SR_IN)
    csr = int(getattr(run_fn, "contract_sr", 44100))
    xin = resample(mono, SR_IN, csr)
    d = run_fn(np.stack([xin, xin], axis=-1))          # {target: (N,2)} @ csr
    # 目标键三选一:
    #   "enhanced" -> 普通降噪 / dereverb (单 stem)
    #   "dry"      -> dereverb-echo (2 stem: dry=去混响干声, other=混响残留)
    if "enhanced" in d:
        tgt = "enhanced"
    elif "dry" in d:
        tgt = "dry"
    else:
        tgt = next(iter(d))
    est = np.asarray(d[tgt], dtype=np.float32)          # (N,2) @ csr
    nat_sr = int(info.get("sample_rate", csr))
    nat_ch = int(info.get("channels", 2))
    if nat_ch == 1:
        m = est.mean(axis=1)
        if csr != nat_sr:
            m = resample(m, csr, nat_sr)
        return m, nat_sr, 1, tgt
    if csr != nat_sr:
        est = resample(est, csr, nat_sr)
    return est, nat_sr, 2, tgt


def save_wav(path, data, sr):
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data, sr, subtype="FLOAT")
    return os.path.getsize(str(path))


# ------------------------------------------------------------------ manifest
def load_manifest():
    if MANIFEST.is_file():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            pass
    return {"task": "valentini denoise export", "cells": {}}


def save_manifest(man):
    OUT.mkdir(parents=True, exist_ok=True)
    man["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1),
                        encoding="utf-8")


# ------------------------------------------------------------------ 主流程
def resolve_keys(spec):
    keys = []
    for a in spec.split(","):
        a = a.strip()
        if not a:
            continue
        keys.extend(TOOL_ALIAS.get(a.upper(), [a]))
    bad = [k for k in keys if k not in REG.REGISTRY]
    if bad:
        raise SystemExit("[FATAL] 未知模型键: %s\n可用: %s"
                         % (bad, list(REG.REGISTRY)))
    return keys


def cmd_plan(args):
    clips = list_clips(args.limit)
    keys = resolve_keys(args.models) if args.models else list(REG.REGISTRY)
    print("原始片段 : %d  (%s)" % (len(clips), NOISY))
    print("模型     : %d -> %s" % (len(keys), keys))
    print("总前向数 : %d" % (len(clips) * len(keys)))
    print("输出根   : %s" % OUT.relative_to(ROOT).as_posix())
    return 0


def cmd_run(args):
    keys = resolve_keys(args.models) if args.models else list(REG.REGISTRY)
    if not keys:
        raise SystemExit("[FATAL] 无可跑模型")
    clips = list_clips(args.limit)
    man = load_manifest()
    done = set(man.get("cells", {}).keys())

    print("=" * 74)
    print("Valentini 降噪导出 | 模型 %d | 片段 %d | force=%s"
          % (len(keys), len(clips), args.force))
    print("=" * 74)

    t_all = time.time()
    for mk in keys:
        t0 = time.time()
        try:
            run_fn, load_s, info = REG.REGISTRY[mk]["loader"]()
            label = REG.REGISTRY[mk].get("label", mk)
        except Exception as e:                             # noqa: BLE001
            print("[FAIL-LOAD] %-26s %s" % (mk, e))
            traceback.print_exc()
            continue
        nat_sr = int(info.get("sample_rate", 0))
        nat_ch = int(info.get("channels", 0))
        print("\n-- %-26s load=%.1fs  原生 %s Hz / %s ch  device=%s"
              % (mk, load_s, nat_sr, nat_ch, info.get("device")))

        n_ok = n_skip = n_err = 0
        for cid, npath, _cpath in clips:
            ckey = "%s|%s" % (mk, cid)
            outp = OUT / mk / (cid + ".wav")
            if ckey in done and outp.is_file() and not args.force:
                n_skip += 1
                continue
            try:
                est, sr_o, ch_o, tgt = enhance(run_fn, info, npath)
                sz = save_wav(outp, est, sr_o)
                y_in, _ = sf.read(str(npath), dtype="float32", always_2d=True)
                r_in = float(np.sqrt(np.mean(y_in.astype(np.float64) ** 2)))
                r_out = float(np.sqrt(np.mean(est.astype(np.float64) ** 2)))
                man.setdefault("cells", {})[ckey] = {
                    "model": mk, "label": label, "clip_id": cid,
                    "out": outp.relative_to(ROOT).as_posix(),
                    "sr": sr_o, "ch": ch_o, "target": tgt,
                    "dur_s": round(len(est) / float(sr_o), 3),
                    "rms_in": round(r_in, 6), "rms_out": round(r_out, 6),
                    "level_ratio": round(r_out / (r_in + 1e-12), 4),
                    "wav_mb": round(sz / 1e6, 3),
                    "ok": True,
                }
                n_ok += 1
            except Exception as e:                          # noqa: BLE001
                tb = traceback.format_exc()
                man.setdefault("cells", {})[ckey] = {
                    "model": mk, "clip_id": cid, "ok": False,
                    "error": "%s: %s" % (type(e).__name__, e),
                    "traceback": tb[-1200:],
                }
                n_err += 1
                print("   FAIL %-12s %s: %s" % (cid, type(e).__name__, e))
            if (n_ok + n_err) % 50 == 0 and (n_ok + n_err):
                save_manifest(man)
        save_manifest(man)
        print("   ok=%d skip=%d err=%d  wall=%.1fs" % (n_ok, n_skip, n_err,
                                                       time.time() - t0))
        # 换模型前释放显存/内存
        run_fn = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:                                   # noqa: BLE001
            pass

    man["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_manifest(man)
    cells = man.get("cells", {})
    ok = sum(1 for v in cells.values() if v.get("ok"))
    bad = [k for k, v in cells.items() if not v.get("ok")]
    print("\n[manifest] %s" % MANIFEST.relative_to(ROOT).as_posix())
    print("[总计] ok=%d  失败=%d  用时=%.1fs"
          % (ok, len(bad), time.time() - t_all))
    if bad:
        print("[失败清单] %s" % bad[:20])
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="Valentini 全量降噪导出")
    ap.add_argument("--plan", action="store_true", help="只列规模")
    ap.add_argument("--models", default=None,
                    help="A / B / 逗号分隔 registry key (默认全部 7 个)")
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 条片段")
    ap.add_argument("--force", action="store_true", help="忽略已有输出重跑")
    ap.add_argument("--all", action="store_true", help="全量 (默认行为)")
    a = ap.parse_args()
    if a.plan:
        return cmd_plan(a)
    return cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())

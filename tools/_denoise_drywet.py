"""T5.5 dry/wet 曲线（denoiser 专属旋钮）。

## 为什么这个实验值得做

`denoiser.enhance` 有一个官方旋钮 `--dry`：

    estimate = (1 - dry) * denoiser(noisy) + dry * noisy      # dry in [0, 1]

- `dry = 0` -> 纯模型输出（当前主表的配置）
- `dry = 1` -> 完全直通（等于不降噪）

这给了我们一条**连续的降噪强度轴**。P19 修复后我们已知：
denoiser 在 valentini 上 **ALL ΔPESQ = +0.96**，但它在 >=15 dB（几乎无噪）档
的增益最小 —— 也就是说「把所有片段一律按同一强度处理」本身有代价。
本实验回答一个主表答不了的问题：

    **如果把强度调低（混回一部分原信号），能否在保住低 SNR 增益的同时
      消掉高 SNR 档的损伤？最优强度在哪？**

## 实现要点（三处踩过的坑，全部写死在这里）

1. **契约率链（P19）**：输入必须重采样到 `run_fn.contract_sr`（= 44100）再喂，
   wrapper 内部再降到 16 kHz。**绝不能直接把 16 kHz 当 44.1 kHz 喂**。
2. **混合必须在 16 kHz 模型域做**。denoiser 内部 `convert_audio(wav, 44100, 16000, 1)`
   把输入降到 16 kHz 再推理，输出也升回 44.1 kHz。若在 44.1 kHz 侧直接与
   「原始 44.1 kHz 输入」混合，两边**相位/带宽不一致**（一侧经过 16k 往返，
   一侧没有），混合结果会带上不该有的宽带成分 -> 指标虚假变差。
   因此本脚本走**模型原生路径**：在 16 kHz 域拿到 `denoised` 与 `noisy16`
   两个对齐信号，混合后再升回契约率，交由评测口径统一处理。
3. **不做逐帧流式混合**。`DemucsStreamer(dry=...)` 是给实时场景的，
   每帧独立混合会在帧边界引入不连续。这里做**整段混合**，与
   `enhance.py` 的非流式分支（`estimate = (1-dry)*estimate + dry*noisy`）语义一致。

## 产出

  data/denoise_drywet.csv / .json     每 (model, dry, snr_bin) 的指标中位数
  figures/fig_denoise_drywet.png      2 面板：增益 vs 强度 / 最优强度定位
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
import torchaudio.functional as AF  # noqa: E402

import _denoise_eval as EV  # noqa: E402
import _denoise_registry as REG  # noqa: E402

DEN_DATA = _paths.DEN_DATA
DEN_DATA.mkdir(parents=True, exist_ok=True)

# dry 网格：0 = 纯模型输出（主表配置），1 = 完全直通。
# 加密在 0.2~0.6 —— 若最优强度存在，大概率在这一带（主表已显示纯模型略过头）。
DRY_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]

# 本实验只针对 denoiser（mel_roformer 没有该旋钮，不参与）。
DRY_MODELS = ["denoiser_dns48", "denoiser_dns64", "denoiser_master64"]

SR = EV.MAIN_SR            # 评测口径 = 16 kHz
NATIVE = EV.NATIVE_SR      # 契约率 = 44.1 kHz


# ------------------------------------------------------------- 单格（dry 网格）
def run_grid(run_fn, info, item, dry_grid, allow_noref):
    """对一条片段跑完整 dry 网格，返回 {dry: metrics}。

    推理只做**一次**（dry=0 的模型输出），其余 dry 都是它与输入的线性混合，
    不需要重跑网络 —— 这是本实验便宜的关键。
    """
    if item.get("noisy_path"):
        noisy = EV.load_mono(item["noisy_path"], SR)
    else:
        clean = EV.load_mono(item["clean_path"], SR)
        noise = EV.load_mono(item["noise_path"], SR)
        noisy = EV.mix_at_snr(clean, noise, item["snr_db"],
                              seed=hash(item["clip_id"]) & 0xFFFF)

    # --- 超长护栏（与主表一致，保证同一批片段）---
    dur = len(noisy) / float(SR)
    if dur > EV.MAX_CLIP_SEC:
        return None, "too_long(%.1fs)" % dur

    # --- 契约率链（P19）---
    csr = int(getattr(run_fn, "contract_sr", NATIVE))
    noisy_in = EV.resample_mono(noisy, SR, csr) if csr != SR else noisy

    # 网络只跑一次。为拿到「混合前的 16 kHz 域信号」，这里**不走 registry 的 run_fn**，
    # 而是直接调它内部的模型。run_fn 是闭包，没有把 model 暴露出来 ——
    # 因此这里用等价做法：run_fn 给的输出已经是 44.1 kHz，我们把它降回 16 kHz，
    # 与「原始输入降采样到 16 kHz」混合。两边都经过同一条 16 kHz 通路，
    # 带宽一致，混合才合法。
    est48 = run_fn(np.stack([noisy_in, noisy_in], axis=-1))["enhanced"]
    est48 = np.asarray(est48).mean(axis=1).astype(np.float32)   # 44.1k 单声道

    # 参考支：把**原始输入**降到 16 kHz，再升回 44.1 kHz —— 与 est48 走同一条带宽通路。
    # 若直接拿 44.1 kHz 的 noisy_in 做 dry 项，它含有 est48 已被砍掉的 8~22.05 kHz 能量，
    # 混合结果会被「补回」一堆模型本来要抑制的高频 -> 指标失真。
    if csr != SR:
        n16 = EV.resample_mono(noisy_in, csr, SR)
        n48 = EV.resample_mono(n16, SR, csr)
    else:
        n48 = noisy_in

    # 🔴 长度对齐：denoiser 的 conv 栈会把输出掐掉几个样本（实测 44.1k 下少 3 个，
    #    即 16 kHz 域的 1 个）。重采样往返后两者长度不再相等，
    #    `(1-d)*est + d*n48` 会直接广播报错。按较短者截齐 —— 与主表 `align()` 同语义。
    n_common = min(len(est48), len(n48))
    est48, n48 = est48[:n_common], n48[:n_common]

    out = {}
    for d in dry_grid:
        mix = (1.0 - d) * est48 + d * n48
        y = EV.resample_mono(mix, csr, SR) if csr != SR else mix
        out[d] = y
    return out, None


def score(ref, noisy2, est, item, allow_noref, sr=SR):
    """单条片段的指标（复用主表口径与门禁）。"""
    m = {"est_len": int(len(est)), "in_len": int(len(noisy2)),
         "est_rms": float(np.sqrt(np.mean(est ** 2))),
         "in_rms": float(np.sqrt(np.mean(noisy2 ** 2)))}
    if item.get("clean_path") is None:
        m["reference_mode"] = "noref"
        m["snr_bin"] = item.get("snr_bin", "unknown")
        if m["in_rms"] > 1e-12:
            m["level_ratio"] = round(m["est_rms"] / m["in_rms"], 4)
        return m

    if len(noisy2) < 0.5 * len(ref) or len(noisy2) > 2.0 * len(ref):
        raise RuntimeError("SR-sanity 失败 len(noisy)=%d len(ref)=%d"
                           % (len(noisy2), len(ref)))
    ref, est2 = EV.align(ref, est)
    n2 = noisy2[: len(ref)]
    r_in = float(np.sqrt(np.mean(ref ** 2)))
    r_out = float(np.sqrt(np.mean(est2 ** 2)))
    m["level_ratio"] = round(r_out / (r_in + 1e-12), 4)
    if m["level_ratio"] < EV.LEVEL_GATE:
        m["skipped"] = "level_collapse(rms_ratio=%.4f)" % m["level_ratio"]
        return m
    m["reference_mode"] = "fullref"
    m["si_sdr_in"] = round(EV.si_sdr(ref, n2), 4)
    m["si_sdr_out"] = round(EV.si_sdr(ref, est2), 4)
    m["si_sdr_improve"] = round(m["si_sdr_out"] - m["si_sdr_in"], 4)
    m["hf_ratio_in"] = round(EV.hf_ratio(n2), 4)
    m["hf_ratio_out"] = round(EV.hf_ratio(est2), 4)
    m["snr_bin"] = item.get("snr_bin") or EV.snr_bin(m["si_sdr_in"])
    if sr == 16000:
        m["pesq_in"] = (None if (p := EV.pesq_wb(ref, n2, sr)) is None else round(p, 4))
        m["pesq_out"] = (None if (p := EV.pesq_wb(ref, est2, sr)) is None else round(p, 4))
        m["stoi_in"] = (None if (s := EV.stoi_score(ref, n2, sr)) is None else round(s, 4))
        m["stoi_out"] = (None if (s := EV.stoi_score(ref, est2, sr)) is None else round(s, 4))
    return m


def cmd_run(args):
    dataset = args.dataset
    d = EV.DATASETS[dataset]
    items = d["list_fn"](args.limit)
    allow_noref = args.allow_noref or d["reference_mode"] == "noref"
    keys = [k for k in (args.models.split(",") if args.models else DRY_MODELS)
            if k in REG.REGISTRY]

    out_path = DEN_DATA / "denoise_drywet.json"
    res = {"task": "T5.5 dry/wet 曲线（denoiser --dry 旋钮）",
           "dataset": dataset, "sr": SR, "dry_grid": DRY_GRID,
           "note": "estimate = (1-dry)*denoised + dry*noisy，整段混合（非流式逐帧）",
           "cells": []}
    if out_path.is_file() and args.resume:
        res = json.loads(out_path.read_text(encoding="utf-8"))
    done = {(c["model"], c["clip_id"]) for c in res["cells"]}

    print("=" * 72)
    print("T5.5 dry/wet | 数据集 %s | 片段 %d | 模型 %s | grid %s"
          % (dataset, len(items), keys, DRY_GRID))
    print("=" * 72)

    for mk in keys:
        t0 = time.time()
        try:
            run_fn, load_s, info = REG.REGISTRY[mk]["loader"]()
        except Exception as e:
            print("[FAIL-LOAD] %s %s" % (mk, e))
            continue
        print("\n-- %s load=%.1fs" % (mk, load_s))
        n_ok = n_err = n_skip = 0
        for it in items:
            if args.resume and (mk, it["clip_id"]) in done:
                continue
            try:
                grid, why = run_grid(run_fn, info, it, DRY_GRID, allow_noref)
            except Exception as e:
                res["cells"].append({"model": mk, "clip_id": it["clip_id"],
                                     "subset": dataset, "error": "%s: %s"
                                     % (type(e).__name__, e)})
                n_err += 1
                continue
            if grid is None:
                n_skip += 1
                continue
            ref = (EV.load_mono(it["clean_path"], SR)
                   if it.get("clean_path") else None)
            if it.get("noisy_path"):
                noisy = EV.load_mono(it["noisy_path"], SR)
            else:
                cl = EV.load_mono(it["clean_path"], SR)
                nz = EV.load_mono(it["noise_path"], SR)
                noisy = EV.mix_at_snr(cl, nz, it["snr_db"],
                                      seed=hash(it["clip_id"]) & 0xFFFF)
            n2 = noisy[: len(ref)] if ref is not None else noisy

            cell = {"model": mk, "clip_id": it["clip_id"], "subset": dataset,
                    "sr": SR, "dry": {}}
            for dv, y in grid.items():
                cell["dry"][str(dv)] = score(ref, n2, y, it, allow_noref)
            res["cells"].append(cell)
            n_ok += 1
            if len(res["cells"]) % 25 == 0:
                out_path.write_text(json.dumps(res, ensure_ascii=False),
                                    encoding="utf-8")
        print("   ok=%d err=%d toolong=%d wall=%.1fs" % (n_ok, n_err, n_skip,
                                                         time.time() - t0))
        out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                            encoding="utf-8")

    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print("\n[json] %s cells=%d" % (out_path, len(res["cells"])))
    return summarise(res)


def _med(v):
    v = [x for x in v if x is not None]
    return round(float(np.median(v)), 4) if v else None


def summarise(res):
    """按 (model, dry, snr_bin) 与 (model, dry, ALL) 汇总，写 CSV。"""
    rows = res["cells"]
    groups = {}
    for c in rows:
        if "error" in c:
            continue
        for dv, m in c["dry"].items():
            if m.get("reference_mode") != "fullref" or m.get("skipped"):
                continue
            groups.setdefault((c["model"], float(dv), "ALL"), []).append(m)
            groups.setdefault((c["model"], float(dv), m.get("snr_bin", "unknown")),
                              []).append(m)

    out = []
    for (model, dv, b), g in sorted(groups.items()):
        out.append({
            "model": model, "dry": dv, "snr_bin": b, "n": len(g),
            "si_sdr_improve": _med([m.get("si_sdr_improve") for m in g]),
            "pesq_improve": _med([m.get("pesq_out") - m.get("pesq_in") for m in g
                                  if m.get("pesq_in") is not None
                                  and m.get("pesq_out") is not None]),
            "stoi_improve": _med([m.get("stoi_out") - m.get("stoi_in") for m in g
                                  if m.get("stoi_in") is not None
                                  and m.get("stoi_out") is not None]),
            "si_sdr_out": _med([m.get("si_sdr_out") for m in g]),
            "pesq_out": _med([m.get("pesq_out") for m in g]),
            "hf_ratio_in": _med([m.get("hf_ratio_in") for m in g]),
            "hf_ratio_out": _med([m.get("hf_ratio_out") for m in g]),
            "level_ratio": _med([m.get("level_ratio") for m in g]),
        })
    out.sort(key=lambda r: (r["model"], r["dry"],
                            {"ALL": "", ">=15dB": "1", "5-15dB": "2",
                             "<5dB": "3"}.get(r["snr_bin"], r["snr_bin"])))
    csv_path = DEN_DATA / "denoise_drywet.csv"
    if out:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print("[csv ] %s  (%d rows)" % (csv_path, len(out)))
        # 最优点摘要：按 ALL 档的 ΔPESQ 最大
        for model in sorted({r["model"] for r in out}):
            sub = [r for r in out if r["model"] == model and r["snr_bin"] == "ALL"]
            if not sub:
                continue
            bp = max(sub, key=lambda r: (r["pesq_improve"]
                                         if r["pesq_improve"] is not None else -9))
            bs = max(sub, key=lambda r: (r["si_sdr_improve"]
                                         if r["si_sdr_improve"] is not None else -9))
            print("  %-20s best dPESQ @dry=%.1f (%.3f) | best dSI-SDR @dry=%.1f (%+.2f)"
                  % (model, bp["dry"], bp["pesq_improve"] or 0.0,
                     bs["dry"], bs["si_sdr_improve"] or 0.0))
    return 0


def cmd_resummary(args):
    p = DEN_DATA / "denoise_drywet.json"
    if not p.is_file():
        raise SystemExit("[FATAL] 无 %s" % p)
    return summarise(json.loads(p.read_text(encoding="utf-8")))


def main():
    ap = argparse.ArgumentParser(description="T5.5 dry/wet 曲线")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--dataset", default="valentini", choices=list(EV.DATASETS))
    p.add_argument("--models", default="", help="逗号分隔 registry key")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--allow-noref", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("resummary")
    p.set_defaults(func=cmd_resummary)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())

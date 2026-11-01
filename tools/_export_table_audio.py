# -*- coding: utf-8 -*-
"""导出表格中「代表样本」的真实 output 音频 + 原始数据音频。

目录结构（root = 03_outputs/TableSample_Audio）：
    <root>/<模型或组合>/<数据源>/原始数据/<样本>__input.wav
                                  <样本>__reference.wav   （无 clean 时省略）
                                  <样本>__noise.wav       （仅 dns）
    <root>/<模型或组合>/<数据源>/output/<样本>__output.wav

「代表样本」= 与 Excel 完全同口径（复用 `_build_eval_excel.filter_recs` + `select_reps`）：
    极端值过滤（时长<1s 或 SDR<-25）→ 每组选 最接近均值/最高/最低 各 3 个（去重）。

模型命名：sep:mdx_q -> mdx_q；cascade:mdx_q:denoiser_master64 -> mdx_q_to_denoiser_master64。

用法：
  python tools/_export_table_audio.py --dry-run               # 只列计划，不跑模型
  python tools/_export_table_audio.py                         # 全量导出（需 GPU，约 40 min）
  python tools/_export_table_audio.py --limit-groups 1 --limit-samples 1   # 冒烟

内存策略（重要）：
  每个 (pipeline, db) 分组「加载 → 处理 → 立即释放显存」。曾经用 run_cache
  跨组缓存模型权重，20 个级联管线（各含分离+去噪两个子模型）累积在 8GB
  显存里，跑到第 21 组时 CUDA OOM。现在每组 finally 里 del + gc + empty_cache，
  任意时刻只保留 1 个管线（cascade 为 2 个子模型），8GB 足够。
"""
from __future__ import annotations

import argparse
import gc
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _eval_pipeline as EP          # noqa: E402  (load_pipeline / load_mono / mix_at_snr)
import _build_eval_excel as BE       # noqa: E402  (filter_recs / select_reps)

DNS_SNR = 5.0   # 全量评测时 dns 用的目标 SNR（bat 未覆盖，默认 5.0）


def model_dir_name(pipeline: str) -> str:
    parts = pipeline.split(":")
    if parts[0] == "sep":
        return parts[1]
    return "%s_to_%s" % (parts[1], parts[2])


def _safe(name: str) -> str:
    for ch in "\\/:*?\"<>|":
        name = name.replace(ch, "_")
    return name.strip()


def _cuda_gb() -> float:
    if not torch.cuda.is_available():
        return 0.0
    return torch.cuda.memory_allocated() / 1e9


def gather_plan(root: Path):
    """返回 [ {pipeline, db, rec}, ... ]，与 Excel 代表样本一致。"""
    plan = []
    for jf in sorted(root.rglob("results.json")):
        recs = json.loads(jf.read_text(encoding="utf-8"))
        if not recs:
            continue
        for r in BE.select_reps(recs):
            plan.append({"pipeline": r["pipeline"], "db": r["db"], "rec": r})
    return plan


def _reconstruct(pipeline, rec):
    """返回 (input_mono_44k, reference_mono_44k_or_None, reference_src_path_or_None,
             input_src_path_or_None, noise_src_path_or_None)。"""
    db = rec["db"]
    clean_path = rec.get("clean")
    noisy_path = rec.get("noisy")

    if db == "wham":
        return EP.load_mono(noisy_path), None, None, noisy_path, None
    if db == "dns":
        clean = EP.load_mono(clean_path)
        noise = EP.load_mono(noisy_path)
        return EP.mix_at_snr(clean, noise, DNS_SNR), clean, clean_path, None, noisy_path
    # musdb / valentini
    clean = EP.load_mono(clean_path)
    return EP.load_mono(noisy_path), clean, clean_path, noisy_path, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="03_outputs/_eval")
    ap.add_argument("--out-root", default="03_outputs/TableSample_Audio")
    ap.add_argument("--limit-groups", type=int, default=0, help="0=全部")
    ap.add_argument("--limit-samples", type=int, default=0, help="每组最多导出的样本数(0=全部9)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    plan = gather_plan(Path(a.root))
    print("[export] 计划导出 %d 个样本" % len(plan))

    # 按 (pipeline, db) 分组，便于一次性加载模型
    from collections import defaultdict
    groups = defaultdict(list)
    for p in plan:
        groups[(p["pipeline"], p["db"])].append(p["rec"])

    if a.limit_groups:
        groups = dict(list(groups.items())[: a.limit_groups])

    out_root = Path(a.out_root)
    manifest = []

    for gi, ((pipeline, db), recs) in enumerate(groups.items(), 1):
        if a.limit_samples:
            recs = recs[: a.limit_samples]
        print("[export] [%d/%d] %s | %s | %d 样本" % (gi, len(groups), pipeline, db, len(recs)),
              file=sys.stderr)
        if a.dry_run:
            for r in recs:
                print("   -", r["sample"], "| SDR %.2f" % r["sdr_db"])
            continue

        # 每组：加载 -> 处理 -> finally 释放显存（见模块 docstring 的内存策略）
        run = None
        try:
            t0 = time.time()
            run = EP.load_pipeline(pipeline)[0]
            print("    load %.1fs (alloc %.2f GB)" % (time.time() - t0, _cuda_gb()),
                  file=sys.stderr)

            for r in recs:
                sid = _safe(r["sample"])
                mdir = out_root / model_dir_name(pipeline) / db
                raw_dir = mdir / "原始数据"
                out_dir = mdir / "output"
                raw_dir.mkdir(parents=True, exist_ok=True)
                out_dir.mkdir(parents=True, exist_ok=True)

                try:
                    inp, ref, ref_src, inp_src, noise_src = _reconstruct(pipeline, r)
                    t0 = time.time()
                    est = run(inp)
                    infer_s = time.time() - t0
                    if est.ndim == 2:
                        est = est[:, 0]
                    m = min(len(inp), len(est))
                    est = est[:m]

                    # 原始数据：复制源文件；dns 的合成输入需落盘
                    if inp_src:
                        shutil.copy2(inp_src, raw_dir / ("%s__input.wav" % sid))
                    else:
                        sf.write(str(raw_dir / ("%s__input.wav" % sid)), inp, EP.SR)
                    if ref_src:
                        shutil.copy2(ref_src, raw_dir / ("%s__reference.wav" % sid))
                    if noise_src:
                        shutil.copy2(noise_src, raw_dir / ("%s__noise.wav" % sid))
                    # output
                    sf.write(str(out_dir / ("%s__output.wav" % sid)), est, EP.SR)

                    manifest.append({
                        "pipeline": pipeline, "db": db, "sample": r["sample"],
                        "sdr_db": round(r["sdr_db"], 3), "dur_s": round(r["dur_s"], 3),
                        "infer_s": round(infer_s, 3),
                        "input": str(raw_dir / ("%s__input.wav" % sid)),
                        "output": str(out_dir / ("%s__output.wav" % sid)),
                    })
                    print("    ok %s (%.1fs)" % (r["sample"][:36], infer_s), file=sys.stderr)
                except Exception as e:  # noqa: BLE001
                    print("    FAIL %s: %s" % (r["sample"], e), file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print("    GROUP FAIL %s: %s" % (pipeline, e), file=sys.stderr)
        finally:
            if run is not None:
                del run
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("    release -> alloc %.2f GB" % _cuda_gb(), file=sys.stderr)

    if not a.dry_run:
        (out_root / "_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        n_out = len(list(out_root.rglob("*__output.wav")))
        n_plan = len(plan)
        status = ("OK" if len(manifest) == n_out == n_plan
                  else "PARTIAL" if len(manifest) == n_out else "MISMATCH")
        print("[export] DONE manifest=%d/%d -> %s" % (len(manifest), n_plan, out_root))
        print("[export] VERIFY manifest=%d output_wav=%d -> %s"
              % (len(manifest), n_out, status))


if __name__ == "__main__":
    main()

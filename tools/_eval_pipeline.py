# -*- coding: utf-8 -*-
"""批量评测：分离模型 / 级联流水线 × 4 数据库，逐样本 SDR + spectrogram 图 + JSON 明细。

统一模式（Sheet 1 分离模型 与 Sheet 2 级联 共用）：
  对每个样本 (clean, noisy)：
    1. clean = 参考（干净语音 / GT 分轨）
    2. noisy = 输入（混音 / 带噪语音 / 合成噪声）
    3. 管线(pipeline) 跑 noisy -> est（分离输出的 vocals，或级联输出的 enhanced）
    4. SDR = 10·log10( Σ clean² / Σ (est − clean)² )   [dB]
    5. 出图：clean↑est↓ 并排 spectrogram，共用 clean 峰值 0 dB（能量对齐）
    6. 写 JSON 明细（断点续跑用 .done 标记）

管线：
  --pipeline sep:<key>                分离模型（bsroformer_l12 / demucs / mdx_q / mdx_extra_q）
  --pipeline cascade:<sep>:<den>      分离 -> 降噪 级联

数据库：
  musdb      MUSDB18-HQ test（clean=vocals.wav，noisy=mixture.wav）
  valentini  clean_testset_wav + noisy_testset_wav（同名配对）
  dns        clean 池 + noise 池（合成 noisy，seed 固定可复现，目标 SNR）
  wham       high_res_wham/audio（**无 clean 分轨**：把模型最终 output 当作 clean 参考，
             与原始输入对比 → SDR 表示「输出相对输入的差异」，图 top=output / bottom=input）

用法：
  python tools/_eval_pipeline.py --pipeline sep:mdx_q --db musdb --limit 3 --out-dir OUT
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

# ---- stdout 让给 loader 的自由打印，协议/进度走 stderr ---------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import benchmark_model_universal as BM  # noqa: E402
import _denoise_registry as DEN  # noqa: E402
from _chunked_infer import chunked_separate  # noqa: E402

ROOT = Path(_paths.PROJECT_ROOT)
SR = 44100
CHUNK_S = 10.0
OVERLAP_S = 1.0
DEFAULT_MAX_SAMPLES = 500   # 每库默认上限：超过 500 只跑前 500，不足则全跑


# ------------------------------------------------------------------ 数据源
def _list_musdb():
    """[(sample_id, clean_path, noisy_path)]"""
    base = ROOT / "02_databases" / "MUSDB18-HQ" / "test"
    out = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        clean, noisy = d / "vocals.wav", d / "mixture.wav"
        if clean.exists() and noisy.exists():
            out.append((d.name, clean, noisy))
    return out


def _list_valentini():
    base = ROOT / "02_databases" / "Valentini"
    clean_dir, noisy_dir = base / "clean_testset_wav", base / "noisy_testset_wav"
    out = []
    for c in sorted(clean_dir.glob("*.wav")):
        n = noisy_dir / c.name
        if n.exists():
            out.append((c.stem, c, n))
    return out


def _list_dns(seed=0, target_snr=5.0):
    """clean 池 + noise 池 合成 noisy（seed 固定可复现）。"""
    clean_base = ROOT / "02_databases" / "DNS-Challenge" / "clean"
    noise_base = ROOT / "02_databases" / "DNS-Challenge" / "noise" / "freesound" / "datasets_fullband" / "noise_fullband"
    cleans = sorted(clean_base.rglob("*.wav"))
    noises = sorted(noise_base.glob("*.wav"))
    rng = np.random.default_rng(seed)
    out = []
    for c in cleans:
        n = noises[int(rng.integers(0, len(noises)))]
        out.append((c.stem, c, n, target_snr))
    return out


def _list_wham():
    base = Path(r"F:\high_res_wham\audio")
    if not base.exists():
        return []
    out = []
    for f in sorted(base.glob("*.wav")):
        out.append((f.stem, None, f))       # clean=None -> 参考改用模型输出
    return out


DATABASES = {
    "musdb": _list_musdb,
    "valentini": _list_valentini,
    "dns": _list_dns,
    "wham": _list_wham,
}


# ------------------------------------------------------------------ 工具
def load_mono(path, sr_out=SR):
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != sr_out:
        import torch
        import torchaudio.functional as AF
        t = torch.as_tensor(np.ascontiguousarray(x[None, :]))
        x = AF.resample(t, sr, sr_out).numpy()[0]
    return x.astype(np.float32)


def mix_at_snr(clean, noise, target_db):
    """noisy = clean + gain*noise，使 SNR(clean/noise)=target_db。"""
    clean = clean.astype(np.float64)
    noise = noise.astype(np.float64)
    m = min(len(clean), len(noise))
    clean, noise = clean[:m], noise[:m]
    cpow = np.mean(clean ** 2)
    npow = np.mean(noise ** 2)
    if npow < 1e-15 or cpow < 1e-15:
        return clean
    gain = np.sqrt(cpow / npow / (10 ** (target_db / 10.0)))
    return (clean + gain * noise).astype(np.float32)


def sdr_db(clean, est):
    clean = clean.astype(np.float64)
    est = est.astype(np.float64)
    m = min(len(clean), len(est))
    clean, est = clean[:m], est[:m]
    denom = np.sum((est - clean) ** 2)
    num = np.sum(clean ** 2)
    if denom < 1e-15:
        return float("inf") if num > 0 else 0.0
    return float(10.0 * np.log10(num / denom))


def _spec_mag(x, sr, n_fft=2048, hop=1024):
    win = np.hanning(n_fft)
    n_frames = 1 + (len(x) - n_fft) // hop
    S = np.zeros((n_fft // 2 + 1, n_frames))
    for i in range(n_frames):
        seg = x[i * hop: i * hop + n_fft] * win
        S[:, i] = np.abs(np.fft.rfft(seg))
    return S


def draw_pair(clean, est, sr, out_png, name, sdr_val, title="",
              top_label="clean", bot_label="est"):
    """top↑ bottom↓ 并排 spectrogram，共用 top 峰值 0 dB。"""
    m = min(len(clean), len(est))
    Sc = _spec_mag(clean[:m], sr)
    Se = _spec_mag(est[:m], sr)
    # per-panel normalize: 各面板以自身峰值为 0dB，避免一边能量高把另一边衬成饱和糊

    fig, axes = plt.subplots(2, 1, figsize=(7, 4.4), sharex=True)
    for ax, S, label in ((axes[0], Sc, top_label), (axes[1], Se, bot_label)):
        db = 20 * np.log10(S / (float(np.max(S)) + 1e-15) + 1e-12)
        im = ax.imshow(db, aspect="auto", origin="lower", cmap="magma",
                       vmin=-80, vmax=0,
                       extent=[0, m / sr, 0, sr / 2])
        ax.set_ylabel(label + "\n(kHz)")
        ax.set_yticks([0, 4000, 8000, 12000, 16000, 20000])
        ax.set_yticklabels(["0", "4", "8", "12", "16", "20"])
    axes[1].set_xlabel("time (s)")
    sdr_txt = "SDR inf" if sdr_val == float("inf") else ("SDR %.2f dB" % sdr_val) if sdr_val is not None else "SDR N/A"
    fig.suptitle(f"{title}  {name}\n{sdr_txt}", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


# ------------------------------------------------------------------ 管线
def load_pipeline(pipeline):
    """返回 (run_pipeline, label)。run_pipeline(noisy_mono_44k) -> est_mono_44k。"""
    parts = pipeline.split(":")
    kind = parts[0]

    if kind == "sep":
        key = parts[1]
        spec = BM.REGISTRY[key]
        run_fn, load_s, info = spec["loader"]()
        contract = int(getattr(run_fn, "contract_sr", SR))

        def run(x):
            mix = np.stack([x, x], axis=-1).astype(np.float32)
            if len(mix) > CHUNK_S * SR:
                stems = chunked_separate(run_fn, mix, sr=SR, chunk_s=CHUNK_S, overlap_s=OVERLAP_S)
            else:
                stems = run_fn(mix)
            y = stems.get("vocals", next(iter(stems.values())))
            return y[:, 0] if y.ndim == 2 else y

        return run, f"{spec.get('label', key)} (sep)"

    if kind == "cascade":
        sep_key, den_key = parts[1], parts[2]
        sep_spec = BM.REGISTRY[sep_key]
        den_spec = DEN.REGISTRY[den_key]
        sep_fn, _, _ = sep_spec["loader"]()
        den_fn, _, _ = den_spec["loader"]()
        den_contract = int(getattr(den_fn, "contract_sr", SR))

        def run(x):
            mix = np.stack([x, x], axis=-1).astype(np.float32)
            if len(mix) > CHUNK_S * SR:
                stems = chunked_separate(sep_fn, mix, sr=SR, chunk_s=CHUNK_S, overlap_s=OVERLAP_S)
            else:
                stems = sep_fn(mix)
            voc = stems.get("vocals", next(iter(stems.values())))
            if voc.ndim == 2:
                voc = voc[:, 0]
            den_in = np.stack([voc, voc], axis=-1).astype(np.float32)
            out = den_fn(den_in)
            enh = out.get("enhanced", next(iter(out.values())))
            return enh[:, 0] if enh.ndim == 2 else enh

        return run, f"{sep_spec.get('label', sep_key)} -> {den_spec.get('label', den_key)} (cascade)"

    raise ValueError("unknown pipeline: %s" % pipeline)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", required=True, help="sep:<key> 或 cascade:<sep>:<den>")
    ap.add_argument("--db", required=True, choices=list(DATABASES))
    ap.add_argument("--limit", type=int, default=0,
                    help="显式样本数(>0 生效)；默认每库上限 %d（不足全跑）" % DEFAULT_MAX_SAMPLES)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--dns-snr", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--force", action="store_true",
                    help="忽略 .done 断点，重跑全部样本并覆盖 results.json")
    a = ap.parse_args()

    out_dir = Path(a.out_dir)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "results.json"
    done_dir = out_dir / ".done"
    done_dir.mkdir(exist_ok=True)

    # 收集样本（默认每库上限 500）
    if a.db == "dns":
        samples = _list_dns(seed=a.seed, target_snr=a.dns_snr)
    else:
        samples = DATABASES[a.db]()
    cap = a.limit if a.limit > 0 else DEFAULT_MAX_SAMPLES
    samples = samples[:cap]

    # 加载管线（一次加载，循环复用）
    print("[eval] loading pipeline %s ..." % a.pipeline, file=sys.stderr)
    t0 = time.time()
    run, label = load_pipeline(a.pipeline)
    print("[eval] loaded in %.1fs" % (time.time() - t0), file=sys.stderr)

    results = []
    for i, item in enumerate(samples):
        sid = item[0]
        marker = done_dir / (sid + ".done")
        if marker.exists() and not a.force:
            continue

        clean_path, noisy_path = item[1], item[2]
        try:
            # 读 clean / noisy
            if a.db == "dns":
                clean = load_mono(clean_path)
                noise = load_mono(noisy_path)
                noisy = mix_at_snr(clean, noise, a.dns_snr)
            elif a.db == "wham":
                clean = None
                noisy = load_mono(noisy_path)
            else:  # musdb / valentini
                clean = load_mono(clean_path)
                noisy = load_mono(noisy_path)

            t1 = time.time()
            est = run(noisy)
            infer_s = time.time() - t1

            fig_path = fig_dir / (sid + ".png")
            if a.db == "wham":
                # 无 clean 分轨：把模型最终 output 当作 clean 参考，与原始输入对比
                m = min(len(noisy), len(est))
                est = est[:m]
                ref = est                 # clean 参考 = 模型输出
                tgt = noisy[:m]           # 对比目标 = 原始输入
                sdr_val = sdr_db(ref, tgt)   # 输出相对输入的差异
                draw_pair(ref, tgt, SR, fig_path, sid, sdr_val, title=label,
                          top_label="output (ref)", bot_label="input")
                ref_mode = "model_output"
            else:
                m = min(len(clean), len(est))
                est = est[:m]
                sdr_val = sdr_db(clean, est)
                draw_pair(clean, est, SR, fig_path, sid, sdr_val, title=label)
                ref_mode = "gt"

            rec = {
                "sample": sid, "db": a.db, "pipeline": a.pipeline, "label": label,
                "sdr_db": sdr_val, "ref": ref_mode, "infer_s": round(infer_s, 3),
                "dur_s": round(m / SR, 3),
                "clean": str(clean_path) if clean_path else None,
                "noisy": str(noisy_path),
                "figure": str(fig_path),
            }
            results.append(rec)
            marker.write_text("ok")
            print("[%d/%d] %s  SDR=%s  %.1fs" % (
                i + 1, len(samples), sid,
                ("%.2f" % sdr_val) if sdr_val is not None else "N/A", infer_s), file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print("[%d/%d] %s  FAIL %s: %s" % (i + 1, len(samples), sid, type(e).__name__, e), file=sys.stderr)
            (out_dir / "errors.txt").open("a", encoding="utf-8").write(
                "%s\t%s\n%s\n" % (sid, e, traceback.format_exc()[-1500:]))

    # 写 manifest（--force 直接覆盖；否则累积不覆盖已完成）
    if manifest.exists() and not a.force:
        old = json.loads(manifest.read_text(encoding="utf-8"))
        seen = {r["sample"] for r in old}
        for r in results:
            if r["sample"] not in seen:
                old.append(r)
        results = old
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    # 汇总
    sdrs = [r["sdr_db"] for r in results if r["sdr_db"] is not None and r["sdr_db"] != float("inf")]
    print("[eval] DONE  n=%d  SDR mean=%.2f min=%.2f max=%.2f" % (
        len(sdrs), np.mean(sdrs) if sdrs else 0.0,
        np.min(sdrs) if sdrs else 0.0, np.max(sdrs) if sdrs else 0.0), file=sys.stderr)


if __name__ == "__main__":
    main()

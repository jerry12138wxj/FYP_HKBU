"""Export a small, listenable A/B set for the denoise board (board 2 / step 09).

Why this script exists
----------------------
`_denoise_eval.py` computes metrics **in memory** and never writes audio: after
a full sweep the only thing on disk is CSV/JSON.  So the project had no way to
*hear* what the numbers describe -- the only listenable denoise audio was the
1.74 s stage-0 gate probe.  This script closes that gap.

What it produces
----------------
    03_outputs/_denoise_ab/<clip_id>/{noisy,clean,<model>.wav}
    04_reports/02_denoising/data/denoise_ab_manifest.json

Inputs are replayed along **exactly the eval contract** so that the audio you
hear is the audio the recorded metric describes:

    source --(48k)--> load_mono @16k --> resample @44.1k (run_fn.contract_sr)
           --> model --> (N,2) @44.1k   [== the wav written for playback]
           --> downmix mono --> resample @16k --> SI-SDR / PESQ / STOI
                                              [== the numbers on the page]

Two hard rules carried over from P19 / the SR contract
------------------------------------------------------
1. The signal handed to `run_fn` MUST already be at `run_fn.contract_sr`
   (44100).  Feeding a 16 kHz array makes denoiser's wrapper resample a second
   time (audio sped up 2.76x) -- see P19_SAMPLE_RATE_CONTRACT_BUG.md.
2. The metric side MUST use the 16 kHz array, never the contract-rate array
   (mixing them produced the absurd si_sdr_in = -73 dB).

Determinism note (important, honest)
------------------------------------
`_denoise_eval.py` seeds the synthetic mixture with Python's builtin `hash()`,
which is randomised per process (no PYTHONHASHSEED is set anywhere in the
repo).  The recorded synth metrics therefore are **not reproducible across
runs** -- re-synthesising gives the same SNR but a different noise window, and
for an impulsive (door) noise the window decides whether the transient even
lands inside the clip.

This script therefore uses a **deterministic** seed (`zlib.crc32(clip_id)`) and
**recomputes** every metric on the exact mixture it exports, so the page is
self-consistent ("what you hear is what the number says").  The recorded
manifest value is stored alongside for traceability and the delta is printed.

Usage
-----
    python tools/_export_denoise_ab.py                 # full 16-clip set
    python tools/_export_denoise_ab.py --limit 2       # smoke test
    python tools/_export_denoise_ab.py --clips p232_340,p232_412_s-05
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

import _denoise_registry as REG  # noqa: E402
from _denoise_eval import (  # noqa: E402
    list_synth, list_valentini, load_mono, mix_at_snr, resample_mono,
    pesq_wb, si_sdr, stoi_score,
)

ROOT = _paths.PROJECT_ROOT
OUT_AUDIO = ROOT / "03_outputs" / "_denoise_ab"
OUT_JSON = _paths.DEN_DATA / "denoise_ab_manifest.json"
EVAL_MANIFEST = _paths.DEN_DATA / "denoise_manifest.json"

MAIN_SR = 16000          # metric rate (PESQ-legal, and the eval's main口径)
PLAY_SR = 44100          # playback rate == the registry contract rate

# ---------------------------------------------------------------- models ----
# key -> (short file stem, display label, note)
MODELS = [
    ("denoiser_dns48", "denoiser-dns48",
     "denoiser dns48", "波形域因果 U-Net · 16 kHz · 18.9 M 参数 · 最轻"),
    ("denoiser_dns64", "denoiser-dns64",
     "denoiser dns64", "同上，hidden=64 · 33.5 M · 训练集不含 Valentini"),
    ("denoiser_master64", "denoiser-master64",
     "denoiser master64", "同上，训练集**含** Valentini（in-domain）· ΔPESQ 最优"),
    ("mel_roformer_denoise", "mel-roformer-denoise",
     "Mel-RoFormer-Denoise", "mel 分带 + RoPE Transformer · 44.1 kHz 立体声 · 228 M"),
    ("mel_roformer_denoise_aggr", "mel-roformer-denoise-aggr",
     "Mel-RoFormer-Denoise (aggr)", "同上，更强抑制版"),
]

# ----------------------------------------------------------------- clips ----
# 10 real Valentini clips.  Selection is deliberate, not arbitrary: it spans
# the three input-SI-SDR strata used by the report, and inside each stratum it
# takes the two disagreement extremes (denoiser-dominant / mel-dominant) plus a
# near-median case, so the page shows *where each model wins* rather than only
# the average.  Numbers quoted in `why` are read from denoise_eval_16k.csv.
VALENTINI_PICKS = [
    ("p232_340", "<5dB",   "denoiser 优势最大档：dns48 +21.9 dB vs mel +1.0 dB"),
    ("p232_130", "<5dB",   "denoiser 大幅领先：+19.1 vs +1.1"),
    ("p232_361", "<5dB",   "★ mel 反而赢：+23.0 vs dns48 +11.2（有效域互补）"),
    ("p232_263", "<5dB",   "同档中位：+10.2 vs +5.0，差距不极端"),
    ("p232_381", "5-15dB", "denoiser 优势最大档：+15.9 vs mel +0.9"),
    ("p257_105", "5-15dB", "★ mel 赢：+14.0 vs dns48 +4.5"),
    ("p232_083", "5-15dB", "近似打平：+13.2 vs +12.6（最能说明「看情况」）"),
    ("p232_255", ">=15dB", "输入已较干净，denoiser 仍 +7.5 vs mel +1.5"),
    ("p232_309", ">=15dB", "★ dns48 几乎不动（+0.2），mel +11.4"),
    ("p232_001", ">=15dB", "★ 指标分歧：mel ΔSI-SDR +8.7 但 ΔPESQ −0.27（感知变差）"),
]

# 6 synthetic transient clips.  The synth set is Valentini clean + a freesound
# noise pool that is dominated by impulsive `door` recordings -- i.e. this is
# the transient/冲击 case.  It is the single clearest result of step 09:
# mel_roformer is ~identity on transients (median ΔSI-SDR +0.1..+0.4 dB across
# every SNR level) while denoiser recovers 9-14 dB.
# NOTE: the synth set is re-mixed here with a deterministic seed, whereas the
# eval manifest used builtin hash() (unpinned) -- so the numbers below would go
# stale.  These strings therefore carry only the *role* of each clip; the
# measured dSDR is appended at run time by build_clip().
SYNTH_PICKS = [
    ("p232_412_s-05", "冲击噪声 · 最低 SNR · denoiser 优势最大的个案"),
    ("p257_393_s-05", "冲击噪声 · 最低 SNR · 中位个案"),
    ("p232_115_s+00", "冲击噪声 · SNR 0 dB · denoiser 优势个案"),
    ("p232_171_s+00", "冲击噪声 · SNR 0 dB · 中位个案"),
    ("p232_066_s+05", "冲击噪声 · SNR +5 dB · denoiser 优势个案"),
    ("p232_177_s+10", "冲击噪声 · SNR +10 dB · denoiser 优势个案"),
]


# ----------------------------------------------------------- eval manifest ----
def load_eval_manifest():
    """Index the recorded 16 kHz eval cells: (subset, clip, model) -> cell."""
    if not EVAL_MANIFEST.is_file():
        return {}
    man = json.loads(EVAL_MANIFEST.read_text(encoding="utf-8"))
    out = {}
    for c in man.get("cells", []):
        if c.get("sr") != MAIN_SR or not c.get("ok"):
            continue
        out[(c.get("subset"), c.get("clip_id"), c.get("model"))] = c
    return out


def _dx(o, i):
    if o is None or i is None:
        return None
    return round(o - i, 4)


def measure(ref, noisy, est, sr=MAIN_SR):
    """Same metric set as _denoise_eval.eval_one, on already-16k mono arrays."""
    ref, est = (np.asarray(a, dtype=np.float32) for a in (ref, est))
    n = min(len(ref), len(est))
    ref, est = ref[:n], est[:n]
    noisy = np.asarray(noisy, dtype=np.float32)[:n]
    r_out = float(np.sqrt(np.mean(est ** 2)))
    r_ref = float(np.sqrt(np.mean(ref ** 2)))
    m = {
        "si_sdr_in": round(si_sdr(ref, noisy), 4),
        "si_sdr_out": round(si_sdr(ref, est), 4),
        "level_ratio": round(r_out / (r_ref + 1e-12), 4),
        "pesq_in": None, "pesq_out": None,
        "stoi_in": None, "stoi_out": None,
    }
    m["si_sdr_improve"] = round(m["si_sdr_out"] - m["si_sdr_in"], 4)
    if sr == 16000:
        m["pesq_in"] = pesq_wb(ref, noisy, sr)
        m["pesq_out"] = pesq_wb(ref, est, sr)
        m["stoi_in"] = stoi_score(ref, noisy, sr)
        m["stoi_out"] = stoi_score(ref, est, sr)
    m["pesq_improve"] = _dx(m["pesq_out"], m["pesq_in"])
    m["stoi_improve"] = _dx(m["stoi_out"], m["stoi_in"])
    return m


# ------------------------------------------------------------------ audio ----
def write_wav(path, audio, sr):
    """Write stereo float->PCM_16.  Always (N,2): every model is addressed by the
    same (N,2) contract, and mono sources are duplicated so the player can align
    every row on one timeline."""
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 1:
        a = np.stack([a, a], axis=-1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(str(path), a, sr, subtype="PCM_16")
    return os.path.getsize(path)


def _rel_src(abs_path):
    """Path relative to the HTML dir, URL-quoted (server root == project root)."""
    from urllib.parse import quote
    html_dir = ROOT / "04_reports" / "02_denoising" / "html"
    rel = os.path.relpath(str(abs_path), str(html_dir)).replace("\\", "/")
    return quote(rel, safe="/+")


def build_clip(item, kind, why, regs, evalm):
    cid = item["clip_id"]
    t0 = time.time()

    # ---- 1. the 16 kHz signal the metrics are defined on --------------------
    if kind == "valentini":
        noisy16 = load_mono(item["noisy_path"], MAIN_SR)
        clean16 = load_mono(item["clean_path"], MAIN_SR)
        noise_name = None
        target_snr = None
    else:
        clean16 = load_mono(item["clean_path"], MAIN_SR)
        noise16 = load_mono(item["noise_path"], MAIN_SR)
        # deterministic seed -- see module docstring (builtin hash() is not stable)
        seed = zlib.crc32(cid.encode("utf-8")) & 0xFFFF
        noisy16 = mix_at_snr(clean16, noise16, item["snr_db"], seed=seed)
        noise_name = str(item["noise_path"]).replace("\\", "/").split("/")[-1]
        target_snr = float(item["snr_db"])

    n = min(len(noisy16), len(clean16))
    noisy16, clean16 = noisy16[:n], clean16[:n]

    # ---- 2. the 44.1 kHz signal the models actually receive -----------------
    noisy44 = resample_mono(noisy16, MAIN_SR, PLAY_SR)
    clean44 = resample_mono(clean16, MAIN_SR, PLAY_SR)

    clip_dir = OUT_AUDIO / cid
    refs = []
    for role, label, arr in (("noisy", "输入：含噪信号 noisy（模型看到的就是它）", noisy44),
                             ("clean", "参考：干净语音 clean（GT，用于算指标）", clean44)):
        p = clip_dir / ("%s.wav" % role)
        mb = write_wav(p, arr, PLAY_SR)
        refs.append({"role": role, "label": label, "src": _rel_src(p),
                     "mb": round(mb / 1e6, 2), "sr": PLAY_SR, "ch": 2,
                     "dur": round(len(arr) / PLAY_SR, 2)})

    # ---- 3. run every model, save 44.1k output, score at 16k -----------------
    out_models = []
    for key, stem, label, note in MODELS:
        run_fn, load_s, info = regs[key]
        stack = np.stack([noisy44, noisy44], axis=-1).astype(np.float32)
        t1 = time.time()
        est44 = np.asarray(run_fn(stack)["enhanced"], dtype=np.float32)
        infer_s = time.time() - t1

        p = clip_dir / ("%s.wav" % stem)
        mb = write_wav(p, est44, PLAY_SR)

        est16 = resample_mono(est44.mean(axis=1), PLAY_SR, MAIN_SR)
        met = measure(clean16, noisy16, est16)

        prev = evalm.get((item["subset"], cid, key), {})
        rec = {
            "key": key, "label": label, "note": note, "stem": stem,
            "src": _rel_src(p), "mb": round(mb / 1e6, 2),
            "sr": PLAY_SR, "ch": int(est44.shape[1]) if est44.ndim == 2 else 1,
            "dur": round(len(est44) / PLAY_SR, 2),
            "infer_s": round(infer_s, 3), "load_s": round(load_s, 2),
            "params": info.get("params"),
            "native_sr": info.get("sample_rate"),
            "metrics": met,
            "eval_manifest": {
                "si_sdr_improve": prev.get("si_sdr_improve"),
                "pesq_out": prev.get("pesq_out"), "pesq_in": prev.get("pesq_in"),
                "stoi_out": prev.get("stoi_out"), "stoi_in": prev.get("stoi_in"),
                "level_ratio": prev.get("level_ratio"),
                "skipped": prev.get("skipped"),
            },
        }
        out_models.append(rec)

        d = None
        if prev.get("si_sdr_improve") is not None:
            d = round(met["si_sdr_improve"] - prev["si_sdr_improve"], 4)
        print("    %-28s dSDR %+7.2f  dPESQ %s  dSTOI %s   (manifest %s, delta %s)"
              % (key, met["si_sdr_improve"],
                 "%+.3f" % met["pesq_improve"] if met["pesq_improve"] is not None else "  n/a",
                 "%+.4f" % met["stoi_improve"] if met["stoi_improve"] is not None else "  n/a",
                 prev.get("si_sdr_improve"), d))

    # synth clips: append the freshly measured dSDR so the annotation can never
    # quote a stale manifest number (the mix is re-done with a pinned seed).
    if kind == "synth":
        _m = {r["key"]: r["metrics"]["si_sdr_improve"] for r in out_models}
        why = "%s 【重算 dns48 %+.1f dB vs mel %+.1f dB】" % (
            why, _m.get("denoiser_dns48", 0.0), _m.get("mel_roformer_denoise", 0.0))

    clip = {
        "id": cid, "kind": kind, "subset": item["subset"], "why": why,
        "title": cid if kind == "valentini" else cid,
        "snr_bin": item.get("snr_bin"),
        "target_snr_db": target_snr,
        "noise_name": noise_name,
        "dur_s": round(n / MAIN_SR, 2),
        "refs": refs,
        "models": out_models,
    }
    print("  [%s] %s  %.2fs  (%.1fs wall)"
          % (kind, cid, clip["dur_s"], time.time() - t0))
    return clip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", default=None, help="逗号分隔的 clip_id 白名单")
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 条（冒烟）")
    a = ap.parse_args()

    evalm = load_eval_manifest()
    print("eval manifest cells indexed:", len(evalm))

    # resolve the source rows from the eval's own enumerators (no hand-rolled paths)
    val = {r["clip_id"]: r for r in list_valentini()}
    syn = {r["clip_id"]: r for r in list_synth()}

    plan = []
    for cid, bin_, why in VALENTINI_PICKS:
        if cid not in val:
            raise SystemExit("[FATAL] valentini clip not found: %s" % cid)
        plan.append((val[cid], "valentini", "%s · %s" % (bin_, why)))
    for cid, why in SYNTH_PICKS:
        if cid not in syn:
            raise SystemExit("[FATAL] synth clip not found: %s" % cid)
        plan.append((syn[cid], "synth", "瞬态冲击噪声 · %s · %s"
                     % (syn[cid]["snr_bin"], why)))

    if a.clips:
        want = {c.strip() for c in a.clips.split(",") if c.strip()}
        plan = [p for p in plan if p[0]["clip_id"] in want]
        missing = want - {p[0]["clip_id"] for p in plan}
        if missing:
            raise SystemExit("[FATAL] unknown clip(s): %s" % ", ".join(sorted(missing)))
    if a.limit:
        plan = plan[:a.limit]
    print("clips to export:", len(plan))

    # load all models up front: a load failure must be loud, not per-clip
    regs = {}
    for key, stem, label, note in MODELS:
        t0 = time.time()
        run_fn, load_s, info = REG.REGISTRY[key]["loader"]()
        _ = run_fn
        regs[key] = (run_fn, load_s, info)
        print("  loaded %-28s %.2f M params  native %s Hz  (%.1fs)"
              % (key, info.get("params", 0) / 1e6, info.get("sample_rate"),
                 time.time() - t0))

    clips, problems = [], []
    for item, kind, why in plan:
        try:
            clips.append(build_clip(item, kind, why, regs, evalm))
        except Exception as e:                                   # noqa: BLE001
            import traceback
            print("  !! FAILED %s: %s" % (item["clip_id"], e))
            traceback.print_exc()
            problems.append("%s: %s" % (item["clip_id"], e))

    db = {
        "task": "09 降噪评测 · 可聆听 A/B 集",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "play_sr": PLAY_SR, "metric_sr": MAIN_SR,
        "audio_dir": str(OUT_AUDIO).replace("\\", "/"),
        "models": [{"key": k, "stem": s, "label": l, "note": n} for k, s, l, n in MODELS],
        "clips": clips,
        "problems": problems,
        "caveats": [
            "指标口径 = 16 kHz（PESQ 只在该率合法）；播放音频 = 44.1 kHz 契约率。",
            "denoiser 原生 16 kHz：8 kHz 以上无内容，听感偏闷是带宽上限，不是降噪损坏。",
            "合成集(瞬态)是在 16 kHz 上混音的，因此其冲击噪声本身带宽 ≤ 8 kHz —— 与评测完全一致。",
            "合成集每次重合成会得到不同噪声窗口（评测脚本用了不可复现的 hash() 种子）；"
            "本页数字是在**导出音频上重算**的，manifest 旧值仅作对照。",
        ],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\njson :", OUT_JSON)
    print("audio:", OUT_AUDIO)
    tot = sum(f.stat().st_size for f in OUT_AUDIO.rglob("*.wav"))
    print("wav  : %d files, %.1f MB" % (len(list(OUT_AUDIO.rglob("*.wav"))), tot / 1e6))
    if problems:
        print("\n!! problems (%d)" % len(problems))
        for p in problems:
            print("   ", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""T5.1 降噪评测统一入口（板 2）。

一个入口，服务「工具 A/B × 两数据集」，不分叉：

    dataset x model  ->  per-clip metrics  ->  aggregate CSV/JSON

工具（models，来自 `_denoise_registry.REGISTRY`）
------------------------------------------------
  A. mel_roformer_denoise        Mel-RoFormer-Denoise-Aufr33      (44.1 kHz stereo)
     mel_roformer_denoise_aggr   同上，aggressive 版
  B. denoiser_dns48 / dns64 / master64   facebookresearch/denoiser (16 kHz mono)

数据集
------
  valentini  : 824 noisy/clean 配对  ->  full-reference 指标
  dns_dev    : 921 条 noisy_testclips，**无 clean GT**  ->  只能无参考指标

🔴 口径铁律（本项目踩过的坑，全部写死在这里）
------------------------------------------------
1. **PESQ 只支持 8/16 kHz** -> 主口径统一重采样到 **16 kHz**；副口径用原生率但**不报 PESQ**。
2. **DNS dev 无 GT** -> 该集**不产出** SI-SDR/PESQ/STOI，只产出无参考量；
   结果 JSON 里 `reference_mode = "noref"`，CSV 中 full-ref 列写 NaN 而不是 0。
3. **绝不混表**：主副口径各出一张表，文件名带口径后缀。
4. **denoiser 输出恒为单声道**（原生 16 kHz mono）-> 与立体声参考比指标前先下混，
   且 `info["native_sr"]` 必须显式记录。

产出（全部落 `04_reports/denoiser/data/`）
------------------------------------------
  denoise_eval_<sr>k.csv          主/副口径指标表
  denoise_eval_<sr>k.json         同内容 + provenance + 每格可复现命令
  denoise_manifest.json           clip 级中间结果（可续跑）

用法
----
  python _denoise_eval.py plan                       # 看将跑哪些格子
  python _denoise_eval.py run --models a --dataset valentini --limit 20
  python _denoise_eval.py run --dataset valentini    # 全量（824 条 x N 模型）
  python _denoise_eval.py resummary                  # 只重算汇总，不重推理

CPU 亦可跑（denoiser 很小），GPU 更快。每 (model, clip) 独立异常隔离，
单条失败不拖垮整批。
"""
from __future__ import annotations

import argparse
import csv
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

DEN_DATA = _paths.DEN_DATA
DEN_DATA.mkdir(parents=True, exist_ok=True)

VAL = _paths.PROJECT_ROOT / "02_databases" / "Valentini"
DNS = _paths.PROJECT_ROOT / "02_databases" / "DNS-Challenge"
DNS_NOISY = (DNS / "dev_testset" / "datasets_fullband" / "dev_testset"
             / "noisy_testclips")

MAIN_SR = 16000          # 主口径（PESQ 可用的唯一公平口径）
NATIVE_SR = 44100        # 副口径：本 registry 的对外契约采样率

# 🔴 单条片段最大时长（秒）。超过则判 skipped 而不是让它把 CUDA 上下文打死。
#    实测案例：DNS dev 有一条 77.5 s 的片段（数据集最长，中位仅 18.6 s），
#    mel_roformer 是**全序列** transformer，3416414 样本 × 2ch 直接
#    触发 `CUDA driver error: device not ready`（不是 OOM，是上下文崩）。
#    denoiser 因为内部自动分块，同一条能跑过。
#    → 统一跳过，保证**所有模型看到同一批片段**（可比性优先于覆盖率），
#      并在 manifest 里显式记录，而不是静默失败。
MAX_CLIP_SEC = 30.0

# 工具别名 -> registry key(s)
TOOL_ALIAS = {
    "A": ["mel_roformer_denoise", "mel_roformer_denoise_aggr"],
    "B": ["denoiser_dns48", "denoiser_dns64", "denoiser_master64"],
}


# ------------------------------------------------------------------ 数据枚举
def list_valentini(limit=None):
    """返回 [{clip_id, noisy_path, clean_path, subset}]，已按 id 排序、成对校验。"""
    noisy_dir = VAL / "noisy_testset_wav"
    clean_dir = VAL / "clean_testset_wav"
    if not noisy_dir.is_dir():
        raise SystemExit("[FATAL] 缺 %s" % noisy_dir)
    rows = []
    for p in sorted(noisy_dir.glob("*.wav")):
        c = clean_dir / p.name
        if not c.is_file():
            continue                                  # 不成对 -> 丢弃而非报错
        rows.append({"clip_id": p.stem, "subset": "valentini",
                     "noisy_path": str(p), "clean_path": str(c)})
    return rows[:limit] if limit else rows


def list_dns_dev(limit=None):
    """DNS dev_testset：只有 noisy，无 clean GT -> clean_path=None。"""
    if not DNS_NOISY.is_dir():
        raise SystemExit("[FATAL] 缺 %s" % DNS_NOISY)
    rows = []
    for p in sorted(DNS_NOISY.glob("*.wav")):
        rows.append({"clip_id": p.stem, "subset": "dns_dev",
                     "noisy_path": str(p), "clean_path": None})
    return rows[:limit] if limit else rows


def list_synth(limit=None):
    """自造带噪对（P12）：Valentini clean + freesound 噪声，SNR 可控，GT 与 SNR 均为真值。

    不落盘音频；评测时按 `mix_recipe` 现算，因此 SNR 分档是真值而非事后估计。
    """
    mf = DEN_DATA / "synth_pairs_manifest.json"
    if not mf.is_file():
        raise SystemExit("[FATAL] 缺自造清单，先跑 _dns_make_pairs.py：%s" % mf)
    man = json.loads(mf.read_text(encoding="utf-8"))
    rows = []
    for r in man["rows"]:
        rows.append({
            "clip_id": r["id"], "subset": "synth",
            "clean_path": str(_paths.PROJECT_ROOT / r["clean"]),
            "noise_path": str(_paths.PROJECT_ROOT / r["noise"]),
            "snr_db": float(r["snr_db"]),
            "snr_bin": r["snr_bin"],           # 真值分档
            "noisy_path": None,                # 运行时合成
        })
    return rows[:limit] if limit else rows


def mix_at_snr(clean, noise, snr_db, seed=0, eps=1e-12):
    """按目标 SNR 合成 noisy。噪声不足则循环铺满（含随机偏移）。"""
    n = len(clean)
    if len(noise) < n:
        reps = int(np.ceil(n / len(noise)))
        noise = np.tile(noise, reps)
    off = seed % max(1, len(noise) - n + 1)
    noise = noise[off:off + n].astype(np.float32)
    p_s = float(np.mean(clean ** 2))
    p_n = float(np.mean(noise ** 2))
    g = np.sqrt((p_s + eps) / ((p_n + eps) * (10 ** (snr_db / 10.0))))
    return (clean + g * noise).astype(np.float32)


DATASETS = {
    "valentini": dict(list_fn=list_valentini, reference_mode="fullref"),
    "synth": dict(list_fn=list_synth, reference_mode="fullref"),
    "dns_dev": dict(list_fn=list_dns_dev, reference_mode="noref"),
}

# 电平保真门禁：模型输出 rms / 输入 clean rms 的下限。
# 已实测：denoiser 带【绝对电平门控】，对低电平语音会把整段静音
# （Valentini 里约 3~5% 的片段会踩到；DNS clean 子集则大面积踩到）。
# 这类片段上算出的指标没有意义，标 skipped 而不是计入统计。
LEVEL_GATE = 0.20


# ------------------------------------------------------------------ 音频 IO
def load_mono(path, target_sr, max_seconds=None):
    """读任意 wav -> mono float32 @ target_sr。用 soundfile 而非 torchaudio，
    避免后端差异；长度上限切成整段读（不流式）。"""
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if max_seconds:
        x = x[: int(max_seconds * sr)]
    if sr != target_sr:
        import torch
        import torchaudio.functional as AF
        t = torch.as_tensor(np.ascontiguousarray(x.T))
        t = AF.resample(t, sr, target_sr)
        x = t.numpy().T
    return x.mean(axis=1).astype(np.float32)          # 下混到 mono


def resample_mono(x, sr_in, sr_out):
    """单声道重采样。用于在评测口径与 run_fn 契约率之间转换，
    避免把已降采样的信号当 44.1k 再降一次（曾导致音频加速 2.76x）。"""
    if sr_in == sr_out:
        return np.asarray(x, dtype=np.float32)
    import torch
    import torchaudio.functional as AF
    t = torch.from_numpy(np.ascontiguousarray(np.asarray(x, dtype=np.float32)))[None]
    return AF.resample(t, sr_in, sr_out)[0].numpy().astype(np.float32)


def align(a, b):
    """按下混单声道后对齐长度（模型可能少/多几样本）。"""
    n = min(len(a), len(b))
    return a[:n], b[:n]


# ------------------------------------------------------------------ 指标
def si_sdr(ref, est, eps=1e-8):
    """scale-invariant SDR（dB）。ref/est 均为 mono float32。"""
    ref = ref - ref.mean()
    est = est - est.mean()
    alpha = float(np.dot(est, ref) / (np.dot(ref, ref) + eps))
    target = alpha * ref
    noise = est - target
    return float(10.0 * np.log10((np.sum(target ** 2) + eps)
                                 / (np.sum(noise ** 2) + eps)))


def pesq_wb(ref, est, sr):
    """PESQ wide-band，仅 16 kHz 合法。"""
    from pesq import pesq as _p
    try:
        return float(_p(sr, ref, est, "wb"))
    except Exception:
        return None


def stoi_score(ref, est, sr):
    from pystoi import stoi as _s
    try:
        return float(_s(ref, est, sr, extended=False))
    except Exception:
        return None


def lsd(ref, est, n_fft=1024, hop=256):
    """log-spectral distance（dB）。仅作副口径参考量。"""
    import torch
    w = torch.hann_window(n_fft)
    A = torch.stft(torch.as_tensor(ref), n_fft, hop, window=w,
                   return_complex=True).abs()
    B = torch.stft(torch.as_tensor(est), n_fft, hop, window=w,
                   return_complex=True).abs()
    A = torch.clamp(A, min=1e-8)
    B = torch.clamp(B, min=1e-8)
    return float(torch.sqrt(torch.mean((20 * torch.log10(A / B)) ** 2)).item())


def snr_db(ref, est, eps=1e-8):
    n = min(len(ref), len(est))
    ref, est = ref[:n], est[:n]
    p_s = float(np.sum(ref ** 2))
    p_n = float(np.sum((est - ref) ** 2))
    return float(10.0 * np.log10((p_s + eps) / (p_n + eps)))


def hf_ratio(x):
    """高频能量占比（上半频带）。用于检测「低通式过度抑制」：
    模型把高频砍掉但 clean 里高频本该存在 -> 占比塌陷。"""
    X = np.abs(np.fft.rfft(x))
    if X.sum() <= 0:
        return 0.0
    return float(X[len(X) // 4:].sum() / X.sum())


def snr_bin(v):
    """输入 SNR 分层。分档边界取整，便于报告。"""
    if v is None:
        return "unknown"
    if v >= 15:
        return ">=15dB"
    if v >= 5:
        return "5-15dB"
    return "<5dB"


# ------------------------------------------------------------------ 单格
def eval_one(run_fn, info, item, sr, allow_noref):
    """跑一个 (model, clip) 格。返回 metrics dict；异常时带 error 字段。

    noisy 来源二选一：
      a. `noisy_path` 给定 -> 直接读（Valentini / DNS dev）
      b. `clean_path` + `noise_path` + `snr_db` -> 即时合成（DNS synth）
    真实 SNR 分档：优先用清单里的 `snr_bin`（真值），否则按输入 SI-SDR 事后分档。
    """
    clean48 = None
    if item.get("noisy_path"):
        noisy = load_mono(item["noisy_path"], sr)
    else:
        clean48 = load_mono(item["clean_path"], sr)
        noise = load_mono(item["noise_path"], sr)
        noisy = mix_at_snr(clean48, noise, item["snr_db"], seed=hash(item["clip_id"]) & 0xFFFF)

    # 🔴 超长片段护栏：全序列 transformer 在超长输入上会把 CUDA 上下文打死
    #    （实测 DNS dev 有一条 77.5 s，报 "device not ready" 而非 OOM）。
    #    这里统一判 skipped，保证所有模型看到同一批片段。
    dur = len(noisy) / float(sr)
    if dur > MAX_CLIP_SEC:
        m = {"clip_id": item["clip_id"], "subset": item["subset"], "sr": sr,
             "reference_mode": "noref" if item.get("clean_path") is None else "fullref",
             "skipped": "too_long(%.1fs > %.0fs)" % (dur, MAX_CLIP_SEC),
             "dur_sec": round(dur, 2)}
        if item.get("snr_bin"):
            m["snr_bin"] = item["snr_bin"]
        if item.get("snr_db") is not None:
            m["target_snr_db"] = float(item["snr_db"])
        return m

    # 🔴 采样率契约（2026-09-23 修，P19）：混音必须重采样到 run_fn 的契约率再喂，
    # 否则 denoiser 的 wrapper 会把已降采样的信号再降一次 -> 音频加速 2.76x。
    # ⚠️ 关键：契约率信号绝不可覆盖 `noisy` 本身 —— 指标侧（参考比对、hf_ratio、
    #    pesq/stoi）必须一律使用【评测率】数组，否则长度错位 -> si_sdr_in 出 -73 dB 荒谬值。
    csr = int(getattr(run_fn, "contract_sr", NATIVE_SR))
    noisy_in = resample_mono(noisy, sr, csr) if csr != sr else noisy
    est_stereo = run_fn(np.stack([noisy_in, noisy_in], axis=-1))   # (N,2) 契约
    est = np.asarray(est_stereo["enhanced"]).mean(axis=1).astype(np.float32)
    if csr != sr:
        est = resample_mono(est, csr, sr)

    m = {"clip_id": item["clip_id"], "subset": item["subset"],
         "sr": sr, "est_len": int(len(est)), "in_len": int(len(noisy)),
         "est_rms": float(np.sqrt(np.mean(est ** 2))),
         "in_rms": float(np.sqrt(np.mean(noisy ** 2)))}
    if item.get("snr_db") is not None:
        m["target_snr_db"] = float(item["snr_db"])
    if item.get("src_group"):
        m["src_group"] = item["src_group"]

    if item.get("clean_path") is None:
        if not allow_noref:
            raise RuntimeError("dns_dev 无 clean GT；需 --allow-noref")
        m["reference_mode"] = "noref"
        m["snr_bin"] = item.get("snr_bin", "unknown")
        # 🔴 level_ratio 是**无参考量**（只依赖输入/输出 rms），noref 集同样能算。
        #    此前这里直接 return，导致 dns_dev 的 level_ratio 要手工从 rms 现算。
        if m["in_rms"] > 1e-12:
            m["level_ratio"] = round(m["est_rms"] / m["in_rms"], 4)
            if m["level_ratio"] < LEVEL_GATE:
                m["skipped"] = "level_collapse(rms_ratio=%.4f)" % m["level_ratio"]
        return m

    ref = load_mono(item["clean_path"], sr)
    # 🔴 P19 附则护栏：输入参考必须与参考同口径。长度比例失衡 = 信号被写坏，
    # 直接抛错而不是算出 -73 dB 这种荒谬指标（曾静默污染 4120 个 cell）。
    if len(noisy) < 0.5 * len(ref) or len(noisy) > 2.0 * len(ref):
        raise RuntimeError(
            "SR-sanity 失败：len(noisy)=%d vs len(ref)=%d @sr=%d "
            "(比例 %.2f)。输入参考与目标口径不符 —— 检查是否被契约率信号覆盖。"
            % (len(noisy), len(ref), sr, len(noisy) / max(len(ref), 1)))
    ref, est2 = align(ref, est)
    noisy2 = noisy[: len(ref)]
    m["reference_mode"] = "fullref"

    # ---- 电平保真门禁（必须在算指标之前）----
    r_in = float(np.sqrt(np.mean(ref ** 2)))
    r_out = float(np.sqrt(np.mean(est2 ** 2)))
    m["level_ratio"] = round(r_out / (r_in + 1e-12), 4)
    if m["level_ratio"] < LEVEL_GATE:
        m["skipped"] = "level_collapse(rms_ratio=%.4f)" % m["level_ratio"]
        return m                                   # 该片段指标无意义，不计统计

    m["si_sdr_in"] = round(si_sdr(ref, noisy2), 4)
    m["si_sdr_out"] = round(si_sdr(ref, est2), 4)
    m["si_sdr_improve"] = round(m["si_sdr_out"] - m["si_sdr_in"], 4)
    m["snr_out"] = round(snr_db(ref, est2), 4)
    m["lsd_out"] = round(lsd(ref, est2), 4)
    # 频谱保真：降噪是否把 clean 本该有的高频砍掉（过度抑制探测）
    m["hf_ratio_in"] = round(hf_ratio(noisy2), 4)
    m["hf_ratio_clean"] = round(hf_ratio(ref), 4)
    m["hf_ratio_out"] = round(hf_ratio(est2), 4)
    # 分层键：合成集用【清单真值】，真实集用【输入 SI-SDR 事后分档】
    m["snr_bin"] = item.get("snr_bin") or snr_bin(m["si_sdr_in"])
    if sr == 16000:
        m["pesq_out"] = None if (p := pesq_wb(ref, est2, sr)) is None else round(p, 4)
        m["pesq_in"] = None if (p := pesq_wb(ref, noisy2, sr)) is None else round(p, 4)
        m["stoi_out"] = None if (s := stoi_score(ref, est2, sr)) is None else round(s, 4)
        m["stoi_in"] = None if (s := stoi_score(ref, noisy2, sr)) is None else round(s, 4)
    else:
        m["pesq_out"] = None
        m["pesq_in"] = None
        m["stoi_out"] = None
        m["stoi_in"] = None
    return m


# ------------------------------------------------------------------ 汇总
def resummary():
    """从 manifest 重算 CSV/JSON，不重推理。"""
    mf = DEN_DATA / "denoise_manifest.json"
    if not mf.is_file():
        raise SystemExit("[FATAL] 无 manifest：%s" % mf)
    man = json.loads(mf.read_text(encoding="utf-8"))
    write_tables(man)
    return 0


def _med(vals):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
    return round(float(np.median(vals)), 4) if vals else None


def _empty_row(model, label, subset, sr, reference_mode, extra=None):
    r = {"model": model, "label": label, "subset": subset, "sr": sr,
         "reference_mode": reference_mode}
    if extra:
        r.update(extra)
    return r


def _agg(rs):
    """对一组 cell 取中位数。fr = 有 GT **且未被门禁剔除**的子集。

    注意配对量：`si_sdr_improve` / `pesq_improve` 均为**逐条作差后取中位数**，
    不是两个中位数相减。二者在非同分布时不可互换（实测可反号）。
    """
    ok = [r for r in rs if r.get("ok")]
    fr = [r for r in ok if r.get("reference_mode") == "fullref" and not r.get("skipped")]
    sk = [r for r in ok if r.get("skipped")]
    return {
        "n_total": len(rs), "n_ok": len(ok), "n_fullref": len(fr),
        "n_skipped": len(sk),
        "skip_reason": (sorted({str(r.get("skipped")).split("(")[0] for r in sk})[0]
                        if sk else None),
        "si_sdr_in": _med([r.get("si_sdr_in") for r in fr]),
        "si_sdr_out": _med([r.get("si_sdr_out") for r in fr]),
        "si_sdr_improve": _med([r.get("si_sdr_improve") for r in fr]),
        "snr_out": _med([r.get("snr_out") for r in fr]),
        "lsd_out": _med([r.get("lsd_out") for r in fr]),
        "hf_ratio_in": _med([r.get("hf_ratio_in") for r in fr]),
        "hf_ratio_clean": _med([r.get("hf_ratio_clean") for r in fr]),
        "hf_ratio_out": _med([r.get("hf_ratio_out") for r in fr]),
        "pesq_in": _med([r.get("pesq_in") for r in fr]),
        "pesq_out": _med([r.get("pesq_out") for r in fr]),
        "pesq_improve": _med([r.get("pesq_out") - r.get("pesq_in") for r in fr
                              if r.get("pesq_in") is not None
                              and r.get("pesq_out") is not None]),
        "stoi_in": _med([r.get("stoi_in") for r in fr]),
        "stoi_out": _med([r.get("stoi_out") for r in fr]),
        "stoi_improve": _med([r.get("stoi_out") - r.get("stoi_in") for r in fr
                              if r.get("stoi_in") is not None
                              and r.get("stoi_out") is not None]),
    }


def _delta(a, b):
    """b - a，任一侧为 None 则 None。"""
    if a is None or b is None:
        return None
    return round(b - a, 4)


def write_tables(man):
    """按口径分表：16k（含 PESQ）与非 16k（不含 PESQ）。
    每张表同时输出：① 总体；② 按输入 SNR 分层。分层是必须的 ——
    实测证明模型的 SI-SDR 增益与 PESQ 增益在 SNR 区间上方向不一致。"""
    rows = man["cells"]
    by_sr = {}
    for r in rows:
        by_sr.setdefault(r["sr"], []).append(r)

    written = []
    for sr, rs in sorted(by_sr.items()):
        tag = "%dk" % (sr // 1000)
        groups = {}

        # ① 总体
        for r in rs:
            groups.setdefault((r["model"], r["subset"], "ALL"), []).append(r)
        # ② SNR 分层
        for r in rs:
            if r.get("reference_mode") == "fullref":
                groups.setdefault((r["model"], r["subset"], r.get("snr_bin", "unknown")),
                                  []).append(r)

        out_rows = []
        for (model, subset, b), g in groups.items():
            row = _empty_row(model, g[0].get("label", model), subset, sr,
                             g[0].get("reference_mode", "fullref"),
                             extra={"snr_bin": b})
            row.update(_agg(g))
            out_rows.append(row)
        out_rows.sort(key=lambda r: (r["subset"], r["model"],
                                     {"ALL": "", ">=15dB": "1", "5-15dB": "2",
                                      "<5dB": "3"}.get(r["snr_bin"], r["snr_bin"])))

        cols = list(out_rows[0].keys())
        csv_path = DEN_DATA / ("denoise_eval_%s.csv" % tag)
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(out_rows)

        # 分层差异摘要：直接给出「指标分歧」的证据
        verdict = []
        for model in sorted({r["model"] for r in out_rows}):
            sub = [r for r in out_rows if r["model"] == model
                   and r["snr_bin"] in (">=15dB", "5-15dB", "<5dB")]
            if len(sub) < 2:
                continue
            # 配对口径：逐条 (out-in) 后取中位数，**不是** med(out) - med(in)。
            # 实测二者在本数据上可以反号（>=15dB 档 +0.028 vs -0.063）。
            paired = {}
            for b in (">=15dB", "5-15dB", "<5dB"):
                g = [r for r in rows
                     if r["model"] == model and r["sr"] == sr
                     and r.get("snr_bin") == b and r.get("ok")
                     and r.get("reference_mode") == "fullref" and not r.get("skipped")]
                paired[b] = _med([r.get("pesq_out") - r.get("pesq_in") for r in g
                                  if r.get("pesq_in") is not None
                                  and r.get("pesq_out") is not None])
            verdict.append({
                "model": model,
                "si_sdr_improve_by_bin": {r["snr_bin"]: r["si_sdr_improve"] for r in sub},
                "pesq_gain_by_bin_PAIRED": {b: paired.get(b)
                                            for b in (">=15dB", "5-15dB", "<5dB")},
                "note": "PESQ 增益必须用逐条配对差的中位数；"
                        "用 med(out)-med(in) 会因非同分布而在高 SNR 档反号",
            })

        json_path = DEN_DATA / ("denoise_eval_%s.json" % tag)
        json_path.write_text(json.dumps({
            "task": "T5.1-T5.3 降噪评测（%s 口径）" % tag,
            "sr": sr, "pesq_applicable": sr == MAIN_SR,
            "metric_defs": {
                "si_sdr": "scale-invariant SDR, dB, 越大越好",
                "pesq": "PESQ-WB，仅 16 kHz 合法；非 16k 一律不报",
                "stoi": "STOI 短时客观可懂度，0~1",
                "lsd": "log-spectral distance, dB, 越小越好",
                "improve": "out - in（同一条 noisy 输入的前后对比）",
                "hf_ratio": "上半频带能量占比，用于探测低通式过度抑制",
            },
            "aggregation": "跨片段取中位数（median），与板 1 纪律一致",
            "paired_note": "所有 *_improve 列均为【逐条作差后取中位数】(med(out-in))，"
                           "不是 med(out)-med(in) —— 后者在非同分布时会反号（见 P14）",
            "snr_binning": "真实集（valentini/dns_dev）按【输入 SI-SDR】事后分档"
                           "（>15 / 5-15 / <5 dB），分层键不受模型影响，可跨模型对齐；"
                           "自造集（synth）用【真值 SNR】（-5/0/5/10 dB），"
                           "因此其 snr_bin 映射为 -5/0 -> <5dB、5/10 -> 5-15dB，"
                           "细分档请用 cell 里的 target_snr_db",
            "reference_mode_note": "dns_dev 无 clean GT -> fullref 列为 null，不得当 0 用",
            "metric_disagreement": verdict,
            "rows": out_rows,
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append((str(csv_path), str(json_path)))

    for a, b in written:
        print("[csv ] %s" % a)
        print("[json] %s" % b)
    return 0


# ------------------------------------------------------------------ 主流程
def cmd_plan(args):
    print("工具别名: %s" % json.dumps(TOOL_ALIAS, ensure_ascii=False))
    for dname, d in DATASETS.items():
        try:
            n = len(d["list_fn"]())
        except SystemExit as e:
            print("  %-10s UNAVAILABLE (%s)" % (dname, e))
            continue
        print("  %-10s clips=%-5d reference_mode=%s" % (dname, n, d["reference_mode"]))
    print("\n口径: 主 %d Hz（含 PESQ）/ 副 %d Hz（不含 PESQ）" % (MAIN_SR, NATIVE_SR))
    return 0


def cmd_run(args):
    keys = []
    for a in args.models.split(","):
        a = a.strip()
        keys.extend(TOOL_ALIAS.get(a.upper(), [a]))
    keys = [k for k in keys if k in REG.REGISTRY]
    if not keys:
        raise SystemExit("[FATAL] 无可跑模型：%s" % args.models)

    dname = args.dataset
    if dname not in DATASETS:
        raise SystemExit("[FATAL] 未知数据集 %s" % dname)
    d = DATASETS[dname]
    items = d["list_fn"](args.limit)
    allow_noref = args.allow_noref or d["reference_mode"] == "noref"
    srs = [int(s) for s in args.sr.split(",")]

    mf_path = DEN_DATA / "denoise_manifest.json"
    man = {"task": "T5.1 降噪评测 manifest", "cells": []}
    if mf_path.is_file():
        man = json.loads(mf_path.read_text(encoding="utf-8"))
    done = {(c["model"], c["clip_id"], c.get("sr")) for c in man["cells"]}

    print("=" * 72)
    print("模型 %s | 数据集 %s | 片段 %d | 口径 %s | resume=%s"
          % (keys, dname, len(items), srs, args.resume))
    print("=" * 72)

    for mk in keys:
        t0 = time.time()
        try:
            run_fn, load_s, info = REG.REGISTRY[mk]["loader"]()
            label = REG.REGISTRY[mk].get("label", mk)
        except Exception as e:
            print("[FAIL-LOAD] %-24s %s" % (mk, e))
            traceback.print_exc()
            continue
        print("\n-- %s (%s)  load=%.1fs  targets=%s native=%s Hz/%sch"
              % (mk, label, load_s, info.get("targets"), info.get("sample_rate"),
                 info.get("channels")))
        n_ok = n_err = 0
        for it in items:
            for sr in srs:
                if args.resume and (mk, it["clip_id"], sr) in done:
                    continue
                cell = {"model": mk, "label": label, "clip_id": it["clip_id"],
                        "subset": dname, "sr": sr, "ok": False}
                try:
                    met = eval_one(run_fn, info, it, sr, allow_noref)
                    cell.update(met)
                    cell["ok"] = True
                    n_ok += 1
                except Exception as e:
                    cell["error"] = "%s: %s" % (type(e).__name__, e)
                    n_err += 1
                man["cells"].append(cell)
                # 增量落盘（每 50 条）：长任务中途被杀时不丢全部进度
                if len(man["cells"]) % 50 == 0:
                    mf_path.write_text(
                        json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print("   ok=%d err=%d  wall=%.1fs" % (n_ok, n_err, time.time() - t0))
        mf_path.write_text(json.dumps(man, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    man["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    mf_path.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n[manifest] %s  cells=%d" % (mf_path, len(man["cells"])))
    write_tables(man)
    return 0


def main():
    ap = argparse.ArgumentParser(description="T5.1 降噪评测统一入口")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="列出将跑的数据集与格数")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("run", help="跑评测")
    p.add_argument("--models", default="A,B", help="A / B / 或 registry key，逗号分隔")
    p.add_argument("--dataset", default="valentini", choices=list(DATASETS))
    p.add_argument("--sr", default=str(MAIN_SR), help="采样率，逗号分隔")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--allow-noref", action="store_true")
    p.add_argument("--resume", action="store_true", help="跳过 manifest 已有格")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("resummary", help="只重算汇总，不重推理")
    p.set_defaults(func=lambda a: resummary())

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

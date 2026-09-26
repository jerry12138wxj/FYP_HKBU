"""T5.7 探针：降噪器的「域外失效」判定。

背景（本轮实测）：
  - 真实 Valentini：mel_roformer 有效（+4.2 dB），denoiser 表现为固定低通损伤。
  - 自造 synth（Valentini clean + DNS freesound 噪声）：mel_roformer ΔSI-SDR 仅 +0.01 dB，
    hf_ratio 输入 0.336 -> 输出 0.338（纹丝不动），level_ratio 中位 2.0（输出能量翻倍）。

  「模型没降噪」与「模型在放大后原样输出」要用不同证据区分，本探针做三件事：

  探针 A  纯 clean 直通    -> 输出/输入 rms 比、hf_ratio 位移。判定模型是否 near-identity。
  探针 B  纯 noise 直通    -> 若模型真在做降噪，纯噪声输入应被强抑制（rms 大幅下降）。
                             若输出≈输入，说明它把这个噪声当成"非噪声"。
  探针 C  g 扫描           -> 固定 clean+noise，扫噪声增益 g，看 ΔSI-SDR 是否恒定。
                             「与输入状态无关」的失效 vs「随噪声强度恢复」的失效。

🔴 输入契约（曾因此脚本报 cannot reshape tensor of 0 elements，已修）
  run_fn 恒收 (N, 2) @ 44.1 kHz（见 `_denoise_registry` 模块 docstring）。
  ✓ 探针输入必须落回【契约采样率 44.1 kHz】再叠双声道，
    **不能**先在 16 kHz 合成再喂 —— 那等于让 denoiser 的 wrapper 把 16 kHz
    当 44.1 kHz 重采样到 16 kHz，输入被二次畸变，量出来的 ratio 全无意义。
  ✓ mel_roformer 传 (N,1) 会 assert 失败；denoiser 传 (N,1) 能跑但不能作契约。

产物： denoiser/data/denoise_ood_probe.json
       denoiser/figures/fig_denoise_ood_probe.png

复现：
  cd tools
  PYTHONPATH=. <venv>/python.exe -X utf8 _denoise_ood_probe.py
"""
from __future__ import annotations

import json
import sys

import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

import _denoise_registry as REG  # noqa: E402

ROOT = _paths.PROJECT_ROOT
OUT_JSON = ROOT / "04_reports" / "denoiser" / "data" / "denoise_ood_probe.json"
FIGS = ROOT / "04_reports" / "denoiser" / "figures"
CONTRACT_SR = 44100      # registry 对外契约采样率；run_fn 只接受这个率
ANALYSIS_SR = 16000      # 分析带宽：判 hf/rms 在统一带宽下才可比
N_SAMPLES = 6

MODELS = [
    ("mel_roformer_denoise", 44100),
    ("denoiser_dns48", 16000),
    ("denoiser_master64", 16000),
]


def hf_ratio(x):
    X = np.abs(np.fft.rfft(x))
    return float(X[len(X) // 4:].sum() / (X.sum() + 1e-12))


def rms(x):
    return float(np.sqrt(np.mean(x ** 2)))


def resample(x, sr_in, sr_out):
    if sr_in == sr_out:
        return np.asarray(x, dtype=np.float32)
    import torch
    import torchaudio.functional as AF
    t = torch.from_numpy(np.asarray(x, dtype=np.float32))[None]
    return AF.resample(t, sr_in, sr_out)[0].numpy()


def run_contract(run_fn, x_mono, sr_in):
    """按 registry 契约调用：先到 44.1k，再叠双声道；返回分析带宽下的 mono。"""
    x44 = resample(x_mono, sr_in, CONTRACT_SR)
    out = run_fn(np.ascontiguousarray(np.stack([x44, x44], axis=-1)))
    est = np.asarray(out["enhanced"], dtype=np.float32).mean(axis=1)
    return resample(est, CONTRACT_SR, ANALYSIS_SR)


def main() -> int:
    man = json.loads((ROOT / "04_reports" / "denoiser" / "data"
                      / "synth_pairs_manifest.json").read_text(encoding="utf-8"))
    rows = man["rows"]
    # 取 n_speech 条不同语音：每个 clean 只取第一个（-5 dB 档）
    seen, picks = set(), []
    for r in rows:
        if r["clean"] in seen:
            continue
        seen.add(r["clean"])
        picks.append(r)
        if len(picks) >= N_SAMPLES:
            break

    # 预载素材（统一到分析带宽 16 kHz；训练源若是 44.1k 会被正确降采样）
    items = []
    for r in picks:
        c, s1 = sf.read(str(ROOT / r["clean"]), dtype="float32", always_2d=True)
        n, s2 = sf.read(str(ROOT / r["noise"]), dtype="float32", always_2d=True)
        c, n = resample(c.mean(axis=1), s1, ANALYSIS_SR), resample(n.mean(axis=1), s2, ANALYSIS_SR)
        L = min(len(c), len(n))
        items.append({"id": r["id"], "clean": c[:L], "noise": n[:L], "snr_db": r["snr_db"]})
    print("[data] %d items, L=%d samples each @ %d Hz"
          % (len(items), len(items[0]["clean"]), ANALYSIS_SR))

    out = {"task": "T5.7 降噪器域外失效探针", "analysis_sr": ANALYSIS_SR,
           "contract_sr": CONTRACT_SR, "n_items": len(items), "probes": {}}

    for name, native in MODELS:
        print("\n=== %s (native %d Hz) ===" % (name, native))
        try:
            run_fn, load_s, info = REG.REGISTRY[name]["loader"]()
        except Exception as e:  # noqa: BLE001
            print("  [skip] load failed: %s" % e)
            continue

        rec = {"native_sr": native, "A_clean_passthrough": [], "B_noise_passthrough": [],
               "C_gain_sweep": []}

        for it in items:
            c, n = it["clean"], it["noise"]
            pc, pn = float((c ** 2).mean()), float((n ** 2).mean())

            # ---- A. 纯 clean 直通 ----
            try:
                y = run_contract(run_fn, c, ANALYSIS_SR)
                L = min(len(y), len(c))
                y, c2 = y[:L], c[:L]
                rec["A_clean_passthrough"].append({
                    "id": it["id"], "ratio": rms(y) / (rms(c2) + 1e-12),
                    "hf_in": hf_ratio(c2), "hf_out": hf_ratio(y)})
            except Exception as e:  # noqa: BLE001
                print("  A err %s: %s" % (it["id"], e))

            # ---- B. 纯 noise 直通 ----
            try:
                y = run_contract(run_fn, n, ANALYSIS_SR)
                L = min(len(y), len(n))
                y, n2 = y[:L], n[:L]
                rec["B_noise_passthrough"].append({
                    "id": it["id"], "ratio": rms(y) / (rms(n2) + 1e-12),
                    "suppression_db": 20 * np.log10((rms(y) + 1e-12) / (rms(n2) + 1e-12))})
            except Exception as e:  # noqa: BLE001
                print("  B err %s: %s" % (it["id"], e))

            # ---- C. 增益扫描（固定 clean+noise，改变 g） ----
            for extra_db in [-10.0, 0.0, +10.0, +20.0]:
                g = np.sqrt(pc / (pn * 10 ** ((it["snr_db"] + extra_db) / 10.0) + 1e-12))
                mix = c + g * n
                try:
                    y = run_contract(run_fn, mix.astype(np.float32), ANALYSIS_SR)
                    L = min(len(y), len(mix))
                    y, m2 = y[:L], mix[:L]
                    # SI-SDR（相对混音输入，即「模型对混音做了什么」）
                    m2c = m2 - m2.mean()
                    yc = y - y.mean()
                    a = float((m2c * m2c).sum()) + 1e-12
                    alpha = float((yc * m2c).sum()) / a
                    tgt = alpha * m2c
                    si = 10 * np.log10((tgt ** 2).sum() / (((yc - tgt) ** 2).sum() + 1e-12) + 1e-12)
                    # 真实可达 SI-SDR 上界（相对 clean 真值），用于判「是否真的降了噪」
                    L2 = min(len(y), len(c))
                    si_gt_in = 10 * np.log10(
                        ((c[:L2] ** 2).sum() + 1e-12) / (((m2[:L2] - c[:L2]) ** 2).sum() + 1e-12))
                    si_gt_out = 10 * np.log10(
                        ((c[:L2] ** 2).sum() + 1e-12) / (((y[:L2] - c[:L2]) ** 2).sum() + 1e-12))
                    rec["C_gain_sweep"].append({
                        "id": it["id"], "extra_db": extra_db,
                        "snr_db_eff": it["snr_db"] + extra_db,
                        "si_sdr_vs_mix": round(float(si), 3),
                        "d_si_sdr_vs_gt": round(float(si_gt_out - si_gt_in), 3),
                        "level_ratio": round(rms(y) / (rms(m2) + 1e-12), 4),
                        "hf_in": round(hf_ratio(m2), 4),
                        "hf_out": round(hf_ratio(y), 4)})
                except Exception as e:  # noqa: BLE001
                    print("  C err %s: %s" % (it["id"], e))

        def med(key, sub):
            vals = [r.get(key) for r in rec[sub]]
            vals = [v for v in vals if v is not None]
            return round(float(np.median(vals)), 4) if vals else None

        rec["summary"] = {
            "A_clean_ratio_med": med("ratio", "A_clean_passthrough"),
            "A_hf_in_med": med("hf_in", "A_clean_passthrough"),
            "A_hf_out_med": med("hf_out", "A_clean_passthrough"),
            "B_noise_ratio_med": med("ratio", "B_noise_passthrough"),
            "B_suppression_db_med": med("suppression_db", "B_noise_passthrough"),
            "C_si_sdr_vs_mix_med": med("si_sdr_vs_mix", "C_gain_sweep"),
            "C_d_si_sdr_vs_gt_med": med("d_si_sdr_vs_gt", "C_gain_sweep"),
            "C_level_ratio_med": med("level_ratio", "C_gain_sweep"),
        }
        s = rec["summary"]
        print("  A clean ratio %s (hf %s -> %s)" % (
            s["A_clean_ratio_med"], s["A_hf_in_med"], s["A_hf_out_med"]))
        print("  B noise ratio %s (suppression %s dB)" % (
            s["B_noise_ratio_med"], s["B_suppression_db_med"]))
        print("  C level_ratio %s | dSI-SDR vs GT %s dB | vs mix %s dB" % (
            s["C_level_ratio_med"], s["C_d_si_sdr_vs_gt_med"], s["C_si_sdr_vs_mix_med"]))
        out["probes"][name] = rec

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n[json] %s" % OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

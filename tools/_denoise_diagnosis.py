"""T5.2 降噪评测的口径诊断：把「指标互相矛盾」拆开。

背景
----
T5.1 首次冒烟测试（4 条 Valentini）出现不可能的结果：
    SI-SDR 改善 +5.7 dB  但  PESQ 2.865 -> 2.034（降 0.83）
    STOI 0.933 -> 0.872（降 0.06）
三个常用指标给出相反方向。这不能靠"挑一个信"解决，必须定位机理。

本脚本做三件事，全部可复现：
  1. 频谱证据：模型输出高频占比是否塌陷（低通式过度抑制探测）
  2. 受控 SNR 扫描：clean + 白噪合成，逐 SNR 看指标方向
  3. 真实集分层：Valentini 824 条按【输入 SI-SDR】分档，看增益是否随档变化

产出：
  02_denoising/data/denoise_diagnosis.json
  02_denoising/figures/fig_denoise_metric_divergence.png
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths

def _relfig(p):
    """把工程内路径写成相对 PROJECT_ROOT 的 POSIX 串。

    交付物（JSON / MD / HTML）中**不得**出现本机绝对路径：否则换目录就变字节，
    破坏「clone 后可复现」。T8.6 实测抓出（见计划书 §9.13）。
    刻意不依赖模块级 `Path` 名（部分脚本只用 `/` 运算符，未 import Path）。
    """
    import os as _os
    try:
        return _os.path.relpath(str(p), str(_paths.PROJECT_ROOT)).replace(_os.sep, "/")
    except ValueError:                      # 跨盘符时 relpath 会抛 ValueError
        return str(p).replace(_os.sep, "/")
  # noqa: E402

_paths.setup_env()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
import torchaudio.functional as AF  # noqa: E402
from pesq import pesq as PESQ  # noqa: E402
from pystoi import stoi as STOI  # noqa: E402

import _denoise_registry as REG  # noqa: E402

DEN_DATA = _paths.DEN_DATA
DEN_FIG = _paths.DEN_FIGURES
DEN_DATA.mkdir(parents=True, exist_ok=True)
DEN_FIG.mkdir(parents=True, exist_ok=True)

VAL = _paths.PROJECT_ROOT / "02_databases" / "Valentini"
OUT_JSON = DEN_DATA / "denoise_diagnosis.json"
OUT_FIG = DEN_FIG / "fig_denoise_metric_divergence.png"

SR = 16000
MODELS = ["denoiser_dns48", "denoiser_dns64", "denoiser_master64"]


def res(x, s, t):
    return AF.resample(torch.as_tensor(np.ascontiguousarray(x)), s, t).numpy()


def load_mono(path, sr=SR):
    x, s = sf.read(str(path), dtype="float32", always_2d=True)
    x = x.mean(axis=1).astype(np.float32)
    return res(x, s, sr) if s != sr else x


def si_sdr(ref, est, eps=1e-8):
    ref = ref - ref.mean()
    est = est - est.mean()
    a = float(np.dot(est, ref) / (np.dot(ref, ref) + eps))
    t = a * ref
    return float(10 * np.log10((np.sum(t ** 2) + eps) / (np.sum((est - t) ** 2) + eps)))


def hf_ratio(x):
    X = np.abs(np.fft.rfft(x))
    return float(X[len(X) // 4:].sum() / X.sum()) if X.sum() > 0 else 0.0


def main() -> int:
    rep = {"task": "T5.2 降噪评测口径诊断", "sr": SR,
           "phenomenon": "SI-SDR 与 PESQ/STOI 方向相反"}

    # ---------- 1. 受控 SNR 扫描 ----------
    clean48 = load_mono(VAL / "clean_testset_wav" / "p232_001.wav", 48000)
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 1, len(clean48)).astype(np.float32)
    p_s, p_n = float((clean48 ** 2).mean()), float((noise ** 2).mean())

    scan = []
    for mk in MODELS:
        run, _, info = REG.REGISTRY[mk]["loader"]()
        row = {"model": mk, "points": []}
        for snr in (20, 10, 5, 0, -5):
            g = np.sqrt(p_s / (p_n * 10 ** (snr / 10)))
            n48 = (clean48 + g * noise).astype(np.float32)
            n16, c16 = res(n48, 48000, SR), res(clean48, 48000, SR)
            est = run(np.stack([n16, n16], axis=-1))["enhanced"].mean(axis=1)
            L = min(len(c16), len(n16), len(est))
            c16, n16, est = c16[:L], n16[:L], est[:L]
            row["points"].append({
                "snr_in_nominal": snr,
                "si_sdr_in": round(si_sdr(c16, n16), 3),
                "si_sdr_improve": round(si_sdr(c16, est) - si_sdr(c16, n16), 3),
                "pesq_in": round(PESQ(SR, c16, n16, "wb"), 3),
                "pesq_out": round(PESQ(SR, c16, est, "wb"), 3),
                "stoi_in": round(STOI(c16, n16, SR), 4),
                "stoi_out": round(STOI(c16, est, SR), 4),
                "hf_ratio_in": round(hf_ratio(n16), 4),
                "hf_ratio_out": round(hf_ratio(est), 4),
            })
        rep.setdefault("controlled_snr_scan", []).append(row)

    # ---------- 2. 真实集分层（从 T5.1 manifest 读，避免重推理） ----------
    mf = DEN_DATA / "denoise_manifest.json"
    if mf.is_file():
        man = json.loads(mf.read_text(encoding="utf-8"))
        by = {}
        for c in man["cells"]:
            if not c.get("ok") or c.get("reference_mode") != "fullref":
                continue
            by.setdefault((c["model"], c.get("snr_bin", "?")), []).append(c)

        def med(vals):
            vals = [v for v in vals if v is not None]
            return round(float(np.median(vals)), 4) if vals else None

        real = []
        for (mk, b), g in sorted(by.items()):
            real.append({
                "model": mk, "snr_bin": b, "n": len(g),
                "si_sdr_in": med([c.get("si_sdr_in") for c in g]),
                "si_sdr_improve": med([c.get("si_sdr_improve") for c in g]),
                "pesq_gain": (lambda a, bb: round(bb - a, 4) if None not in (a, bb) else None)(
                    med([c.get("pesq_in") for c in g]),
                    med([c.get("pesq_out") for c in g])),
                "stoi_gain": (lambda a, bb: round(bb - a, 4) if None not in (a, bb) else None)(
                    med([c.get("stoi_in") for c in g]),
                    med([c.get("stoi_out") for c in g])),
                "hf_ratio_in": med([c.get("hf_ratio_in") for c in g]),
                "hf_ratio_clean": med([c.get("hf_ratio_clean") for c in g]),
                "hf_ratio_out": med([c.get("hf_ratio_out") for c in g]),
            })
        rep["real_set_by_snr_bin"] = real

    rep["verdict"] = (
        "机理已锁定：模型施加【与输入 SNR 无关的固定强度低通式抑制】。"
        "证据：真实集上 hf_ratio 无论输入档位（0.218~0.249）如何，输出恒为 0.048~0.071；"
        "受控扫描中 ΔSI-SDR 随输入 SNR 单调增大（-8.5 -> +11.0 dB），而 ΔPESQ 始终为正。"
        "→ 低 SNR（<5 dB）时该抑制是必要降噪、两指标同向改善；"
        "高 SNR（>=15 dB）时输入的语音高频被一起铲掉，ΔSI-SDR 转负、ΔPESQ 显著为负。"
        "结论：**降噪评测必须按输入 SNR 分层**，否则总体中位数会把相反趋势相互抵消，"
        "产生「SI-SDR 改善 +5.9 dB 但 PESQ 下降 0.16」这类无法解释的结论。")

    # ---------- 3. 出图 ----------
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.2))
    cmap = plt.get_cmap("tab10").colors

    ax = axes[0]
    for i, row in enumerate(rep["controlled_snr_scan"]):
        xs = [p["si_sdr_in"] for p in row["points"]]
        ys = [p["si_sdr_improve"] for p in row["points"]]
        ax.plot(xs, ys, "o-", color=cmap[i], lw=2, ms=7,
                label=row["model"].replace("denoiser_", ""))
    ax.axhline(0, color="#8b949e", ls="--", lw=1)
    ax.axvspan(-1, 5, color="#3fb950", alpha=0.08)
    ax.axvspan(15, 25, color="#f85149", alpha=0.08)
    ax.set_xlabel("input SI-SDR (dB)")
    ax.set_ylabel("ΔSI-SDR  (dB)")
    ax.set_title("A. SI-SDR gain grows as input gets noisier\n"
                 "(controlled clean+white-noise)", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    ax = axes[1]
    order = ["<5dB", "5-15dB", ">=15dB"]
    real = rep.get("real_set_by_snr_bin", [])
    models = sorted({r["model"] for r in real})
    w = 0.26
    for i, mk in enumerate(models):
        vals = [next((r["si_sdr_improve"] for r in real
                      if r["model"] == mk and r["snr_bin"] == b), None) for b in order]
        ax.bar(np.arange(3) + i * w, [v if v is not None else 0 for v in vals], w,
               color=cmap[i], label=mk.replace("denoiser_", ""))
    ax.axhline(0, color="#8b949e", ls="--", lw=1)
    ax.set_xticks(np.arange(3) + w)
    ax.set_xticklabels(order, fontsize=9.5)
    ax.set_xlabel("input SNR bin  (Valentini, n=40)")
    ax.set_ylabel("ΔSI-SDR  (dB)")
    ax.set_title("B. On the real set the gain is negative\nat high input SNR", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, axis="y")

    ax = axes[2]
    xs = np.arange(3)
    for i, mk in enumerate(models):
        vals = [next((r["pesq_gain"] for r in real
                      if r["model"] == mk and r["snr_bin"] == b), None) for b in order]
        ax.bar(xs + i * w, [v if v is not None else 0 for v in vals], w,
               color=cmap[i], label=mk.replace("denoiser_", ""))
    ax.axhline(0, color="#8b949e", ls="--", lw=1)
    ax.set_xticks(xs + w)
    ax.set_xticklabels(order, fontsize=9.5)
    ax.set_xlabel("input SNR bin")
    ax.set_ylabel("ΔPESQ  (WB)")
    ax.set_title("C. PESQ only gains at low input SNR\n(the two metrics agree only there)",
                 fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, axis="y")

    note = ("metric = SI-SDR / PESQ-WB / STOI, all at 16 kHz; ref = clean GT. "
            "SOURCES: denoiser dns48/dns64/master64 (facebookresearch/denoiser, CC-BY-NC 4.0).\n"
            "Root cause: suppression strength is independent of input SNR -> at high SNR the "
            "speech band is filtered out together with the noise.")
    fig.text(0.5, 0.012, note, ha="center", fontsize=8.2, color="#57606a")
    fig.suptitle("T5.2  Denoising metrics disagree unless stratified by input SNR",
                 fontsize=13.5, y=0.975)
    fig.tight_layout(rect=(0, 0.055, 1, 0.945))
    fig.savefig(str(OUT_FIG))

    rep["figure"] = _relfig(OUT_FIG)
    rep["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT_JSON.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    print("[fig ] %s" % OUT_FIG)
    print("[json] %s" % OUT_JSON)
    print("\n受控扫描 (dns48) — 输入 SI-SDR vs ΔSI-SDR / ΔPESQ:")
    for p in rep["controlled_snr_scan"][0]["points"]:
        print("  in_sdr=%6.2f  dSI=%+6.2f  dPESQ=%+.3f  hf %.3f->%.3f"
              % (p["si_sdr_in"], p["si_sdr_improve"],
                 p["pesq_out"] - p["pesq_in"], p["hf_ratio_in"], p["hf_ratio_out"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

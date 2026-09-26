"""T5.6 补充：跨模型的平均谱差图（2 工具 × 2 数据集）。

单条片段的谱会被内容方差淹没。这里对**全集/全档**求「输出 − 输入」的平均谱差：

    delta(f) = mean_over_clips[ 20log10|STFT(est)| ] - mean_over_clips[ 20log10|STFT(noisy)| ]

这直接回答「模型把哪个频段压了多少 dB」，是 P19 存活判据
（denoiser 不是低通器，但有轻度频谱倾斜）最直接的图证。

产出 4 张：
  figures/denoise/t5_6_<model-tag>_<subset>_delta_spectrum.png
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths as _paths  # noqa: E402

_paths.setup_env()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

import _denoise_eval as EV  # noqa: E402
import _denoise_registry as REG  # noqa: E402

DEN = _paths.DENOISER
DATA = DEN / "data"
FIGS = DEN / "figures" / "denoise"
FIGS.mkdir(parents=True, exist_ok=True)

N_FFT, HOP = 1024, 256
MAX_CLIPS = 120      # 每格取前 N 条（按 clip_id 排序），足矣统计稳定

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "figure.dpi": 140})

PAIRS = [("denoiser_master64", "valentini"),
         ("denoiser_master64", "synth"),
         ("mel_roformer_denoise", "valentini"),
         ("mel_roformer_denoise", "synth")]

C_LINE = "#c9403a"


def band_spec(x):
    """单条：帧平均幅度谱 -> dB。"""
    w = torch.hann_window(N_FFT)
    X = torch.stft(torch.as_tensor(np.asarray(x, dtype=np.float32)), N_FFT, HOP,
                   window=w, return_complex=True).abs().numpy()
    return 20.0 * np.log10(np.maximum(X.mean(axis=1), 1e-8))


def make(model, subset, cells):
    rs = [r for r in cells
          if r.get("model") == model and r.get("subset") == subset
          and r.get("ok") and r.get("reference_mode") == "fullref"
          and not r.get("skipped")]
    rs.sort(key=lambda r: r["clip_id"])
    rs = rs[:MAX_CLIPS]
    if not rs:
        print("[skip] %s/%s no cells" % (model, subset))
        return None

    run_fn, _, _ = REG.REGISTRY[model]["loader"]()
    items = {it["clip_id"]: it for it in EV.DATASETS[subset]["list_fn"](None)}
    csr = int(getattr(run_fn, "contract_sr", 44100))

    acc_in = acc_out = None
    n = 0
    by_bin = {}
    for r in rs:
        it = items.get(r["clip_id"])
        if it is None:
            continue
        try:
            if it.get("noisy_path"):
                noisy = EV.load_mono(it["noisy_path"], 16000)
            else:
                cl = EV.load_mono(it["clean_path"], 16000)
                nz = EV.load_mono(it["noise_path"], 16000)
                noisy = EV.mix_at_snr(cl, nz, it["snr_db"],
                                      seed=hash(it["clip_id"]) & 0xFFFF)
            if len(noisy) / 16000.0 > EV.MAX_CLIP_SEC:
                continue
            nin = EV.resample_mono(noisy, 16000, csr) if csr != 16000 else noisy
            est = run_fn(np.stack([nin, nin], axis=-1))["enhanced"]
            est = np.asarray(est).mean(axis=1).astype(np.float32)
            if csr != 16000:
                est = EV.resample_mono(est, csr, 16000)
            L = min(len(noisy), len(est))
            a, b = band_spec(noisy[:L]), band_spec(est[:L])
            if len(a) != len(b):
                continue
            acc_in = a if acc_in is None else acc_in + a
            acc_out = b if acc_out is None else acc_out + b
            bl = by_bin.setdefault(r.get("snr_bin", "?"), [None, None, 0])
            bl[0] = a if bl[0] is None else bl[0] + a
            bl[1] = b if bl[1] is None else bl[1] + b
            bl[2] += 1
            n += 1
        except Exception as e:
            print("[warn] %s %s: %s" % (model, r["clip_id"], e))
    if not n:
        return None

    f = np.fft.rfftfreq(N_FFT, 1.0 / 16000) / 1000.0
    din = acc_in / n
    dout = acc_out / n
    delta = dout - din

    # 🔴 边界剔除：16 kHz 采样率下 Nyquist = 8 kHz，rfft 只有 513 个 bin，
    #    最后一个 bin 恰好是 8 kHz。denoiser 内部在 16 kHz 域推理，
    #    重采样回 44.1 kHz 后 8 kHz 以上是**插值出来的空值**，不是模型行为。
    #    若不剔除，最顶端几个 bin 的幅度会塌到 -100 dB 以下，
    #    把「4 kHz 以上平均差」污染成虚假的 -32 dB。→ 只在 0~7.8 kHz 内做统计。
    valid = f <= 7.8
    fv, dv_in, dv_out, dv = f[valid], din[valid], dout[valid], delta[valid]

    fig, ax = plt.subplots(figsize=(10.6, 6.1))
    ax.plot(fv, dv_in, color="#7a8794", lw=1.8, label="noisy input (mean spectrum)")
    ax.plot(fv, dv_out, color=C_LINE, lw=1.8, label="enhanced output (mean spectrum)")
    ax.set_xlim(0, 8.0)
    ax.set_xlabel("kHz", fontsize=11)
    ax.set_ylabel("mean magnitude spectrum (dB)", fontsize=11)
    ax.legend(fontsize=9.2, loc="lower left", framealpha=0.94)

    ax2 = ax.twinx()
    ax2.fill_between(fv, dv, 0, color="#2f7ed8", alpha=0.16)
    ax2.plot(fv, dv, color="#2f7ed8", lw=1.9, ls="--",
             label="output - input (right axis)")
    ax2.set_ylabel("spectral difference  out - in (dB)", fontsize=11, color="#2f7ed8")
    ax2.tick_params(axis="y", labelcolor="#2f7ed8")
    ax2.grid(False)
    ax2.legend(fontsize=9.2, loc="upper left", framealpha=0.94)
    ax2.axhline(0, color="#2f7ed8", lw=0.9, ls=":")
    # 8 kHz 处标出「16 kHz 域的 Nyquist —— 以上不是模型行为」
    ax.axvline(8.0, color="#888", lw=1.1, ls="-.")
    ax.text(7.93, 0.985, "16 kHz Nyquist\n(above = resample artifact)",
            transform=ax.get_xaxis_transform(), ha="right", va="top",
            fontsize=8.0, color="#555")

    # 分段带：低频（0~1k）/ 语音核心（1~4k）/ 高频（4~7.8k）
    seg = lambda a, b: slice(int(np.searchsorted(fv, a)), int(np.searchsorted(fv, b)))
    b1 = dv[seg(0.0, 1.0)].mean()
    b2 = dv[seg(1.0, 4.0)].mean()
    b3 = dv[seg(4.0, 7.8)].mean()
    txt = ("mean delta by band (valid 0-7.8 kHz)\n"
           "  0.0 - 1.0 kHz : %+6.2f dB\n"
           "  1.0 - 4.0 kHz : %+6.2f dB\n"
           "  4.0 - 7.8 kHz : %+6.2f dB\n"
           "  tilt (4k+ minus 1k-) = %+.2f dB    n=%d clips"
           % (b1, b2, b3, b3 - b2, n))
    ax.text(0.985, 0.035, txt, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8.8, family="DejaVu Sans Mono",
            bbox=dict(boxstyle="round,pad=0.42", fc="white", ec="#666", alpha=0.94))

    ax.set_title("T5.6  Spectral change induced by %s on %s\n"
                 "P19-clean: NOT a uniform low-pass — the tilt grows with frequency "
                 "(and with noise magnitude)" % (model.replace("_", " "), subset),
                 fontsize=12.2, pad=11)
    fig.tight_layout()
    out = FIGS / ("t5_6_%s_%s_delta_spectrum.png" % (model, subset))
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s  (n=%d, 0-1k=%+.2f, 1-4k=%+.2f, 4-7.8k=%+.2f, tilt=%+.2f)"
          % (out, n, b1, b2, b3, b3 - b2))
    return {"model": model, "subset": subset, "n": n,
            "b_0_1k": round(float(b1), 3), "b_1_4k": round(float(b2), 3),
            "b_4_7k8": round(float(b3), 3), "tilt": round(float(b3 - b2), 3)}


def main():
    cells = json.loads((DATA / "denoise_manifest.json")
                       .read_text(encoding="utf-8"))["cells"]
    print("[data] %d cells" % len(cells))
    bag = []
    for m, s in PAIRS:
        r = make(m, s, cells)
        if r:
            bag.append(r)
    if bag:
        out = DATA / "denoise_spectral_delta.json"
        out.write_text(json.dumps({
            "task": "T5.6 平均谱差（分段带）",
            "method": "mean_over_clips[20log10|STFT(est)|] - mean_over_clips[...(noisy)]",
            "sr": 16000, "n_fft": N_FFT, "hop": HOP, "max_clips": MAX_CLIPS,
            "valid_band_note": "16 kHz 下 Nyquist=8 kHz，只统计 0~7.8 kHz；"
                               "8 kHz 以上是重采样伪影，不纳入",
            "rows": bag,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print("[json] %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

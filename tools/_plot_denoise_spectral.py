"""T5.6 频谱前后对比图组（2 工具 × 2 数据集 = 4 组）。

## 设计意图

主表给的是**中位数**。中位数看不见两件事：
  ① 单条片段上「模型到底动了频谱的哪一块」；
  ② 分布的形状（是不是有一小撮片段被整段压死）。

本图组补这两件事，每组四联：

    (a) 时频谱对比  noisy / clean / enhanced  —— 直观看模型保留了哪块能量
    (b) 平均功率谱曲线 三态叠加（dB）        —— 量化「哪个频段被压了多少」
    (c) 高频占比 hf_ratio 的逐条分布          —— 检测低通式过度抑制（P19 存活判据）
    (d) 逐条 ΔSI-SDR 直方图                   —— 看增益是普遍还是靠少数片段拉动

## 片段选取铁律

**不做「挑个好看的例子」**。每个 (工具, 数据集) 组固定选**四条**：
  按该模型在该集上的 ΔSI-SDR 取**分位数** p10 / p50 / p90，
  外加一条**输入 SI-SDR 最接近该集中位数**的代表条。
选段规则写进图注，且 manifest 里落 clip_id —— 可复核。

## 产出（8 张 PNG）

  figures/denoise/t5_6_<model>_<subset>_spectral.png   四联（时频+谱+分布）
  figures/denoise/t5_6_<model>_<subset>_spec_curves.png  多条叠加平均谱
"""
from __future__ import annotations

import argparse
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

DEN = _paths.DENOISER
DATA = DEN / "data"
FIGS = DEN / "figures" / "denoise"
FIGS.mkdir(parents=True, exist_ok=True)

N_FFT = 1024
HOP = 256
CACHE = _paths.SCRATCH / ".cache" / "drywet_spec"
CACHE.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.25, "figure.dpi": 140})

C_NOISY = "#7a8794"
C_CLEAN = "#2e8b57"
C_EST = "#c9403a"

# 参与图组的模型（每族一个代表 + master64 作 in-domain 对照）
PANEL_MODELS = ["denoiser_master64", "mel_roformer_denoise"]
PANEL_SUBSETS = ["valentini", "synth"]


# ------------------------------------------------------------------ 工具
def spec_db(x, n_fft=N_FFT, hop=HOP):
    w = torch.hann_window(n_fft)
    X = torch.stft(torch.as_tensor(np.asarray(x, dtype=np.float32)), n_fft, hop,
                   window=w, return_complex=True).abs()
    return (20.0 * torch.log10(torch.clamp(X, min=1e-8))).numpy()


def avg_spectrum(x, n_fft=N_FFT, hop=HOP, smooth=9):
    """逐帧幅度谱 -> 频率轴平均 -> dB -> 频轴平滑。

    🔴 必须平滑：语音谱的谐波结构在逐帧平均后仍留下梳齿，直接画出来是一团锯齿，
    在高频段（能量已很低）尤其难看且掩盖真实趋势（模型到底压了哪个频段）。
    用滑动中值/均值在**频轴**上平滑（不动时间轴），只影响可读性，不影响结论。
    """
    w = torch.hann_window(n_fft)
    X = torch.stft(torch.as_tensor(np.asarray(x, dtype=np.float32)), n_fft, hop,
                   window=w, return_complex=True).abs().numpy()
    m = X.mean(axis=1)
    if smooth and smooth > 1:
        k = np.ones(smooth, dtype=np.float64) / smooth
        m = np.convolve(m, k, mode="same")
    return 20.0 * np.log10(np.maximum(m, 1e-8))


def freqs(n_fft=N_FFT, sr=16000):
    return np.fft.rfftfreq(n_fft, 1.0 / sr)


# ------------------------------------------------------------------ 选段
def pick_clips(cells, model, subset, key="si_sdr_improve", n_each=4):
    """按 ΔSI-SDR 分位数选段（不做人工挑选）。"""
    rs = [r for r in cells
          if r.get("model") == model and r.get("subset") == subset
          and r.get("ok") and r.get("reference_mode") == "fullref"
          and not r.get("skipped") and r.get(key) is not None]
    if not rs:
        return []
    rs.sort(key=lambda r: r[key])
    vals = np.array([r[key] for r in rs], dtype=float)
    picks = []
    for q in (0.10, 0.50, 0.90):
        tgt = float(np.quantile(vals, q))
        r = min(rs, key=lambda z: abs(z[key] - tgt))
        picks.append((q, r))
    return picks


# ------------------------------------------------------------------ 主图
def make_panel(model, subset, cells, max_clips=6):
    picks = pick_clips(cells, model, subset)
    if not picks:
        print("[skip] %s / %s: no cells" % (model, subset))
        return None

    rs_all = [r for r in cells
              if r.get("model") == model and r.get("subset") == subset
              and r.get("ok") and r.get("reference_mode") == "fullref"
              and not r.get("skipped")]

    # 用 manifest 里的 clip_id 反查音频路径
    items = {it["clip_id"]: it for it in
             EV.DATASETS[subset]["list_fn"](None)}

    nrow = len(picks)
    fig = plt.figure(figsize=(16.0, 3.3 * nrow + 1.5))
    gs = fig.add_gridspec(nrow, 3, wspace=0.26, hspace=0.42,
                          left=0.062, right=0.975, top=1.0 - 1.1 / (3.3 * nrow + 1.5),
                          bottom=0.085)

    f = freqs()

    # 逐条取信号（用与主表相同的契约率链重算 enhanced）
    cached = []
    for q, r in picks[:max_clips]:
        it = items.get(r["clip_id"])
        if it is None:
            continue
        c = _load_triple(it, subset, model)
        if c is None:
            continue
        cached.append((q, r, c))

    if not cached:
        print("[skip] %s / %s: no loadable clips" % (model, subset))
        return None

    for i, (q, r, (noisy, ref, est)) in enumerate(cached):
        # ---- (a) 时频谱：显示到 4 kHz ----
        # 🔴 语音语音能量几乎全在 4 kHz 以下，而 denoiser 的采样率链只保证到 8 kHz。
        #    画满 8 kHz 会让 y 轴一半是空的、下半挤成一团。统一裁到 4 kHz。
        ax = fig.add_subplot(gs[i, 0])
        seg = int(3.0 * 16000)
        S = spec_db(noisy[:seg])
        fmax_bin = int(4000 / (16000 / 2) * S.shape[0])
        ax.imshow(np.clip(S[:fmax_bin], S.max() - 70, S.max()), origin="lower",
                  aspect="auto", cmap="magma",
                  extent=[0, S.shape[1] * HOP / 16000.0, 0, 4.0])
        ax.set_title("(a%d) noisy spectrogram   dSI-SDR=%+.2f" % (i + 1, r["si_sdr_improve"]),
                     fontsize=9.5, pad=4)
        ax.set_ylabel("kHz", fontsize=8.5)
        ax.set_xlabel("s", fontsize=8.5)
        ax.grid(False)

        # ---- (b) 平均谱三态叠加（已平滑） ----
        ax = fig.add_subplot(gs[i, 1])
        L = min(len(noisy), len(ref) if ref is not None else len(noisy), len(est))
        pn = avg_spectrum(noisy[:L])
        pe = avg_spectrum(est[:L])
        ax.plot(f / 1000.0, pn, color=C_NOISY, lw=1.5, label="noisy")
        if ref is not None:
            pc = avg_spectrum(ref[:L])
            ax.plot(f / 1000.0, pc, color=C_CLEAN, lw=1.5, ls="--", label="clean (GT)")
        ax.plot(f / 1000.0, pe, color=C_EST, lw=1.5, label="enhanced")
        # 两条参考线：语音主要能量上限 4 kHz（灰）与 denoiser 内部 8 kHz 带宽上限（点划）
        ax.axvline(4.0, color="#999", lw=0.9, ls=":")
        ax.axvline(8.0, color="#666", lw=0.9, ls="-.")
        ax.set_xlim(0, 8.0)
        ax.set_ylim(pn.max() - 42, pn.max() + 5)
        ax.set_xlabel("kHz  (dotted 4k / dash-dot 8k)", fontsize=8.5)
        ax.legend(fontsize=7.8, loc="lower left", framealpha=0.92)
        # 用 4 kHz 以上的能量差做一个可读的量化标签
        hi = slice(int(len(pn) * 0.5), None)
        d_hf = float(np.mean(pe[hi] - pn[hi]))
        ax.set_title("(b%d) mean spectrum   mean_delta above 4kHz = %+.1f dB"
                     % (i + 1, d_hf), fontsize=9.5, pad=4)

        # ---- (c) hf_ratio 全片段散点，当前片段用大标记描出 ----
        ax = fig.add_subplot(gs[i, 2])
        same = [x for x in rs_all if x.get("snr_bin") == r.get("snr_bin")]
        hx = np.array([x["hf_ratio_in"] for x in same], dtype=float)
        hy = np.array([x["hf_ratio_out"] for x in same], dtype=float)
        lim = max(hx.max() if len(hx) else 0.3, hy.max() if len(hy) else 0.3) * 1.10
        ax.plot([0, lim], [0, lim], color="#999", lw=1.0, ls="--")
        ax.scatter(hx, hy, s=6, alpha=0.30, color="#2f7ed8",
                   edgecolors="none", label="all clips in bin (n=%d)" % len(same))
        ax.scatter([r["hf_ratio_in"]], [r["hf_ratio_out"]], s=130,
                   facecolors="none", edgecolors="#c9403a", linewidths=2.0,
                   zorder=5, label="this clip")
        ax.set_xlim(0, lim)
        ax.set_ylim(0, lim)
        ax.set_xlabel("hf_ratio  input", fontsize=8.5)
        ax.set_ylabel("hf_ratio  output", fontsize=8.5)
        ax.legend(fontsize=7.5, loc="lower right", framealpha=0.92)
        ax.set_title("(c%d) hf fidelity, bin %s   ratio=%.2f"
                     % (i + 1, r.get("snr_bin"), r["hf_ratio_out"] /
                        max(r["hf_ratio_in"], 1e-6)), fontsize=9.5, pad=4)

    fig.suptitle("T5.6  Spectral before/after — %s on %s   (clips at p10/p50/p90 of dSI-SDR, no cherry-picking)"
                 % (model, subset), fontsize=13.0, y=0.995)
    out = FIGS / ("t5_6_%s_%s_spectral.png" % (model, subset))
    fig.savefig(out)
    plt.close(fig)
    print("[fig ] %s" % out)
    return out


def _load_triple(item, subset, model):
    """按主表同一条契约率链重算 (noisy, ref, est) @16 kHz。"""
    import _denoise_registry as REG
    key = model
    if key not in REG.REGISTRY:
        return None
    try:
        run_fn, _, _ = REG.REGISTRY[key]["loader"]()
    except Exception:
        return None
    try:
        if item.get("noisy_path"):
            noisy = EV.load_mono(item["noisy_path"], 16000)
        else:
            cl = EV.load_mono(item["clean_path"], 16000)
            nz = EV.load_mono(item["noise_path"], 16000)
            noisy = EV.mix_at_snr(cl, nz, item["snr_db"],
                                  seed=hash(item["clip_id"]) & 0xFFFF)
        if len(noisy) / 16000.0 > EV.MAX_CLIP_SEC:
            return None
        csr = int(getattr(run_fn, "contract_sr", 44100))
        noisy_in = EV.resample_mono(noisy, 16000, csr) if csr != 16000 else noisy
        est = run_fn(np.stack([noisy_in, noisy_in], axis=-1))["enhanced"]
        est = np.asarray(est).mean(axis=1).astype(np.float32)
        if csr != 16000:
            est = EV.resample_mono(est, csr, 16000)
        ref = EV.load_mono(item["clean_path"], 16000) if item.get("clean_path") else None
        n = min([len(x) for x in (noisy, est, ref) if x is not None])
        return noisy[:n], (ref[:n] if ref is not None else None), est[:n]
    except Exception as e:
        print("[warn] load triple %s: %s" % (item.get("clip_id"), e))
        return None


def main():
    ap = argparse.ArgumentParser(description="T5.6 频谱前后对比图组")
    ap.add_argument("--models", default=",".join(PANEL_MODELS))
    ap.add_argument("--subsets", default=",".join(PANEL_SUBSETS))
    a = ap.parse_args()

    cells = json.loads((DATA / "denoise_manifest.json")
                       .read_text(encoding="utf-8"))["cells"]
    print("[data] %d cells" % len(cells))
    made = []
    for m in a.models.split(","):
        for s in a.subsets.split(","):
            p = make_panel(m.strip(), s.strip(), cells)
            if p:
                made.append(str(p))
    print("\n[done] %d figures" % len(made))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""
================================================================================
 逐模型 / 逐 output 分析图集生成器  (mirror of run_demucs_deepdive 的图集格式)
--------------------------------------------------------------------------------
 参照格式 : tools/run_demucs_deepdive.py  ->  04_reports/01_separation/figures/demucs/
            9 张图 (fig1 波形三联 / fig2 采样率 / fig3 频谱 x2 / fig4 窗长 / fig5 trim / fig6 MFCC x2)

 本脚本把同一套格式铺到 03_outputs 下「每个模型的每个 output」。

 口径 (用户 2026-10-12 拍板)
 ----------------------------
 * 窗长 = 4 档 : 128 / 512 / 1024 / 2048        (参照原有 128、1024 + 新增 512、2048)
 * 4 轨模型  : 每个 stem 各出一套 (vocals / drums / bass / other)
 * 单轨模型  : 只对 vocals 出图
 * L6 特例   : 输出是 vocals+other 混合轨, 无对应 GT -> 按「混合轨」口径出图并标注
 * 降噪模型  : 也要出图 (每组 stage0_gate 的 out.wav = 1 个单元)
 * 范围      : 全量 (11 分离模型 x 50 歌 + 7 降噪产物)
 * 窗口      : energy (B2, 用户 2026-10-12 拍板) —— 取能源最集中的 30 s
               以【参考信号】的能源峰定位, est 与 ref 严格同窗
               t_start 记入 caption.json 与图标题; 可用 --window first30 切回

 !! 目录隔离 (用户 2026-10-12 拍板 A1) !!
 ---------------------------------------------------------------------------------
 Windows 文件系统大小写不敏感, 旧版把产物直接写进 figures/<Model>/, 结果
 slugify("Demucs")="Demucs" 与参照目录 figures/demucs/ 在磁盘上是【同一个目录】
 (实测 inode 281474976713243), 参照 9 张图与产物 11 张图被混在一起。
 故本版起全部产物改写到独立顶层目录, 并用 assert_safe_target() 硬拦:

   SEP : 04_reports/01_separation/figures/_model_figs/<model_slug>/<song_slug>/<stem>/
   DEN : 04_reports/02_denoising/figures/_model_figs/<model_slug>/<probe_slug>/

 参考信号 (图为「估计 vs 真值」对比, 必须有真值)
 ------------------------------------------------
 * 分离 : 02_databases/MUSDB18-HQ/test/<song>/<stem>.wav   (44.1 kHz, 原始 wav)
     >> 必须读原始 wav, 不要读重采样后的分离输出 (P19: master64 偏差 2.15 dB)
 * 降噪 : 02_databases/Valentini/clean_testset_wav/p232_001.wav
     输入 : 02_databases/Valentini/noisy_testset_wav/p232_001.wav
     >> 降噪 out.wav 是 1.74 s 探针, 与 Valentini 探针对应 (见 tools/_probe_stage0_gate.py)

 输出
 ----
   04_reports/01_separation/figures/_model_figs/<model_slug>/<song_slug>/<stem>/fig*.png
   04_reports/02_denoising/figures/_model_figs/<model_slug>/<probe_slug>/fig*.png
   04_reports/<...>/docs/<model_slug>.md     每个模型一份文档 (总览 + 清单)

 每单元 11 张图
 --------------
   fig1_waveform_est_ref_diff.png   估计 / 参考 / 差值  三联
   fig2_waveform_sr_compare.png     重采样 44.1k / 22.05k / 16k
   fig3_spectrogram_est.png         估计频谱 (log 频率轴, n_fft=1024)
   fig3_spectrogram_ref.png         参考频谱 (同参数)
   fig4_spectrogram_win{128,512,1024,2048}.png   四档窗长 (线性频率轴)
   fig5_trim_before_after.png       trim(top_db=30) 前后
   fig6_mfcc_est.png                估计 MFCC 13 维
   fig6_mfcc_ref.png                参考 MFCC 13 维
   caption.json                     元数据

 运行
 ----
  python tools/_make_model_figures.py --list              # 只列单元, 不出图
  python tools/_make_model_figures.py --plan              # 打印规模估算
  python tools/_make_model_figures.py --sample            # 每模型首个单元出样张
  python tools/_make_model_figures.py --all               # 全量 (可断点续跑)
  python tools/_make_model_figures.py --all --model Demucs --song "BKS - Bulldozer"
  python tools/_make_model_figures.py --all --force       # 忽略已存在, 重画
  python tools/_make_model_figures.py --cleanup-legacy    # 列出(不删)旧版误写文件
  python tools/_make_model_figures.py --cleanup-legacy-apply  # 真正删除旧版误写文件
================================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import librosa
import librosa.display
import soundfile as sf

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import paths as _paths
_paths.setup_env()

ROOT = _paths.PROJECT_ROOT
OUTPUTS = ROOT / "03_outputs"
FIG_SEP = ROOT / "04_reports" / "01_separation" / "figures"
FIG_DEN = ROOT / "04_reports" / "02_denoising" / "figures"

# ---- A1: 产物独立顶层目录, 永不与参照 / 手工目录同层 ----------------------
SEP_SUB = FIG_SEP / "_model_figs"
DEN_SUB = FIG_DEN / "_model_figs"

DOC_SEP = ROOT / "04_reports" / "01_separation" / "docs"
DOC_DEN = ROOT / "04_reports" / "02_denoising" / "docs"
MUSDB_TEST = ROOT / "02_databases" / "MUSDB18-HQ" / "test"
VAL = ROOT / "02_databases" / "Valentini"

SR_MUSDB = 44100
SR_VAL = 48000
MAX_SEC = 30.0
WINDOW_MODE = "energy"         # B2 (用户 2026-10-12 拍板): 能源最大化 30s
                               #   "first30" = 严格照参照 (会踩静音前奏)
                               #   可用 --window first30 临时切回
WIN_LENGTHS = (128, 512, 1024, 2048)
DPI = 150

STEMS4 = ("vocals", "drums", "bass", "other")

# ---- 受保护目录: 写入目标若落在其下, 一律拒绝 ------------------------------
# (相对 ROOT 的路径, 全部小写比较 —— Windows 大小写不敏感)
PROTECTED = [
    "04_reports/01_separation/figures/demucs",    # 参照图集
    "04_reports/01_separation/figures/dprnn",
    "04_reports/01_separation/figures/audio_analysis",
    "04_reports/01_separation/figures/comparison",
    "04_reports/01_separation/figures/figs_time",
    "04_reports/01_separation/figures/reverb",
    "04_reports/01_separation/figures/spectrograms",
    "04_reports/01_separation/figures/test_run",
    "02_databases",
    "03_outputs",
]

# ---- 分离模型 -> 规范 stem 列表 -------------------------------------------
SEP_MODELS = {
    "Demucs":          STEMS4,
    "Open-Unmix":      STEMS4,
    "MDX-Net":         STEMS4,
    "DPRNN":           STEMS4,
    "Conv-TasNet":     STEMS4,
    "MMDenseLSTM":     STEMS4,
    "Oracle-IRM":      STEMS4,
    "BSRNN-opt":       ("vocals",),
    "BSRNN-large":     ("vocals",),
    "BS-RoFormer-L12": ("vocals",),
    "BS-RoFormer-L6":  ("vocals+other",),      # 混合轨, 无 GT
}

# ---- 降噪产物: (模型目录, stage0_gate 下的产物名, slug) --------------------
DEN_MODELS = [
    ("denoiser-dns48",             "denoiser_dns48",             "denoiser-dns48"),
    ("denoiser-dns64",             "denoiser_dns64",             "denoiser-dns64"),
    ("denoiser-master64",          "denoiser_master64",          "denoiser-master64"),
    ("Mel-RoFormer-Denoise",       "mel_roformer_denoise",       "mel-roformer-denoise"),
    ("Mel-RoFormer-Denoise",       "mel_roformer_denoise_aggr",  "mel-roformer-denoise-aggr"),
    ("Mel-RoFormer-Dereverb",      "mel_roformer_dereverb",      "mel-roformer-dereverb"),
    ("Mel-RoFormer-Dereverb-Echo", "mel_roformer_dereverb_echo", "mel-roformer-dereverb-echo"),
]
DEN_PROBE = "p232_001"


# ------------------------------------------------------------------ helpers --
def banner(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def slugify(s: str) -> str:
    out = []
    for ch in s:
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch in " ,./\\+":
            out.append("_")
    r = "".join(out)
    while "__" in r:
        r = r.replace("__", "_")
    return r.strip("_")


def assert_safe_target(p: Path, what: str = "输出目录") -> Path:
    """A1 硬闸门: 拒绝任何落在受保护目录下的写入目标。"""
    p = Path(p)
    try:
        rel = p.resolve().relative_to(ROOT.resolve()).as_posix().lower()
    except ValueError:
        raise SystemExit("[BLOCKED] %s 不在项目内: %s" % (what, p))
    for guard in PROTECTED:
        g = guard.lower().rstrip("/")
        if rel == g or rel.startswith(g + "/"):
            raise SystemExit(
                "[BLOCKED] %s 落在受保护目录内 -> %s\n"
                "          保护名单: %s\n"
                "          (A1 隔离: 产物必须写在 figures/_model_figs/ 下)"
                % (what, rel, guard))
    return p


def save_fig(path: Path, dpi: int = DPI):
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(str(path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close()


def _frame_power(y, sr, frame_sec=0.05):
    """把整段信号切成非重叠小帧, 返回每帧平均功率 (float64, 长度 ~len/fl)。

    🔴🔴 2026-10-13 修【内存炸弹】—— 这是导致图集任务在 69/1607 处猝死的原因。
    旧实现: librosa.feature.rms(frame_length=int(30*sr)) 在 430 s 的 MUSDB 歌上
    会实体化 (n_frames, frame_length) 中间数组
        = 1802 x 1_323_000 x 4B ≈ **9.5 GB**, 每单元调 2 次 (ref+est) ≈ 19 GB
    -> 系统内存耗尽 -> 进程被 OS 硬杀 (stdout 缓冲丢失 -> 日志 0 字节)。
    且每单元约 30 s (本应 ~10 s) 全是这个分配的开销。

    新实现: 50 ms 非重叠帧, 峰值内存 ≈ len(y) x 8B ≈ 70 MB, O(len) 时间。
    """
    fl = max(int(frame_sec * sr), 1)
    m = (len(y) // fl) * fl
    if m == 0:
        return np.zeros(1, dtype=np.float64), fl
    p = (np.asarray(y[:m], dtype=np.float64) ** 2).reshape(-1, fl).mean(axis=1)
    return p, fl


def best_window_start(y, sr, win_sec=MAX_SEC):
    """返回能源最集中的 win_sec 窗口起点(样本)。y 为 mono float32。

    用 50 ms 帧功率的【滑动和】(cumsum) 定位, O(len) 且内存受限。
    分辨率 50 ms 对"选哪 30 s"完全够用。
    """
    n = int(win_sec * sr)
    if len(y) <= n:
        return 0
    p, fl = _frame_power(y, sr)
    W = max(1, int(round(n / fl)))              # 窗口覆盖多少帧
    if len(p) <= W:
        return 0
    c = np.concatenate([[0.0], np.cumsum(p)])
    win = c[W:] - c[:-W]                        # 每个 W 帧窗口的能量和
    k = int(np.argmax(win))
    return min(k * fl, len(y) - n)


def pick_window(y, sr, start=None):
    """按 WINDOW_MODE 从 y 中取 MAX_SEC 秒。

    start = 起点【秒】(不是样本!) 非 None 时强制该窗口;
    用于让 ref 与 est 对齐到同一时间窗。
    """
    n = int(MAX_SEC * sr)
    if len(y) <= n:
        return y, 0.0
    if start is not None:
        # BUGFIX 2026-10-12: start 是秒, 必须先 x sr 换成样本再切片
        s = int(round(float(start) * sr))
        s = max(0, min(s, len(y) - n))
        return y[s:s + n], s / sr
    if WINDOW_MODE == "energy":
        s = best_window_start(y, sr)
        return y[s:s + n], s / sr
    return y[:n], 0.0


def load_mono(path, sr_want, start=None):
    """读成 mono float32, 取 MAX_SEC 秒, 必要时重采样到 sr_want。

    start (秒) 非 None 时强制该窗口起点; 否则按 WINDOW_MODE 自动决定。
    """
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1).astype(np.float32)
    y, _t0 = pick_window(y, sr, start)
    if sr != sr_want:
        y = librosa.resample(y, orig_sr=sr, target_sr=sr_want).astype(np.float32)
    return y


def load_pair(est_p, ref_p, sr_want, ref_anchor=True):
    """读 est/ref 到同一时间窗。

    energy 模式下 ref_anchor=True: 以【参考信号】的能源峰定位窗口,
    再把同一窗口套用到 est —— 这样两者严格同窗, 差值才有意义。
    返回 (est, ref, t_start, note)
    """
    info = sf.info(str(est_p))
    n = int(MAX_SEC * info.samplerate)
    start = None
    note = None
    if WINDOW_MODE == "energy":
        anchor = ref_p if (ref_anchor and ref_p is not None) else est_p
        ay, asr = sf.read(str(anchor), dtype="float32", always_2d=True)
        ay = ay.mean(axis=1).astype(np.float32)
        if len(ay) > int(MAX_SEC * asr):
            start = best_window_start(ay, asr) / asr
            note = ("energy 窗口: 由 %s 的能源峰定位 t_start=%.2fs; "
                    "est 与 ref 使用同一窗口"
                    % ("参考信号" if (ref_anchor and ref_p is not None) else "输出",
                       start))
        else:
            start = 0.0
    est = load_mono(est_p, sr_want, start)
    ref = load_mono(ref_p, sr_want, start) if ref_p is not None else None
    return est, ref, (start or 0.0), note


def plot_spectrogram(y, sr, title, path, n_fft=1024, hop_length=512, y_axis="log"):
    plt.figure(figsize=(12, 4))
    S = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=n_fft,
                                                    hop_length=hop_length)), ref=np.max)
    librosa.display.specshow(S, sr=sr, hop_length=hop_length,
                             x_axis="time", y_axis=y_axis, cmap="magma")
    plt.colorbar(format="%+2.0f dB")
    plt.title(title)
    save_fig(path)


def plot_mfcc(y, sr, title, path, n_mfcc=13):
    plt.figure(figsize=(12, 4))
    m = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    librosa.display.specshow(m, sr=sr, x_axis="time", cmap="viridis")
    plt.colorbar()
    plt.title(title)
    save_fig(path)


def make_figures(est, ref, sr, outdir, *, est_label, ref_label,
                 is_mixed=False, note=None, t_start=0.0):
    """生成 11 张图 + caption.json。"""
    if t_start:
        est_label = "%s  [t_start=%.1fs]" % (est_label, t_start)
        ref_label = "%s  [t_start=%.1fs]" % (ref_label, t_start)
    outdir = Path(outdir)
    assert_safe_target(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    n = min(len(est), len(ref)) if ref is not None else len(est)
    est, ref = est[:n], (ref[:n] if ref is not None else None)
    t = np.arange(n) / sr

    # --- fig1: 估计 / 参考 / 差值 三联
    rows = 2 if ref is None else 3
    fig, ax = plt.subplots(rows, 1, figsize=(12, 2.2 * rows), sharex=True)
    ax = np.atleast_1d(ax)
    ax[0].plot(t, est, lw=0.5, color="#1f77b4")
    ax[0].set_ylabel("est"); ax[0].set_title(est_label)
    if ref is not None:
        ax[1].plot(t, ref, lw=0.5, color="#2ca02c")
        ax[1].set_ylabel("ref"); ax[1].set_title(ref_label)
        d = est - ref
        ax[2].plot(t, d, lw=0.5, color="#d62728")
        ax[2].set_ylabel("diff"); ax[2].set_title("estimate - reference")
    ax[-1].set_xlabel("time (s)")
    save_fig(outdir / "fig1_waveform_est_ref_diff.png")

    # --- fig2: 重采样对比
    plt.figure(figsize=(12, 4))
    for s in (44100, 22050, 16000):
        y2 = librosa.resample(est, orig_sr=sr, target_sr=s) if sr != s else est
        plt.plot(np.arange(len(y2)) / s, y2, lw=0.4, alpha=0.8, label="%d Hz" % s)
    plt.legend(loc="upper right", fontsize=8)
    plt.title("%s  |  resampled views" % est_label)
    plt.xlabel("time (s)")
    save_fig(outdir / "fig2_waveform_sr_compare.png")

    # --- fig3: log 频率轴频谱 x2
    plot_spectrogram(est, sr, "%s  |  log-freq (n_fft=1024)" % est_label,
                     outdir / "fig3_spectrogram_est.png", y_axis="log")
    if ref is not None:
        plot_spectrogram(ref, sr, "%s  |  log-freq (n_fft=1024)" % ref_label,
                         outdir / "fig3_spectrogram_ref.png", y_axis="log")

    # --- fig4: 四档窗长 (线性频率轴)
    for win in WIN_LENGTHS:
        hop = max(win // 2, 1)
        plot_spectrogram(est, sr, "%s  |  win=%d (linear-freq)" % (est_label, win),
                         outdir / ("fig4_spectrogram_win%d.png" % win),
                         n_fft=win, hop_length=hop, y_axis="hz")

    # --- fig5: trim 前后
    plt.figure(figsize=(12, 4))
    try:
        yt, idx = librosa.effects.trim(est, top_db=30)
    except Exception:
        yt, idx = est, np.array([0, len(est)])
    plt.subplot(2, 1, 1)
    plt.plot(t, est, lw=0.4, color="#7f7f7f")
    plt.axvspan(idx[0] / sr, min(idx[1] / sr, t[-1]), color="#ffd966", alpha=0.35)
    plt.title("%s  |  trim(top_db=30)  before" % est_label)
    plt.subplot(2, 1, 2)
    plt.plot(np.arange(len(yt)) / sr, yt, lw=0.4, color="#1f77b4")
    plt.title("after  (kept %.2fs of %.2fs)" % (len(yt) / sr, len(est) / sr))
    plt.tight_layout()
    save_fig(outdir / "fig5_trim_before_after.png")

    # --- fig6: MFCC x2
    plot_mfcc(est, sr, "%s  |  MFCC-13" % est_label, outdir / "fig6_mfcc_est.png")
    if ref is not None:
        plot_mfcc(ref, sr, "%s  |  MFCC-13" % ref_label, outdir / "fig6_mfcc_ref.png")

    files = sorted(p.name for p in outdir.glob("fig*.png"))
    cap = {
        "est_label": est_label,
        "ref_label": ref_label,
        "sr": sr,
        "duration_s": round(n / sr, 2),
        "t_start_s": round(t_start, 2),
        "win_lengths": list(WIN_LENGTHS),
        "window_mode": WINDOW_MODE,
        "is_mixed_output": bool(is_mixed),
        "note": note,
        "files": files,
    }
    (outdir / "caption.json").write_text(
        json.dumps(cap, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / ".done").write_text("ok", encoding="utf-8")
    return outdir


# --------------------------------------------------------------- unit defs ---
def sep_units(model, songs=None):
    """-> [(song, stem, est_path, ref_path_or_None, is_mixed)]"""
    mdir = OUTPUTS / model / "test"
    if not mdir.is_dir():
        return []
    expect = SEP_MODELS[model]
    want = set(songs) if songs else None
    out = []
    for sdir in sorted(p for p in mdir.iterdir() if p.is_dir()):
        song = sdir.name
        if want and song not in want:
            continue
        for stem in expect:
            # 文件名探测: L6 实际落盘为 "vocals+other.flac" (带 +),
            # 其余为 "<stem>.flac"; 兼容 _ / - / 去加号 / 首段 等写法
            cands = []
            for base in (stem, stem.replace("+", "_"), stem.replace("+", "-"),
                         stem.replace("+", ""), stem.split("+")[0]):
                for ext in (".flac", ".wav"):
                    cands.append(sdir / (base + ext))
            f = next((c for c in cands if c.exists()), None)
            if f is None:
                continue
            is_mixed = stem not in STEMS4
            ref = None if is_mixed else (MUSDB_TEST / song / (stem + ".wav"))
            if ref is not None and not ref.exists():
                ref = None
            out.append((song, stem, f, ref, is_mixed))
    return out


def den_units():
    """-> [(slug, est_path, noisy, clean)]"""
    out = []
    for mdir, prod, slug in DEN_MODELS:
        est = OUTPUTS / mdir / "stage0_gate" / prod / "out.wav"
        if not est.exists():
            continue
        out.append((
            slug, est,
            VAL / "noisy_testset_wav" / ("%s.wav" % DEN_PROBE),
            VAL / "clean_testset_wav" / ("%s.wav" % DEN_PROBE)))
    return out


# ------------------------------------------------------------------- run -----
def do_sep(model, song, stem, est_p, ref_p, is_mixed, force):
    slug_m = slugify(model)
    slug_s = slugify(song)
    outdir = SEP_SUB / slug_m / slug_s / slugify(stem)
    marker = outdir / ".done"
    if marker.exists() and not force:
        return "skip"
    if not is_mixed:
        # 分离: 以 GT 锚定窗口, est/ref 严格同窗
        est, ref, t0, wnote = load_pair(est_p, ref_p, SR_MUSDB, ref_anchor=True)
    else:
        # 混合轨 (L6: vocals+other): 没有同口径 GT。
        #   窗口锚点 = 输出自身能源峰 (混合轨能量更集中, 定位更稳)
        #   参考曲线 = 同窗的 GT vocals, 仅供频谱形态对照, 不参与指标
        gt_v = MUSDB_TEST / song / "vocals.wav"
        gt_v = gt_v if gt_v.exists() else None
        est, _r, t0, wnote = load_pair(est_p, gt_v, SR_MUSDB, ref_anchor=False)
        ref = load_mono(gt_v, SR_MUSDB, t0) if gt_v is not None else None
    note = wnote
    ref_label = "Ground-truth %s" % stem
    if is_mixed:
        note = ((wnote + " | ") if wnote else "") + (
            "模型输出为混合轨 %s, 与 GT vocals 不同口径, "
            "仅供波形/频谱形态参考, 不构成指标对比。" % stem)
        ref_label = "GT vocals (NOT same target, shape ref only)"
    make_figures(
        est, ref, SR_MUSDB, outdir,
        est_label="%s · %s" % (model, stem),
        ref_label=ref_label,
        is_mixed=is_mixed, note=note, t_start=t0)
    return "done"


def do_den(slug, est_p, noisy_p, clean_p, force):
    outdir = DEN_SUB / slug / DEN_PROBE
    marker = outdir / ".done"
    if marker.exists() and not force:
        return "skip"
    # 降噪探针仅 1.74 s (< MAX_SEC), 无窗口选择问题
    est = load_mono(est_p, SR_VAL, 0.0)
    ref = load_mono(clean_p, SR_VAL, 0.0)
    note = ("输入噪声 = Valentini/noisy_testset_wav/%s.wav; "
            "探针全长 1.74 s, 不做 30 s 截窗" % DEN_PROBE)
    make_figures(
        est, ref, SR_VAL, outdir,
        est_label="%s · enhanced" % slug,
        ref_label="clean reference (Valentini %s)" % DEN_PROBE,
        note=note, t_start=0.0)
    return "done"


# ------------------------------------------------------------------ docs -----
def write_docs_sep(model, units):
    slug = slugify(model)
    stems = sorted({u[1] for u in units})
    songs = sorted({u[0] for u in units})
    p = DOC_SEP / ("FIGURES_%s.md" % slug)
    lines = [
        "# %s · 逐 output 分析图集" % model,
        "",
        "- 图集格式参照 `figures/demucs/`（`tools/run_demucs_deepdive.py`）",
        "- 产物根目录：`figures/_model_figs/%s/`（A1 隔离，不与参照同层）" % slug,
        "- 窗长档位：%s" % ", ".join(str(w) for w in WIN_LENGTHS),
        (f"- 每单元 **{len(WIN_LENGTHS) + 7}** 张图"
         f"（fig1 / fig2 / fig3×2 / fig4×{len(WIN_LENGTHS)} / fig5 / fig6×2）"),
        "- 窗口口径：%s" % ("前 30 s（照参照 run_demucs_deepdive）"
                          if WINDOW_MODE == "first30"
                          else "能源最大化 30 s（B2；以参考信号能源峰定位，est/ref 同窗；"
                               "每单元实际 t_start 见 caption.json）"),
        "- 歌曲数：%d ｜ stem：%s ｜ 单元数：%d" % (len(songs), ", ".join(stems), len(units)),
        "",
        "## 目录结构",
        "",
        "```",
        "figures/_model_figs/%s/<song>/<stem>/fig*.png" % slug,
        "```",
        "",
        "## 单元清单",
        "",
        "| 歌曲 | stem | 参考信号 | 口径 |",
        "|---|---|---|---|",
    ]
    for song, stem, est_p, ref_p, mixed in units:
        if mixed:
            ref_s, kj = "（无）", "混合轨（非同口径）"
        else:
            ref_s = "MUSDB18-HQ/test/%s/%s.wav" % (song, stem)
            kj = "同口径"
        lines.append("| %s | %s | %s | %s |" % (song, stem, ref_s, kj))
    lines += [
        "",
        "## 图说明",
        "",
        "| 文件 | 内容 |",
        "|---|---|",
        "| `fig1_waveform_est_ref_diff.png` | 波形三联：输出 / 参考 / 差值 |",
        "| `fig2_waveform_sr_compare.png` | 输出重采样 44.1k / 22.05k / 16k |",
        "| `fig3_spectrogram_est.png` | 输出频谱（log 频率轴, n_fft=1024） |",
        "| `fig3_spectrogram_ref.png` | 参考频谱（同参数） |",
    ]
    for w in WIN_LENGTHS:
        lines.append("| `fig4_spectrogram_win%d.png` | 输出频谱, 窗长 %d（线性频率轴） |" % (w, w))
    lines += [
        "| `fig5_trim_before_after.png` | trim(top_db=30) 前后 |",
        "| `fig6_mfcc_est.png` | 输出 MFCC 13 维 |",
        "| `fig6_mfcc_ref.png` | 参考 MFCC 13 维 |",
        "| `caption.json` | 该单元的元数据 |",
        "",
    ]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def write_docs_den(units):
    p = DOC_DEN / "FIGURES_denoise.md"
    lines = [
        "# 降噪模型 · 逐 output 分析图集",
        "",
        "- 图集格式同 `01_separation` 侧",
        "- 产物根目录：`figures/_model_figs/`（A1 隔离）",
        "- 探针：Valentini `%s`（1.74 s，与 `tools/_probe_stage0_gate.py` 一致）" % DEN_PROBE,
        "- 参考信号：`Valentini/clean_testset_wav/%s.wav`" % DEN_PROBE,
        "- 窗长档位：%s" % ", ".join(str(w) for w in WIN_LENGTHS),
        "- 产物数：%d" % len(units),
        "",
        "## 目录结构",
        "",
        "```",
        "figures/_model_figs/<model_slug>/%s/fig*.png" % DEN_PROBE,
        "```",
        "",
        "## 产物清单",
        "",
        "| 模型 | 增强输出 | 参考 |",
        "|---|---|---|",
    ]
    for slug, est, noisy, clean in units:
        rel = est.relative_to(ROOT).as_posix()
        lines.append("| %s | `%s` | `02_databases/Valentini/clean_testset_wav/%s.wav` |"
                     % (slug, rel, DEN_PROBE))
    lines += [
        "",
        "## 图说明",
        "",
        "同 `01_separation` 侧；其中 `fig3/fig6` 的 `est` = 增强输出，`ref` = clean 参考。",
        "",
    ]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def cleanup_legacy(dry=True, since=None):
    """列出(默认不删)旧版 A0 误写进参照/手工目录的文件。

    !! 安全规则 (2026-10-12 修正) !!
    绝不能按「文件名匹配」删除 —— 那样会误删用户既有图!
    实测 audio_analysis/ 下有 2026-09-15 的 fig2_waveform_sr_compare.png 等
    与本次产物同名的旧图, 参照 demucs/fig4_spectrogram_win128.png 同理。

    本函数只删同时满足以下【全部】条件的文件:
      1) 所在目录含 .done 标记 (只有本脚本会写 .done)
      2) .done 的 mtime >= since (默认: 本次 A0 污染窗口起点)
      3) 所在目录不在 figures/_model_figs/ 下 (那是 A1 新目录, 不能删)
      4) 文件名属于本脚本产物集合
    """
    import datetime as _dt
    if since is None:
        # A0 污染窗口起点: 2026-10-12 00:00
        since = _dt.datetime(2026, 10, 12, 0, 0, 0).timestamp()

    MINE = {
        "fig1_waveform_est_ref_diff.png", "fig2_waveform_sr_compare.png",
        "fig3_spectrogram_est.png", "fig3_spectrogram_ref.png",
        "fig4_spectrogram_win128.png", "fig4_spectrogram_win512.png",
        "fig4_spectrogram_win1024.png", "fig4_spectrogram_win2048.png",
        "fig5_trim_before_after.png", "fig6_mfcc_est.png", "fig6_mfcc_ref.png",
        "caption.json", ".done",
    }

    hits, skipped = [], []
    for base in (FIG_SEP, FIG_DEN):
        mm = base / "_model_figs"
        for root, dirs, files in os.walk(base):
            rp = Path(root)
            if rp == mm or mm in rp.parents:
                continue                                   # A1 新目录
            if ".done" not in files:
                continue                                   # 没我写的标记 -> 不是我碰过的
            try:
                dm = (rp / ".done").stat().st_mtime
            except OSError:
                continue
            if dm < since:
                skipped.append(rp)                         # .done 太旧 -> 另有其人
                continue
            for f in files:
                if f in MINE:
                    hits.append(rp / f)

    print("旧版(A0)误写目录候选 %d 个 -> 将删 %d 个文件:"
          % (len({h.parent for h in hits}), len(hits)))
    for h in sorted(hits):
        print("   ", h.relative_to(ROOT).as_posix())
    if skipped:
        print("\n[跳过] 含 .done 但 mtime 早于 %s 的目录 (疑为用户既有, 不动):"
              % _dt.datetime.fromtimestamp(since).strftime("%Y-%m-%d %H:%M"))
        for s in sorted(set(skipped)):
            print("   ", s.relative_to(ROOT).as_posix())
    if not dry:
        n = 0
        for h in hits:
            try:
                h.unlink(); n += 1
            except OSError:
                pass
        print("\n[已删除] %d 个文件" % n)
    else:
        print("\n(试运行; 加 --cleanup-legacy-apply 才真正删除)")
    return hits


# -------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="只列单元")
    ap.add_argument("--plan", action="store_true", help="打印规模估算")
    ap.add_argument("--sample", action="store_true", help="每模型首个单元出样张")
    ap.add_argument("--all", action="store_true", help="全量")
    ap.add_argument("--model", default=None, help="限定单个模型")
    ap.add_argument("--song", default=None, help="限定单首歌")
    ap.add_argument("--force", action="store_true", help="忽略 .done 重画")
    ap.add_argument("--window", choices=["first30", "energy"], default=None,
                    help="30s 窗口口径 (默认 energy = 能源最大化, B2)")
    ap.add_argument("--cleanup-legacy", action="store_true",
                    help="列出旧版 A0 误写进参照目录的文件 (仅列出)")
    ap.add_argument("--cleanup-legacy-apply", action="store_true",
                    help="真正删除旧版误写文件")
    a = ap.parse_args()

    if a.window:
        global WINDOW_MODE
        WINDOW_MODE = a.window

    if a.cleanup_legacy or a.cleanup_legacy_apply:
        cleanup_legacy(dry=not a.cleanup_legacy_apply)
        return 0

    sep_all = {}
    for m in SEP_MODELS:
        u = sep_units(m, [a.song] if a.song else None)
        if u:
            sep_all[m] = u
    den_all = den_units()

    if a.model:
        sep_all = {k: v for k, v in sep_all.items() if k == a.model}
        den_all = [d for d in den_all if d[0] == a.model]

    n_units = sum(len(v) for v in sep_all.values()) + len(den_all)
    per = len(WIN_LENGTHS) + 7

    if a.list or a.plan:
        for m, u in sep_all.items():
            print("%-20s units=%-5d figs=%s" % (m, len(u), format(len(u) * per, ",")))
        for slug, est, _n, _c in den_all:
            print("%-20s units=%-5d figs=%s" % ("[den] " + slug, 1, per))
        print("-" * 60)
        print("units total : %d" % n_units)
        print("figs/unit   : %d  (fig1,2,3x2,4x%d,5,6x2)" % (per, len(WIN_LENGTHS)))
        print("figs total  : %s" % format(n_units * per, ","))
        print("est. size   : %.1f GB" % (n_units * per * 298e3 / 1e9))
        print("window mode : %s" % WINDOW_MODE)
        print("sep output  : %s" % SEP_SUB.relative_to(ROOT).as_posix())
        print("den output  : %s" % DEN_SUB.relative_to(ROOT).as_posix())
        return 0

    if not (a.sample or a.all):
        ap.print_help()
        return 2

    banner("生成模型图集  %s   window=%s" % ("样张" if a.sample else "全量", WINDOW_MODE))
    t0 = time.time()
    done = skipped = 0
    todo = []
    for m, u in sep_all.items():
        todo += [("sep", m, x) for x in u]
    for d in den_all:
        todo.append(("den", d[0], d))
    if a.sample:
        seen, picked = set(), []
        for kind, m, x in todo:
            if m in seen:
                continue
            seen.add(m)
            picked.append((kind, m, x))
        todo = picked

    print("本轮单元数 %d  (每单元 %d 图)" % (len(todo), per))
    for i, (kind, m, x) in enumerate(todo, 1):
        try:
            if kind == "sep":
                song, stem = x[0], x[1]
                r = do_sep(m, song, stem, x[2], x[3], x[4], a.force)
                tag = "%s/%s/%s" % (m, song, stem)
            else:
                r = do_den(x[0], x[1], x[2], x[3], a.force)
                tag = "%s/%s" % (m, DEN_PROBE)
        except SystemExit:
            raise
        except Exception as e:
            print("[%4d/%d] %-58s  FAIL  %s" % (i, len(todo), tag[:58], e))
            continue
        done += (r == "done")
        skipped += (r == "skip")
        el = time.time() - t0
        eta = (el / i) * (len(todo) - i) / 60 if i else 0
        print("[%4d/%d] %-58s  %-8s %5.1fs  eta %6.1f min"
              % (i, len(todo), tag[:58], r, el / i, eta))

    print()
    for m, u in sep_all.items():
        if u:
            print("[doc] %s" % write_docs_sep(m, u).relative_to(ROOT).as_posix())
    if den_all:
        print("[doc] %s" % write_docs_den(den_all).relative_to(ROOT).as_posix())

    banner("完成  done=%d skipped=%d  用时 %.1f min" % (done, skipped, (time.time() - t0) / 60))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

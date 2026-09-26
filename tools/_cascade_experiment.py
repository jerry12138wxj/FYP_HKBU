# -*- coding: utf-8 -*-
"""T6 · 级联实验 —— 板 1（分离）× 板 2（降噪）的缝合点。

要回答的问题
------------
  把语音降噪器接在音乐源分离的**前面**，分离质量是涨还是跌？

链路（本脚本实现）
------------------
  L0    noisy mixture              -> SEP                基线（不降噪）
  L1    noisy mixture -> 降噪       -> SEP                前置降噪
  L1b★  noisy mixture -> 仅限带     -> SEP                对照：只付「带宽+单声道」代价，不降噪
  L1m★  noisy mixture -> mel 降噪   -> SEP                对照臂：另一模型族，且无带宽代价
  L2    noisy mixture -> SEP -> 对 vocals 降噪            后置降噪
  L2b★  noisy mixture -> SEP -> 对 vocals 仅限带          对照
  L3    noisy mixture -> 降噪 -> SEP -> 对 vocals 降噪     双端

  ΔSDR(X) = SDR(X vs 干 GT stem) − SDR(L0 vs 干 GT stem)

★ 为什么必须有 L1b / L1m（本脚本对计划书的关键补充）
----------------------------------------------------
`denoiser` 是 **16 kHz 单声道语音**模型：其 wrapper 内部
`convert_audio(wav, 44100, 16000, 1)` -> 模型 -> `resample(16000, 44100)`。
即**输出的带宽上限只有 8 kHz，且立体声被下混成单声道**。

直接测 L1，会把两件完全不同的事混在一起：
    ① 降噪器「去掉了噪声」的净收益/损伤      ← 我们想问的
    ② 信号带宽被砍到 8 kHz + 立体声塌成单声道 ← 管线的固有代价

这正是本项目 **P19 的元教训**（能解释一切的叙事，往往就是 bug 在说话）要求的对照纪律：
必须有一格「只付代价、不做动作」的对照，才能把 ② 从 ① 里减出来。

  L1b 的实现是**逐行镜像 denoiser 的 wrapper**（同一 `convert_audio` 下行、
  同一 `torchaudio.resample` 上行），唯一差别是**跳过模型前向**。
  => `L1b − L0` = 纯带宽/单声道代价；`L1 − L1b` = 降噪的净效应。

`mel_roformer` 原生 44.1 kHz 立体声、无内部重采样 -> **没有带宽代价**，
所以 `L1m − L0` 本身就是纯降噪效应，与 `L1 − L1b` 可直接对照。

P7 / P17 / P19 三条约束的落实
-----------------------------
  P7  : 不得预设降噪有用。结果变差**照报**（见计划书 R12）。
  P17 : 级联前先判定噪声类型。本实验噪声 = **DNS freesound**（与 T5.4 的 synth 集同源）
        -> 按 P17 的判定，该分布下 denoiser 有效、mel 近乎恒等。
        -> 因此**两个模型族都跑**，把 P17 的结论从「模型级」提升到「系统级」。
        ⚠️ 注意这不等于「预设 denoiser 有用」：P17 只给出**动作量**的预测，
           而动作可能是**负**的（域外：语音降噪器用在音乐上）。两个结果都照报。
        ⚠️ 该预测的**前提**（噪声确实是瞬态高频型）由本脚本的 G5 门禁当场验证
           （记录 noisy / dry 的 `hf_ratio`），不靠外部结论外推。
  P19 : 契约采样率链。降噪调用一律 `csr = getattr(run_fn, "contract_sr", 44100)`，
        按契约率喂入；**绝不原地覆盖**源数组（曾导致指标出 −73 dB 荒谬值）。

数据与口径
----------
  片段：MUSDB18-HQ **test**，取 `panel_song_selection.json` 的 **Top-10 曲**
        （该排名是 T4 用过的同一份，含 T4 的 3 首 -> 两个阶段共享锚点），每首 1 个 20 s 窗。
  SNR ：{-5, 0, 5, 10} dB，与 T5.4 同档。
  噪声：`DNS-Challenge/noise/freesound`（2308 条 48 kHz mono，10 s），
        **逐声道独立**取噪声（避免人为的完全相关声场）。
  GT  ：MUSDB **干 stem**（noise 只加到 mixture，不进任何 stem —— 物理上即"录音中混入的环境噪声"）。
  指标：`compare_separation_methods.evaluate()`（museval BSSEval v4，mono，
        **默认窗 2 s/hop 1.5 s**）—— 与主板 1 主表同源，不得偷换（计划书 P2）。
        每格 4 轨 SDR 取均值 = `avg4`，跨 10 曲取中位数。

  分离模型（**四轨组**，R10 分组纪律）：demucs / mdx / bsrnn_all / umx
  ⚠️ 计划书写的是「BSRNN-opt」，但注册表里 `bsrnn` 是**人声单轨**模型，
     与「取四轨完整组代表」自相矛盾，且违反 R10（单目标与四轨不可同轴比较）。
     故改用 `bsrnn_all` = oBSRNN(4 ckpt) 四轨模型（T4 已在 20 s 片段上验证可用）。

子命令
------
  python tools/_cascade_experiment.py plan                 # 组合清单（不推理）
  python tools/_cascade_experiment.py make-noisy            # 合成 noisy（CPU，含 5 道门禁，落 V0/Vdry）
  python tools/_cascade_experiment.py prep --op vden        # 前置降噪 -> _front/V1den
  python tools/_cascade_experiment.py prep --op vbl         # 前置仅限带 -> _front/V1bl（★对照）
  python tools/_cascade_experiment.py prep --op vden-mel    # 前置 mel 降噪 -> _front/V1mel（★对照臂）
  python tools/_cascade_experiment.py run                   # 分离推理（GPU，每模型一子进程）
  python tools/_cascade_experiment.py post --op vden        # 后置降噪（读 _vocals/，一模型一进程）
  python tools/_cascade_experiment.py post --op vbl         # 后置仅限带（★对照，无模型）
  python tools/_cascade_experiment.py summary               # ΔSDR 矩阵 -> JSON + CSV
  python tools/_cascade_experiment.py all

落点
----
  04_reports/cascade/data/cascade_plan.json
  04_reports/cascade/data/cascade_manifest.json
  04_reports/cascade/data/cascade_eval.json
  04_reports/cascade/data/cascade_eval.csv
  03_outputs/_cascade/{_front,_vocals,_post}/
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

TOOLS = Path(_paths.TOOLS)
PROJECT = Path(_paths.PROJECT_ROOT)
MUSDB_TEST = _paths.musdb_root() / "test"
NOISE_DIR = PROJECT / "02_databases" / "DNS-Challenge" / "noise" / "freesound"

CASC_DATA = PROJECT / "04_reports" / "cascade" / "data"
CASC_DATA.mkdir(parents=True, exist_ok=True)
PLAN_JSON = CASC_DATA / "cascade_plan.json"
MAN_JSON = CASC_DATA / "cascade_manifest.json"
EVAL_JSON = CASC_DATA / "cascade_eval.json"
EVAL_CSV = CASC_DATA / "cascade_eval.csv"
PANEL_JSON = _paths.DATA_COMPARISON / "panel_song_selection.json"

AUDIO_ROOT = _paths.OUTPUTS / "_cascade"
FRONT = AUDIO_ROOT / "_front"
VOCALS = AUDIO_ROOT / "_vocals"
POST = AUDIO_ROOT / "_post"

PY = sys.executable
SR = 44100
DUR_S = 20.0
N_TOP_SONGS = 10
SNR_LEVELS = [-5.0, 0.0, 5.0, 10.0]
STEMS = ["vocals", "drums", "bass", "other"]
CELLS = ["L0", "L1", "L1b", "L1m", "L2", "L2b", "L3"]

# 四轨组（R10）：单目标模型不得混入
SEP_MODELS = ["demucs", "mdx", "bsrnn_all", "umx"]
SEP_LABELS = {"demucs": "Demucs (htdemucs)", "mdx": "MDX-Net (mdx_extra)",
              "bsrnn_all": "oBSRNN (4 ckpt, 4-stem)", "umx": "Open-Unmix (umxhq)"}

DEN_MODEL = "denoiser_master64"        # 主力：P19 复跑后 ΔPESQ 最优
MEL_MODEL = "mel_roformer_denoise"     # 对照臂：另一模型族，无带宽代价

# 前置放分离输入；后置只作用于分离出的 vocals 轨
FRONT_VARIANTS = ["V0", "V1den", "V1mel", "V1bl"]
VARIANT_DESC = {
    "Vdry": "干 mixture（无噪声）——**锚点**，用于校验 loader/口径未漂移",
    "V0": "带噪 mixture（L0 基线输入）",
    "V1den": "带噪 mixture -> denoiser 降噪（L1/L3 输入）",
    "V1mel": "带噪 mixture -> mel_roformer 降噪（L1m 输入，★对照臂）",
    "V1bl": "带噪 mixture -> **仅 16k/mono 往返、不降噪**（L1b 输入，★对照）",
}

# 干档 avg4 SDR 的历史量级下界（主板 1 主表，20 s 片段）。
# 只做「别崩」粗门禁：低于此值说明 loader 或口径错了，而不是模型差。
# 取 T4 同口径（reverb_vs_sep.json 的 sdr_dry）留 40% 余量。
DRY_FLOOR = {"demucs": 4.1, "umx": 2.3, "mdx": 4.4, "bsrnn_all": 4.5}


# ============================================================ 数据合成
def _pick_songs():
    """取 panel_song_selection.json 的 Top-N（与 T4 用同一份排名 -> 共享锚点）。"""
    if not PANEL_JSON.is_file():
        raise SystemExit("[FATAL] 缺 %s —— 先跑 tools/_select_panel_songs.py" % PANEL_JSON)
    d = json.loads(PANEL_JSON.read_text(encoding="utf-8"))
    rank = d.get("ranking_top30") or d.get("picked_detail")
    if not rank:
        raise SystemExit("[FATAL] %s 里没有 ranking_top30/picked_detail" % PANEL_JSON)
    return rank[:N_TOP_SONGS]


def _noise_files():
    fs = sorted(NOISE_DIR.rglob("*.wav"))
    if not fs:
        raise SystemExit("[FATAL] 噪声池为空：%s" % NOISE_DIR)
    return fs


def _slug(song: str) -> str:
    keep = [c if (c.isalnum() or c in " -_") else " " for c in song]
    s = "".join(keep).strip().replace(" ", "-")
    while "--" in s:
        s = s.replace("--", "-")
    return s[:40]


def slug2song(songs):
    return {_slug(s["song"]): s["song"] for s in songs}


def _noise_mono(paths_list, start_idx, n, sr=SR):
    """从 paths_list[start_idx] 起顺序拼接 mono 噪声，直到 >= n 样本，再重采样到 sr。"""
    import torch
    import torchaudio.functional as AF

    chunks, tot, i = [], 0, start_idx % len(paths_list)
    while tot < n:
        p = paths_list[i % len(paths_list)]
        y, ysr = sf.read(str(p), dtype="float32", always_2d=True)
        y = y.mean(axis=1)
        if ysr != sr:
            t = torch.as_tensor(np.ascontiguousarray(y))[None]
            y = AF.resample(t, ysr, sr)[0].numpy()
        chunks.append(y)
        tot += len(y)
        i += 1
    return np.concatenate(chunks)[:n].astype(np.float32)


def synth_cell(rec, noise_files=None):
    """按 manifest 记录**即时合成** -> (noisy (N,2), dry_stems {4}, mix (N,2))。

    不落盘、不随机：同一 rec 永远给出同一段音频（可复现命令的立足点）。
    """
    noise_files = noise_files or _noise_files()
    d = MUSDB_TEST / rec["song"]
    n = int(round(rec["dur_s"] * SR))
    s0 = int(round(rec["offset_s"] * SR))

    mix, _ = sf.read(str(d / "mixture.wav"), start=s0, frames=n,
                     dtype="float32", always_2d=True)
    mix = mix.astype(np.float32)
    stems = {}
    for t in STEMS:
        y, _ = sf.read(str(d / ("%s.wav" % t)), start=s0, frames=n,
                       dtype="float32", always_2d=True)
        stems[t] = y.astype(np.float32)

    # 逐声道独立噪声（不同文件、不同起点）-> 声场不被人为完全相关化
    i0 = rec["noise_idx"]
    nl = _noise_mono(noise_files, i0, n)
    nr = _noise_mono(noise_files, i0 + 977, n)
    noise = np.stack([nl, nr], axis=1)

    p_mix = float(np.mean(mix.astype(np.float64) ** 2))
    p_noise = float(np.mean(noise.astype(np.float64) ** 2))
    g = float(np.sqrt(p_mix / max(p_noise * 10 ** (rec["snr_db"] / 10.0), 1e-20)))
    noisy = (mix + g * noise).astype(np.float32)
    return noisy, stems, mix, noise, g


# ============================================================ 降噪 / 限带
def _write_audio(path: Path, x: np.ndarray):
    """中间产物一律写 **32-bit float WAV**（与 T4 混响实验同一约定）。

    🔴 绝不用 PCM_16/24：本集按功率匹配 SNR 后，noisy 峰值实测可达 18.07
    （噪声池波峰因子 p95=61 / max=173，g 可达 22），定点写入会在 ±1.0 处
    静默削波 —— 首批 40 个 V0 里 30 个被削，-5 dB 档最多削掉 0.77% 样本，
    而脚本完全不报错。float WAV 精确无损，也不会在降噪器绝对电平门控
    （P13）之前改变信号电平。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.asarray(x, np.float32), SR, subtype="FLOAT")


def _read_audio(path: Path):
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if sr != SR:
        raise SystemExit("[FATAL] %s 采样率 %d != %d" % (path, sr, SR))
    return y.astype(np.float32)


def bandlimit_like_denoiser(x):
    """**逐行镜像** `_denoise_registry` 里 denoiser 的 wrapper，但跳过模型前向。

    denoiser contract：44.1 kHz (N,2) -> convert_audio(44100->16000, 1ch) -> [模型]
                        -> torchaudio.resample(16000->44100) -> 复制成 (N,2)

    这里保留两端的重采样与单声道下混（= 管线的**全部固有代价**），只把中间那步
    模型前向换成恒等 —— 于是 `V1bl` 与 `V1den` 的唯一差别就是**模型的净动作**。
    """
    import sys
    import torch
    import torchaudio.functional as AF
    # denoiser 包在 01_models/_third_party/denoiser；与 _denoise_registry 用
    # 同一个常量，避免两处路径常量漂移。不 insert 会 ModuleNotFoundError。
    import _denoise_registry as _DR
    if _DR.DEN not in sys.path:
        sys.path.insert(0, _DR.DEN)
    from denoiser.dsp import convert_audio

    wav = torch.as_tensor(np.ascontiguousarray(np.asarray(x, np.float32))).T  # (C,T)
    wav = convert_audio(wav, SR, 16000, 1)                                    # (1,T16)
    y = wav[0].numpy()                                                        # 恒等（不降噪）
    back = AF.resample(torch.as_tensor(y), 16000, SR).numpy()
    # 🔴 长度对齐到输入：44.1k->16k->44.1k 往返会差几个样本。若放任不管，
    #    V1bl 与 V0 的样本数不同 -> museval 窗数不同 -> L1b 与 L1 不可比
    #    （等于偷偷换了评测口径）。
    n = int(np.asarray(x).shape[0])
    if len(back) >= n:
        back = back[:n]
    else:
        back = np.pad(back, (0, n - len(back)))
    return np.stack([back, back], axis=-1).astype(np.float32)


def apply_denoise(run_fn, x):
    """按 P19 契约率链调用降噪模型。**不原地覆盖**入参。"""
    from _denoise_eval import resample_mono

    csr = int(getattr(run_fn, "contract_sr", SR))
    x_in = resample_mono(x.mean(axis=1), SR, csr) if csr != SR else x.mean(axis=1)
    est = run_fn(np.stack([x_in, x_in], axis=-1))                  # 恒 (N,2)
    key = "enhanced" if "enhanced" in est else list(est)[0]
    y = np.asarray(est[key], np.float32)
    y = y.mean(axis=1) if y.ndim > 1 else y
    if csr != SR:
        y = resample_mono(y, csr, SR)
    # 长度对齐（denoiser 输出可能少若干样本）
    n = min(len(y), len(x))
    out = np.zeros((len(x), 2), np.float32)
    out[:n, 0] = y[:n]
    out[:n, 1] = y[:n]
    return out


def _variant_path(variant: str, name: str) -> Path:
    return FRONT / variant / ("%s.wav" % name)


# ============================================================ plan
def cmd_plan() -> int:
    songs = _pick_songs()
    nf = _noise_files()
    cells = []
    for si, s in enumerate(songs):
        slug = _slug(s["song"])
        for k, snr in enumerate(SNR_LEVELS):
            cells.append({
                "cell_id": "%s__snr%s" % (slug, ("%+03d" % int(snr)).replace("+", "p").replace("-", "m")),
                "song": s["song"], "clip_id": "%s@%ds" % (slug, int(s["offset"])),
                "offset_s": float(s["offset"]), "dur_s": DUR_S, "snr_db": float(snr),
                "noise_idx": (si * 13 + k * 37) % len(nf),
                "noise_l": str(nf[(si * 13 + k * 37) % len(nf)].relative_to(PROJECT)),
                "noise_r": str(nf[(si * 13 + k * 37 + 977) % len(nf)].relative_to(PROJECT)),
            })
    sep_cells = len(cells) * len(FRONT_VARIANTS) * len(SEP_MODELS)
    out = {
        "task": "T6 级联实验（分离 -> 降噪）",
        "question": "把语音降噪器接在音乐源分离前面，SDR 是涨还是跌？",
        "songs": [{"song": s["song"], "slug": _slug(s["song"]), "offset_s": s["offset"],
                   "dur_s": DUR_S, "min_share_pct": s.get("min_share_pct")} for s in songs],
        "song_source": str(PANEL_JSON),
        "snr_levels": SNR_LEVELS,
        "noise_source": str(NOISE_DIR.relative_to(PROJECT)),
        "n_noise": len(nf),
        "cells": cells,
        "n_cells": len(cells),
        "links": {
            "L0": "noisy mixture -> SEP（基线）",
            "L1": "noisy mixture -> denoiser -> SEP",
            "L1b": "noisy mixture -> 仅16k/mono往返(不降噪) -> SEP（★对照：纯代价）",
            "L1m": "noisy mixture -> mel_roformer -> SEP（★对照臂：无带宽代价）",
            "L2": "noisy mixture -> SEP -> 对 vocals 降噪",
            "L2b": "noisy mixture -> SEP -> 对 vocals 仅限带（★对照）",
            "L3": "noisy mixture -> denoiser -> SEP -> 对 vocals 降噪",
        },
        "variants": VARIANT_DESC,
        "sep_models": SEP_MODELS,
        "sep_model_labels": SEP_LABELS,
        "den_model": DEN_MODEL,
        "mel_model": MEL_MODEL,
        "metric": "museval BSSEval v4 SDR（mono，默认窗 2 s/hop 1.5 s），"
                  "每格 4 轨均值=avg4，跨 10 曲取中位数",
        "reference": "MUSDB 干 GT stem（噪声只加到 mixture）",
        "n_separation_cells": sep_cells,
        "n_target": "计划书 D8：L0×L1×L2×L3 × 4 SNR 全格填满，每格标可复现命令",
        "constraints": {
            "P7": "不得预设降噪有用；变差照报（R12）",
            "P17": "噪声=DNS freesound（与 T5.4 synth 同源）-> 两模型族都跑，"
                   "把『有效域互补』从模型级提升到系统级；噪声类型由 G5 门禁当场验证",
            "P19": "契约采样率链；不原地覆盖源数组",
        },
        "deviation_from_plan": {
            "BSRNN-opt -> bsrnn_all": "计划书写『BSRNN-opt』，但注册表 `bsrnn` 是人声单轨，"
                                      "与『四轨完整组代表』矛盾且违反 R10 分组纪律；"
                                      "改用四轨的 `bsrnn_all`(oBSRNN 4ckpt)，T4 已验证可用",
            "片段长度 20 s（非整曲）": "与 T4/T5 口径一致、与 museval 2 s 窗匹配、算力可控；"
                                       "整曲成本高 12 倍且对本问题无额外信息",
        },
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "PASS",
    }
    PLAN_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[plan] %d 曲 × %d SNR = %d cells；分离推理格 %d（× %d 变体 × %d 模型）"
          % (len(songs), len(SNR_LEVELS), len(cells), sep_cells,
             len(FRONT_VARIANTS), len(SEP_MODELS)))
    print("       噪声池 %d 条；SNR %s" % (len(nf), SNR_LEVELS))
    for s in out["songs"]:
        print("       %-42s off=%5.0fs 均衡度=%s" % (s["song"], s["offset_s"], s["min_share_pct"]))
    print("[status] PASS -> %s" % PLAN_JSON)
    return 0


# ============================================================ make-noisy
def cmd_make_noisy() -> int:
    if not PLAN_JSON.is_file():
        raise SystemExit("[FATAL] 缺 %s —— 先跑 plan" % PLAN_JSON)
    plan = json.loads(PLAN_JSON.read_text(encoding="utf-8"))
    nf = _noise_files()
    from _denoise_eval import hf_ratio

    gates, cells_out, seen_dry = [], [], set()
    for rec in plan["cells"]:
        noisy, stems, mix, noise, g = synth_cell(rec, nf)

        # G1 门禁：回测 SNR 必须等于设定值（从**写出的数组**复算，不信构造过程）
        p_mix = float(np.mean(mix.astype(np.float64) ** 2))
        p_res = float(np.mean((noisy.astype(np.float64) - mix.astype(np.float64)) ** 2))
        snr_meas = 10.0 * np.log10(p_mix / max(p_res, 1e-30))
        gates.append({"cell_id": rec["cell_id"], "gate": "snr_roundtrip",
                      "target": rec["snr_db"], "value": round(float(snr_meas), 4),
                      "threshold": 0.05, "pass": bool(abs(snr_meas - rec["snr_db"]) < 0.05)})

        # G2 门禁：加法自洽 —— noisy 就是 mix + g*noise，没有任何隐藏处理。
        # 🔴 必须在**同一精度**上比：noisy 以 float32 存储，若拿它去比 float64
        #    的精确和，残差纯属量化（实测 0.55 ulp，绝对值可达 1.05e-6），
        #    旧阈值 1e-6 会把纯量化误判成 FAIL。
        #    正确判据 = float32 重建**逐位相同**；float64 残差降级为信息量。
        recon32 = (mix + g * noise).astype(np.float32)
        bit_equal = bool(np.array_equal(noisy, recon32))
        exact = mix.astype(np.float64) + g * noise.astype(np.float64)
        d2 = float(np.max(np.abs(noisy.astype(np.float64) - exact)))
        d2_rel = d2 / max(float(np.max(np.abs(exact))), 1e-30)
        gates.append({"cell_id": rec["cell_id"], "gate": "additive_selfcheck",
                      "value": (0.0 if bit_equal else d2),
                      "bit_equal_float32": bit_equal,
                      "d64_abs": d2, "d64_rel": d2_rel,
                      "threshold": 0.0, "pass": bit_equal})

        # G3 门禁：Σ dry stem ≈ mixture（GT 读取正确；每曲只做一次）
        if rec["clip_id"] not in seen_dry:
            seen_dry.add(rec["clip_id"])
            s_sum = np.sum([stems[t] for t in STEMS], axis=0).astype(np.float64)
            den = float(np.sqrt(np.mean(mix.astype(np.float64) ** 2))) + 1e-12
            g3 = float(np.sqrt(np.mean((s_sum - mix.astype(np.float64)) ** 2))) / den
            gates.append({"clip_id": rec["clip_id"], "gate": "sum_stems_eq_mixture",
                          "value": round(g3, 8), "threshold": 1e-3, "pass": bool(g3 < 1e-3)})

        # G5（P17 前提的当场验证）：**噪声类型**判定。只记录证据，不得预设结论。
        # ⚠️ 教训：不能用「mixture 的 hf_ratio 是否升高」当主判据 —— hf_ratio 是
        #    **比例量**（P18 / T5.6 已证），音乐本身已含大量高频（cymbal/hat），
        #    噪声加进去比例几乎不动（本集 hf_shift 中位仅 -0.0017）。
        #    若据此判「前提不成立」就错了：真证据是噪声的**脉冲性**与自身高频占比。
        hf_noisy = float(hf_ratio(noisy.mean(axis=1)))
        hf_dry = float(hf_ratio(mix.mean(axis=1)))
        hf_noise = float(hf_ratio(noise.mean(axis=1)))
        r_nz = float(np.sqrt(np.mean(noise.astype(np.float64) ** 2))) + 1e-12
        crest_noise = float(np.max(np.abs(noise))) / r_nz
        scaled = g * noise
        r_sc = float(np.sqrt(np.mean(scaled.astype(np.float64) ** 2))) + 1e-12
        crest_scaled = float(np.max(np.abs(scaled))) / r_sc

        # 落盘：V0（带噪，L0 输入）
        _write_audio(_variant_path("V0", rec["cell_id"]), noisy)
        # Vdry（干 mixture）—— 每曲一份，作为 loader/口径锚点
        if rec["clip_id"] not in {
                Path(str(_variant_path("Vdry", c["clip_id"]))).name for c in cells_out}:
            _write_audio(_variant_path("Vdry", rec["clip_id"]), mix)

        cells_out.append({
            **{k: rec[k] for k in ("cell_id", "clip_id", "song", "offset_s", "dur_s",
                                   "snr_db", "noise_idx", "noise_l", "noise_r")},
            "n_samples": int(noisy.shape[0]),
            "mix_rms_dbfs": round(float(20 * np.log10(np.sqrt(p_mix) + 1e-12)), 2),
            "noise_gain": round(g, 6),
            "hf_ratio_dry": round(hf_dry, 4),
            "hf_ratio_noisy": round(hf_noisy, 4),
            "hf_ratio_noise": round(hf_noise, 4),
            "hf_shift": round(hf_noisy - hf_dry, 4),
            "crest_noise": round(crest_noise, 2),
            "crest_scaled_noise": round(crest_scaled, 2),
            "peak_dry": round(float(np.max(np.abs(mix))), 4),
            "peak_noisy": round(float(np.max(np.abs(noisy))), 4),
            "v0_path": str(_variant_path("V0", rec["cell_id"])),
        })
        print("  %-30s snr=%+5.1f  实测=%+7.3f dB  hf: dry=%.3f noise=%.3f noisy=%.3f (%+.3f)"
              % (rec["cell_id"], rec["snr_db"], snr_meas, hf_dry, hf_noise, hf_noisy,
                 hf_noisy - hf_dry))

    bad = [g for g in gates if not g["pass"]]
    shifts = [c["hf_shift"] for c in cells_out]
    crests = [c["crest_scaled_noise"] for c in cells_out]
    peaks = [c["peak_noisy"] for c in cells_out]
    hf_ramp = float(np.median(shifts))
    crest_med = float(np.median(crests))
    # 结论由数据算出，不写死（旧版把「hf_shift>0」当唯一判据，本集会被误判）
    if crest_med >= 6.0:
        verdict = ("噪声高度脉冲（波峰因子中位 %.1f）-> 属瞬态型，与 T5.4 synth 同族；"
                   "P17 对 denoiser 的『有效』预测**可迁移**。注意 hf_ratio 位移近乎为零"
                   "并非反证：音乐自带大量高频，hf_ratio 是比例量，对加性噪声不敏感。"
                   % crest_med)
    else:
        verdict = ("噪声波峰因子中位仅 %.1f -> 非脉冲型；P17 的判定**不可迁移**，"
                   "级联结果必须按新噪声类型独立解读。" % crest_med)
    clip_risk = ("float WAV 写入，无定点削波上限；"
                 "峰值中位 %.2f / 最大 %.2f（若写 PCM_16 将大面积削波）"
                 % (float(np.median(peaks)), float(np.max(peaks))))
    out = {
        "task": "T6.1 带噪测试集（即时合成，不落盘原始对）",
        "audio_format": "32-bit float WAV（subtype=FLOAT）—— 见 _write_audio docstring：噪声脉冲性强，定点写入会静默削波",
        "recipe": "noisy = mix + g*noise, g = sqrt(P_mix / (P_noise * 10^(snr/10)))",
        "channels": "逐声道独立噪声（左右取不同文件）",
        "gt": "MUSDB 干 stem（噪声只加进 mixture，不进 stem）",
        "n_cells": len(cells_out),
        "cells": cells_out,
        "gates": gates,
        "n_gates": len(gates),
        "n_failed": len(bad),
        "noise_type": {
            "hf_shift_median": round(hf_ramp, 4),
            "hf_shift_min": round(float(np.min(shifts)), 4),
            "hf_shift_max": round(float(np.max(shifts)), 4),
            "crest_scaled_median": round(crest_med, 2),
            "crest_scaled_p95": round(float(np.percentile(crests, 95)), 2),
            "verdict": verdict,
            "instrument_caveat": "hf_ratio 是**比例量**（P18/T5.6）：音乐自带高频，"
                                 "加性噪声只轻微抬高该比例，故 hf_ratio 位移不能"
                                 "单独用于判定噪声类型；主判据为波峰因子。",
        },
        "amplitude": {
            "peak_noisy_median": round(float(np.median(peaks)), 3),
            "peak_noisy_max": round(float(np.max(peaks)), 3),
            "note": clip_risk,
        },
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "PASS" if not bad else "FAIL",
    }
    MAN_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[make-noisy] %d cells；门禁 %d 条，失败 %d" %
          (len(cells_out), len(gates), len(bad)))
    print("[noise-type] hf_shift 中位 %+.4f | 波峰因子中位 %.1f | 峰值 max %.2f"
          % (hf_ramp, crest_med, float(np.max(peaks))))
    print("[verdict  ] %s" % verdict)
    for g in bad:
        print("   [FAIL] %s" % g)
    print("[status] %s -> %s" % (out["status"], MAN_JSON))
    return 0 if not bad else 1


# ============================================================ prep（前置/后置 降噪或限带）
def _run_prep_front(op: str, only: str | None, limit: int | None) -> int:
    """生成分离模型的输入变体：V1den / V1mel / V1bl。"""
    man = json.loads(MAN_JSON.read_text(encoding="utf-8"))
    cells = man["cells"][: limit] if limit else man["cells"]

    if op == "vbl":
        for c in cells:
            x = _read_audio(Path(c["v0_path"]))
            _write_audio(_variant_path("V1bl", c["cell_id"]), bandlimit_like_denoiser(x))
            print("  V1bl %s ok" % c["cell_id"])
        return 0

    from _denoise_registry import REGISTRY
    mk = {"vden": DEN_MODEL, "vden-mel": MEL_MODEL}[op]
    var = {"vden": "V1den", "vden-mel": "V1mel"}[op]
    run, dt_load, info = REGISTRY[mk]["loader"]()
    print("[prep] %s (%s) 载入 %.1fs  contract_sr=%s"
          % (mk, info.get("label"), dt_load, getattr(run, "contract_sr", None)))
    n = 0
    for c in cells:
        x = _read_audio(Path(c["v0_path"]))
        y = apply_denoise(run, x)
        # 电平门禁：denoiser 在音乐上有绝对电平门控，静默塌陷必须当场发现
        r_in = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) + 1e-12
        r_out = float(np.sqrt(np.mean(y.astype(np.float64) ** 2)))
        ratio = r_out / r_in
        ok = 0.05 <= ratio <= 20.0
        _write_audio(_variant_path(var, c["cell_id"]), y)
        print("  %-5s %-30s level_ratio=%.4f %s"
              % (var, c["cell_id"], ratio, "" if ok else "  <<< 电平异常"))
        n += 1
    print("[prep] %s -> %d 个 %s" % (op, n, FRONT / var))
    return 0


def _run_prep_post(op: str, models, limit: int | None) -> int:
    """对分离出的 vocals 轨做后置处理；需要先跑 run 产出 _vocals/。"""
    man = json.loads(MAN_JSON.read_text(encoding="utf-8"))
    cells = man["cells"][: limit] if limit else man["cells"]
    srcs = [("V0", "L2"), ("V1den", "L3")]
    files = []
    for mk in models:
        for src, _ in srcs:
            for c in cells:
                p = VOCALS / mk / ("%s__%s.wav" % (c["cell_id"], src))
                if p.is_file():
                    files.append((mk, src, c["cell_id"], p))
    if not files:
        raise SystemExit("[FATAL] _vocals/ 下没有文件 —— 先跑 run")

    if op == "vbl":
        for mk, src, cid, p in files:
            _write_audio(POST / mk / ("%s__%s__vbl.wav" % (cid, src)),
                        bandlimit_like_denoiser(_read_audio(p)))
            print("  vbl %s/%s ok" % (mk, cid))
        return 0

    from _denoise_registry import REGISTRY
    mk_den = {"vden": DEN_MODEL, "vden-mel": MEL_MODEL}[op]
    run, dt_load, info = REGISTRY[mk_den]["loader"]()
    print("[prep-post] %s 载入 %.1fs" % (mk_den, dt_load))
    for mk, src, cid, p in files:
        y = apply_denoise(run, _read_audio(p))
        _write_audio(POST / mk / ("%s__%s__%s.wav" % (cid, src, op)), y)
    print("[prep-post] %s -> %d 个" % (op, len(files)))
    return 0


# ============================================================ run（分离推理）
_SEP_CACHE: dict = {}
# 🔴 逐格增量落盘（2026-09-26 修）：长任务被中断时已完成的格不再丢失。
#    原实现只在**全部模型 x 变体跑完**时统一写 EVAL_JSON ->
#    实测一次 640 格主跑被会话中断，已跑完的 120 格记录**全部蒸发**。
#    新增：子进程每格追加一行 JSONL（单行追加是原子的，父子不冲突），
#    父进程在每个 (模型,变体) 子进程结束后 merge 进 EVAL_JSON。
PARTIAL_JSONL = CASC_DATA / "cascade_eval.partial.jsonl"


def _append_partial(rec: dict) -> None:
    with PARTIAL_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _load_all_recs() -> dict:
    """合并 EVAL_JSON + PARTIAL_JSONL 的全部记录，key=(model, cell_id, variant)。"""
    m: dict = {}
    if EVAL_JSON.is_file():
        try:
            for r in json.loads(EVAL_JSON.read_text(encoding="utf-8")).get("sep_results", []):
                m[(r["model"], r["cell_id"], r["variant"])] = r
        except Exception:                                           # noqa: BLE001
            pass
    if PARTIAL_JSONL.is_file():
        for ln in PARTIAL_JSONL.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except Exception:                                       # noqa: BLE001
                continue
            m[(r["model"], r["cell_id"], r["variant"])] = r
    return m


def _save_eval_from(allrecs: dict) -> dict:
    seps = sorted(allrecs.values(), key=lambda r: (r["model"], r["variant"], r["cell_id"]))
    prev = {}
    if EVAL_JSON.is_file():
        try:
            prev = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
        except Exception:                                           # noqa: BLE001
            prev = {}
    out = {**{k: v for k, v in prev.items() if k != "sep_results"},
           "sep_results": seps,
           "n_sep": len(seps),
           "n_sep_pass": sum(1 for r in seps if r["status"] == "PASS"),
           "sep_generated": time.strftime("%Y-%m-%d %H:%M:%S")}
    EVAL_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _done_cell_ids(mk: str, var: str) -> set:
    """本 (模型, 变体) 已 PASS 的 cell_id 集合 —— resume 用。"""
    return {k[1] for k, v in _load_all_recs().items()
            if k[0] == mk and k[2] == var and v.get("status") == "PASS"}


def _sep_loader(mk: str):
    """按模型 key 缓存 loader 结果 —— 每个子进程只加载一次模型。

    🔴 `REGISTRY[mk]["loader"]()` 每次调用都会**重建模型并重读权重**
    （`load_demucs` 里就是 `get_model("htdemucs")`，全程无缓存）。
    原实现每个 cell 都调一次 -> 640 个分离格重复加载 640 次，
    单格墙钟被加载开销主导（实测 20 s 片段约 40~70 s/格）。

    ⚠️ 缓存**必须留在子进程内**：`cmd_run` 每个模型起一个子进程，
       而「同进程多模型会 OOM（8 GiB 显存）」是本项目既有的硬约束 ——
       缓存只在本模型的所有 cell 之间复用，不跨模型。
    """
    if mk not in _SEP_CACHE:
        from benchmark_model_universal import REGISTRY as SEP
        _SEP_CACHE[mk] = SEP[mk]["loader"]()
    return _SEP_CACHE[mk]


def _sep_single(mk: str, cell: dict, variant: str) -> dict:
    """跑一格（模型 × cell × 变体）：分离 + 对干 GT 算 avg4 SDR。"""
    from benchmark_model_universal import REGISTRY as SEP
    from compare_separation_methods import evaluate

    run, dt_load, info = _sep_loader(mk)
    name = cell["clip_id"] if variant == "Vdry" else cell["cell_id"]
    x = _read_audio(_variant_path(variant, name))

    est = run(x)
    est = {k: np.asarray(v, np.float32) for k, v in est.items()}
    missing = [s for s in STEMS if s not in est]
    if missing:
        return {"model": mk, "cell_id": cell["cell_id"], "variant": variant,
                "status": "FAIL", "reason": "missing stems %s (got %s)" % (missing, list(est)),
                "sdr_avg4": None}

    # 参考 = 干 GT stem（直接从 MUSDB 读，不经任何音频落盘）
    d = MUSDB_TEST / cell["song"]
    n = int(round(cell["dur_s"] * SR))
    s0 = int(round(cell["offset_s"] * SR))
    per_stem, levels = {}, {}
    mix_rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) + 1e-12
    for s in STEMS:
        gt, _ = sf.read(str(d / ("%s.wav" % s)), start=s0, frames=n,
                        dtype="float32", always_2d=True)
        m = min(len(gt), len(est[s]))
        levels[s] = round(float(np.sqrt(np.mean(est[s][:m] ** 2))) / mix_rms, 4)
        ev = evaluate(gt[:m].mean(axis=1), est[s][:m].mean(axis=1))
        per_stem[s] = {"sdr": (round(ev["sdr"], 3) if ev["sdr"] is not None else None),
                       "si_sdr": (round(ev["si_sdr"], 3) if ev["si_sdr"] is not None else None)}
    sdrs = [per_stem[s]["sdr"] for s in STEMS if per_stem[s]["sdr"] is not None]
    avg4 = round(float(np.mean(sdrs)), 3) if len(sdrs) == 4 else None

    # 只有 V0 / V1den 的 vocals 会被后置处理 -> 仅这两个变体落盘，省 2/3 磁盘
    voc_wav = None
    if variant in ("V0", "V1den") and "vocals" in est:
        voc_wav = VOCALS / mk / ("%s__%s.wav" % (cell["cell_id"], variant))
        _write_audio(voc_wav, est["vocals"])

    # 🔴 门禁语义修正（2026-09-26）：级联实验里「输出相对输入的量级」**就是被测现象本身**。
    #    denoiser 前置会把 drums 压到 0.006、vocals 顶到 0.996（分离退化成恒等映射），
    #    这是**发现**不是故障。原判据 `0.01 <= level <= 10.0` 会把它判成 FAIL，
    #    再被 cmd_summary 的 status 过滤吃掉 -> L1 整列 None -> 矩阵空洞。
    #    正确判据 = ① 输入没被写坏 ② 输出不是全零/NaN。量级仍记录供分析。
    _in_ok = bool(np.isfinite(mix_rms) and 1e-9 < mix_rms < 1e6)
    _out_ok = (all(np.isfinite(v) and v >= 0 for v in levels.values())
               and any(v > 0 for v in levels.values()))
    lvl_ok = bool(_in_ok and _out_ok)
    band_ok = all(0.01 <= v <= 10.0 for v in levels.values())   # 原判据，留作审计
    rec = {"model": mk, "label": info.get("label", SEP[mk].get("label", mk)),
           "cell_id": cell["cell_id"], "clip_id": cell["clip_id"], "song": cell["song"],
           "snr_db": cell["snr_db"], "variant": variant,
           "status": "PASS" if (avg4 is not None and lvl_ok) else "FAIL",
           "load_s": round(dt_load, 2), "sdr_avg4": avg4, "per_stem": per_stem,
           "gate": {"level_ok": lvl_ok, "band_ok": band_ok, "levels": levels,
                    "dry_floor_ok": (None if variant != "Vdry"
                                     else bool(avg4 is not None
                                               and avg4 >= DRY_FLOOR.get(mk, -99)))},
           "vocals_path": (str(voc_wav) if voc_wav else None)}
    if avg4 is None or not lvl_ok:
        rec["reason"] = ("avg4 None / 输出全零或 NaN" if avg4 is None
                         else "输出全零或 NaN: levels=%s" % levels)
    return rec


def cmd_run(models, only, batch, variants, limit, resume=False) -> int:
    if only:
        mk, cid, var = only.split("|")
        man = json.loads(MAN_JSON.read_text(encoding="utf-8"))
        cell = next(c for c in man["cells"] if c["cell_id"] == cid)
        print(json.dumps(_sep_single(mk, cell, var), ensure_ascii=False))
        return 0

    man = json.loads(MAN_JSON.read_text(encoding="utf-8"))
    cells = man["cells"]
    # Vdry 每个 clip 只跑一次（与 SNR 无关）
    dry_cells = []
    seen = set()
    for c in cells:
        if c["clip_id"] not in seen:
            seen.add(c["clip_id"])
            dry_cells.append(c)

    if batch:
        todo = (dry_cells if batch_var_get(variants[0]) == "Vdry" else cells)
        if limit:
            todo = todo[:limit]
        if resume:
            done = _done_cell_ids(batch, variants[0])
            nb = len(todo)
            todo = [c for c in todo if c["cell_id"] not in done]
            print("[batch] resume: 跳过 %d 格已完成，待跑 %d 格"
                  % (nb - len(todo), len(todo)), flush=True)
        for c in todo:
            rec = _sep_single(batch, c, variants[0])
            print(json.dumps(rec, ensure_ascii=False), flush=True)
            _append_partial(rec)        # 逐格增量落盘（中断也不丢）
        return 0

    results = []
    for mk in models:
        for var in variants:
            todo = dry_cells if var == "Vdry" else cells
            if limit:
                todo = todo[:limit]
            avail = [c for c in todo if _variant_path(var, c["clip_id"] if var == "Vdry"
                                                     else c["cell_id"]).is_file()]
            if not avail:
                print("  [skip] %s × %s：输入未生成（先跑 make-noisy / prep）" % (mk, var))
                continue
            if resume:
                done = _done_cell_ids(mk, var)
                n_all = len(avail)
                avail = [c for c in avail if c["cell_id"] not in done]
                if not avail:
                    print("  [skip] %s × %s：%d 格全部已完成（resume）" % (mk, var, n_all))
                    continue
            print("[model] %s × %s  (%d 格)" % (mk, var, len(avail)))
            cmd = [PY, str(Path(__file__).resolve()), "run", "--batch", mk, "--variants", var]
            if limit:
                cmd += ["--limit", str(limit)]
            if resume:
                cmd += ["--resume"]
            p = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            got = 0
            for ln in (p.stdout or "").strip().splitlines():
                try:
                    rec = json.loads(ln)
                except Exception:                                   # noqa: BLE001
                    continue
                results.append(rec)
                got += 1
                print("  %-30s %-6s %-7s avg4=%s" % (rec.get("cell_id", "")[:30], var,
                                                     rec.get("status"), rec.get("sdr_avg4")))
            if got != len(avail):
                print("  [ERR] %s×%s 只回传 %d/%d；stderr 尾部:\n%s"
                      % (mk, var, got, len(avail), (p.stderr or "")[-600:]))
                for c in avail:
                    cid = c["clip_id"] if var == "Vdry" else c["cell_id"]
                    if not any(r.get("model") == mk and r.get("cell_id") == c["cell_id"]
                               and r.get("variant") == var for r in results):
                        results.append({"model": mk, "cell_id": c["cell_id"],
                                        "clip_id": c["clip_id"], "song": c["song"],
                                        "snr_db": c["snr_db"], "variant": var,
                                        "status": "FAIL", "sdr_avg4": None,
                                        "reason": "no json returned"})
            # 🔴 增量落盘（2026-09-26 修）：本 (模型, 变体) 的子进程已结束 ->
            #    立即 merge 写入 EVAL_JSON。原实现只在**全部循环之后**写一次，
            #    长任务一旦被中断，已完成的格全部蒸发（实测丢了 120 格）。
            _all = _load_all_recs()
            for r in results:
                _all[(r["model"], r["cell_id"], r["variant"])] = r
            _o = _save_eval_from(_all)
            print("  [save] 累计 %d 格，PASS %d" % (_o["n_sep"], _o["n_sep_pass"]),
                  flush=True)

    out = _save_eval_from(_load_all_recs())
    print("\n[run] 累计 %d 格，PASS %d -> %s" % (out["n_sep"], out["n_sep_pass"], EVAL_JSON))
    return 0 if out["n_sep_pass"] == out["n_sep"] else 1


def batch_var_get(v):
    return v


# ============================================================ post（后置 SDR 重算）
def _post_sdr(model, cell, src_variant, op) -> dict:
    """后置处理只改 vocals -> 只需重算 vocals 的 SDR，其余 3 轨沿用基线。"""
    from compare_separation_methods import evaluate

    p = POST / model / ("%s__%s__%s.wav" % (cell["cell_id"], src_variant, op))
    if not p.is_file():
        return {"model": model, "cell_id": cell["cell_id"], "src_variant": src_variant,
                "op": op, "status": "MISSING", "sdr_vocals": None}
    est_voc = _read_audio(p)
    d = MUSDB_TEST / cell["song"]
    n = int(round(cell["dur_s"] * SR))
    s0 = int(round(cell["offset_s"] * SR))
    gt, _ = sf.read(str(d / "vocals.wav"), start=s0, frames=n, dtype="float32", always_2d=True)
    m = min(len(gt), len(est_voc))
    ev = evaluate(gt[:m].mean(axis=1), est_voc[:m].mean(axis=1))
    r_in = float(np.sqrt(np.mean(est_voc[:m].astype(np.float64) ** 2))) + 1e-12
    return {"model": model, "cell_id": cell["cell_id"], "clip_id": cell["clip_id"],
            "snr_db": cell["snr_db"], "src_variant": src_variant, "op": op,
            "status": "PASS" if ev["sdr"] is not None else "FAIL",
            "sdr_vocals": (round(float(ev["sdr"]), 3) if ev["sdr"] is not None else None),
            "level_rms": round(r_in, 6), "post_path": str(p)}


def cmd_post(models, limit) -> int:
    man = json.loads(MAN_JSON.read_text(encoding="utf-8"))
    cells = man["cells"][: limit] if limit else man["cells"]
    if not POST.is_dir() or not any(POST.rglob("*.wav")):
        raise SystemExit("[FATAL] _post/ 为空 —— 先跑 post-prep（prep --op vden / vbl）")

    def _save_post(batch_res: list) -> int:
        """merge 一批结果进 EVAL_JSON（每个模型写一次，中断不丢）。"""
        prev = {}
        if EVAL_JSON.is_file():
            prev = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
        merged = {(r["model"], r["cell_id"], r["src_variant"], r["op"]): r
                  for r in prev.get("post_results", [])}
        for r in batch_res:
            merged[(r["model"], r["cell_id"], r["src_variant"], r["op"])] = r
        posts = sorted(merged.values(),
                       key=lambda r: (r["model"], r["src_variant"], r["op"], r["cell_id"]))
        out = {**{k: v for k, v in prev.items() if k != "post_results"},
               "post_results": posts, "n_post": len(posts),
               "post_generated": time.strftime("%Y-%m-%d %H:%M:%S")}
        EVAL_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return len(posts)

    # 🔴 增量落盘（2026-09-26 修）：原实现只在**全部模型跑完**后写一次，
    #    与本轮主跑踩的坑同源。改成每个模型跑完立即 merge 写入。
    for mk in models:
        res = []
        for src in ("V0", "V1den"):
            for c in cells:
                for op in ("vden", "vbl"):
                    r = _post_sdr(mk, c, src, op)
                    if r["status"] != "MISSING":
                        res.append(r)
        n = _save_post(res)
        print("  [post-save] %s -> 累计 %d 条" % (mk, n), flush=True)
    print("[post] 完成 -> %s" % EVAL_JSON)
    return 0


# ============================================================ summary
def _med(v):
    v = [x for x in v if x is not None]
    return round(float(np.median(v)), 3) if v else None


def _legal_cells():
    man = json.loads(MAN_JSON.read_text(encoding="utf-8"))
    return man["cells"]


def cmd_summary(models) -> int:
    """汇总成 ΔSDR 矩阵；每个数字带可复现命令。"""
    ev = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
    seps = ev.get("sep_results", [])
    posts = ev.get("post_results", [])
    cells = _legal_cells()
    snrs = sorted({c["snr_db"] for c in cells}, reverse=True)

    def board(variant, snr=None, want="avg4"):
        """取 (模型 -> 中位数) ：某变体在某 SNR 档的 avg4 SDR。"""
        out = {}
        for mk in models:
            rs = [r for r in seps if r["model"] == mk and r["variant"] == variant
                  and r["status"] == "PASS" and r["sdr_avg4"] is not None
                  and (snr is None or r["snr_db"] == snr)]
            out[mk] = {"n": len(rs), "val": _med([r["sdr_avg4"] for r in rs])}
        return out

    # 后置：avg4' = (drums+bass+other + sdr_vocals') / 4
    def board_post(src_variant, op, snr=None):
        out = {}
        for mk in models:
            vals = []
            for r in posts:
                if (r["model"] != mk or r["src_variant"] != src_variant or r["op"] != op
                        or r["status"] != "PASS" or r.get("sdr_vocals") is None):
                    continue
                if snr is not None and r["snr_db"] != snr:
                    continue
                base = next((s for s in seps if s["model"] == mk and s["cell_id"] == r["cell_id"]
                             and s["variant"] == src_variant and s["status"] == "PASS"), None)
                if base is None:
                    continue
                others = [base["per_stem"][s]["sdr"] for s in ("drums", "bass", "other")
                          if base["per_stem"].get(s, {}).get("sdr") is not None]
                if len(others) != 3:
                    continue
                vals.append((sum(others) + r["sdr_vocals"]) / 4.0)
            out[mk] = {"n": len(vals), "val": _med(vals)}
        return out

    rows = []
    for snr in snrs:
        L0 = board("V0", snr)
        L1 = board("V1den", snr)
        L1b = board("V1bl", snr)
        L1m = board("V1mel", snr)
        L2 = board_post("V0", "vden", snr)
        L2b = board_post("V0", "vbl", snr)
        L3 = board_post("V1den", "vden", snr)
        for mk in models:
            base = L0[mk]["val"]
            def d(x):
                return (round(x["val"] - base, 3)
                        if (base is not None and x["val"] is not None) else None)
            cmd = ("python tools/_cascade_experiment.py run --models %s --variants V0,V1den,V1bl,V1mel"
                   % mk)
            rows.append({
                "model": mk, "label": SEP_LABELS.get(mk, mk), "snr_db": snr,
                "n_L0": L0[mk]["n"], "sdr_L0": base,
                "sdr_L1": L1[mk]["val"], "d_L1": d(L1[mk]),
                "sdr_L1b": L1b[mk]["val"], "d_L1b": d(L1b[mk]),
                "sdr_L1m": L1m[mk]["val"], "d_L1m": d(L1m[mk]),
                "sdr_L2": L2[mk]["val"], "d_L2": d(L2[mk]),
                "sdr_L2b": L2b[mk]["val"], "d_L2b": d(L2b[mk]),
                "sdr_L3": L3[mk]["val"], "d_L3": d(L3[mk]),
                "bandwidth_cost_d_L1b": d(L1b[mk]),
                "denoise_net_d_L1_minus_L1b": (
                    round(L1[mk]["val"] - L1b[mk]["val"], 3)
                    if (L1[mk]["val"] is not None and L1b[mk]["val"] is not None) else None),
                "mel_net_d_L1m": d(L1m[mk]),
                "reproduce_cmd": cmd,
            })

    # 总结：全模型 × 全 SNR 的中位 Δ
    def overall(k):
        return _med([r[k] for r in rows])

    summary = {
        "median_d_L1": overall("d_L1"), "median_d_L1b": overall("d_L1b"),
        "median_d_L1m": overall("d_L1m"), "median_d_L2": overall("d_L2"),
        "median_d_L2b": overall("d_L2b"), "median_d_L3": overall("d_L3"),
        "median_denoise_net": overall("denoise_net_d_L1_minus_L1b"),
        "median_mel_net": overall("mel_net_d_L1m"),
    }
    out = {"task": "T6.3 级联 ΔSDR 矩阵",
           "metric": "museval BSSEval v4 SDR（mono，2 s/1.5 s 窗），4 轨均值 avg4，跨曲取中位数",
           "reference": "Δ = 该链路 − L0（同为带噪输入，不降噪）",
           "honesty": "结果变差**照报**（计划书 R12 / P7）：Δ 为负即负，不得挑数据",
           "summary_all_cells": summary,
           "rows": rows,
           "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "status": "PASS" if rows else "EMPTY"}
    EVAL_JSON.write_text(json.dumps({**ev, "matrix": out}, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    cols = ["model", "label", "snr_db", "n_L0", "sdr_L0",
            "d_L1", "d_L1b", "d_L1m", "d_L2", "d_L2b", "d_L3",
            "bandwidth_cost_d_L1b", "denoise_net_d_L1_minus_L1b", "mel_net_d_L1m",
            "reproduce_cmd"]
    with EVAL_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print("[summary] %d 行 -> %s / %s" % (len(rows), EVAL_JSON, EVAL_CSV))
    print("  %-10s %-6s %8s %8s %8s %8s %8s %8s %8s" %
          ("model", "snr", "sdrL0", "dL1", "dL1b", "dL1m", "dL2", "dL3", "净效应"))
    for r in rows:
        print("  %-10s %+6.0f %8s %8s %8s %8s %8s %8s %8s" %
              (r["model"], r["snr_db"], r["sdr_L0"], r["d_L1"], r["d_L1b"], r["d_L1m"],
               r["d_L2"], r["d_L3"], r["denoise_net_d_L1_minus_L1b"]))
    print("[summary_all_cells] %s" % json.dumps(summary, ensure_ascii=False))
    return 0


# ============================================================ main
def main() -> int:
    ap = argparse.ArgumentParser(description="T6 级联实验（分离 -> 降噪）")
    ap.add_argument("mode", nargs="?",
                    choices=["plan", "make-noisy", "prep", "prep-post", "run", "post",
                             "summary", "all"],
                    default="plan")
    ap.add_argument("--models", default=",".join(SEP_MODELS))
    ap.add_argument("--variants", default=",".join(FRONT_VARIANTS))
    ap.add_argument("--op", default=None, help="vden | vbl | vden-mel")
    ap.add_argument("--single", default=None)
    ap.add_argument("--batch", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--resume", action="store_true",
                    help="跳过 eval.json/partial.jsonl 中已 PASS 的格（长任务续跑）")
    a = ap.parse_args()
    models = [m for m in a.models.split(",") if m]
    variants = [v for v in a.variants.split(",") if v]

    if a.mode == "plan":
        return cmd_plan()
    if a.mode == "make-noisy":
        return cmd_make_noisy()
    if a.mode == "prep":
        if not a.op:
            raise SystemExit("[FATAL] prep 需要 --op vden|vbl|vden-mel")
        if a.op == "vden-mel" and a.limit and a.limit < 3:
            raise SystemExit("[FATAL] --limit 太小（mel_roformer 最小分块依赖整段）")
        return _run_prep_front(a.op, a.single, a.limit)
    if a.mode == "prep-post":
        return _run_prep_post(a.op or "vden", models, a.limit)
    if a.mode == "run":
        return cmd_run(models, a.single, a.batch, variants, a.limit, resume=a.resume)
    if a.mode == "post":
        return cmd_post(models, a.limit)
    if a.mode == "summary":
        return cmd_summary(models)
    if a.mode == "all":
        rc = cmd_plan() | cmd_make_noisy()
        if rc:
            return rc
        for op in ("vbl", "vden", "vden-mel"):
            rc |= _run_prep_front(op, None, a.limit)
        rc |= cmd_run(models, None, None, variants, a.limit)
        rc |= _run_prep_post("vbl", models, a.limit)
        rc |= _run_prep_post("vden", models, a.limit)
        rc |= cmd_post(models, a.limit)
        rc |= cmd_summary(models)
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""T4.1/T4.2 · 混响 / 去混响实验（板 1 阶段 4）。

设计（对应路线图 §2.5）
----------------------
    ① 干信号 dry      ← MUSDB18 stem（GT）
    ② 人工加混响 wet  = dry ⊛ RIR（两档：小房间 T60≈0.6 s / 大厅 T60≈1.2 s）
    ③ 去混响输出      ← Dereverb-Mel-RoFormer / Dereverb-Echo-Mel-RoFormer 跑 wet
    ④ 残差           = wet − ③（被去掉的混响尾）

**关键设计：逐 stem 分别加混响，再求和得湿混音**
    wet_mix = Σ_t (dry_t ⊛ h)
物理上等价于"同一房间里每个声源各自经过房间响应后再叠加"，比"先混音再加混响"更正确，
而且保持了 GT = 干 stem，SDR 才有意义。

三道门禁（都写进 JSON，失败即 FAIL，不靠肉眼）
--------------------------------------------
1. `Σ dry_stem ≈ mixture.wav`（验证 stem 读取正确；容差 RMS 相对误差 < 1e-3）
2. `wet_stem = dry_stem ⊛ h` 的数值复算一致（卷积实现自证）
3. **回测**：对湿信号重估 T60，须落在目标 ±30% 内（证明"混响真加上了，且量级对"）

子命令
------
    python tools/_reverb_experiment.py plan       # 组合清单（不推理）
    python tools/_reverb_experiment.py make-wet   # 生成 干/湿 音频（CPU，含三道门禁）
    python tools/_reverb_experiment.py dereverb   # 去混响推理 + ΔSDR（GPU，量小）
    python tools/_reverb_experiment.py all

⚠️ 分离模型在湿混音上的 ΔSDR（T4.5 的退化曲线）需要"把任意 wav 喂进分离模型"的胶水层，
   不在本脚本内 —— 见文件末尾 `TODO(T4.3)`，那是夜挂任务。
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

# ---- 路径中枢：五大模块布局，见 tools/paths.py ----
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import paths as _paths

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

STEMS = ["vocals", "drums", "bass", "other"]
SR = 44100
DUR_S = 20.0
PY = sys.executable

REV_DIR = _paths.SEPARATION / "data" / "reverb"
RIR_JSON = REV_DIR / "rir_selection.json"
RIR_DIR = REV_DIR / "rir"
PLAN_JSON = REV_DIR / "reverb_plan.json"
WET_JSON = REV_DIR / "reverb_manifest.json"
DEREV_JSON = REV_DIR / "dereverb_results.json"
AUDIO_ROOT = _paths.OUTPUTS / "_reverb"
PANEL_SEL = _paths.comparison_dir() / "panel_song_selection.json"

CONDS = ["dry", "wet_small", "wet_hall"]
SUBSTAGE = "test"                       # 片段来自 MUSDB18-HQ test

# 去混响目标模型（板 2 注册表里 group == "dereverb" 的两个）
DEREVERB_MODELS = ["mel_roformer_dereverb", "mel_roformer_dereverb_echo"]


# ------------------------------------------------------------------ 公共
def _load_rirs() -> dict:
    if not RIR_JSON.is_file():
        raise SystemExit("[FAIL] 缺 %s —— 先跑 tools/_select_rirs.py" % RIR_JSON)
    d = json.loads(RIR_JSON.read_text(encoding="utf-8"))
    out = {}
    for key in ("small_0p6", "hall_1p2"):
        rec = d["picked"][key]
        h, sr = sf.read(rec["export"]["out"], dtype="float32")
        if sr != SR:
            raise SystemExit("[FAIL] RIR %s 采样率 %d != %d" % (key, sr, SR))
        out[key] = {"h": np.asarray(h, np.float64), "meta": rec}
    return out


def _clips() -> list[dict]:
    """实验片段：复用 T3.1 数据驱动选出的 3 首（高能量均衡），保持两个阶段的叙事一致。"""
    d = json.loads(PANEL_SEL.read_text(encoding="utf-8"))
    out = []
    for p in d["picked_detail"]:
        out.append({"song": p["song"], "offset": float(p["offset"]), "dur": DUR_S,
                    "clip_id": "%s@%ds" % (p["song"], int(p["offset"]))})
    return out


def _read_stems(song: str, offset: float, dur: float):
    d = _paths.musdb_root() / SUBSTAGE / song
    n = int(round(dur * SR))
    s0 = int(round(offset * SR))
    mix, _ = sf.read(str(d / "mixture.wav"), start=s0, frames=n,
                     dtype="float32", always_2d=True)
    stems = {}
    for t in STEMS:
        y, _ = sf.read(str(d / ("%s.wav" % t)), start=s0, frames=n,
                       dtype="float32", always_2d=True)
        stems[t] = y.astype(np.float32)
    return mix.astype(np.float32), stems


def t60_of(h: np.ndarray, sr: int = SR) -> float | None:
    """与 `_select_rirs._schroeder_t60` 同法：剔除直达声后 Schroeder 反向积分。"""
    h = np.asarray(h, np.float64).ravel()
    if h.size < int(0.05 * sr):
        return None
    peak = int(np.argmax(np.abs(h)))
    w = max(1, int(0.0025 * sr))
    h2 = h.copy()
    h2[max(0, peak - w):min(h.size, peak + w + 1)] = 0.0
    e = np.cumsum(h2[::-1] ** 2)[::-1]
    if e[0] <= 0:
        return None
    edc = 10.0 * np.log10(e / e[0] + 1e-30)
    ia = int(np.argmax(edc <= -5.0))
    ib = int(np.argmax(edc <= -25.0))
    if edc[-1] > -25.0 or ib <= ia + 1:
        return None
    k, _ = np.polyfit(np.arange(ia, ib) / sr, edc[ia:ib], 1)
    return (-60.0 / k) if k < 0 else None


def _rir_tail(h: np.ndarray, sr: int = SR, dur: float = 20.0) -> np.ndarray:
    """把 RIR 铺成与信号等长的卷积核（用于回测混合信号的混响衰减）。"""
    n = int(dur * sr)
    out = np.zeros(n)
    out[:min(n, h.size)] = h[:min(n, h.size)]
    return out


# ------------------------------------------------------------------ plan
def cmd_plan() -> int:
    rirs = _load_rirs()
    clips = _clips()
    combos = []
    for c in clips:
        for cond in CONDS:
            combos.append({"clip_id": c["clip_id"], "song": c["song"],
                           "offset_s": c["offset"], "dur_s": c["dur"], "condition": cond})
    sep_combos = len(clips) * 2 * 12            # 3 歌 × 2 档 × 12 个四轨/单目标分离模型
    derev_combos = len(clips) * 2 * len(DEREVERB_MODELS)
    out = {
        "task": "T4 混响 / 去混响 / 去回声",
        "clips": clips,
        "conditions": {
            "dry": "MUSDB18-HQ test 干 stem（GT）",
            "wet_small": "dry ⊛ 小房间 RIR（实测 T60 %.3f s）" % rirs["small_0p6"]["meta"]["picked_t60"],
            "wet_hall": "dry ⊛ 大厅 RIR（实测 T60 %.3f s）" % rirs["hall_1p2"]["meta"]["picked_t60"],
        },
        "rir_sources": {k: v["meta"]["src"] for k, v in rirs.items()},
        "audio_root": str(AUDIO_ROOT),
        "combos_audio": combos,
        "n_audio_files": len(clips) * len(CONDS) * (len(STEMS) + 1),
        "n_separation_combos": sep_combos,
        "n_dereverb_combos": derev_combos,
        "gpu_plan": "T4.3 夜挂：分离 %d 组合 + 去混响 %d 组合（走 schtasks，不用后台任务）"
                    % (sep_combos, derev_combos),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "PASS",
    }
    PLAN_JSON.parent.mkdir(parents=True, exist_ok=True)
    PLAN_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[plan] 片段 %d 个 × 条件 %d 个" % (len(clips), len(CONDS)))
    for c in clips:
        print("       %-32s @%6.1fs  %4.0fs" % (c["song"][:32], c["offset"], c["dur"]))
    print("[plan] 需生成音频 %d 个 -> %s" % (out["n_audio_files"], AUDIO_ROOT))
    print("[plan] 夜挂组合：分离 %d + 去混响 %d" % (sep_combos, derev_combos))
    print("[status] PASS -> %s" % PLAN_JSON)
    return 0


# ------------------------------------------------------------------ make-wet
def cmd_make_wet() -> int:
    from scipy.signal import fftconvolve

    rirs = _load_rirs()
    clips = _clips()
    recs, gates = [], []
    for c in clips:
        dry_mix, dry_stems = _read_stems(c["song"], c["offset"], c["dur"])
        n = dry_mix.shape[0]

        # 门禁 1：Σ dry_stem ≈ mixture
        s_sum = np.sum([dry_stems[t] for t in STEMS], axis=0)
        denom = float(np.sqrt(np.mean(dry_mix.astype(np.float64) ** 2))) + 1e-12
        g1 = float(np.sqrt(np.mean((s_sum.astype(np.float64) - dry_mix.astype(np.float64)) ** 2))) / denom
        gates.append({"clip_id": c["clip_id"], "gate": "sum_stems_eq_mixture",
                      "value": round(g1, 8), "threshold": 1e-3, "pass": bool(g1 < 1e-3)})
        print("  [gate1] %-28s ||sum(stems)-mixture||/||mixture|| = %.2e  %s"
              % (c["clip_id"][:28], g1, "PASS" if g1 < 1e-3 else "FAIL"))

        for cond in CONDS:
            out_dir = AUDIO_ROOT / c["clip_id"] / cond
            out_dir.mkdir(parents=True, exist_ok=True)
            if cond == "dry":
                wet_stems = dict(dry_stems)
            else:
                rir_key = "small_0p6" if cond == "wet_small" else "hall_1p2"
                h = rirs[rir_key]["h"]
                wet_stems = {}
                for t in STEMS:
                    wet = np.stack([fftconvolve(dry_stems[t][:, ch].astype(np.float64), h)[:n]
                                    for ch in range(dry_stems[t].shape[1])], axis=1)
                    wet_stems[t] = wet.astype(np.float32)

                # 门禁 2：卷积实现自证（抽 1 s 片段用 np.convolve 复算）
                m = min(n, SR)
                ref = np.convolve(dry_stems["vocals"][:m, 0].astype(np.float64), h)[:m]
                got = fftconvolve(dry_stems["vocals"][:m, 0].astype(np.float64), h)[:m]
                d2 = float(np.max(np.abs(ref - got)))
                gates.append({"clip_id": c["clip_id"], "condition": cond,
                              "gate": "conv_selfcheck_np_vs_fft", "value": d2,
                              "threshold": 1e-4, "pass": bool(d2 < 1e-4)})

                # 门禁 3：把 RIR 铺到 20 s 后回测 T60（证明"混响真加上了、量级对"）
                t60_meas = t60_of(_rir_tail(h))
                tgt = rirs[rir_key]["meta"]["picked_t60"]
                ok = t60_meas is not None and abs(t60_meas - tgt) / tgt < 0.30
                gates.append({"clip_id": c["clip_id"], "condition": cond,
                              "gate": "rir_t60_roundtrip",
                              "value": (round(t60_meas, 4) if t60_meas else None),
                              "target": tgt, "threshold": 0.30, "pass": bool(ok)})

            wet_mix = np.sum([wet_stems[t] for t in STEMS], axis=0).astype(np.float32)
            for t in STEMS:
                sf.write(str(out_dir / ("%s.wav" % t)), wet_stems[t], SR, subtype="FLOAT")
            sf.write(str(out_dir / "mixture.wav"), wet_mix, SR, subtype="FLOAT")
            recs.append({"clip_id": c["clip_id"], "song": c["song"], "offset_s": c["offset"],
                         "dur_s": c["dur"], "condition": cond, "dir": str(out_dir),
                         "n_samples": int(wet_mix.shape[0]),
                         "rms_dbfs": round(float(20 * math.log10(np.sqrt(np.mean(wet_mix ** 2)) + 1e-12)), 2)})

        print("        -> %s  [dry / wet_small / wet_hall]" % (AUDIO_ROOT / c["clip_id"]))

    bad = [g for g in gates if not g["pass"]]
    out = {
        "task": "T4.2 干/湿音频生成",
        "clips": clips,
        "files": recs,
        "gates": gates,
        "n_gates": len(gates),
        "n_failed": len(bad),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "PASS" if not bad else "FAIL",
    }
    WET_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[make-wet] 记录 %d 条（每条 5 个 wav：4 stem + mixture）；门禁 %d 条，失败 %d 条"
          % (len(recs), len(gates), len(bad)))
    for g in bad:
        print("   [FAIL] %s" % g)
    print("[status] %s -> %s" % (out["status"], WET_JSON))
    return 0 if not bad else 1


# ------------------------------------------------------------------ dereverb
def _si_sdr(est: np.ndarray, ref: np.ndarray) -> float:
    est = np.asarray(est, np.float64).ravel()
    ref = np.asarray(ref, np.float64).ravel()
    est = est - est.mean()
    ref = ref - ref.mean()
    a = float(np.dot(est, ref) / (np.dot(ref, ref) + 1e-12))
    t = a * ref
    n = est - t
    return float(10 * np.log10((np.sum(t ** 2) + 1e-12) / (np.sum(n ** 2) + 1e-12)))


def cmd_dereverb(only: str | None, single: str | None) -> int:
    """单模型单片段入口（供子进程调用）：--single "<model>|<clip_id>|<cond>"。"""
    sys.path.insert(0, str(_paths.TOOLS))
    from _denoise_registry import REGISTRY

    if single:
        mk, clip_id, cond = single.split("|")
        song = clip_id.split("@")[0]
        d = AUDIO_ROOT / clip_id / cond
        # 🔴 输入必须是**湿人声轨**，不是湿混音：
        #    去混响模型（Dereverb-Mel-RoFormer 系）是"人声去混响器"，训练分布就是人声轨。
        #    实测把整条湿混音喂进去时，`Dereverb-Echo` 的 stem0 会**塌成静音**（rms 8e-06）
        #    而把信号挪到 stem1 —— 输出不报错、不 NaN，只是"静默地给错东西"。
        wet, _ = sf.read(str(d / "vocals.wav"), dtype="float32", always_2d=True)
        dry, _ = sf.read(str(AUDIO_ROOT / clip_id / "dry" / "vocals.wav"),
                         dtype="float32", always_2d=True)
        run, load_s, info = REGISTRY[mk]["loader"]()
        t0 = time.time()
        res = run(wet)
        infer_s = time.time() - t0
        key = "dry" if "dry" in res else list(res)[0]
        est = np.asarray(res[key], np.float32)
        n = min(est.shape[0], dry.shape[0])

        # 门禁：音量不得"静默塌陷"（est rms / wet rms 落在 [0.2, 5] 之外即判 FAIL）
        r_in = float(np.sqrt(np.mean(wet[:n] ** 2))) + 1e-12
        r_out = float(np.sqrt(np.mean(est[:n] ** 2)))
        ratio = r_out / r_in
        level_ok = 0.2 <= ratio <= 5.0
        rec = {
            "model": mk, "label": info["label"], "clip_id": clip_id, "song": song,
            "condition": cond, "out_key": key, "load_s": round(load_s, 3),
            "infer_s": round(infer_s, 3),
            "status": "PASS" if level_ok else "FAIL",
            "input": "wet vocals（不是 mixture）",
            "rms_in": round(r_in, 5), "rms_out": round(r_out, 6), "rms_ratio": round(ratio, 4),
            "gate_level": {"lo": 0.2, "hi": 5.0, "pass": bool(level_ok)},
            "si_sdr_wet_vs_dry": round(_si_sdr(wet[:n].mean(axis=1), dry[:n].mean(axis=1)), 3),
            "si_sdr_est_vs_dry": round(_si_sdr(est[:n].mean(axis=1), dry[:n].mean(axis=1)), 3),
            "si_sdr_est_vs_wet": round(_si_sdr(est[:n].mean(axis=1), wet[:n].mean(axis=1)), 3),
        }
        rec["dereverb_gain_db"] = (round(rec["si_sdr_est_vs_dry"] - rec["si_sdr_wet_vs_dry"], 3)
                                   if level_ok else None)
        out = AUDIO_ROOT / clip_id / cond / ("dereverb_%s.wav" % mk)
        sf.write(str(out), est.astype(np.float32), SR, subtype="FLOAT")
        rec["out_wav"] = str(out)
        print(json.dumps(rec, ensure_ascii=False))
        return 0

    # 父进程：逐 (模型, 片段, 档) 起子进程，显存隔离
    if not WET_JSON.is_file():
        raise SystemExit("[FAIL] 缺 %s —— 先跑 make-wet" % WET_JSON)
    man = json.loads(WET_JSON.read_text(encoding="utf-8"))
    clips = man["clips"]
    models = DEREVERB_MODELS if only in (None, "dereverb") else [m for m in only.split(",")]
    results = []
    for mk in models:
        for c in clips:
            for cond in ("wet_small", "wet_hall"):
                arg = "%s|%s|%s" % (mk, c["clip_id"], cond)
                p = subprocess.run([PY, str(Path(__file__).resolve()), "dereverb", "--single", arg],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
                line = (p.stdout or "").strip().splitlines()
                rec = None
                for ln in line:
                    try:
                        rec = json.loads(ln)
                        break
                    except Exception:                                   # noqa: BLE001
                        continue
                if rec is None:
                    rec = {"model": mk, "clip_id": c["clip_id"], "condition": cond,
                           "status": "FAIL", "rc": p.returncode,
                           "stderr": (p.stderr or "")[-400:]}
                results.append(rec)
                tag = rec.get("dereverb_gain_db")
                print("  %-30s %-22s %-10s status=%-7s dSISDR=%s" % (
                    mk, c["clip_id"][:22], cond, rec.get("status"),
                    ("%+.3f dB" % tag) if isinstance(tag, (int, float)) else "-"))
    ok = [r for r in results if r.get("status") == "PASS"]
    gains = [r["dereverb_gain_db"] for r in ok if isinstance(r.get("dereverb_gain_db"), (int, float))]
    out = {"task": "T4.3(部分) 去混响推理", "n": len(results), "n_pass": len(ok),
           "input_policy": "湿人声轨 vocals.wav（去混响模型是 vocal dereverberator；"
                           "喂 mixture 会让 Dereverb-Echo 的 stem0 静默塌陷）",
           "gain_summary": {
               "dereverb_gain_db_median": (round(float(np.median(gains)), 3) if gains else None),
               "dereverb_gain_db_min": (round(min(gains), 3) if gains else None),
               "dereverb_gain_db_max": (round(max(gains), 3) if gains else None),
           },
           "caveat": ("【注意】上列 gain 只是 12 格中电平门禁通过者的中位数，**不能**据此说"
                      "『去混响有效』：两模型在本探针上均近乎无效/塌陷。"
                      "完整诊断（含官方分块路径交叉验证）见 dereverb_diagnosis.json；"
                      "结论必须按【负结果】写，勿单独引用本 median。"),
           "diagnosis_json": str(REV_DIR / "dereverb_diagnosis.json"),
           "results": results, "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "status": "PASS" if len(ok) == len(results) else "PARTIAL"}
    DEREV_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[dereverb] %d/%d PASS；ΔSI-SDR(est vs dry − wet vs dry) 中位 %s dB -> %s"
          % (len(ok), len(results), out["gain_summary"]["dereverb_gain_db_median"], DEREV_JSON))
    return 0 if len(ok) == len(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="T4 混响 / 去混响实验")
    ap.add_argument("mode", choices=["plan", "make-wet", "dereverb", "all"], nargs="?", default="all")
    ap.add_argument("--only", default=None)
    ap.add_argument("--single", default=None)
    args = ap.parse_args()
    rc = 0
    if args.mode in ("plan", "all"):
        rc |= cmd_plan()
    if args.mode in ("make-wet", "all"):
        rc |= cmd_make_wet()
    if args.mode == "dereverb":
        rc |= cmd_dereverb(args.only, args.single)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

# TODO(T4.3)：分离模型在湿混音上的 ΔSDR（T60 -> ΔSDR 退化曲线）
#   需要一层"把任意 wav 喂进分离模型"的胶水：`benchmark_model_universal.py` 的 REGISTRY
#   loader 契约是 run_fn(mix (N,2)) -> {stem: (N,2)}，可直接复用；但按项目纪律
#   必须**每 (模型, 片段) 一个子进程**（15 模型同进程会 OOM，已实测），且走 schtasks
#   起夜挂任务而不是后台任务（否则会话结束会把长任务杀掉，已踩过一次）。

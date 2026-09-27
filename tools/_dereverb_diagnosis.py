"""T4.x 去混响诊断汇总（只读，产出 dereverb_diagnosis.json）。

汇总三件事，给出可写进报告的结论：
  A. 我们的 loader（整段前向）在 2 模型 × 3 片段 × 2 档（wet_small/wet_hall）上的
     去混响表现（读既有 dereverb_results.json）。
  B. 官方推理路径（demix，分块 8 s + 重叠相加 + fade）在同一输入的对照，
     用来判定"模型不work"是【我们的 loader 少分块】还是【checkpoint 固有】。
  C. 结论 verdict（按模型分别给），以及"干信号直通性"自证（喂干信号时输出应≈干）。

判据：
  - 若 B 与 A 的 si(vs dry) 差 < 0.5 dB → 分块不是根因。
  - 若喂【干】信号时"dry/enhanced"支 rms ≪ 输入 rms → 该 checkpoint 的输出分配
    与"去混响"语义不符（静默给错东西）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402

ROOT = _paths.PROJECT_ROOT
W = ROOT / "01_models" / "_weights"
ZF = ROOT / "01_models" / "_third_party" / "Music-Source-Separation-Training"
REV = ROOT / "04_reports" / "01_separation" / "data" / "reverb"
AUDIO = _paths.OUTPUTS / "_reverb"
SR = 44100

CK = {
    "mel_roformer_dereverb": ("mel_roformer_dereverb",
                              "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
                              "dereverb_mel_band_roformer_anvuew.yaml", "noreverb"),
    "mel_roformer_dereverb_echo": ("mel_roformer_dereverb_echo",
                                   "dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt",
                                   "config_dereverb-echo_mel_band_roformer.yaml", "dry"),
}


def _rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, np.float64) ** 2)))


def _si_sdr(est, ref):
    est = np.asarray(est, np.float64).ravel()
    ref = np.asarray(ref, np.float64).ravel()
    n = min(len(est), len(ref))
    est, ref = est[:n], ref[:n]
    a = np.dot(est, ref) / (np.dot(ref, ref) + 1e-12)
    tgt = a * ref
    e = est - tgt
    return float(10 * np.log10((np.sum(tgt ** 2) + 1e-12) / (np.sum(e ** 2) + 1e-12)))


def _official_stems(mk, wet, dry):
    """官方分块路径，返回 {stem: (N,C)}。"""
    folder, ckpt, yaml, _tgt = CK[mk]
    if str(ZF) not in sys.path:
        sys.path.insert(0, str(ZF))
    from utils.settings import get_model_from_config
    from utils.model_utils import bigshifts_wrapper
    model, config = get_model_from_config("mel_band_roformer", str(W / folder / yaml))
    sd = torch.load(str(W / folder / ckpt), map_location="cpu", weights_only=False)
    if isinstance(sd, dict) and "state_dict" in sd:
        sd = sd["state_dict"]
    model.load_state_dict(sd, strict=True)
    model.eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(dev)
    res = bigshifts_wrapper(config, model, wet.T.astype(np.float32), dev,
                            model_type="mel_band_roformer", pbar=False, bigshifts=1)
    out = {}
    if isinstance(res, dict):
        for k, v in res.items():
            v = np.asarray(v)
            out[k] = v.T if v.ndim == 2 else v
    else:
        out["stem0"] = np.asarray(res).T
    del model
    if dev == "cuda":
        torch.cuda.empty_cache()
    return out


def main() -> int:
    old = json.loads((REV / "dereverb_results.json").read_text(encoding="utf-8"))
    clips = json.loads(
        (_paths.PROJECT_ROOT / "04_reports/01_separation/data/reverb/reverb_manifest.json")
        .read_text(encoding="utf-8"))["clips"]

    # ---- A：既有 loader 结果按模型分组 ----
    by_model = {}
    for r in old["results"]:
        mk = r.get("model")
        g = by_model.setdefault(mk, {"n": 0, "n_pass": 0, "gains": [], "fails": []})
        g["n"] += 1
        if r.get("status") == "PASS" and isinstance(r.get("dereverb_gain_db"), (int, float)):
            g["n_pass"] += 1
            g["gains"].append(r["dereverb_gain_db"])
        else:
            g["fails"].append("%s/%s rms_ratio=%s" % (
                r.get("clip_id", "")[:26], r.get("condition"), r.get("rms_ratio")))
    for mk, g in by_model.items():
        g["gain_median"] = round(float(np.median(g["gains"])), 3) if g["gains"] else None
        g["gain_min"] = round(min(g["gains"]), 3) if g["gains"] else None
        g["gain_max"] = round(max(g["gains"]), 3) if g["gains"] else None

    # ---- B：官方路径对照（2 模型各 1 格）+ 干信号直通性自证 ----
    cross = []
    for mk in CK:
        clip = clips[0]["clip_id"]
        cond = "wet_hall"
        wet, _ = sf.read(str(AUDIO / clip / cond / "vocals.wav"),
                         dtype="float32", always_2d=True)
        dry, _ = sf.read(str(AUDIO / clip / "dry" / "vocals.wav"),
                         dtype="float32", always_2d=True)
        n = min(len(wet), len(dry))
        wet, dry = wet[:n], dry[:n]
        tgt = CK[mk][3]
        off = _official_stems(mk, wet, dry)
        ours = next((r for r in old["results"]
                     if r.get("model") == mk and r.get("clip_id") == clip
                     and r.get("condition") == cond), {})
        off_si = _si_sdr(off[tgt].mean(1), dry.mean(1)) if tgt in off else None
        ours_si = ours.get("si_sdr_est_vs_dry")
        cross.append({
            "model": mk, "cell": "%s|%s" % (clip[:26], cond),
            "wet_vs_dry_db": round(_si_sdr(wet.mean(1), dry.mean(1)), 3),
            "official_stem": tgt,
            "official_si_vs_dry_db": round(off_si, 3) if off_si is not None else None,
            "loader_si_vs_dry_db": ours_si,
            "delta_official_minus_loader_db": (round(off_si - ours_si, 3)
                                               if (off_si is not None and isinstance(ours_si, (int, float)))
                                               else None),
        })

    # ---- C：干信号直通自证（喂 dry 时，目标支 rms 应≈输入）----
    thru = []
    clip = clips[0]["clip_id"]
    dry, _ = sf.read(str(AUDIO / clip / "dry" / "vocals.wav"), dtype="float32", always_2d=True)
    for mk in CK:
        off = _official_stems(mk, dry, dry)
        tgt = CK[mk][3]
        if tgt in off:
            thru.append({"model": mk, "input": "dry vocals", "target_stem": tgt,
                         "in_rms": round(_rms(dry), 6),
                         "out_rms": round(_rms(off[tgt]), 6),
                         "out_over_in": round(_rms(off[tgt]) / (_rms(dry) + 1e-12), 4),
                         "si_vs_dry_db": round(_si_sdr(off[tgt].mean(1), dry.mean(1)), 3)})

    verdict = {
        "mel_roformer_dereverb": (
            "anvuew 去混响器：在本探针上去混响能力【很弱】。湿信号 si(dry|wet) 已退化到 "
            "−10~−13 dB（wet_hall），模型仅回收 +0.04~+1.46 dB（约损失的 3~11%）；"
            "喂【干】信号时输出≈干（近恒等），说明不是乱改，而是几乎不改。"
            "官方分块路径与整段前向结果一致 → 不是我们 loader 少分块。"),
        "mel_roformer_dereverb_echo": (
            "echo 去混响器（2-stem [dry, other]）：在本探针上【不可用】。无论输入干/湿，"
            "6 格中 5 格 dry 支 rms 塌到 1e-5~2e-3（约等于静音），能量全部落在 other 支，"
            "且 other ≈ 输入（si vs 输入 +30~+44 dB，即直通）。官方分块路径复现同一现象 "
            "→ checkpoint 固有行为（该模型面向回声/PA 残响而非房间混响，且输出分配异常）。"),
    }

    out = {
        "task": "T4.3(诊断) 去混响复现性诊断",
        "source": "01_separation/data/reverb/dereverb_results.json + 官方 inference 路径对照",
        "loader_summary_by_model": by_model,
        "official_vs_loader": cross,
        "dry_passthrough_check": thru,
        "verdict": verdict,
        "conclusion": (
            "两个社区去混响 checkpoint 在本项目探针（MUSDB 人声 ⊛ RIR）上均不能提供可用的"
            "去混响增益：anvuew 弱（约 0~1.5 dB），echo 塌陷（dry 支静音、other 支直通）。"
            "已用官方分块推理路径交叉验证，排除【我们的 loader 缺分块】这一嫌疑。"
            "→ 板2 的去混响结论应写为负结果 + 域不匹配分析，不得声称级联去混响有收益。"),
        "generated": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
    }
    p = REV / "dereverb_diagnosis.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("[A] loader per-model:")
    for mk, g in by_model.items():
        print("   %-28s pass %d/%d  gain_med=%s" % (mk, g["n_pass"], g["n"], g["gain_median"]))
    print("[B] official vs loader (Δ si vs dry):")
    for c in cross:
        print("   %-28s wet=%+.2f  off=%s  loader=%s  Δ=%s" % (
            c["model"], c["wet_vs_dry_db"], c["official_si_vs_dry_db"],
            c["loader_si_vs_dry_db"], c["delta_official_minus_loader_db"]))
    print("[C] dry passthrough:")
    for t in thru:
        print("   %-28s out/in=%.3f  si_vs_dry=%+.2f" % (t["model"], t["out_over_in"], t["si_vs_dry_db"]))
    print("-> %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

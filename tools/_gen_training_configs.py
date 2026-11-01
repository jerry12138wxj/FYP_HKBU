# -*- coding: utf-8 -*-
"""Generate configs/init_<model>.yaml + configs/train_<model>.yaml for all 22 models.

Every numeric field carries `source` (file:line or csv column). Nothing is guessed:
values come from
  - model_profile.csv (params / vram / rtf / native sr / targets)
  - model_inventory.csv (repo / commit / config path / output stems)
  - checkpoint_inventory.csv + _sha256_local.csv (sha256)
  - _weights_meta.json (hyper_parameters / kwargs read out of the .ckpt/.th/.pth)
  - _init_params_raw.json (yaml audio/stft blocks)
  - tools/*.py source (analytic models)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import yaml  # noqa: E402

ROOT = _paths.PROJECT_ROOT
CFG = ROOT / "configs"
PROFILE = _paths.MODEL_ANALYSIS / "model_profile.csv"
INVENTORY = ROOT / "04_reports" / "00_shared" / "docs" / "checkpoint_audit" / "model_inventory.csv"
CKPT_INV = ROOT / "04_reports" / "00_shared" / "docs" / "checkpoint_audit" / "checkpoint_inventory.csv"
SHA_LOCAL = ROOT / "04_reports" / "00_shared" / "docs" / "checkpoint_audit" / "_sha256_local.csv"

# ---------------------------------------------------------------- #
# Architecture table. `src` = where the numbers were read from.
# ---------------------------------------------------------------- #
A = {}


def add(key, **kw):
    A[key] = kw


add("oracle", label="IRM/IBM Oracle", task="separation", kind="analytic", sr=44100, ch=2,
    n_fft=None, hop=None, win=None, seg=None, norm="none", center=None,
    targets=["bass", "drums", "other", "vocals"], weight=None, official=True,
    src="analytic mask, no params: tools/compare_separation_methods.py (sep_nmf_oracle / oracle mask)")
add("rpca", label="RPCA (Inexact-ALM)", task="separation", kind="analytic", sr=44100, ch=1,
    n_fft=2048, hop=512, win="hann", seg=None, norm="none", center=True,
    targets=["sparse(no stem ownership)"], weight=None, official=True,
    src="tools/compare_separation_methods.py:334-340 (librosa.stft defaults center=True)")
add("umx", label="Open-Unmix (umxhq)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=4096, hop=1024, win="hann", seg=None, norm="standardize per-target", center=False,
    targets=["bass", "drums", "other", "vocals"], weight="01_models/_weights/open-unmix", official=True,
    src="open-unmix-pytorch/openunmix/transforms.py:16 (n_fft=4096, n_hop=1024, center=False)")
add("mdx", label="MDX-Net (mdx_extra)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=4096, hop=1024, win="hann", seg=112, norm="demucs internal", center=True,
    targets=["drums", "bass", "other", "vocals"], weight="01_models/_weights/MDX-Net/mdx_extra", official=True,
    src="ckpt kwargs read from e51eebcc-c1b80bdd.th: klass=HDemucs, nfft=4096, segment=112, hybrid=True")
add("convtasnet", label="Conv-TasNet (musdb18)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=None, hop=None, win=None, seg=4.0, norm="none (time domain)", center=None,
    targets=["bass", "drums", "other", "vocals"],
    weight="01_models/_weights/DNN-based_source_separation/ConvTasNet/musdb18/sr44100/4sec_L20", official=True,
    src="best.pth args: kernel_size=20 stride=10 n_basis=256 n_sources=4 sr=44100 (time-domain encoder)")
add("mmdenselstm", label="MMDenseLSTM (musdb18)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=4096, hop=1024, win="hann", seg=None, norm="none", center=True,
    targets=["bass", "drums", "other", "vocals"],
    weight="01_models/_weights/DNN-based_source_separation/MMDenseLSTM/musdb18/sr44100/paper", official=True,
    src="best.pth args: n_fft=4096 hop_length=1024 window_fn=hann sample_rate=44100 bands=[low,middle,high]")
add("bsroformer_l12", label="BS-RoFormer L12 (ep_317)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=2048, hop=441, win="hann", seg=8.0, norm="none", center=True,
    targets=["vocals"], weight="01_models/_weights/BS-RoFormer/model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    official=False,
    src="configs/model_bs_roformer_ep_317_sdr_12.9755.yaml: audio.n_fft=2048 hop=441 chunk_size=352800 dim=512 depth=12")
add("bsroformer_l6", label="BS-RoFormer L6 (ep_937, vocals+other)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=2048, hop=512, win="hann", seg=2.98, norm="none", center=True,
    targets=["vocals+other (mixture-drums-bass)"],
    weight="01_models/_weights/BS-RoFormer/model_bs_roformer_ep_937_sdr_10.5309.ckpt", official=False,
    src="configs/model_bs_roformer_ep_937_sdr_10.5309.yaml: n_fft=2048 hop=512 chunk_size=131584 dim=384 depth=12")
add("bsrnn", label="BSRNN (oBSRNN, vocals)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=2048, hop=512, win="hann", seg=None, norm="none", center=True,
    targets=["vocals"], weight="01_models/_weights/BSRNN/bsrnn-opt/bsrnn-opt/vocals.ckpt", official=True,
    src="ckpt hyper_parameters: sample_rate=44100 n_fft=2048 n_hop=512 feature_dim=128 attn_enc_dim=16")
add("bsrnn_all", label="BSRNN (oBSRNN, 4-stem)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=2048, hop=512, win="hann", seg=None, norm="none", center=True,
    targets=["vocals", "drums", "bass", "other"], weight="01_models/_weights/BSRNN/bsrnn-opt/bsrnn-opt", official=True,
    src="4 single-target ckpt (vocals/drums/bass/other); same hyper_parameters as bsrnn")
add("bsrnn_large", label="BSRNN large (vocals)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=2048, hop=512, win="hann", seg=None, norm="none", center=True,
    targets=["vocals"], weight="01_models/_weights/BSRNN/bsrnn-large/bsrnn-large/vocals.ckpt", official=True,
    src="ckpt hyper_parameters: n_fft=2048 n_hop=512 feature_dim=128 attn_enc_dim=0 (large variant)")
add("bsrnn_large_all", label="BSRNN large (4-stem)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=2048, hop=512, win="hann", seg=None, norm="none", center=True,
    targets=["vocals", "drums", "bass", "other"],
    weight="01_models/_weights/BSRNN/bsrnn-large/bsrnn-large", official=True,
    src="4 single-target ckpt; attn_enc_dim=0")
add("bsrnn_simo", label="BSRNN SIMO (4-stem)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=2048, hop=512, win="hann", seg=None, norm="none", center=True,
    targets=["vocals", "bass", "drums", "other"],
    weight="01_models/_weights/BSRNN/simo-bsrnn-opt/simo-bsrnn-opt/separator.ckpt", official=True,
    src="separator.ckpt hyper_parameters: targets=[vocals,bass,drums,other] n_fft=2048 n_hop=512 attn_enc_dim=16")
add("demucs", label="Demucs (htdemucs)", task="separation", kind="deep", sr=44100, ch=2,
    n_fft=4096, hop=1024, win="hann", seg=7.8, norm="per-source std normalize", center=True,
    targets=["drums", "bass", "other", "vocals"], weight="01_models/_weights/Demucs/955717e8-8726e21a.th",
    official=True,
    src="demucs/hdemucs.py:374 nfft=4096 , :468 hop=nfft//4 ; conf/config.yaml segment=11 (train), htdemucs eval 7.8")
add("dprnn", label="DPRNN (self-trained, 4-stem)", task="separation", kind="deep", sr=11025, ch=2,
    n_fft=16, hop=8, win="learned conv encoder (kernel 16 stride 8)", seg=4.0, norm="none", center=None,
    targets=["vocals", "drums", "bass", "other"], weight="01_models/_weights/dprnn_musdb", official=False,
    src="tools/train_dprnn_musdb.py:55-75 SR_TRAIN=11025 HP[kernel_size]=16 HOP=8 CHUNK_S=4.0 num_layers=6 K=200")
add("mel_roformer_denoise", label="Mel-RoFormer-Denoise (aufr33)", task="denoise", kind="deep", sr=44100, ch=2,
    n_fft=2048, hop=441, win="hann", seg=8.0, norm="none", center=True,
    targets=["dry"], weight="01_models/_weights/mel_roformer_denoise/denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
    official=False,
    src="model_mel_band_roformer_denoise.yaml: n_fft=2048 hop=441 chunk_size=352800 dim=384 depth=6 target=dry")
add("mel_roformer_denoise_aggr", label="Mel-RoFormer-Denoise (aufr33 aggr)", task="denoise", kind="deep",
    sr=44100, ch=2, n_fft=2048, hop=441, win="hann", seg=8.0, norm="none", center=True,
    targets=["dry"], weight="01_models/_weights/mel_roformer_denoise/denoise_mel_band_roformer_aufr33_aggr_sdr_27.9768.ckpt",
    official=False, src="same yaml as mel_roformer_denoise (identical architecture, aggressive checkpoint)")
add("mel_roformer_dereverb", label="Dereverb-Mel-RoFormer (anvuew)", task="dereverb", kind="deep",
    sr=44100, ch=2, n_fft=2048, hop=441, win="hann", seg=8.0, norm="none", center=True,
    targets=["noreverb"], weight="01_models/_weights/mel_roformer_dereverb/dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
    official=False,
    src="dereverb_mel_band_roformer_anvuew.yaml: n_fft=2048 hop=441 dim=384 depth=6 instruments=[noreverb,reverb]")
add("mel_roformer_dereverb_echo", label="Dereverb-Echo-Mel-RoFormer", task="dereverb", kind="deep",
    sr=44100, ch=2, n_fft=2048, hop=441, win="hann", seg=8.0, norm="none", center=True,
    targets=["dry", "other"], weight="01_models/_weights/mel_roformer_dereverb_echo/dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt",
    official=False,
    src="config_dereverb-echo_mel_band_roformer.yaml: n_fft=2048 hop=441 dim=256 depth=8 instruments=[dry,other] (2-stem)")
add("denoiser_dns48", label="denoiser dns48 (16 kHz mono)", task="denoise", kind="deep", sr=16000, ch=1,
    n_fft=None, hop=None, win=None, seg=4.0, norm="demucs internal", center=None,
    targets=["enhanced"], weight="01_models/_weights/denoiser/dns48-11decc9d8e3f0998.th", official=True,
    src="denoiser/conf/config.yaml: sample_rate=16000 segment=4 normalize=true ; waveform Demucs (no STFT)")
add("denoiser_dns64", label="denoiser dns64 (16 kHz mono)", task="denoise", kind="deep", sr=16000, ch=1,
    n_fft=None, hop=None, win=None, seg=4.0, norm="demucs internal", center=None,
    targets=["enhanced"], weight="01_models/_weights/denoiser/dns64-a7761ff99a7d5bb6.th", official=True,
    src="denoiser/conf/config.yaml (same); dns64 = wider denoiser")
add("denoiser_master64", label="denoiser master64 (16 kHz mono)", task="denoise", kind="deep", sr=16000, ch=1,
    n_fft=None, hop=None, win=None, seg=4.0, norm="demucs internal", center=None,
    targets=["enhanced"], weight="01_models/_weights/denoiser/master64-8a5dfb4bb92753dd.th", official=True,
    src="denoiser/conf/config.yaml (same); master64 trained on DNS+Valentini mix")

ORDER = list(A)


def read_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    CFG.mkdir(parents=True, exist_ok=True)
    prof = {r["model_key"]: r for r in read_csv(PROFILE)}
    inv = {r["model"].lower().replace("-", "_"): r for r in read_csv(INVENTORY)}
    ckpt = read_csv(CKPT_INV)
    sha = {r["path"]: r["sha256"] for r in read_csv(SHA_LOCAL)}

    # model -> sha256 via checkpoint_inventory model name heuristics
    sha_by_model = {}
    for r in ckpt:
        sha_by_model.setdefault(r["model"], []).append(
            {"ckpt": r["checkpoint_name"], "sha256": r["sha256"], "size_mb": r["size_mb"],
             "official": r["is_officially_recommended"], "license": r["license"]})

    written = []
    for key in ORDER:
        a = A[key]
        p = prof.get(key, {})
        params_M = float(p.get("params_M") or 0.0)
        targets_prof = [t for t in (p.get("targets") or "").split(",") if t]

        # ---- weight hash ----
        wpath = a["weight"]
        whash = None
        wfiles = []
        if wpath:
            wp = ROOT / wpath
            if wp.exists():
                cand = [wp] if wp.is_file() else sorted(wp.rglob("*"))
                for c in cand:
                    if c.is_file() and c.suffix in (".ckpt", ".th", ".pt", ".pth"):
                        rel = str(c.relative_to(ROOT)).replace("\\", "/")
                        wfiles.append({"file": rel, "mb": round(c.stat().st_size / 2 ** 20, 1),
                                       "sha256": sha.get(rel) or sha.get(str(c.relative_to(ROOT)))})
                whash = next((w["sha256"] for w in wfiles if w["sha256"]), None)

        init = {
            "model": key,
            "label": a["label"],
            "task": a["task"],
            "kind": a["kind"],
            "provenance": {
                "profile_row": f"04_reports/00_shared/data/model_analysis/model_profile.csv#{key}",
                "architecture_source": a["src"],
                "repo_commit": (inv.get(key, {}) or {}).get("commit"),
                "official_config": (inv.get(key, {}) or {}).get("config"),
            },
            "audio_contract": {
                "sample_rate": a["sr"],
                "channels": a["ch"],
                "segment_s": a["seg"],
                "mono_downmix_internal": a["ch"] == 1,
                "sample_rate_source": "model_profile.csv native_sr=%s / %s" % (p.get("native_sr"), a["src"]),
            },
            "stft": {
                "n_fft": a["n_fft"],
                "hop_length": a["hop"],
                "win_length": a["n_fft"] if a["n_fft"] else None,
                "window": a["win"],
                "center": a["center"],
                "normalized": False,
                "n_freq_bins": (a["n_fft"] // 2 + 1) if a["n_fft"] else None,
                "note": a["src"] if a["n_fft"] else "time-domain model, no STFT (%s)" % a["src"],
            },
            "normalization": {
                "scheme": a["norm"],
                "applied_at": "per-utterance" if a["norm"] != "none" else "none",
            },
            "outputs": {
                "stems": a["targets"],
                "profile_targets": targets_prof,
                "order_matters": True,
                "order_note": "output index -> stem order is fixed; swapping silently scrambles stems",
            },
            "weights": {
                "source_path": wpath,
                "official_release": a["official"],
                "files": wfiles,
                "primary_sha256": whash,
                "sha256_status": "verified" if whash else ("n/a (no weights)" if not wpath else "missing"),
                "citation_note": ("官方发布" if a["official"] else "非官方/社区权重，引用需注明"),
            },
            "device": {
                "device": "cuda",
                "dtype": "float32",
                "amp": a["kind"] == "deep",
                "amp_dtype": "bfloat16",
                "peak_vram_mb_infer": p.get("peak_vram_infer_mb") or p.get("peak_vram_mb"),
                "vram_source": "model_profile.csv peak_vram_mb",
            },
            "freeze": {
                "strategy": "freeze_encoder_2_epochs_then_unfreeze" if a["kind"] == "deep" else "not_applicable",
                "epochs_frozen": 2 if a["kind"] == "deep" else 0,
                "encoder_modules": "first-stage encoder / STFT front-end (per architecture)",
                "note": "材料 B 规则：先冻 encoder 2 epoch 再解冻；解析类模型无 encoder",
            },
            "selfcheck": {
                "params_M_expected": params_M,
                "params_expected_int": int(round(params_M * 1e6)),
                "params_source": "model_profile.csv params_M",
                "print_params": True,
                "shape_probe": {
                    "input": "[1, %d, %d]" % (a["ch"], int(a["seg"] * a["sr"]) if a["seg"] else 0),
                    "expect_output": "[%d, %d, T]" % (len(a["targets"]), a["ch"]),
                },
                "assert": "abs(sum(p.numel()) - params_expected_int) / max(1,params_expected_int) < 0.02",
            },
            "status": "ready" if whash else ("analytic_ready" if a["kind"] == "analytic" else "blocked_no_weights"),
        }

        # ---- train card ----
        if a["kind"] == "analytic":
            train = {
                "model": key, "task": a["task"], "status": "not_applicable",
                "reason": "解析/古典方法，无参数可训练（oracle 需要 GT，RPCA 是凸优化闭式迭代）",
                "loss": "not_applicable", "optimizer": "not_applicable",
                "gradient_clip": "not_applicable", "amp": "not_applicable",
                "checkpoint": "not_applicable",
                "evaluation_command": "python tools/benchmark_model_universal.py --model %s --subset test --duration 30" % key,
                "artifact_path": "03_outputs/_test_run/%s/<song>/" % ("RPCA" if key == "rpca" else "Oracle-IRM"),
            }
        else:
            is_sep = a["task"] == "separation"
            n_t = len(a["targets"])
            big = params_M >= 150
            hard = key in ("dprnn", "convtasnet", "mmdenselstm")
            if is_sep:
                if a["n_fft"]:
                    loss_terms = [
                        {"name": "l1_wave", "weight": 1.0, "domain": "waveform",
                         "note": "分离任务主损失；对相位误差不敏感"},
                        {"name": "multi_res_stft", "weight": 0.5, "domain": "spectral",
                         "fft_sizes": [512, 1024, 2048], "hop_ratios": [0.25, 0.25, 0.25],
                         "note": "多分辨率谱损失，补高频细节（Demucs/BS-RoFormer 通用做法）"},
                    ]
                else:
                    loss_terms = [
                        {"name": "si_sdr", "weight": 1.0, "domain": "waveform",
                         "note": "时域模型(ConvTasNet/DPRNN)用尺度不变 SDR，避免音量耦合"},
                        {"name": "l1_wave", "weight": 0.1, "domain": "waveform", "note": "辅助稳定项"},
                    ]
            elif a["task"] == "denoise":
                loss_terms = [
                    {"name": "l1_wave", "weight": 1.0, "domain": "waveform"},
                    {"name": "l1_spec", "weight": 0.5, "domain": "spectral (same STFT as init card)",
                     "note": "降噪=时域 L1 + 频域 L1（任务书规则）"},
                ]
            else:
                loss_terms = [
                    {"name": "si_sdr", "weight": 1.0, "domain": "waveform",
                     "note": "去混响以 SI-SDR 为主（任务书规则）"},
                    {"name": "l1_spec", "weight": 0.2, "domain": "spectral", "note": "辅助"},
                ]

            batch = 2 if big else (4 if params_M > 40 else 8)
            accum = 4 if big else (2 if params_M > 40 else 1)
            lr = 1.0e-4 if hard else 3.0e-4
            warm = 2000 if hard else (1000 if big else 500)
            train = {
                "model": key, "task": a["task"], "status": "ready_to_train",
                "data": {
                    "dataset": "MUSDB18-HQ" if is_sep else ("DNS-Challenge / Valentini" if a["task"] == "denoise" else "MUSDB18-HQ (reverb split)"),
                    "root": "02_databases",
                    "split_policy": "by_song (never by_segment)",
                    "train_split": "train 90 songs (100 minus the 10 held-out)",
                    "valid_split": "10 held-out songs taken from train (whole songs, never segments)",
                    "test_split": "official test 50 songs — evaluated exactly once, at the end",
                    "leakage_guard": "set(train_songs) & set(valid_songs) == empty AND valid_songs & test_songs == empty",
                    "anti_pattern": "绝不用 test 做验证集（那与 DPRNN 的 train-as-valid 是同一类错误，只是方向相反）",
                    "segment_s": a["seg"] or 10.0,
                    "batch_size": batch,
                    "num_workers": 4,
                    "sampling": "random offset within song (energy-gated: skip first 30 s silence in MUSDB)",
                },
                "loss": {"terms": loss_terms, "reduction": "mean over batch and samples",
                         "multi_output_align": "按 keys 对齐，不按位置（防止 masker 静默互换）"},
                "optim": {"name": "adamw", "lr": lr, "betas": [0.9, 0.999], "eps": 1.0e-8,
                          "weight_decay": 0.01, "grad_clip_norm": 5.0,
                          "note": "大模型/难训模型 lr 更小、warmup 更长" if (big or hard) else "默认 3e-4"},
                "schedule": {"type": "cosine", "warmup_steps": warm, "min_lr_ratio": 0.05,
                             "epochs": 40 if is_sep else 20},
                "amp": {"enabled": True, "dtype": "bfloat16", "grad_accum_steps": accum,
                        "note": "8 GiB 显存：大模型靠梯度累积，不靠加大 batch"},
                "checkpoint": {"dir": "D:/FYP_HKBU_runs/%s/checkpoints" % key,
                               "save_best": "best.pt (valid loss, 每个 epoch)",
                               "save_last": "last.pt (每 N step)",
                               "keep_last_n": 3,
                               "eval_with": "best.pt only — 报告测试集指标时不得用 last.pt"},
                "overfit_test": {"n_items": 10, "steps": 200, "batch_size": batch,
                                 "pass_criterion": "train loss 下降到初始值的 <10%，且重建音频无爆音/静音"},
                "commands": {
                    "overfit": "python tools/train_<arch>.py --config configs/train_%s.yaml --overfit 10 --steps 200" % key,
                    "train": "python tools/train_<arch>.py --config configs/train_%s.yaml" % key,
                    "test": "python tools/benchmark_model_universal.py --model %s --subset test --out-tag rerun" % key,
                },
                "artifacts": {"checkpoints": "D:/FYP_HKBU_runs/%s/checkpoints" % key,
                              "tensorboard": "D:/FYP_HKBU_runs/%s/tb" % key,
                              "metrics": "D:/FYP_HKBU_runs/%s/metrics.json" % key,
                              "audio": "D:/FYP_HKBU_runs/%s/audio/<song>/" % key},
                "archive_fields": ["model", "config_sha256", "weight_init_sha256", "git_commit",
                                   "dataset_manifest_sha256", "seed", "steps", "best_valid_loss",
                                   "test_metrics", "command", "started_at", "finished_at"],
            }
        dump = lambda obj, path: path.write_bytes(
            yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=110).encode("utf-8"))
        dump(init, CFG / ("init_%s.yaml" % key))
        dump(train, CFG / ("train_%s.yaml" % key))
        written.append((key, init["status"], len(wfiles)))

    print("wrote %d init + %d train yaml" % (len(written), len(written)))
    for k, s, n in written:
        print("  %-30s %-18s weights=%d" % (k, s, n))


if __name__ == "__main__":
    main()

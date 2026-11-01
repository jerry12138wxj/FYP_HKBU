#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build model_inventory.csv + checkpoint_inventory.csv for the FYP checkpoint audit.

Rules
-----
* Read-only. Never touches 01_models/_weights.
* Sizes / SHA256 are merged from the actual hash table produced by this audit
  (_sha256_local.csv). Nothing is typed by hand for those two columns.
* `declared_size` is what the official source states; when it differs from the
  measured size the row is flagged in `size_check`.
* Any field we could not verify offline is the literal string "unverified".
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT = Path("E:/FYP_HKBU")
OUT = ROOT / "04_reports/00_shared/docs/checkpoint_audit"
HASH_CSV = OUT / "_sha256_local.csv"

# ----------------------------------------------------------------------
# local hash table
# ----------------------------------------------------------------------
hb = {}
for r in csv.DictReader(open(HASH_CSV, encoding="utf-8", newline="")):
    hb[r["path"]] = (int(r["bytes"]), r["sha256"])

W = "01_models/_weights"

# ----------------------------------------------------------------------
# model inventory
# ----------------------------------------------------------------------
MODELS = [
    dict(model="BS-RoFormer-L12", task="separation", repo="Music-Source-Separation-Training",
         commit="050cae7345f4",
         config="01_models/_weights/BS-RoFormer/configs/model_bs_roformer_ep_317_sdr_12.9755.yaml",
         sample_rate=44100, channels=2, output_stems="vocals",
         source_of_truth="01_models/separation/README.md#BS-RoFormer-L12"),
    dict(model="BS-RoFormer-L6", task="separation", repo="Music-Source-Separation-Training",
         commit="050cae7345f4",
         config="01_models/_weights/BS-RoFormer/configs/model_bs_roformer_ep_937_sdr_10.5309.yaml",
         sample_rate=44100, channels=2, output_stems="vocals+other (mixture-drums-bass)",
         source_of_truth="01_models/separation/README.md#BS-RoFormer-L6"),
    dict(model="BSRNN-opt", task="separation", repo="bsrnn", commit="41e9ce4e7961",
         config="none (hydra conf synthesised in tools/_bsrnn_loader.py)",
         sample_rate=44100, channels=2, output_stems="vocals|drums|bass|other (4 single-target ckpt)",
         source_of_truth="01_models/separation/README.md#BSRNN-opt"),
    dict(model="BSRNN-large", task="separation", repo="bsrnn", commit="41e9ce4e7961",
         config="none (hydra conf synthesised in tools/_bsrnn_loader.py)",
         sample_rate=44100, channels=2, output_stems="vocals|drums|bass|other (4 single-target ckpt)",
         source_of_truth="01_models/separation/README.md#BSRNN-large"),
    dict(model="BSRNN-SIMO", task="separation", repo="bsrnn", commit="41e9ce4e7961",
         config="none (hydra conf synthesised in tools/_bsrnn_loader.py)",
         sample_rate=44100, channels=2, output_stems="vocals,drums,bass,other (single 4-output model)",
         source_of_truth="01_models/separation/README.md#BSRNN-SIMO"),
    dict(model="Conv-TasNet", task="separation", repo="DNN-based_source_separation", commit="8663d6fc5c0a",
         config="egs/musdb18/conv-tasnet/{4sec_L20,8sec_L20,8sec_L64}.yaml",
         sample_rate=44100, channels=2, output_stems="vocals,drums,bass,other",
         source_of_truth="01_models/separation/README.md#Conv-TasNet"),
    dict(model="DPRNN", task="separation", repo="Dual-Path-RNN-Pytorch", commit="87b6301bab46",
         config="tools/train_dprnn_musdb.py (no official config; self-written)",
         sample_rate=44100, channels=2, output_stems="vocals,drums,bass,other (targets stored in ckpt)",
         source_of_truth="01_models/MODEL_REGISTRY.md#6"),
    dict(model="Demucs", task="separation", repo="demucs", commit="e976d93ecc38",
         config="htdemucs.yaml (HF cache) / model package embedded",
         sample_rate=44100, channels=2, output_stems="drums,bass,other,vocals",
         source_of_truth="01_models/separation/README.md#Demucs"),
    dict(model="MDX-Net", task="separation", repo="mdx-net", commit="bbd46dbf2ceb",
         config="01_models/_weights/MDX-Net/mdx_extra/mdx_extra.yaml",
         sample_rate=44100, channels=2, output_stems="vocals,drums,bass,other",
         source_of_truth="01_models/separation/README.md#MDX-Net"),
    dict(model="MDX-Net-quant", task="separation", repo="demucs", commit="e976d93ecc38",
         config="01_models/_weights/MDX-Net/{mdx_q,mdx_extra_q}/*.yaml",
         sample_rate=44100, channels=2, output_stems="vocals,drums,bass,other",
         source_of_truth="01_models/MODEL_REGISTRY.md#2.1"),
    dict(model="MMDenseLSTM", task="separation", repo="DNN-based_source_separation", commit="8663d6fc5c0a",
         config="n_fft=4096 hop=1024 sections=[380,644,1025] (in code)",
         sample_rate=44100, channels=2, output_stems="vocals,drums,bass,other (4 separate nets)",
         source_of_truth="01_models/separation/README.md#MMDenseLSTM"),
    dict(model="Open-Unmix", task="separation", repo="open-unmix-pytorch", commit="814f144e34b2",
         config="none (package default, n_fft=4096 hop=1024)",
         sample_rate=44100, channels=2, output_stems="vocals,drums,bass,other (4 separate nets)",
         source_of_truth="01_models/separation/README.md#Open-Unmix"),
    dict(model="Oracle-IRM", task="separation", repo="sigsep-mus-oracle", commit="1590b096c3fc",
         config="none", sample_rate=44100, channels=2, output_stems="vocals,drums,bass,other",
         source_of_truth="01_models/separation/README.md#Oracle-IRM"),
    dict(model="RPCA", task="separation", repo="_selfimpl", commit="n/a (in-tree)",
         config="none", sample_rate=44100, channels=2, output_stems="vocals (sparse component)",
         source_of_truth="01_models/separation/README.md#RPCA"),
    dict(model="denoiser-dns48", task="denoising", repo="denoiser", commit="8afd7c166699",
         config="none (architecture fully in code)", sample_rate=16000, channels=1,
         output_stems="enhanced", source_of_truth="01_models/denoising/README.md#denoiser-dns48"),
    dict(model="denoiser-dns64", task="denoising", repo="denoiser", commit="8afd7c166699",
         config="none (architecture fully in code)", sample_rate=16000, channels=1,
         output_stems="enhanced", source_of_truth="01_models/denoising/README.md#denoiser-dns64"),
    dict(model="denoiser-master64", task="denoising", repo="denoiser", commit="8afd7c166699",
         config="none (architecture fully in code)", sample_rate=16000, channels=1,
         output_stems="enhanced", source_of_truth="01_models/denoising/README.md#denoiser-master64"),
    dict(model="Mel-RoFormer-Denoise", task="denoising", repo="Music-Source-Separation-Training",
         commit="050cae7345f4",
         config="01_models/_weights/mel_roformer_denoise/model_mel_band_roformer_denoise.yaml",
         sample_rate=44100, channels=2, output_stems="enhanced",
         source_of_truth="01_models/denoising/README.md#Mel-RoFormer-Denoise"),
    dict(model="Mel-RoFormer-Dereverb", task="dereverberation", repo="Music-Source-Separation-Training",
         commit="050cae7345f4",
         config="01_models/_weights/mel_roformer_dereverb/dereverb_mel_band_roformer_anvuew.yaml",
         sample_rate=44100, channels=2, output_stems="dry",
         source_of_truth="01_models/denoising/README.md#Mel-RoFormer-Dereverb"),
    dict(model="Mel-RoFormer-Dereverb-Echo", task="dereverberation+deecho",
         repo="Music-Source-Separation-Training", commit="050cae7345f4",
         config="01_models/_weights/mel_roformer_dereverb_echo/config_dereverb-echo_mel_band_roformer.yaml",
         sample_rate=44100, channels=2, output_stems="dry,other (2 stems)",
         source_of_truth="01_models/denoising/README.md#Mel-RoFormer-Dereverb-Echo"),
    dict(model="RPCA+DRNN", task="separation", repo="unavailable", commit="unverified",
         config="unverified", sample_rate="unverified", channels="unverified",
         output_stems="2 stems (vocals/accompaniment)", source_of_truth="04_reports/01_separation/docs/MODEL_PROVISIONING_REPORT.md#3.2"),
    dict(model="Pac-HuBERT-SEP", task="separation", repo="unavailable (MERL)", commit="unverified",
         config="unverified", sample_rate="unverified", channels="unverified",
         output_stems="unverified", source_of_truth="01_models/MODEL_REGISTRY.md#2.2"),
]

# ----------------------------------------------------------------------
# checkpoint inventory
# ----------------------------------------------------------------------
CP = []


def add(model, name, path, source_type, url, training_data, metric, lic, recommended, evidence,
        declared_size=None, note=""):
    b, h = (None, "")
    if path:
        key = path.replace("\\", "/")
        if key in hb:
            b, h = hb[key]
        elif os.path.exists(key):
            # not covered by the .ckpt/.th/.pth sweep (e.g. .zip) -> hash it here
            import hashlib
            hh = hashlib.sha256()
            with open(key, "rb") as fh:
                for chunk in iter(lambda: fh.read(16 << 20), b""):
                    hh.update(chunk)
            b, h = os.path.getsize(key), hh.hexdigest()
            hb[key] = (b, h)
        else:
            raise SystemExit("MISSING HASH ENTRY: " + key)
    size_check = ""
    if b is not None and declared_size is not None:
        size_check = "PASS" if int(declared_size) == b else "MISMATCH:%d" % b
    elif b is not None:
        size_check = "unverified (no official size stated)"
    else:
        size_check = "not downloaded"
    CP.append(dict(model=model, checkpoint_name=name, source_type=source_type, url=url,
                   sha256=h, size_bytes="" if b is None else b,
                   size_mb="" if b is None else round(b / 1048576, 2),
                   declared_size=declared_size if declared_size is not None else "",
                   size_check=size_check, training_data=training_data,
                   reported_metric=metric, license=lic,
                   is_officially_recommended=recommended, evidence_path=evidence, note=note))


BSRV_EV = "01_models/_third_party/Music-Source-Separation-Training/docs/pretrained_models.md"
BSRV_URL = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/"

# --- BS-RoFormer (MSST official list)
add("BS-RoFormer-L12", "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    W + "/BS-RoFormer/model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    "official-list / community-trained (viperx)", BSRV_URL + "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    "MUSDB18-HQ + extra (UVR public model repo); exact mix unverified",
    "SDR vocals 10.87 (Multisong Dataset, mvsep quality checker)",
    "MSST repo MIT; weights license unstated",
    "YES - listed in official MSST docs 'Vocal models' table",
    BSRV_EV + " (Vocal models, row 'BS Roformer (viperx edition)')",
    declared_size=639331213,
    note="local byte size matches project record 639,331,213 B")

add("BS-RoFormer-L6", "model_bs_roformer_ep_937_sdr_10.5309.ckpt",
    W + "/BS-RoFormer/model_bs_roformer_ep_937_sdr_10.5309.ckpt",
    "official-list / community-trained (viperx)", BSRV_URL + "model_bs_roformer_ep_937_sdr_10.5309.ckpt",
    "MUSDB18-HQ + extra; exact mix unverified",
    "SDR other 6.85 (Multisong Dataset)",
    "MSST repo MIT; weights license unstated",
    "YES - listed in official MSST docs 'Single stem models' table",
    BSRV_EV + " (Single stem models, row 'BS Roformer (viperx) | other')",
    declared_size=393068365,
    note="yaml says target=other but measured output is vocals+other (see MODEL_PROVISIONING_REPORT 3.6)")

# --- MSST alternatives NOT downloaded (for comparison)
add("BS-RoFormer-L12", "model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt", None,
    "official-list / community-trained (viperx)",
    "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt",
    "unverified", "SDR vocals 9.67 (Multisong)", "unverified",
    "YES - listed in official MSST docs", BSRV_EV)
CP[-1]["note"] = "alternative not downloaded"

add("BS-RoFormer-L12", "MelBandRoformer.ckpt (KimberleyJensen)", None,
    "official-list / community-trained (KimberleyJensen)",
    "https://huggingface.co/KimberleyJSN/melbandroformer/resolve/main/MelBandRoformer.ckpt",
    "unverified", "SDR vocals 10.98 (Multisong)", "unverified",
    "YES - listed in official MSST docs", BSRV_EV)
CP[-1]["note"] = "alternative not downloaded; highest listed vocals SDR among Mel-Band entries"

add("BS-RoFormer-L12", "model_bs_polarformer_float16.ckpt", None,
    "official-list / community-trained",
    "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v1.0.20/model_bs_polarformer_float16.ckpt",
    "unverified", "SDR vocals 11.00 (Multisong)", "unverified",
    "YES - listed in official MSST docs", BSRV_EV)
CP[-1]["note"] = "alternative not downloaded; highest listed vocals SDR overall"

# --- BSRNN (Zenodo)
ZEN = "https://zenodo.org/records/17516442"
BZ_EV = "01_models/_third_party/bsrnn/README.md (line 14, 41-60, 103-113)"
for t in ("vocals", "drums", "bass", "other"):
    add("BSRNN-opt", "%s.ckpt (bsrnn-opt)" % t, W + "/BSRNN/bsrnn-opt/bsrnn-opt/%s.ckpt" % t,
        "official (Zenodo, authors' own)", ZEN, "MUSDB18-HQ (100 train songs)",
        "oBSRNN: vocals 9.81 / bass 9.85 / drums 10.31 / other 6.31 / avg 9.07 "
        "(MUSDB18-HQ test, chunk SDR = median over 1 s chunks then median over tracks)",
        "bsrnn repo MIT; Zenodo record license unverified",
        "YES - `model_dir` default is `bsrnn-opt` in the official separation CLI",
        BZ_EV + "; default: README line 111")
for t in ("vocals", "drums", "bass", "other"):
    add("BSRNN-large", "%s.ckpt (bsrnn-large)" % t, W + "/BSRNN/bsrnn-large/bsrnn-large/%s.ckpt" % t,
        "official (Zenodo, authors' own)", ZEN, "MUSDB18-HQ (100 train songs)",
        "large (patience=30): vocals 9.5 / bass 7.8 / drums 10.3 / other 6.3 / avg 8.5 "
        "(MUSDB18-HQ test, chunk SDR) - which row the released zip matches is unverified",
        "bsrnn repo MIT; Zenodo record license unverified",
        "NO - listed on Zenodo but no 'recommended/default' marker in README",
        BZ_EV + "; metrics: docs/analysis.md#line-129")
add("BSRNN-SIMO", "separator.ckpt (simo-bsrnn-opt)", W + "/BSRNN/simo-bsrnn-opt/simo-bsrnn-opt/separator.ckpt",
    "official (Zenodo, authors' own)", ZEN, "MUSDB18-HQ (100 train songs)",
    "oBSRNN-SIMO: vocals 10.66 / bass 9.73 / drums 10.98 / other 7.78 / avg 9.79 "
    "(MUSDB18-HQ test, chunk SDR)",
    "bsrnn repo MIT; Zenodo record license unverified",
    "YES - README states 'we encourage to consider this variant if achieving maximum performance is the goal'",
    BZ_EV + "; quote at README line ~58")

# --- Conv-TasNet / MMDenseLSTM / Open-Unmix (tky823)
TK = "01_models/_third_party/DNN-based_source_separation/egs/musdb18/README.md (SDR table)"
GDRV = "https://drive.google.com/ (link recorded in egs/musdb18/<model>/pretrained README)"
for tag, cfg in (("4sec_L20", "4 s / L=20"), ("8sec_L20", "8 s / L=20"), ("8sec_L64", "8 s / L=64")):
    add("Conv-TasNet", "best.pth (%s)" % tag,
        W + "/DNN-based_source_separation/ConvTasNet/musdb18/sr44100/%s/model/best.pth" % tag,
        "official (tky823 mirror of authors' tarin)", GDRV,
        "MUSDB18 train (100 songs)",
        "Conv-TasNet: bass 5.95 / drums 6.11 / other 3.78 / vocals 5.59 / avg 5.36 "
        "(MUSDB18 test, museval median-of-median SDR, 44.1 kHz)",
        "original repo MIT; mirror repo has NO LICENSE file",
        "NO - three community-converted variants, no 'recommended' marker",
        TK + " | 01_models/_third_party/DNN-based_source_separation/egs/musdb18/README.md")
for t in ("vocals", "drums", "bass", "other"):
    add("MMDenseLSTM", "%s/best.pth" % t,
        W + "/DNN-based_source_separation/MMDenseLSTM/musdb18/sr44100/paper/model/%s/best.pth" % t,
        "official (tky823 mirror, 'paper' preset)", GDRV, "MUSDB18 train (100 songs)",
        "MMDenseLSTM: bass 4.80 / drums 6.22 / other 4.43 / vocals 6.87 / avg 5.58 "
        "(MUSDB18 test, museval median-of-median SDR)",
        "mirror repo has NO LICENSE file",
        "NO - no 'recommended' marker", TK)
for t, hh in (("vocals", "b62c91ce"), ("drums", "9619578f"),
              ("bass", "8d85a5bd"), ("other", "b52fbbf7")):
    add("Open-Unmix", "%s-%s.pth" % (t, hh),
        W + "/open-unmix/%s-%s.pth" % (t, hh),
        "official (sigsep / UMX authors) - umxhq set",
        "https://zenodo.org/records/3370489/files/%s-%s.pth" % (t, hh),
        "MUSDB18-HQ (umxhq set, per openunmix/__init__.py::umxhq_spec)",
        "UMX: bass 5.02 / drums 6.06 / other 4.00 / vocals 6.14 / avg 5.30 "
        "(MUSDB18 test, museval median-of-median SDR, per tky823 mirror table)",
        "repo MIT; weight licence not stated for umxhq "
        "(only umxl is flagged CC BY-NC-SA 4.0 in README line 86)",
        "NO - no 'recommended' marker; it is the reference baseline. "
        "Note README line 86 calls umxl the default set - our files are umxhq, not umxl",
        TK + " | 01_models/_third_party/open-unmix-pytorch/openunmix/__init__.py (umxhq_spec)")

# --- Demucs
add("Demucs", "955717e8-8726e21a.th", W + "/Demucs/955717e8-8726e21a.th",
    "official (Meta / demucs authors)", "https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th",
    "MusDB + 800 extra songs (per demucs README line 222)",
    "HTDemucs4: Multisong avg 9.16 (bass 11.76, drums 10.88, vocals 8.24, other 5.74); "
    "README comparison table: HT Demucs f.t. 9.0 overall SDR",
    "MIT",
    "YES - README line 222: 'htdemucs ... Default model'; line 57 'used by default'",
    "01_models/_third_party/demucs/README.md (lines 57, 222); "
    "01_models/_third_party/Music-Source-Separation-Training/docs/pretrained_models.md",
    note="filename suffix 8726e21a == first 8 hex of computed SHA256 -> self-verifying")

# --- MDX-Net family (from demucs package)
FBAI = "https://dl.fbaipublicfiles.com/demucs/"
MDX_EV = "01_models/MODEL_REGISTRY.md#2.1; 04_reports/01_separation/docs/MODEL_PROVISIONING_REPORT.md#3.9"
mdxF = []
for p in sorted(hb):
    parts = p.split("/")
    if len(parts) == 5 and parts[1] == "_weights" and parts[2] == "MDX-Net" \
            and parts[3] in ("mdx", "mdx_extra", "mdx_q", "mdx_extra_q"):
        mdxF.append(p)
MDX_METRIC = {
    "mdx_extra": "mdx_extra: project-measured vocals 8.52 / drums 6.15 / bass 21.23 / other 8.88 "
                 "(museval 1 s window, 10 s clip, RTX 4070) - no official per-file metric published",
    "mdx": "mdx (demucs 'mdx' family): no official per-file metric published",
    "mdx_q": "mdx_q (quantised): demucs README says 'smaller but maybe a bit less accurate'; "
             "project-measured 8.80 dB on 3 clips",
    "mdx_extra_q": "mdx_extra_q (quantised): project-measured 8.37 dB vs mdx_extra 8.96 dB "
                   "(-0.59) on 3 clips x 10 s",
}
for p in mdxF:
    fam = p.split("/")[3]
    stem = p.rsplit("/", 1)[-1][:-3]
    model = "MDX-Net-quant" if fam.endswith("_q") else "MDX-Net"
    if fam == "mdx":
        rec = "YES (P3: demucs README line 228 - 'mdx ... winning model on track A at the MDX challenge')"
    elif fam == "mdx_extra":
        rec = "NO - 4-submission ensemble, no 'recommended' marker in demucs README"
    else:
        rec = "NO - demucs README calls the quantised variant 'smaller but maybe a bit less accurate'"
    add(model, "%s.th (%s)" % (stem, fam), p,
        "official (Meta demucs model pack / MDX challenge submissions)",
        FBAI + fam + "/" + stem + ".th",
        "MUSDB18 (+ extra for mdx_extra), unverified per-file",
        MDX_METRIC[fam],
        "MIT (mdx-net + submission repos)",
        rec,
        MDX_EV)

# --- remaining local artefacts: last-epoch companions + MDX ensemble extras
for p in sorted(hb):
    parts = p.split("/")
    base = parts[-1]
    if base == "last.pth" and "ConvTasNet" in p:
        tag = parts[6]
        add("Conv-TasNet", "last.pth (%s)" % tag, p, "official (tky823 mirror)",
            GDRV, "MUSDB18 train (100 songs)", "same weights family as best.pth",
            "original repo MIT; mirror repo has NO LICENSE file",
            "NO - last-epoch companion of best.pth, kept for completeness",
            TK, note="not used by the benchmark (best.pth is used)")
    elif base == "last.pth" and "MMDenseLSTM" in p:
        tgt = parts[8]
        add("MMDenseLSTM", "%s/last.pth" % tgt, p, "official (tky823 mirror)",
            GDRV, "MUSDB18 train (100 songs)", "same weights family as best.pth",
            "mirror repo has NO LICENSE file",
            "NO - last-epoch companion of best.pth, kept for completeness", TK,
            note="not used by the benchmark (best.pth is used)")

add("MDX-Net", "mixer.ckpt (ensemble mixer)", W + "/MDX-Net/mixer.ckpt",
    "official (Meta demucs model pack)", FBAI, "n/a (mixing weights)",
    "n/a - blends the 4 mdx_extra outputs", "MIT",
    "NO - auxiliary file, only used by the mdx_extra ensemble path", MDX_EV,
    note="1.2 KB blending weights, not a neural checkpoint")
add("MDX-Net", "onnx_A.zip (ONNX export bundle)", W + "/MDX-Net/onnx_A.zip",
    "official (MDX challenge submission A)", "unverified",
    "MUSDB18", "unverified", "MIT (submission repo)",
    "NO - reference artefact, not used by this project's PyTorch path", MDX_EV,
    note="110 MB zip of ONNX exports; never unpacked in this project")

# --- denoiser (CC-BY-NC)
DEN = "https://dl.fbaipublicfiles.com/adiyoss/denoiser/"
DEN_EV = "01_models/_third_party/denoiser/denoiser/pretrained.py (lines 16-20); README lines 211-244"
add("denoiser-dns48", "dns48-11decc9d8e3f0998.th", W + "/denoiser/dns48-11decc9d8e3f0998.th",
    "official (Meta denoiser authors)", DEN + "dns48-11decc9d8e3f0998.th", "DNS (48 hidden)",
    "no metric table in README; paper: Defossez et al. Interspeech 2020 (number unverified here)",
    "CC-BY-NC 4.0 (NON-COMMERCIAL)", "NO - one of 3 offered variants, no default flag",
    DEN_EV, note="filename suffix 11decc9d8e3f0998 == SHA256 prefix -> self-verifying")
add("denoiser-dns64", "dns64-a7761ff99a7d5bb6.th", W + "/denoiser/dns64-a7761ff99a7d5bb6.th",
    "official (Meta denoiser authors)", DEN + "dns64-a7761ff99a7d5bb6.th", "DNS (64 hidden)",
    "no metric table in README (unverified)",
    "CC-BY-NC 4.0 (NON-COMMERCIAL)", "NO - no default flag; get_model() has no fallback branch",
    DEN_EV, note="filename suffix a7761ff99a7d5bb6 == SHA256 prefix -> self-verifying")
add("denoiser-master64", "master64-8a5dfb4bb92753dd.th", W + "/denoiser/master64-8a5dfb4bb92753dd.th",
    "official (Meta denoiser authors)", DEN + "master64-8a5dfb4bb92753dd.th",
    "DNS + Valentini (per CLI help text line 55)",
    "no metric table in README (unverified)",
    "CC-BY-NC 4.0 (NON-COMMERCIAL)",
    "NO - no default flag, BUT its training set includes Valentini -> in-domain on our test set",
    DEN_EV, note="filename suffix 8a5dfb4bb92753dd == SHA256 prefix -> self-verifying")
add("denoiser-dns64", "valentini_nc-93fc4337.th", None,
    "official (Meta denoiser authors)", DEN + "valentini_nc-93fc4337.th",
    "Valentini (non-causal)", "unverified", "CC-BY-NC 4.0 (NON-COMMERCIAL)",
    "NO - offered but not used by this project", DEN_EV)
CP[-1]["note"] = "NOT downloaded - official 4th checkpoint, missing from local inventory"

# --- Mel-RoFormer family (MSST official list, community-trained)
add("Mel-RoFormer-Denoise", "denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
    W + "/mel_roformer_denoise/denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
    "official-list / community-trained (aufr33)",
    "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v.1.0.7/denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
    "unverified", "no SDR column in MSST table (denoise task, '---')",
    "MSST repo MIT; trainer did not state a license",
    "YES - listed in official MSST docs 'Single stem models' (denoise)",
    BSRV_EV + " (row 'MelBand Roformer Denoise (by aufr33)')")
add("Mel-RoFormer-Denoise", "denoise_mel_band_roformer_aufr33_aggr_sdr_27.9768.ckpt",
    W + "/mel_roformer_denoise/denoise_mel_band_roformer_aufr33_aggr_sdr_27.9768.ckpt",
    "official-list / community-trained (aufr33)",
    "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v.1.0.7/denoise_mel_band_roformer_aufr33_aggr_sdr_27.9768.ckpt",
    "unverified", "no SDR column in MSST table (denoise task, '---')",
    "MSST repo MIT; trainer did not state a license",
    "YES - listed in official MSST docs (Denoise Aggressive)",
    BSRV_EV + " (row 'MelBand Roformer Denoise Aggressive (by aufr33)')")
add("Mel-RoFormer-Dereverb", "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
    W + "/mel_roformer_dereverb/dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
    "official-list / community-trained (anvuew)",
    "https://huggingface.co/anvuew/dereverb_mel_band_roformer/resolve/main/dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
    "unverified", "MSST table shows '---' for dereverb; the 19.1729 in the filename is not explained in docs",
    "MSST repo MIT; HF repo license unverified",
    "YES - listed in official MSST docs 'Single stem models' (dereverb)",
    BSRV_EV + " (row 'MelBand Roformer (anvuew) | dereverb')")
add("Mel-RoFormer-Dereverb-Echo", "dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt",
    W + "/mel_roformer_dereverb_echo/dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt",
    "official-list / community-trained (SUC-DriverOld / Sucial)",
    "https://huggingface.co/Sucial/Dereverb-Echo_Mel_Band_Roformer/resolve/main/dereverb-echo_mel_band_roformer_sdr_10.0169.ckpt",
    "unverified", "SDR 10.01 (MSST table, 'Single stem models', row SUC-DriverOld)",
    "MSST repo MIT; HF repo license unverified",
    "YES - listed in official MSST docs",
    BSRV_EV + " (row 'MelBand Roformer Vocals DeReverb/DeEcho (SUC-DriverOld)')")

# --- DPRNN self-trained
add("DPRNN", "best.pt (self-trained, step 31900)", W + "/dprnn_musdb/best.pt",
    "self-trained (NOT official)", "n/a - produced locally by tools/train_dprnn_musdb.py",
    "MUSDB18-HQ train, 4 s chunks, 11.025 kHz",
    "project-measured: 4-stem median SDR mean -1.72 dB (museval, 3 balanced clips, 44.1 kHz)",
    "project's own (no third-party license)",
    "NO - official repo publishes only wsj0-mix / librispeech speech weights, no MUSDB18 music weights",
    "01_models/MODEL_REGISTRY.md#6; 04_reports/01_separation/docs/MODEL_PROVISIONING_REPORT.md#3.4")

add("DPRNN", "last.pt (self-trained, step 31900, final epoch)", W + "/dprnn_musdb/last.pt",
    "self-trained (NOT official)", "n/a - produced locally by tools/train_dprnn_musdb.py",
    "MUSDB18-HQ train, 4 s chunks, 11.025 kHz",
    "project-measured: same run as best.pt; benchmark uses best.pt",
    "project's own (no third-party license)",
    "NO - final-epoch companion; best.pt is the one used for evaluation",
    "01_models/MODEL_REGISTRY.md#6",
    note="43 MB vs best.pt 14 MB -> last.pt also stores optimiser state")

# ----------------------------------------------------------------------
# normalise the "officially recommended" verdict against the 4-level rule
#   P1 README / model card says recommended|best|default
#   P2 official CLI default model
#   P3 official leaderboard / competition best submission
#   P4 weight that produced the paper's main result
#   none of the above -> "no official recommendation, usable weights only"
# ----------------------------------------------------------------------
NO_REC = ("NO - 无官方推荐，仅有可用权重"
          "（已列入官方预训练清单，但清单内无 recommended/best/default 标记）")

P1 = {
    "Demucs": "YES (P1) - demucs README line 222: 'htdemucs ... Default model'; line 57 'now used by default'",
    "BSRNN-SIMO": "YES (P1) - bsrnn README: 'we encourage to consider this variant if achieving maximum performance is the goal'",
}
P2 = {
    "BSRNN-opt": "YES (P2) - official separation CLI default is model_dir=bsrnn-opt (bsrnn README line 111)",
}
P3 = "YES (P3) - demucs README line 228: 'mdx ... winning model on track A at the MDX challenge'"

for r in CP:
    m, n = r["model"], r["checkpoint_name"]
    if m in P1:
        r["is_officially_recommended"] = P1[m]
    elif m in P2:
        r["is_officially_recommended"] = P2[m]
    elif m == "MDX-Net" and n.endswith("(mdx)"):
        r["is_officially_recommended"] = P3
    elif m in ("BS-RoFormer-L12", "BS-RoFormer-L6", "Mel-RoFormer-Denoise",
               "Mel-RoFormer-Dereverb", "Mel-RoFormer-Dereverb-Echo"):
        r["is_officially_recommended"] = NO_REC
    elif m == "MDX-Net":
        r["is_officially_recommended"] = ("NO - 无官方推荐，仅有可用权重"
                                          "（4-submission ensemble，README 未标注推荐）")

# ----------------------------------------------------------------------
# write
# ----------------------------------------------------------------------
mi = OUT / "model_inventory.csv"
with open(mi, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["model", "task", "repo", "commit", "config",
                                      "sample_rate", "channels", "output_stems", "source_of_truth"])
    w.writeheader()
    w.writerows(MODELS)

ci = OUT / "checkpoint_inventory.csv"
cols = ["model", "checkpoint_name", "source_type", "url", "sha256", "size_bytes", "size_mb",
        "declared_size", "size_check", "training_data", "reported_metric", "license",
        "is_officially_recommended", "evidence_path", "note"]
with open(ci, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(CP)

print("model_inventory.csv    : %d rows" % len(MODELS))
print("checkpoint_inventory.csv: %d rows (%d with local hash, %d not downloaded)"
      % (len(CP), sum(1 for r in CP if r["sha256"]), sum(1 for r in CP if not r["sha256"])))
bad = [r for r in CP if r["size_check"].startswith("MISMATCH")]
print("size MISMATCH against official statement: %d" % len(bad))
for r in bad:
    print("   ", r["model"], r["checkpoint_name"], r["size_check"])

# coverage check: every local weight file must appear in the inventory
listed = {r["url"].rsplit("/", 1)[-1] for r in CP}
missing = []
for p, (b, h) in hb.items():
    base = os.path.basename(p)
    if base == "mixer.ckpt" or base == "onnx_A.zip":
        continue
    if base not in " ".join(r["checkpoint_name"] for r in CP) and base not in listed:
        missing.append(p)
print("local weight files not described in inventory: %d" % len(missing))
for m in missing[:10]:
    print("   ", m)

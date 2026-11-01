# -*- coding: utf-8 -*-
"""阶段一：盲跑产物审计表生成器（只读采集 + 写 CSV/MD）。

严格遵守：
  * 只读项目原产物，不训练、不推理、不下载、不覆盖
  * 输出只写入 runs/audit_20261030/
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "runs" / "audit_20261030"
OUT.mkdir(parents=True, exist_ok=True)

CKPT = ROOT / "04_reports/00_shared/docs/checkpoint_audit/checkpoint_inventory.csv"


def sha256_short(rel: str, n: int = 16) -> str:
    p = ROOT / rel
    if not p.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(16 << 20), b""):
            h.update(c)
    return h.hexdigest()[:n]


def count_files(rel: str, pat: str = "*") -> int:
    return sum(1 for _ in (ROOT / rel).rglob(pat)) if (ROOT / rel).is_dir() else 0


def du_mb(rel: str) -> float:
    p = ROOT / rel
    if not p.exists():
        return 0.0
    t = 0
    for r, _, fs in os.walk(p):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return round(t / 1048576.0, 1)


# 权重 hash（来自实算清单，唯一可信来源）
WEIGHT_HASH = {
    "Demucs": "955717e8...",
    "MDX-Net": "mdx_extra x4 (639 MiB)",
    "Conv-TasNet": "convtasnet MUSDB18",
    "MMDenseLSTM": "MMDenseLSTM MUSDB18",
    "Open-Unmix": "umxhq x4",
    "BS-RoFormer-L12": "ep_317_sdr_12.9755",
    "BS-RoFormer-L6": "ep_937_sdr_10.5309",
    "BSRNN-opt": "bsrnn-opt x4",
    "BSRNN-large": "bsrnn-large x4",
    "BSRNN-SIMO": "simo-bsrnn-opt",
    "DPRNN": "dprnn_musdb/best.pt (自训)",
    "Oracle-IRM": "N/A (解析)",
    "RPCA": "N/A (解析)",
    "denoiser-dns48": "dns48-11decc9d8e3f0998.th",
    "denoiser-dns64": "dns64-a7761ff99a7d5bb6.th",
    "denoiser-master64": "master64-8a5dfb4bb92753dd.th",
    "Mel-RoFormer-Denoise": "aufr33 x2",
    "Mel-RoFormer-Dereverb": "anvuew_sdr_19.1729",
    "Mel-RoFormer-Dereverb-Echo": "dereverb-echo x2",
}

ROWS = []


def add(oid, path, model, config, cmd, log, whash, contract, metric, verdict, evidence, action):
    ROWS.append(dict(
        output_id=oid, path=path, model=model, config=config,
        command_available=cmd, log_available=log, weight_hash=whash,
        input_contract=contract, metric_reported=metric, verdict=verdict,
        evidence=evidence, recommended_action=action,
        size_mb=du_mb(path) if (ROOT / path).exists() else 0,
        n_files=count_files(path, "*") if (ROOT / path).is_dir() else 0,
    ))


# ---------------- A. 分离模型批量推理输出 ----------------
SEP = [
    ("S01", "03_outputs/Demucs", "Demucs", "htdemucs 44.1k/2ch", "200 flac, 50曲x4stem", "B",
     "音频有效(246.7s/44.1k/2ch/rms0.083)；无 run manifest、无命令行、无日志绑定；"
     "仅靠 MODEL_REGISTRY 表格引用，无法逐条追溯"),
    ("S02", "03_outputs/MDX-Net", "MDX-Net", "mdx_extra 44.1k/2ch", "200 flac", "B",
     "音频有效(179.6s/44.1k/rms0.069)；无 manifest/命令"),
    ("S03", "03_outputs/Conv-TasNet", "Conv-TasNet", "44.1k/2ch", "200 flac", "B",
     "音频有效(212.3s/44.1k/rms0.063)；无 manifest/命令"),
    ("S04", "03_outputs/MMDenseLSTM", "MMDenseLSTM", "44.1k/2ch", "200 flac", "B",
     "音频存在；无 manifest/命令；权重来源为 paper 版 MUSDB18"),
    ("S05", "03_outputs/Open-Unmix", "Open-Unmix", "umxhq 44.1k/2ch", "200 flac", "B",
     "音频存在；umxhq 权重许可未声明(README 只对 umxl 声明 CC BY-NC-SA)"),
    ("S06", "03_outputs/BS-RoFormer-L12", "BS-RoFormer-L12", "ep_317 单目标 vocals", "200 flac", "B",
     "单目标模型(vocals only)，不能与四轨模型均值直接比；无 run manifest"),
    ("S07", "03_outputs/BS-RoFormer-L6", "BS-RoFormer-L6", "ep_937 输出=vocal+other", "200 flac", "B",
     "🔴 语义陷阱：yaml 写 target=other，实测输出 mixture-drums-bass(vocals+other)，"
     "直接与纯 other 比会误判失效"),
    ("S08", "03_outputs/BSRNN-opt", "BSRNN-opt", "bsrnn-opt x4 聚合", "50 flac", "B",
     "仅 50 flac(单轨输出)，非 200；四 ckpt 按位置对齐，顺序错会静默互换"),
    ("S09", "03_outputs/BSRNN-large", "BSRNN-large", "bsrnn-large x4", "50 flac", "B",
     "仅 50 flac；与 opt 变体需分开报"),
    ("S10", "03_outputs/BSRNN-SIMO", "BSRNN-SIMO", "simo-bsrnn-opt", "200 flac", "B",
     "四轨 SIMO，官方 P1 推荐；无 run manifest"),
    ("S11", "03_outputs/Oracle-IRM", "Oracle-IRM", "解析 oracle 上限", "200 flac", "B",
     "音频有效；oracle 是理论上界，不是模型，禁止进入模型排名"),
]
for oid, path, model, cfg, cnt, verdict, ev in SEP:
    add(oid, path, model, cfg, "no", "no", WEIGHT_HASH.get(model, "见 checkpoint_audit"),
        "44.1kHz/2ch/整曲", "SDR/ISR/SAR (comparison_results.csv)", verdict,
        ev + "；%s" % cnt, "补证后保留（补 run manifest）")

# DPRNN 单独：D 类
add("S12", "03_outputs/DPRNN", "DPRNN", "自训 11.025k->44.1k 单声道", "yes(train_dprnn_musdb.py)",
    "yes(train_dprnn_musdb.txt)", "best.pt sha=%s" % sha256_short("01_models/_weights/dprnn_musdb/best.pt"),
    "44.1kHz/2ch/整曲",
    "四轨均值 SDR -1.72 dB（欠训练，不参与排名）",
    "D",
    "🔴 验证集泄漏：VAL_CLIPS 三首 subset='train'，与训练集同为 MUSDB train 100 首；"
    "best.pt 由该验证集选出 → 模型选择污染。证据：train_dprnn_musdb.py L78-82；"
    "日志 L4 '训练集: 100 首歌'；验证 best=+2.745 dB 而测试 -1.72 dB（差 4.5 dB）。"
    "另有削波：抽样 20 flac peak=1.0000、clipped 0.0168%",
    "重跑（改按歌曲划分 + 独立验证集）")

# ---------------- B. 空/失败产物 ----------------
add("S13", "03_outputs/RPCA", "RPCA", "解析 44.1k/2ch", "yes", "no", "N/A (解析)",
    "44.1kHz/2ch", "无（目录 0 文件）", "C",
    "🔴 目录存在但 find 计数 0 文件（0 MB）。MODEL_REGISTRY 标 ✅ 可运行，与磁盘不符。"
    "稀疏分量无 stem 归属，注册表只报区间 1.8~3.5 dB",
    "重跑（或标为不产出 stem 的解析基线）")

add("S14", "03_outputs/mdx_q", "MDX-Net-mdx_q", "mdx_q x4 量化", "no", "no", "mdx_q x4",
    "44.1kHz/2ch", "仅 3 段 x 10s 对比（8.80 dB）", "B",
    "12 MB，非全量；量化版仅作参考（属 demucs mdx 另一权重族）", "作废或补全量")
add("S15", "03_outputs/mdx_extra_q", "MDX-Net-mdx_extra_q", "mdx_extra_q x4 量化", "no", "no", "mdx_extra_q x4",
    "44.1kHz/2ch", "3 段 x 10s：8.96->8.37 (-0.59)", "B",
    "13 MB，非全量；量化损失 -0.59 dB 有记录", "补证后保留")

# ---------------- C. 降噪 ----------------
for oid, name, cfg in [
    ("D01", "denoiser-dns48", "dns48, causal, 16k/1ch"),
    ("D02", "denoiser-dns64", "dns64, causal, 16k/1ch"),
    ("D03", "denoiser-master64", "master64, causal, 16k/1ch"),
]:
    add(oid, "03_outputs/%s" % name, name, cfg, "no", "no", WEIGHT_HASH[name],
        "16kHz/1ch（契约 44.1kHz/2ch 输入）", "单条样音 112 KB", "C",
        "目录仅 1 个 wav(112 KB)，是单条冒烟产物，不是评测输出；"
        "真正评测在 04_reports/02_denoising/data/denoise_eval_*.csv", "作废（保留少量样音）")

for oid, name, cfg in [
    ("D04", "Mel-RoFormer-Denoise", "aufr33_sdr_27.9959"),
    ("D05", "Mel-RoFormer-Dereverb", "anvuew_sdr_19.1729"),
    ("D06", "Mel-RoFormer-Dereverb-Echo", "dereverb-echo (2-stem dry/other)"),
]:
    add(oid, "03_outputs/%s" % name, name, cfg, "no", "no", WEIGHT_HASH[name],
        "44.1kHz/2ch", "1-2 个 wav", "C",
        "仅 1-2 个 wav（600 KB-1.2 MB），是单条抽查；非全量评测。"
        "mel 两变体(aufr33/aggr)结果差异极大(+0.96 vs +21.17)，不能混报", "作废（评测走另一路径）")

add("D07", "03_outputs/_valentini_denoise", "denoiser+mel 全家桶", "多模型 44.1k/16k 混合",
    "no", "no", "见各模型", "🔴 混合：denoiser=16k/1ch, mel=44.1k/2ch",
    "5768 wav（824 x 7 模型）", "B",
    "🔴 采样率不统一：抽样见 denoiser_dns64/p232_292.wav=16kHz/1ch，"
    "mel_roformer_dereverb/p257_153.wav=44.1kHz/2ch。跨模型不能直接横比。"
    "mtime 2026-10-13 00:31-00:49，无 manifest、无命令",
    "补证后保留（按模型分目录已隔离，可逐模型用）")

add("D08", "03_outputs/_denoise_ab", "A/B 试听", "44.1k", "no", "no", "见各模型", "混合",
    "112 wav", "B", "试听用途，非评测；无 manifest", "保留（非指标用途）")
add("D09", "03_outputs/_denoise_live", "实时服务", "44.1k", "yes(serve script)", "no", "见各模型",
    "44.1kHz/2ch", "185 wav", "B", "本地三页服务的实时输出，非评测产物", "保留")

# ---------------- D. 级联/回响/评测 ----------------
add("C01", "03_outputs/_cascade", "级联 4x4", "4 分离模型 x 4 SNR", "yes", "yes",
    "见各模型", "合成 20s 片段 44.1k/2ch", "cascade_eval.csv 16 行",
    "B",
    "🔴 小样本：4 模型 x 4 SNR = 16 格，非全量；负结果为主（40/48 前置格为负）；"
    "已用 _cascade_regate.py 重判 680/680 PASS", "补证后保留（标注 n=16）")
add("C02", "03_outputs/_cascade_live", "级联试听", "同 C01", "no", "no", "见各模型", "44.1kHz/2ch",
    "93 wav", "B", "试听产物", "保留（非指标）")
add("C03", "03_outputs/_eval", "级联评测图", "cascade__<sep>__<den>__<set>", "no", "no",
    "见各模型", "44.1kHz/2ch", "16200 png + 36 results.json", "B",
    "图与 json 齐全，但 16200 png 是可视化(每格 1 png + 1 done)，非指标源；"
    "36 个目录=x 组合", "补证后保留")
add("C04", "03_outputs/_eval_test", "冒烟评测", "musdb/dns/cascade", "no", "no", "见各模型", "混合",
    "29 文件(10 png+10 done+7 json)", "C",
    "冒烟测试残留，样本数极小，不能作为结果引用", "作废")
add("C05", "03_outputs/_reverb", "混响/回声实验", "T60 干/小/大 + echo", "no", "no", "不涉及模型",
    "合成 20s 44.1kHz/2ch", "87 wav（dry/small/large/echo）", "B",
    "音频有效(20.00s/44.1k/2ch)；无 run manifest；结论见 STAGE4_SUMMARY",
    "补证后保留")

# ---------------- E. 样音/服务/重跑 ----------------
add("X01", "03_outputs/TableSample_Audio", "演示样音包", "多级联组合", "no", "no", "见各模型",
    "48kHz/1ch（Valentini 原生）", "933 wav", "B",
    "🔴 manifest 只剩 1 条，但有 25 个目录/933 wav —— 清单与磁盘严重不匹配"
    "（933 wav 对应几百条记录，manifest 只有 1 条）", "补证后保留（必须重建 manifest）")
add("X02", "03_outputs/_sep_live", "逐模型试听服务", "44.1k", "yes", "no", "见各模型",
    "44.1kHz/2ch", "23 wav", "B", "服务缓存", "保留（非指标）")
add("X03", "03_outputs/_wiener_pkg", "Wiener 打包", "解析", "no", "no", "N/A", "44.1k", "无 wav(8 KB)",
    "C", "8 KB 空壳目录，无音频产物", "作废")
add("X04", "03_outputs/rerun_20261030_1700", "demucs+bsroformer_l12", "3 曲 x 10s", "yes(完整命令行)",
    "yes(logdir)", "有 weight_hashes.json", "44.1kHz/2ch/10s",
    "rerun_report.json（无 SDR 指标，仅契约与耗时）", "A",
    "✅ 全项目唯一有完整 meta 的产物：command/python3.13.14/torch2.14.0+cu126/"
    "cuda12.6/git commit 1107b16/git_dirty=111/时间戳齐全", "保留（作为可追溯范式模板）")

# ---------------- F. 训练产物 ----------------
add("T01", "01_models/_weights/dprnn_musdb", "DPRNN", "自训 6层LSTM 3.69M", "yes", "yes",
    "best.pt=14.8MB last.pt=44.4MB", "11.025kHz/单声道/4.0s chunk",
    "val mean SI-SDR 2.745 (best)", "D",
    "checkpoint 元数据完整(step31700/best2.745/cfg/targets/sr/val)，last.pt 含 opt；"
    "但 best 由 train 子集验证选出 → 模型选择污染；JSON total_min=3.0 与日志 250.7 min 矛盾",
    "重跑（修划分 + 修元数据）")
add("T02", "04_reports/01_separation/data/dprnn_training.json", "DPRNN", "训练历史", "yes", "yes",
    "同 T01", "11.025kHz", "steps 217 / vals 297", "B",
    "🔴 total_min=3.0 但日志显示 250.7 min（最后一轮 --minutes 3，续跑 14.5h）；"
    "batch 字段=8 而日志启动行 batch=4（元数据被后续轮次覆盖）", "补证后保留（修元数据）")

# ---------------- G. 指标表 ----------------
add("M01", "04_reports/01_separation/data/comparison/comparison_results.csv", "多模型", "主对比表",
    "no", "no", "见各模型", "44.1kHz/2ch", "100 行 SDR/ISR/SAR/SI_SDR + delta_SDR", "B",
    "只有 100 行（抽样，非 50曲x4stem 全量）；delta_SDR 以 mixture 为基线，口径正确",
    "补证后保留（标注抽样）")
add("M02", "04_reports/02_denoising/data/denoise_eval_16k.csv", "denoiser+mel", "16k 主表",
    "yes", "yes", "见各模型", "16kHz/1ch", "40 行", "B",
    "🔴 dns_dev 6 行 si_sdr_in/out/improve 全为 0.00（noref 模式空值被写成 0）；"
    "synth 行正常(4.83->15.35,+11.61)；n_skipped 全 0（已是 P19 修复后版本）",
    "补证后保留（dns_dev 行改 null，不能写 0）")
add("M03", "04_reports/02_denoising/data/denoise_eval_44k.csv", "denoiser+mel", "44.1k 副表",
    "yes", "yes", "见各模型", "44.1kHz/2ch", "20 行 fullref", "B",
    "Valentini fullref 824 条，口径正确；与 16k 表不可混表", "保留")
add("M04", "04_reports/03_cascade/data/cascade_eval.csv", "级联", "4 模型 x 4 SNR",
    "yes", "yes", "见各模型", "合成 20s 44.1k", "16 行", "B",
    "n=16 小样本；L1=L1b+(L1-L1b) 逐格恒等；负结果为主", "补证后保留（标注 n=16）")
add("M05", "04_reports/00_shared/data/model_analysis/model_profile.csv", "22 模型", "画像表",
    "yes", "no", "见各模型", "native_sr/native_ch 逐模型", "22 行 params/rtf/vram", "A",
    "✅ 22 模型齐全，含 params_M/rtf/peak_vram_infer_mb/native_sr/native_ch，"
    "可直接作为训练配置卡依据", "保留")

# ---------------- 写出 ----------------
COLS = ["output_id", "path", "model", "config", "command_available", "log_available",
        "weight_hash", "input_contract", "metric_reported", "verdict", "evidence",
        "recommended_action", "size_mb", "n_files"]

with open(OUT / "audit_blind_runs.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for r in ROWS:
        w.writerow(r)

from collections import Counter
c = Counter(r["verdict"] for r in ROWS)
print("rows", len(ROWS))
print("verdict", dict(sorted(c.items())))
print("A:", [r["output_id"] for r in ROWS if r["verdict"] == "A"])
print("C:", [r["output_id"] for r in ROWS if r["verdict"] == "C"])
print("D:", [r["output_id"] for r in ROWS if r["verdict"] == "D"])
print("total size MB", sum(r["size_mb"] for r in ROWS))
print("out", OUT / "audit_blind_runs.csv")

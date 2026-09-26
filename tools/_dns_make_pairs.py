"""T5.4 自造带噪对（P12 决策：给评测补出「可控 SNR」的 fullref 能力）。

背景
----
DNS `dev_testset` 官方只发 `noisy_testclips`（921 条），**没有 clean GT** -> 只能算无参考指标。
本项目要「可跨模型比较的 fullref 指标 + 可复用的 SNR 分层」，所以自主合成带噪对。

⚠️ 语音源的选择（踩过的坑，别改回去）
--------------------------------------
初版用 DNS 自己的 clean 子集（emotional_speech / VocalSet）做语音源，结果**大面积塌陷**：
纯 clean 直通时输出 rms 只有输入的 0.1%~2%。排查结论：
  a. **电平**：DNS clean 的绝对电平偏低（rms 0.005~0.03，即 −46~−30 dBFS），
     而 denoiser 带**绝对电平门控**，低电平语音被整体判为静音。
  b. **内容**：VocalSet 是歌唱练声曲（vibrato scales，无歌词纯元音），
     emotional_speech 含大量气声/长静音 —— 都偏离 denoiser 的语音训练分布。
→ 二者叠加使该组合不可用。**最终改用 Valentini `clean_testset` 作语音源**
  （已验证与模型匹配：纯 clean 直通 ratio ≈ 0.99），噪声仍用 DNS freesound。

数据源
------
  语音：02_databases/Valentini/clean_testset_wav        824 条 48 kHz（已验证匹配）
  噪声：02_databases/DNS-Challenge/noise/freesound      2308 条（DNS 官方噪声库）

设计
----
1. **不落盘音频**：manifest 记 `(clean, noise, snr_db, seed)`，评测时即时合成。
2. **SNR 是真值**：分层键由我们设定，比事后估计更干净。
3. **四档 SNR**：-5 / 0 / 5 / 10 dB（覆盖 P11 发现的指标交叉点两侧）。
4. 噪声按索引循环，保证不同语音配到不同噪声。

产出：
  denoiser/data/synth_pairs_manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

VAL_CLEAN = _paths.PROJECT_ROOT / "02_databases" / "Valentini" / "clean_testset_wav"
NOISE = _paths.PROJECT_ROOT / "02_databases" / "DNS-Challenge" / "noise" / "freesound"

DEN_DATA = _paths.DEN_DATA
DEN_DATA.mkdir(parents=True, exist_ok=True)

SR = 48000
SNR_LEVELS = [-5.0, 0.0, 5.0, 10.0]
OUT_NAME = "synth_pairs_manifest.json"


def build(n_speech=200, snr_levels=None, seed=0, min_dur=2.0, max_dur=12.0):
    import soundfile as sf

    snr_levels = snr_levels or SNR_LEVELS
    clean_files = sorted(VAL_CLEAN.glob("*.wav"))
    noise_files = sorted(NOISE.rglob("*.wav"))
    if not clean_files:
        raise SystemExit("[FATAL] 无语音源：%s" % VAL_CLEAN)
    if not noise_files:
        raise SystemExit("[FATAL] 无噪声源：%s" % NOISE)

    rng = random.Random(seed)
    order = list(range(len(clean_files)))
    rng.shuffle(order)
    picked = []
    for i in order:
        if len(picked) >= n_speech:
            break
        p = clean_files[i]
        try:
            info = sf.info(str(p))
        except Exception:
            continue
        dur = info.frames / float(info.samplerate)
        if min_dur <= dur <= max_dur:
            picked.append(p)
    if not picked:
        raise SystemExit("[FATAL] 没有满足时长 [%s,%s] 的语音" % (min_dur, max_dur))

    rows = []
    for k, snr in enumerate(snr_levels):
        for j, cp in enumerate(picked):
            nf = noise_files[(j + k * 37 + seed) % len(noise_files)]
            rows.append({
                "id": "%s_s%+03d" % (cp.stem, int(snr)),
                "clean": str(cp.relative_to(_paths.PROJECT_ROOT)),
                "noise": str(nf.relative_to(_paths.PROJECT_ROOT)),
                "snr_db": float(snr),
                "subset": "synth",
                "snr_bin": ("<5dB" if snr < 5 else "5-15dB" if snr < 15 else ">=15dB"),
            })

    man = {
        "task": "T5.4 自造带噪对清单（P12）",
        "why": "DNS dev_testset 无 clean GT -> 自造，GT 与 SNR 均为真值",
        "speech_source": "Valentini clean_testset_wav（已验证与 denoiser 匹配）",
        "noise_source": "DNS-Challenge freesound（官方噪声库）",
        "rejected_sources": {
            "dns clean/emotional_speech": "绝对电平偏低 + 多气声/静音 -> 模型整段静音",
            "dns clean/VocalSet_48kHz_mono": "歌唱练声曲，非语音分布 -> 模型整段静音",
        },
        "sr_native": SR,
        "snr_levels": snr_levels,
        "n_speech": len(picked),
        "n_noise_pool": len(noise_files),
        "n_rows": len(rows),
        "mix_recipe": "noisy = clean + g * noise,  g = sqrt(P_clean / (P_noise * 10^(snr/10)))",
        "rows": rows,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    out = DEN_DATA / OUT_NAME
    out.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man, out


def main():
    ap = argparse.ArgumentParser(description="构造自造带噪对清单")
    ap.add_argument("--n-speech", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--snr", default=",".join(str(s) for s in SNR_LEVELS))
    ap.add_argument("--min-dur", type=float, default=2.0)
    ap.add_argument("--max-dur", type=float, default=12.0)
    a = ap.parse_args()

    levels = [float(x) for x in a.snr.split(",")]
    man, out = build(a.n_speech, levels, a.seed, a.min_dur, a.max_dur)
    print("[json] %s" % out)
    print("  语音 %d 条 x SNR %s 档 = %d 条" % (man["n_speech"], man["snr_levels"],
                                               man["n_rows"]))
    print("  噪声池 %d 条" % man["n_noise_pool"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

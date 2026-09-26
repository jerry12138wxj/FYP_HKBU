# -*- coding: utf-8 -*-
"""T4.1 · 从本机 RIR 资产里按 T60 选两档混响（小房间 ≈0.6 s / 大厅 ≈1.2 s）。

为什么不能"随便挑两条 RIR"
--------------------------
路线图要求「小房间 T60≈0.6 s / 大厅 T60≈1.2 s」。**T60 必须实测**：
按房间名字挑（smallroom / largeroom）只能保证"标注的房间大小不同"，
保证不了混响时间落在目标档上，而且 DNS 的 simulated_rirs 全部**只有 1.0 s 长** ——
1 s 的文件**物理上表征不了 1.2 s 的混响**（尾巴被切掉）。

本机资产实况（已探明）
----------------------
| 池 | 位置 | 数量 | 时长 | 是否够 1.2 s |
|---|---|---|---|---|
| simulated smallroom | `SLR26/simulated_rirs_48k/smallroom/` | 20000 | 1.000 s | ✗（截断） |
| simulated mediumroom | `SLR26/simulated_rirs_48k/mediumroom/` | 20000 | 1.000 s | ✗（截断） |
| real AIR | `SLR28/RIRS_NOISES/real_rirs_isotropic_noises/air_*` | 106 | 0.68~**9.99 s** | ✅ `aula_carolina` 9.99 s |

→ 小房间档从 simulated 池选；**大厅档从真实 AIR 池选**（`aula_carolina` 是真实大礼堂）。
这样两档都是"实测 T60 达标"，且大厅档的 RIR 长度足够，不是截断产物。

T60 估算法
----------
Schroeder 反向积分（ISO 3382 常用做法）：
    e[n] = sum_{k>=n} h[k]^2   →   EDC[n] = 10*log10(e[n]/e[0])
在 EDC 的 **-5 ~ -25 dB** 区间做最小二乘拟合，斜率 → T30，`T60 = 2 * T30`。
**动态范围门禁**：EDC 到不了 -25 dB 就返回 `None`（不外推、不猜）。
同时报 EDT（0~-10 dB 外推）与 DRR（直达声能量 / 混响尾能量）。

用法
----
    python tools/_select_rirs.py                     # 默认 stride=5 分层抽样
    python tools/_select_rirs.py --stride 1          # 全量扫描（约 3~5 min）
    python tools/_select_rirs.py --target-small 0.6 --target-hall 1.2
"""
from __future__ import annotations

import argparse
import json
import math
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

DNS_RIR = (_paths.DNS_ROOT / "impulse_responses" / "datasets_fullband"
           / "impulse_responses")
SIM_SMALL = DNS_RIR / "SLR26" / "simulated_rirs_48k" / "smallroom"
SIM_MEDIUM = DNS_RIR / "SLR26" / "simulated_rirs_48k" / "mediumroom"
REAL_AIR = DNS_RIR / "SLR28" / "RIRS_NOISES" / "real_rirs_isotropic_noises"

OUT_DIR = _paths.SEPARATION / "data" / "reverb"
OUT_JSON = OUT_DIR / "rir_selection.json"
OUT_RIR_DIR = OUT_DIR / "rir"

SR_OUT = 44100                      # 与板1 分离模型的评测采样率一致
TRIM_DB = -40.0                     # 直达声前的裁剪阈值（相对峰值）


# ------------------------------------------------------------------ 估计
def _schroeder_t60(h: np.ndarray, sr: int) -> dict | None:
    """Schroeder 反向积分估 T60 / C50 / DRR。

    🔴 **直达声必须剔除**（本函数的关键设计）：
    模拟 RIR 的直达尖峰比混响尾强 10~20 dB，若直接用整条 EDC 拟合 -5~-25 dB，
    -5 dB 点会落在"尖峰塌下来"的那一段，斜率被直达声污染 ——
    实测表现是同一个 RIR 给出 EDT 7 ms / T60 1.3 s 这种自相矛盾的组合。
    做法：把峰值 ±2.5 ms 的窗**置零**后再反向积分，此时 EDC 从 0 dB 起就是**纯混响衰减**，
    拟合出来的才是"混响尾有多长"。

    动态范围门禁：EDC 到不了 -25 dB → 丢弃（不外推）。
    物理门禁：T60 不得超过文件长度（超过 = 拟合退化，例如尾巴几乎不衰减的电话 RIR）。
    """
    h = np.asarray(h, np.float64).ravel()
    n = h.size
    if n < int(0.05 * sr):
        return None
    dur = n / sr
    peak = int(np.argmax(np.abs(h)))

    def _fit_from(sig: np.ndarray):
        e = np.cumsum(sig[::-1] ** 2)[::-1]
        if e[0] <= 0:
            return None, None
        edc = 10.0 * np.log10(e / e[0] + 1e-30)

        def _slope(a_db, b_db):
            ia = int(np.argmax(edc <= a_db))
            ib = int(np.argmax(edc <= b_db))
            if edc[-1] > b_db or ib <= ia + 1:
                return None
            k, _ = np.polyfit(np.arange(ia, ib) / sr, edc[ia:ib], 1)
            return (-60.0 / k) if k < 0 else None

        return _slope(-5.0, -25.0), float(edc[-1])

    # ---- 整体（含直达声）：仅作对照，不用于选型
    t60_full, _ = _fit_from(h)
    # ---- 剔除直达声：选型判据
    h2 = h.copy()
    w = max(1, int(0.0025 * sr))
    h2[max(0, peak - w):min(n, peak + w + 1)] = 0.0
    t60, edc_end = _fit_from(h2)
    if t60 is None:
        return None
    if t60 > dur:
        return None                      # 物理不可能：拟合退化
    if t60 > 5.0:
        return None

    # C50：早/晚能量比（early = 0~50 ms），对直达尖峰不敏感，可与 T60 互证
    i50 = min(n, int(0.050 * sr))
    early = float(np.sum(h[:i50] ** 2))
    late = float(np.sum(h[i50:] ** 2))
    c50 = 10.0 * math.log10(early / late) if late > 0 else None

    direct_e = float(np.sum(h[max(0, peak - w):min(n, peak + w + 1)] ** 2))
    total_e = float(np.sum(h ** 2))
    tail_e = max(total_e - direct_e, 1e-30)
    return {
        "t60": round(float(t60), 4),                       # 选型判据（已剔除直达声）
        "t60_full": round(float(t60_full), 4) if t60_full else None,
        "c50_db": round(float(c50), 2) if c50 is not None else None,
        "drr_db": round(float(10.0 * math.log10(direct_e / tail_e)), 2),
        "edc_end_db": round(float(edc_end), 1),
        "peak_ms": round(peak / sr * 1000.0, 2),
        "dur_s": round(dur, 4),
        "n": int(n),
    }


def _load_mono_48k(path: Path) -> tuple[np.ndarray, int] | tuple[None, None]:
    try:
        y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception:                                               # noqa: BLE001
        return None, None
    if y.size == 0:
        return None, None
    return y.mean(axis=1), sr


def _scan(pool: Path, stride: int, limit: int | None = None) -> tuple[list, int]:
    """分层扫描一个池，返回 (候选记录, 实际扫描文件数)。"""
    files = sorted(pool.rglob("*.wav"))
    if not files:
        return [], 0
    sel = files[::max(1, stride)]
    if limit:
        sel = sel[:limit]
    out = []
    for p in sel:
        h, sr = _load_mono_48k(p)
        if h is None:
            continue
        m = _schroeder_t60(h, sr)
        if m is None:
            continue
        m.update({"path": str(p), "pool": pool.name, "sr": sr})
        out.append(m)
    return out, len(sel)


# ------------------------------------------------------------------ 主流程
def _pick(cands: list, target: float) -> dict | None:
    if not cands:
        return None
    return min(cands, key=lambda c: abs(c["t60"] - target))


def _export(rec: dict, name: str) -> dict:
    """把选中的 RIR 处理成实验可直接用的形态：

    ① 去直流；② **裁掉直达声之前的传播时延**（否则混响输出相对干信号整体延迟，
    与干 GT 做 SDR 时会因错位而崩）；③ 单位能量归一（湿/干响度可比）；
    ④ 重采样到 44.1 kHz 存成 wav，保证实验可复现（不依赖数据集原位）。
    """
    from scipy.signal import resample_poly

    h, sr = _load_mono_48k(Path(rec["path"]))
    h = np.asarray(h, np.float64)
    h = h - h.mean()
    peak = int(np.argmax(np.abs(h)))
    thr = np.abs(h).max() * (10 ** (TRIM_DB / 20.0))
    i0 = peak
    while i0 > 0 and abs(h[i0 - 1]) < thr:
        i0 -= 1
    h = h[i0:]
    hn = float(np.sqrt(np.sum(h ** 2)))
    if hn <= 0:
        raise RuntimeError("RIR 能量为 0：%s" % rec["path"])
    h = h / hn
    if sr != SR_OUT:
        g = math.gcd(int(sr), int(SR_OUT))
        h = resample_poly(h, SR_OUT // g, sr // g)
    OUT_RIR_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_RIR_DIR / ("%s.wav" % name)
    sf.write(str(out), h.astype(np.float32), SR_OUT, subtype="FLOAT")
    return {
        "name": name,
        "src": rec["path"],
        "out": str(out),
        "trim_samples_removed": i0,
        "trim_ms_removed": round(i0 / sr * 1000.0, 2),
        "sr_out": SR_OUT,
        "frames_out": int(h.size),
        "dur_out_s": round(h.size / SR_OUT, 4),
        "energy_normalized": True,
    }


def _hist(vals, lo=0.0, hi=2.0, nb=40):
    if not vals:
        return None
    idx = np.clip(((np.asarray(vals) - lo) / (hi - lo) * nb).astype(int), 0, nb - 1)
    cnt = np.bincount(idx, minlength=nb)
    return {"lo": lo, "hi": hi, "nbins": nb, "counts": cnt.tolist(),
            "edges": [round(lo + (hi - lo) * i / nb, 4) for i in range(nb + 1)]}


def main() -> int:
    ap = argparse.ArgumentParser(description="T4.1 RIR 按 T60 选取")
    ap.add_argument("--stride", type=int, default=5, help="simulated 池的抽样步长（1=全量）")
    ap.add_argument("--limit", type=int, default=0, help="每个池最多扫多少（0=不限）")
    ap.add_argument("--target-small", type=float, default=0.6)
    ap.add_argument("--target-hall", type=float, default=1.2)
    args = ap.parse_args()

    for p in (SIM_SMALL, SIM_MEDIUM, REAL_AIR):
        if not p.is_dir():
            print("[FAIL] 池不存在: %s" % p)
            return 2

    t0 = time.time()
    pools = {}
    print("[scan] stride=%d" % args.stride)
    for label, root in (("sim_smallroom", SIM_SMALL),
                        ("sim_mediumroom", SIM_MEDIUM),
                        ("real_air", REAL_AIR)):
        cands, nscanned = _scan(root, 1 if label == "real_air" else args.stride,
                                args.limit or None)
        t60 = [c["t60"] for c in cands]
        pools[label] = {"root": str(root), "n_on_disk": len(list(root.rglob("*.wav"))),
                        "n_scanned": nscanned, "n_valid_t60": len(cands),
                        "t60_min": round(min(t60), 3) if t60 else None,
                        "t60_median": round(float(np.median(t60)), 3) if t60 else None,
                        "t60_max": round(max(t60), 3) if t60 else None,
                        "hist": _hist(t60)}
        print("  %-15s 磁盘 %-6d 扫 %-6d 有效 %-6d  T60 中位 %s  区间 [%s, %s]"
              % (label, pools[label]["n_on_disk"], nscanned, len(cands),
                 pools[label]["t60_median"], pools[label]["t60_min"], pools[label]["t60_max"]))
        cands.sort(key=lambda c: c["t60"])
        pools[label]["_cands"] = cands
    print("[scan] 用时 %.1fs" % (time.time() - t0))

    small_pool = pools["sim_smallroom"]["_cands"] + pools["sim_mediumroom"]["_cands"]
    hall_pool = [c for c in pools["real_air"]["_cands"]]
    # 大厅档：只认"够长"的真实 RIR（>=2 s 才配谈 1.2 s 混响）
    hall_long = [c for c in hall_pool if c["dur_s"] >= 2.0]
    print("[pool] 小房间候选 %d 条（全 1.0 s）｜大厅候选 %d 条，其中 >=2 s 的 %d 条"
          % (len(small_pool), len(hall_pool), len(hall_long)))

    picked = {}
    for key, pool, tgt in (("small_0p6", small_pool, args.target_small),
                           ("hall_1p2", hall_long or hall_pool, args.target_hall)):
        rec = _pick(pool, tgt)
        if rec is None:
            print("[FAIL] %s：池为空" % key)
            return 2
        ex = _export(rec, key)
        picked[key] = {
            "target_t60": tgt,
            "picked_t60": rec["t60"],
            "picked_t60_full_edc": rec["t60_full"],
            "picked_c50_db": rec["c50_db"],
            "picked_drr_db": rec["drr_db"],
            "picked_dur_s": rec["dur_s"],
            "src": rec["path"],
            "export": ex,
        }
        print("  [pick] %-10s 目标 %.2f s -> 实测 %.3f s (C50 %s dB, DRR %s dB, 源时长 %.2f s; 含直达声口径 %.3f s)"
              % (key, tgt, rec["t60"], rec["c50_db"], rec["drr_db"], rec["dur_s"],
                 rec["t60_full"] or float("nan")))

    # 命中度自检：偏差超过 20% 要显式报警（不静默"差不多就行"）
    for key, v in picked.items():
        dev = abs(v["picked_t60"] - v["target_t60"]) / v["target_t60"]
        v["target_deviation"] = round(dev, 4)
        if dev > 0.20:
            print("  [WARN] %s 偏离目标 %.1f%% —— 池内没有更接近的，如实记录" % (key, dev * 100))

    out = {
        "task": "T4.1 RIR 选取",
        "method": ("Schroeder 反向积分；T60 = 2 x T30（-5~-25 dB 最小二乘）。"
                   "🔴 拟合前把峰值 ±2.5 ms 的直接声窗**置零**，否则直达尖峰会污染斜率"
                   "（实测会产生 EDT 7 ms / T60 1.3 s 这类自相矛盾的组合）；"
                   "含直达声的整体 EDC 口径另存 t60_full 作对照。"
                   "门禁：EDC 到不了 -25 dB 丢弃；T60 > 文件长度或 > 5 s 丢弃。"),
        "criteria": {"target_small_t60": args.target_small, "target_hall_t60": args.target_hall},
        "stride": args.stride,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pools": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                  for k, v in pools.items()},
        "picked": picked,
        "export_policy": {
            "trim_leading_delay": "裁掉直达声前的传播时延（阈值 %.0f dB 相对峰值），使湿信号与干 GT 样本对齐"
                                 % TRIM_DB,
            "energy_normalize": "单位能量归一（sum(h^2)=1），湿/干响度可比",
            "resample": "%d Hz（与板1 评测采样率一致）" % SR_OUT,
        },
        "status": "PASS",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[status] PASS -> %s" % OUT_JSON)
    print("[rir]    %s" % OUT_RIR_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# RPCA 实跑报告

生成时间：2026-10-30 23:58 之后 · 运行批次：`rerun_20261030_2358`
代码位置：`tools/compare_separation_methods.py::sep_rpca` / `_rpca_ialm`（Inexact-ALM，纯 numpy）
统一入口：`tools/benchmark_model_universal.py --model rpca`

---

## 1 结论（一句话）

**RPCA 可以运行，已产出真实音频**。它在 30 s 片段上 RTF ≈ 2.93–2.95（纯 CPU），
但**稀疏分量没有天然 stem 归属**：两首歌分别最匹配 `vocals`（+0.213 dB）与 `drums`（+1.333 dB），
且都在 0 dB 附近 —— 说明它**几乎不具备四轨分离能力**，只能作为「古典基线」而非竞争模型。

---

## 2 运行命令与产物

```bash
python tools/benchmark_model_universal.py --model rpca \
  --subset test --song "Al James - Schoolboy Facination" --duration 30 \
  --out-tag run --audio-format flac
```

| 项 | 值 |
|---|---|
| 数据 | MUSDB18-HQ `test` 集，前 30 s，44.1 kHz，**单声道**（RPCA 内部取 `_mono(mix)` 后复制为双声道落盘） |
| 产物 | `03_outputs/_test_run/RPCA/<song>/vocals.flac`（2 个文件，2.4 MB） |
| 结果 JSON | `04_reports/01_separation/data/comparison/model_runs_run.json`（`runs.rpca`） |
| 汇总 JSON | `D:\FYP_HKBU_runs\rerun_20261030_2358\rpca_results.json` |
| 峰值 / 削波 | 0.376 / 0.293，`clip_frac = 0.0`（无削波） |
| 时长核对 | 输出 30.000 s = 输入 30.000 s（无截断） |

---

## 3 指标（口径：MUSDB18-HQ test，30 s，单声道，CPU）

| 歌曲 | RTF | 最匹配 stem | 该 stem SI-SDR | 相关系数 | vocals | drums | bass | other |
|---|---|---|---|---|---|---|---|---|
| Al James - Schoolboy Facination | 2.949 | vocals | **+0.213** | 0.716 | +0.21 | −6.56 | −8.99 | −11.63 |
| AM Contra - Heart Peripheral | 2.930 | drums | **+1.333** | 0.759 | −6.72 | +1.33 | −75.49 | −6.63 |

（跨 stem SI-SDR 单位 dB，由 `benchmark_model_universal.py` 的 `eval_all_stems` 逐轨交叉评估得到。）

**读法**：两首歌的最佳匹配分别是 vocals 和 drums —— 同一算法、同一参数，落点不同，
这不是 bug，正是「稀疏分量无 stem 归属」的直接证据：它分出来的是「打击性 / 瞬态成分」，
在不同编曲里恰好更像人声或更像鼓。任何把它硬映射到固定轨的做法都会误导结论。

---

## 4 Octave 11.3.0 交叉验证（数值一致性）

用 GNU Octave 11.3.0 独立实现同一 IALM（参数逐项对齐：`lam=1/sqrt(max(m,n))`、
`mu0=1.25/‖M‖₂`、`rho=1.5`、`tol=1e-6`、`max_iter=120`），输入**同一个**幅度谱矩阵
（1025×2584，30 s @ 44.1 kHz，n_fft 2048 / hop 512）。

| 校验项 | numpy 参考 | Octave 11.3.0 | 差异 |
|---|---|---|---|
| 迭代次数 | 34 | 34 | 0 |
| 最终相对残差 | 7.9884331854e-07 | 7.9884331850e-07 | < 1e-15 |
| `rel_err(L)` | — | — | 2.53e-08 |
| `rel_err(S)` | — | — | 2.53e-08 |
| `rel_err(mask)` | — | — | 5.10e-08 |
| mask 相关系数 | — | — | 0.999999999999989 |
| 重建波形最大差 | — | — | 6.42e-08 |
| 两版音频 SI-SDR | — | — | **133.67 dB** |

结论：**两个独立实现数值等价**（差异处于 float32 存储精度量级）。
耗时：Octave 161.6 s，Python（numpy MKL）约 88 s —— 两者都是 CPU，Octave 慢 1.8×，属预期。

产物：
- `tools/_octave/rpca_ialm.m`（Octave 实现）
- `D:\FYP_HKBU_runs\rerun_20261030_2358\rpca_octave\{mag.npy, L_f32.bin, S_f32.bin, mask_f32.bin, octave_stats.txt, compare.json}`

---

## 5 与原状态的关系

- `03_outputs/RPCA/test/<song>/` 在本批次之前是**空目录（0 文件 0 MB）**，而 `MODEL_REGISTRY.md`
  把它标为 ✅ 可运行 —— 这是审计里的 **C 类**（声明与实物不符）。
- 本批次产物写入独立目录 `03_outputs/_test_run/RPCA/`，**没有覆盖**任何原有文件。
- 若要并入正式布局，把上面两个 `vocals.flac` 复制到 `03_outputs/RPCA/test/<song>/` 即可；
  是否并入等你确认（阶段二纪律：不覆盖原产物）。

---

## 6 口径警告（写论文时必须带）

1. **单声道**：RPCA 在 `_mono(mix)` 上做，落盘时复制成双声道；它不是立体声算法。
2. **无 stem 归属**：不得把 `vocals.flac` 当成「RPCA 的人声分离结果」与其他模型的 vocals 横比。
   正确写法是报「跨 stem 最佳匹配 + 该匹配下的 SI-SDR」。
3. **30 s 片段**：与整曲评测不可直接比（本项目主表另有 2 s/1.5 s 窗口径）。
4. **RTF 是 CPU 值**：RPCA 不使用 GPU，`model_profile.csv` 里 8.253 与本次 2.93 的差异来自
   机器负载与片段长度，**只能报区间**（见 `MODEL_REGISTRY.md` §1 的 RTF 陷阱说明）。

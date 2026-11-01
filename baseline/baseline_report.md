# Clean-Data Baseline 报告（可复现基准线）

- 项目根：`E:/FYP_HKBU`
- 产物目录：`E:/FYP_HKBU/baseline/`（新建，不触碰原始数据）
- 生成脚本：`E:/FYP_HKBU/tools/_build_baseline.py`
- 指标工具：`museval.bss_eval/v4` **0.4.1**
- 本报告所有数字均由脚本从 CSV 现算读出，无手填

---

## 1. 数据集盘点

盘点是**只读**扫描：`soundfile.info()` 逐文件读头，不解码、不改写。

### 1.1 总量

| 数据集 | split | role | 文件数 | 采样率 | 声道 | 编码 | 时长 min / median / max | 总时长 |
|---|---|---|---|---|---|---|---|---|
| Valentini | test | clean | 824 | 48000 | 1 | PCM_16 | 1.238 / 2.325 / 9.769 s | 2,072.0 s |
| Valentini | test | mixture | 824 | 48000 | 1 | PCM_16 | 同上（逐条一致） | 2,072.0 s |
| MUSDB18-HQ | test | clean（4 stem） | 200 | 44100 | 2 | PCM_16 | 76.194 / 246.857 / 430.375 s | 49,883.9 s |
| MUSDB18-HQ | test | mixture | 50 | 44100 | 2 | PCM_16 | 同上（逐曲一致） | 12,471.0 s |
| DNS-Challenge | clean | clean | 13,733（唯一 8,673） | 48000 | 1 | PCM_16 | 0.523 / 2.584 / 27.072 s | 36,795.1 s |
| DNS-Challenge | dev_testset | mixture（noisy） | 921 | 48000 | 1 | PCM_16 | 10.304 / 18.618 / 77.470 s | 18,632.9 s |

`baseline_manifest.csv` 共 **16,552 行**。全部文件为 PCM_16，无浮点/压缩格式。

### 1.2 需要特别说明的三处数据事实

**(a) DNS `emotional_speech` 有整份重复副本。**
`clean/emotional_speech/`（5,060 个）与 `clean/emotional_speech/crema_d/`（5,060 个）逐字节相同；13,733 个文件里只有 **8,673 个唯一 stem**。manifest 用 `duplicate_of` 列标记了 5,060 个副本，SDR 与频谱抽样**都先按 `(stem, size)` 去重**。若不去重，同一段音频会被计两次，指标与图都会双计。

**(b) Valentini clean/noisy 的帧数逐条完全相等**（824 对，帧数不一致 0 条）；MUSDB 每首 5 个文件（mixture + 4 stem）帧数也完全相等（50 首，不一致 0 首）。两处都无需任何长度截断或补零，实测 `delta_samples` 全为 0。

**(c) DNS 两个子集连"长度"都对不上。** clean 子集是短的训练切片（中位 2.584 s，最长 27.072 s），`dev_testset` 是长评测片段（中位 18.618 s，最短 10.304 s）。即使抛开"没有配对标注"，两边的时长分布也几乎没有重叠，逐条配对在物理上就不成立——这从第二个角度印证了 §2 的"B 无法计算"。

---

## 2. 配对关系与限制

| 数据集 | clean 侧 | mixture 侧 | 配对成功 | 时长一致 | Method B 可算？ |
|---|---|---|---|---|---|
| Valentini test | 824 | 824 | ✅ 824 | ✅ 824/824 | ✅ 可算 |
| MUSDB18-HQ test | 200 stem | 50 mixture | ✅ 200（每 stem 对同曲 mixture） | ✅ 50/50 曲 | ✅ 可算（4 stem 分别算） |
| DNS clean | 13,733 | **无** | ❌ | — | ❌ **无法计算，缺少混合文件** |
| DNS dev_testset | **无 clean 参考** | 921（noisy） | ❌ | — | ❌ **无法计算，缺少参考信号** |

**结论：只有 Valentini 与 MUSDB 具备「clean ↔ mixture」真配对。** DNS 两个子集各自只有一半：`clean/` 没有混合文件，`dev_testset/noisy_testclips/` 没有干净参考。

对 DNS 的处理是**不生成 B 行**，而不是填 0 或用 clean 冒充 mixture——`baseline_sdr.csv` 中 DNS 只有 A / C 两种方法共 400 行。用 clean 当 mixture 会得到一个恒等于 Method A（+inf）的假下限，属于伪造。

**产物覆盖限制**：因此 Method B 的结论只能约束 Valentini 与 MUSDB，不能外推到 DNS 系降噪数据（后者正是本项目板 2 的主数据）。

---

## 3. SDR 口径说明

### 3.1 工具与参数（逐行写入 CSV，可查）

| 项 | 取值 |
|---|---|
| 库 / 版本 | `museval` **0.4.1**，`bss_eval` mode `v4` |
| 调用 | `museval.evaluate(ref, est, win=1.0s, hop=1.0s, mode="v4", padding=True)` |
| 窗口 | `win = hop = 1.0 s`（48 kHz 数据 48,000 样本；44.1 kHz 数据 44,100 样本） |
| framewise | `True`（逐 1 s 帧出值，非整段单值） |
| 返回值 | **4-tuple** `(SDR, ISR, SIR, SAR)`，每项 shape `(1, n_frames)`；不是 dict |
| 帧数范围 | 1 ~ 430 帧，中位 2 帧 |

CSV 对应列：`framewise, win_samples, hop_samples, window_s, tool, tool_version`。

### 3.2 长度对齐

- 方式：`truncate_to_min`，取 `min(len(ref), len(est))`。
- 实测结果：**3,472 行的 `delta_samples` 全为 0**，即没有任何文件需要截断。
- `len_ref` / `len_est` / `n_samples` / `delta_samples` 全部逐行留档，可复查。

### 3.3 声道处理

- 方式：`channel_mean`（立体声 L/R 取算术平均降到单声道）。
- 合法性已验证：MUSDB 上 `mixture − Σstem` 的残差峰值为 mixture RMS 的 **2.9×10⁻³（PR - Happy Daze）/ 7.4×10⁻⁴（Zeno - Signs）**，属于四轨各自独立 PCM-16 量化的量级，不是混音误差。因此降混后 `mixture = vocals + drums + bass + other` 仍成立，B 的下限语义不受破坏。

### 3.4 采样率

**全程没有做任何重采样。** 各数据集在其原生采样率上评测：Valentini / DNS 为 48 kHz，MUSDB 为 44.1 kHz。`read_mono` 在发现 ref 与 est 采样率不一致时直接抛错，不会静默转换。

这样做的理由：重采样本身是一次低通滤波，会给 SDR 引入与模型无关的损失；把 48 kHz 数据降到 44.1 kHz 只为"统一"会让所有分数带上一层额外惩罚。代价是**不同采样率的数据集之间不能直接横比绝对 SDR**——见 §7。

### 3.5 三种 baseline 的定义与区别

| 方法 | 定义 | 估计信号 | 回答的问题 |
|---|---|---|---|
| **A** | Clean-to-Clean 自检 | `est = clean`（同一数组的副本） | 管线是否无损？ |
| **B** | No-Separation 下限 | `est = mixture`（不做任何分离） | 一个"什么都不做"的系统能拿多少？ |
| **C** | 理论上界参照 | 与 A 完全相同的计算 | 上限在哪？ |

**A 与 C 是同一份计算的两次标号**（脚本里 C 行由 A 行原地复制、只改 `method` 字段），保证两者永不漂移。

⚠️ **A 是一个构造性恒等，不是独立验证。** 因为 `est = ref.copy()`，两次计算读的是同一个内存数组，A 只能证明「museval 调用路径 + CSV 写出路径」通，**不能**证明第二次解码、降混、长度对齐都正确——这些环节在 A 里根本没被走第二遍。真正覆盖这些环节的是 §4.3 的扰动探针（`pipeline_probe.csv`）。这一条必须写明，否则容易把 +inf 误读成"管线全对"。

### 3.6 非有限帧的处理（重要口径）

museval 的逐帧 SDR 里存在两类非有限值，CSV 用一列 `n_nonfinite_frames` 合并计数：

- **NaN**：该 1 s 窗口内估计或参考是数字静音，`0/0` 未定义。**占绝大多数。**
- **+inf**：该窗口完美重构。

逐文件值 = **`np.nanmedian`（帧级中位数）**，于是：**NaN 帧被丢弃，+inf 帧作为最大序统计量保留。**这种不对称是有意为之（NaN 不是"成绩"，inf 是"满分"），但后果必须写清：**每首曲子的 SDR 是"其非静音帧上的中位数"**，不是全曲所有帧的算术平均。

规模：Method B 共 51,431 帧（MUSDB 49,784 + Valentini 1,647），非有限 **6,368 帧**，**全部来自 MUSDB**，占 MUSDB 帧的 **12.79%**；Valentini 为 0 帧。1024 行里有 161 行出现。逐 stem 复算两首极端曲目确认 NaN 占绝对多数：

| 曲目 | stem | 帧数 | NaN | +inf | 有限 | 仅有限帧中位 | nanmedian |
|---|---|---|---|---|---|---|---|
| Mu - Too Bright | bass | 272 | 192 | 0 | 80 | −8.150 | −8.150 |
| Mu - Too Bright | vocals | 272 | 21 | 2 | 249 | −5.120 | −5.083 |
| Detsky Sad - Walkie Talkie | vocals | 190 | 126 | 0 | 64 | −2.486 | −2.486 |
| Detsky Sad - Walkie Talkie | drums | 190 | 1 | 9 | 180 | 2.367 | 2.444 |
| Skelpolu - Resurrection | vocals | 395 | 329 | 1 | 65 | −8.274 | −8.274 |

两种算法差异 ≤0.18 dB，结论不受影响。**但 `Skelpolu - Resurrection` 的 vocals 只有 65/395 帧有效——该首的 B 值几乎不代表整首歌，引用时应知道这一点。**

---

## 4. 三种 baseline 结果

### 4.1 Method A / C（Clean-to-Clean、理论上界）

| method | dataset | stem | n | SDR 中位 | 有限文件数 | 有限率 |
|---|---|---|---|---|---|---|
| A | Valentini | speech | 824 | **inf** | 0 | 0.00 |
| A | MUSDB18-HQ | vocals / drums / bass / other | 50 各 | **inf** | 0 | 0.00 |
| A | DNS-Challenge | speech | 200 | **inf** | 0 | 0.00 |
| C | 同 A | 同 A | 同 A | **inf** | 0 | 0.00 |

全部为 `inf` 且 `n_frames` 全部非有限 —— 这是重构恒等的正确表现，**不是异常**。原因已定位到代码行：`est_kind == "clean"` 分支执行 `est = ref.copy()`，两者位级相同。

⚠️ **不得把这里的 inf 当作模型性能。** 它只说明"输入等于输出时 museval 给 +inf"。

### 4.2 Method B（No-Separation 下限）

| dataset | stem | n | mean | **median** | std | min | max | 负值文件数 |
|---|---|---|---|---|---|---|---|---|
| Valentini | speech | 824 | 8.810 | **8.478** | 5.921 | −16.950 | 25.271 | 28 / 824 |
| MUSDB18-HQ | vocals | 50 | −7.144 | **−5.095** | 9.547 | **−64.568** | −0.986 | 50 / 50 |
| MUSDB18-HQ | drums | 50 | −3.643 | **−3.849** | 4.025 | −11.962 | 8.745 | 41 / 50 |
| MUSDB18-HQ | bass | 50 | −6.128 | **−5.613** | 3.714 | −15.515 | 3.019 | 48 / 50 |
| MUSDB18-HQ | other | 50 | −5.850 | **−5.166** | 4.233 | −19.485 | 1.991 | 46 / 50 |

同时无法计算：DNS clean（无 mixture）、DNS dev_testset（无 clean 参考）—— 见 §2。

**MUSDB 全部 4 个 stem 的 median 都是负的**（185/200 行负值），这不是 bug。已用两条独立路径定位：

1. **公式层**：`est = mixture`、`ref = stem` 时，`mixture − stem = 其余三轨`（§3.3 已验证该恒等式在量化误差内成立），故 `SDR = 10·log10(‖stem‖²/‖others‖²)`。stem 比其他内容安静 → SDR 为负。这是"什么都不做"的应有之义。
2. **复算层**：按 1 s 帧手工算 `10·log10(E_stem/E_others)` 再取 nanmedian，逐条复现 CSV：

| 曲目 | 手算中位 | CSV | 差 |
|---|---|---|---|
| PR - Happy Daze（vocals，CSV 最低值） | −64.568 | −64.568 | −0.0003 |
| BKS - Bulldozer（vocals） | −15.060 | −15.060 | −0.0003 |
| Al James - Schoolboy Facination（vocals） | −0.986 | −0.986 | +0.0002 |

**偏差 ≤0.0003 dB，且不依赖 museval。** 这条 5 行公式的独立复算，是对 B 全部数值的可追溯性证明。

顺带定死一个易错点：B 反映的是**中位帧**的 stem/others 能量比，不是全曲能量比。同一首 `PR - Happy Daze`，全曲能量比只有 −26.06 dB，中位帧却是 −64.57 dB——因为人声只在少数帧出现，多数帧里它远低于伴奏。**引用 B 时若说成"整首歌的人声比伴奏低 64 dB"就是错的。**

### 4.3 管线扰动探针（Method A 不能覆盖的部分）

`pipeline_probe.csv`，同一段 `p232_001`（48 kHz）上做受控扰动：

| 扰动 | 实测 SDR | 期望 | 判定 |
|---|---|---|---|
| identity | inf | +inf | PASS |
| gain 0.50× | 6.021 | `−20log₁₀|1−g|` = 6.021 | PASS |
| gain 0.90× | 20.000 | 20.000 | PASS |
| gain 2.00× | −0.000 | −0.000 | PASS |
| 白噪 20 dB SNR | 19.777 | ≈20 | PASS |
| 白噪 40 dB SNR | 39.792 | ≈40 | PASS |
| 白噪 60 dB SNR | 59.789 | ≈60 | PASS |
| 延迟 1 样本 | 19.788 | 单调下降（512-tap 滤波器部分吸收） | INFO |
| 延迟 10 样本 | 5.493 | 单调下降 | INFO |
| 延迟 100 样本 | −3.665 | 单调下降 | INFO |
| 48k→16k→48k | 31.021 | 20–40 有限值 | INFO |

11 项：**7 PASS + 4 INFO，0 FAIL**。两个反直觉但正确的点，已由公式逐位验证：**BSSEval 不吸收纯增益**（`SDR(g) = −20log₁₀|1−g|`，g=0.5 只有 6 dB，不是 inf）；**1 样本延迟只掉到 19.79 dB**（被畸变滤波器部分吸收），延迟单调递减到 100 样本的 −3.67 dB。这组数据证明指标**对错误敏感**，也给出了敏感度标尺。

---

## 5. Spectrogram 产物

### 5.1 参数（逐行写入 `spectrogram_index.csv`）

| 参数 | 值 |
|---|---|
| `n_fft` | 2048 |
| `hop_length` | 512 |
| `win_length` | 2048 |
| `window` | `hann` |
| `center` | `True` |
| 幅度 | `20·log₁₀|STFT|`，**绝对幅度 dB，不按峰值归一化** |
| 数据 dtype | `.npy`：Valentini / DNS 为 float32；MUSDB 为 float16（长文件省空间，量化步长 ≈0.016 dB @ +25 dB） |
| 时间轴 | `extent` 由 `n_frames × hop / sr` 推出，单位 s |
| 频率轴 | 0 ~ sr/2，单位 kHz |
| 色标 | **统一 `vmin=−90, vmax=+25` dB** |
| 色标标签 | `Magnitude (dB re 1.0, 20*log10|STFT|)` |

**色标为什么是 −90/+25**：把全部 74 个数组的 3.847 亿个有限 bin 汇总后取 p0.5 = −87.7 dB、p99.5 = +23.6 dB，向外取整到 −90 / +25。这样 99% 的 bin 落在色带内。早前一版用 `vmin=−100, vmax=0`，会**截掉每帧最强的约 4%**（实测 p99 达 +19 dB，最大 +47.7 dB），且标签误写为 "dB re max" 而实际未归一化——两处均已修正并重渲染。

统一色标是刻意的：**同一颜色在任意两张图里代表同一绝对电平**，可直接目视比较两个文件的能量；代价是不同录音电平的文件整体明暗不同（这是真实差异，不该被归一化抹掉）。

### 5.2 抽样规则（确定性，无随机）

| 数据 | 抽样 | 数量 | 规则 |
|---|---|---|---|
| Valentini | clean + mixture 成对 | 24 对 = 48 图 | 先按帧数（≈时长）排序，再在有序表上取 `np.linspace(0, n−1, 24)` 的等距下标 → 覆盖最短到最长 |
| MUSDB18-HQ | mixture + vocals | 10 曲 × 2 = 20 图 | 50 首按名字序取 `np.linspace` 等距 10 首 |
| DNS clean | 每子集 3 个 | 2 子集 × 3 = 6 图 | 子集内先去重，再等距取 3 |

每个文件都出了图（未做"多则再抽"的二次裁剪）。DNS 因同名不同路径会互相覆盖，输出名追加 `md5(绝对路径)[:6]` 后缀。

### 5.3 产物清单

- `spectrograms/`：**74 个 `.npy` + 74 个 `.png`**（共 148 文件，无孤儿、无重名）
- `spectrogram_index.csv`：74 行，字段 `dataset,file,role,src,npy,png,shape,dtype,sr,dur_s,n_fft,hop_length,win_length,window,center`
- 已逐项校验：74 行路径全部存在、`.npy` 的 `shape` 与索引一致、全部有限值、0 缺失。

### 5.4 从图里读出的一个数据事实（影响后续用法）

DNS clean 的频谱带宽受限。以各自的 4–8 kHz 频段为基准（中位 dB）：

| 数据集 / role | 4–8 kHz | 8–12 kHz | 12–15 kHz | 15–18 kHz | 18–23 kHz | 相对 4–8k 的落差 |
|---|---|---|---|---|---|---|
| Valentini clean | −39.5 | −40.4 | −40.8 | −41.3 | −41.4 | **−1.9 dB（平坦）** |
| DNS clean | −32.0 | −37.4 | −40.9 | −55.0 | −57.2 | **−25.2 dB（陡降）** |
| Valentini mixture | −25.8 | −26.0 | −27.5 | −28.1 | −27.0 | −1.2 dB |
| MUSDB vocals | −35.8 | −38.7 | −42.5 | −48.7 | −51.9 | −16.1 dB（人声本身如此） |

Valentini 到 23 kHz 基本平坦，DNS 在 12 kHz 以上陡降 25 dB。**结论：DNS 的 clean 不是全带宽参考**，任何"高频段"结论都不能拿它当基准；这也解释了为何 DNS 数据上的宽带指标需要单独口径。（上表是各数据集绝对 dB，**不可跨行横比电平**，只能看行内的相对落差。）

---

## 6. 复现命令

解释器固定为项目 venv（系统 `python` 无 numpy）：

```bash
PY="C:/Users/jerry/.workbuddy/binaries/python/envs/fyp_audio/Scripts/python.exe"

# 1) 盘点（只读，写 baseline_manifest.csv，约 16.5k 行）
"$PY" -X utf8 -u tools/_build_baseline.py scan

# 2) 三种 baseline SDR（写 baseline_sdr.csv；A/C 由同一遍计算产出）
"$PY" -X utf8 -u tools/_build_baseline.py sdr

# 3) 汇总（写 baseline_summary.csv）
"$PY" -X utf8 -u tools/_build_baseline.py summary

# 4) 管线扰动探针（写 pipeline_probe.csv）
"$PY" -X utf8 -u tools/_build_baseline.py probe

# 5) 频谱图（写 spectrograms/*.npy + *.png 与 spectrogram_index.csv）
"$PY" -X utf8 -u tools/_build_baseline.py spectro

# 6) 仅用新色标重渲染 PNG（不解码音频、不改 .npy）
"$PY" -X utf8 -u tools/_build_baseline.py rescale
```

`sdr` 支持 `--resume`（已写过的行会跳过）与 `--limit`（快速试跑）。

---

## 7. 限制与下一步

### 7.1 已知限制（逐条可核查）

1. **Method B 在 DNS 上不存在**，不是"结果不好"而是"无定义"：clean 子集无 mixture、dev_testset 无 clean。本项目板 2 的主数据恰是 DNS 系，因此 B 的结论不能外推到降噪评测。
2. **A 是构造性恒等**（`est = ref.copy()`），只验证调用路径，不验证二次解码/降混/对齐。该缺口由 `pipeline_probe.csv` 覆盖，但探针只做了 1 条音频，未覆盖立体声与 44.1 kHz 路径。
3. **跨数据集不可横比**：Valentini 是 48 kHz 单声道语音，MUSDB 是 44.1 kHz 立体声降混音乐，DNS 是 48 kHz 语音。三者 SR、声道来源、内容域全不同；`baseline_summary.csv` 把它们的 B 值排在一张表里只是"并列列出"，任何"A 数据集比 B 数据集好 X dB"的表述都是错的。可跨数据集比较的只有**ΔSDR**（同一数据集内的相对变化）。
4. **逐文件值是帧级 nanmedian**，静音帧被丢弃。MUSDB 有 **12.79%** 的 B 帧非有限（Valentini 为 0）；`Skelpolu - Resurrection` vocals 只有 65/395 帧有效。对静音多的曲目，B 值代表"有声帧的典型水平"，不代表整首歌。
5. **MUSDB 负 SDR 是下限的正常形态**，不是缺陷；但它的绝对值强烈依赖该曲的配器平衡（人声稀疏的曲子会低到 −64 dB），**50 首的中位数才有参考意义，单曲数值不宜单独引用**。
6. **无 framewise 之外的预算**：只用 `win=hop=1.0 s`，未做 2 s 窗口（板 1 主表用 2 s/1.5 s）。本次 baseline 与主表口径不同，**不能直接拼表**。
7. **`.npy` 的 MUSDB 部分为 float16**，量化步长 ≈0.016 dB @ +25 dB 量级，对目视与统计无影响，但不适合再做精细数值推导（需要高精度请从 wav 重算）。
8. **DNS 带宽受限**（§5.4，12 kHz 以上相对落差 −25.2 dB），不可作全带宽参考。

### 7.2 下一步（按优先级）

1. **把 B 值接入板 1 主表作为下限列**：主表窗口是 2 s/1.5 s，需用同参数重算一遍 B 才能并列；否则口径不一致。
2. **补 DNS 的 B 等价物**：DNS 官方没有 clean 参考，可行路径是自造可控 SNR 对（板 2 已有 `LEVEL_GATE` 方案），但那是"自造参考"不是"官方 B"，报告中必须分开标注。
3. **给 A 换成真解码自检**：把 `est = ref.copy()` 改为"从磁盘二次解码同一路径"，可让 A 覆盖解码确定性与降混路径；成本约一次全量 `sdr` 重跑。
4. 若需 DNS 的 SDR，先补 `dev_testset` 的官方 clean 参考（当前数据集内不存在），否则只能走自造对。

---

## 附：产物清单

| 文件 | 行数 / 数量 | 说明 |
|---|---|---|
| `baseline_manifest.csv` | 16,552 | 逐文件：路径/时长/SR/声道/帧数/是否配对/配对路径/重复标记 |
| `baseline_sdr.csv` | 3,472 | 逐文件逐 stem 逐方法，含 24 列口径字段 |
| `baseline_summary.csv` | 18 | 方法 × 数据集 × stem 的 n/mean/median/std/min/max/有限率 |
| `pipeline_probe.csv` | 11 | 受控扰动对照（7 PASS + 4 INFO） |
| `spectrogram_index.csv` | 74 | 图与数值文件的参数索引 |
| `spectrograms/` | 148 文件（74 npy + 74 png） | 已校验无缺失、无重名、无孤儿 |
| `baseline_report.md` | 本文件 | — |

# 🔴 严重的采样率契约 bug：16 kHz 口径全部作废并重跑

日期：2026-09-23  
影响：`denoise_eval_16k.*` 的**全部 12845 个 cell**（valentini 4120 + synth 4000 + dns_dev 4605）  
状态：**已修、已重跑**

---

## 1. 怎么发现的

dns_dev 与 44.1 kHz 副口径跑完后做交叉核对，发现一个**不可能的数据**：

| 口径       | denoiser 被 `LEVEL_GATE` 剔除的片段数           |
| -------- | ---------------------------------------- |
| 16 kHz   | dns48 **280** / dns64 265 / master64 155 |
| 44.1 kHz | **全为 0**（`level_ratio` 最小值 0.9458）       |

同一个模型、同一批音频，**只改评测采样率就能让「电平塌陷」完全消失**。  
模型行为不可能这样依赖评测口径 —— 一定是管道问题。

## 2. 根因（已用探针决定性验证）

denoiser 的 wrapper 内部写死：

```python
wav = convert_audio(wav, SR, 16000, 1)   # SR = 44100，硬编码
```

它**假定收到的永远是 44.1 kHz**。而 `eval_one` 把已经重采样到**评测口径**的信号直接喂了进去：

```
评测口径 16 kHz：
  load_mono(path, 16000)              -> 已经 16 kHz
  wrapper 认为它是 44.1k，再降一次     -> 44100→16000 的降采样
  => 信号被降采样两次，音频被加速 2.76 倍
```

探针实测（`_scratch/_probe_sr_double.py`，源 48 kHz / 5.52 s）：

| 评测口径       | 传入 wrapper | wrapper 输出   | 有效时长   | 速度               |
| ---------- | ---------- | ------------ | ------ | ---------------- |
| **16 kHz** | 88343 样本   | **32051 样本** | 2.00 s | **× 2.76（音高上移）** |
| 44.1 kHz   | 243495 样本  | 88342 样本     | 5.52 s | × 1.00（正确）       |

**后果**：16 kHz 口径下音频被压缩到 2.00 s、音高整体上移 ——  
远超出 denoiser 的训练分布，于是它把大量片段判为「不是语音」而压低。

**「34% 电平塌陷」是管道假象，不是模型行为。**

## 3. 修复

### 3.1 registry：把契约率显式暴露

```python
run.contract_sr = SR      # 44100
```

并在模块 docstring 写死整个契约（输入形状 (N,2) + 输入必须已在契约率上）。

### 3.2 eval：遵守契约率（**第一版写错了，见 §4.0**）

```python
csr = int(getattr(run_fn, "contract_sr", NATIVE_SR))
if csr != sr:
    noisy = resample_mono(noisy, sr, csr)      # 评测率 -> 契约率
est_stereo = run_fn(np.stack([noisy, noisy], axis=-1))
est = np.asarray(est_stereo["enhanced"]).mean(axis=1)
if csr != sr:
    est = resample_mono(est, csr, sr)          # 契约率 -> 评测率
```

⚠️ 上面这段**有 bug**：它覆盖了 `noisy` 变量，而下游指标侧仍要拿  
评测率的 `noisy` 去和参考比对。见 §4.0。

## 4. 修复后核验

### 4.0 🔴 修复引入的第二个 bug（「修复后重跑 16 kHz 出现荒谬值」）

修完契约率后重跑 valentini 16 kHz，结果里出现**物理上不可能**的数字：

| 字段               | 值          | 应有量级   |
| ---------------- | ---------- | ------ |
| `in_len`         | 76792      | ~27861 |
| `si_sdr_in`      | **−73.12** | +15 左右 |
| `si_sdr_improve` | **+90.65** | 几 dB   |
| `ΔPESQ`          | **+1.5**   | 零点几 dB |

**根因**：`if csr != sr: noisy = resample_mono(noisy, sr, csr)` **覆盖了 `noisy`**，  
于是第 306 行的输入参考变成

```python
noisy2 = noisy[: len(ref)]     # noisy 已是 44.1k 的 76791 长数组
                               # ref 是 16k 的 27861 长数组  -> 长度错位 3 倍
```

长度差 3 倍的两段信号做 SI-SDR → 得到 −73 dB 这种荒谬值。  
而 `level_ratio` 反而正确，因为它是 `est2 / ref`，不经过 `noisy`。

**修法**：把「喂模型的契约率信号」与「算指标的评测率信号」拆成两个变量，  
**绝不覆盖** `noisy`：

```python
csr = int(getattr(run_fn, "contract_sr", NATIVE_SR))
noisy_in = resample_mono(noisy, sr, csr) if csr != sr else noisy   # 仅供喂模型
est_stereo = run_fn(np.stack([noisy_in, noisy_in], axis=-1))
est = np.asarray(est_stereo["enhanced"]).mean(axis=1).astype(np.float32)
if csr != sr:
    est = resample_mono(est, csr, sr)

# ...下文指标一律用【评测率】的 noisy，绝不改：
noisy2 = noisy[: len(ref)]
```

**验证**（单格 `p232_001` @16 kHz，修复前后）：

| 字段               | 修复前（两次降采样 + 变量覆盖） |         修复后 | 手工复现的「正确路径」 |
| ---------------- | ----------------: | ----------: | ----------: |
| `in_len`         |             76792 |   **27861** |       27861 |
| `si_sdr_in`      |          −73.1208 | **+15.469** |      15.469 |
| `si_sdr_out`     |           17.5311 |     17.5311 |      17.531 |
| `si_sdr_improve` |           90.6519 | **+2.0621** |      +2.062 |
| `level_ratio`    |            1.0092 |      1.0092 |           — |

→ 修复后与手工复现**逐位一致**，确认无误。

**教训（并入铁律 14）**：修「输入侧改写」类 bug 时，  
被改写的那个变量**绝不能再被指标侧读到**。  
正确的做法是新增一个变量承载改写结果，而不是原地覆盖。

### 4.1 两口径一致性核验（对 150 条 valentini）

对 150 条 valentini，新旧两条路径对比（`_audit_sr_bug.py`）：

| 模型                                | 旧 16k（bug） | 旧 44.1k | **修复后 16k** | **修复后 44.1k** |
| --------------------------------- | ---------: | ------: | ----------: | ------------: |
| denoiser_dns48 · `level_ratio` 中位 |     0.9815 |  0.9997 |  **0.9466** |    **0.9419** |
| denoiser_master64                 |     1.0076 |  1.0034 |  **0.9474** |    **0.9470** |
| mel_roformer_denoise              |     1.0099 |  1.0004 |  **0.9607** |    **0.9606** |
| < 0.2 的片段数                        |      0/150 |   0/150 |   **0/150** |     **0/150** |

→ 修复后**两个口径完全一致**（0.9466 vs 0.9419），且塌陷片段降为 **0**。

## 5. 被推翻的结论（连锁）

以下结论**全部作废**，必须在新数据上重写：

| 文档                                            | 被推翻的内容                                          |
| --------------------------------------------- | ----------------------------------------------- |
| `T5_DENOISE_STRATIFIED.md` §4.2               | 「denoiser 带绝对电平门控，824 条中 280/265/155 条被剔除」—— 假象 |
| `T5_DENOISE_STRATIFIED.md` §1 / 主表            | `n_skipped` 列、`n_fullref`（实际应全部 824）            |
| `T5_4_DNS_DEV_NOREF.md` §2.1/§3/§4            | 「塌陷率 40.3% / 38.3% / 45.4%」—— 全部是 bug 造成的假象     |
| `T5_7_OOD_NOISE_NEGATIVE.md`                  | synth 上的 `n_skipped` 数字（282/239）                |
| `T5_7_PASSTHROUGH_PROBE_CORRECTION.md` §4     | `level_ratio` 塌陷推论（该探针走契约路径，结论本身未受影响，需复核）       |
| 技能 `audio-metric-disagreement-diagnosis` 铁律 5 | `LEVEL_GATE` 的必要性论述                             |
| 计划书 P11 / P13                                 | 「低电平片段被整段静音」                                    |

⚠️ **注意**：`T5_7_PASSTHROUGH_PROBE_CORRECTION.md` 的核心结论  
（「`hf_ratio` 塌陷 ≠ 低通」，基于 120 条配对 clean）**走的是正确路径，不受影响**。  
但其中引用的「34% 塌陷」需要删除。

### 5.1 但是：`LEVEL_GATE` 本身仍然必要

必须说清楚，否则会用力过猛把门禁一起删掉：

P19 推翻的是「**Valentini 上 34% 的塌陷**」这个**数字**，  
不是「denoiser 有绝对电平门控」这个**机制**。

证据（`denoise_sr_bug_audit.json`，150 条，两口径各跑一遍）：

| 模型                   | bug 版 16k 中位 | bug 版 44.1k 中位 | **修复后 16k** | **修复后 44.1k** |
| -------------------- | -----------: | -------------: | ----------: | ------------: |
| denoiser_dns48       |       0.9815 |         0.9997 |  **0.9466** |    **0.9419** |
| denoiser_master64    |       1.0076 |         1.0034 |  **0.9474** |    **0.9470** |
| mel_roformer_denoise |       1.0099 |         1.0004 |  **0.9607** |    **0.9606** |

关键在**最后两列**：修复后 denoiser 的 `level_ratio` 中位从 ~1.00 掉到 **0.947**，  
而 mel_roformer 只从 1.00 掉到 0.961 —— **denoiser 存在系统性的输出电平压低**，  
只是幅度远小于 bug 造成的假象。门禁保留是正确的（阈值 0.20 仍未触发，只是为  
P13 那种「合成对电平过低」的场景兜底）。

→ 正确的表述：**denoiser 有轻度系统性电平压缩（约 −0.5 dB），  
而不是「把 34% 的片段整段静音」。**

## 5.2 被 P19 波及的**先前结论**中，哪些还站得住

| 结论                          | 状态                 |
| --------------------------- | ------------------ |
| denoiser 不是低通器（配对 clean 探针） | ✅ 站得住（走契约路径）       |
| denoiser 抑制量随 SNR 单调变化      | ✅ 站得住              |
| mel_roformer 是近恒等映射         | ✅ 站得住              |
| 「34% 电平塌陷」                  | ❌ 作废（管道假象）         |
| dns_dev 塌陷率 40.3/38.3/45.4% | ❌ 作废，待重跑           |
| master64 门控「最温和」→「最激进」的反转   | ❌ 作废（反转本身是 bug 产物） |
| P16：in-domain master64 反而不佳 | ⚠️ 需在干净数据上复核       |

## 6. 教训（进技能）

🔴 **铁律 14：给模型 wrapper 喂数据前，必须先确认它期望的采样率。**

- 症状极其隐蔽：**不报错、能出声、指标还「看起来合理」**（SI-SDR 甚至为正）。  
  唯一的破绽是「同一模型在换评测口径后行为剧变」。
- 检测手段：**同一输入用两个不同评测口径跑，对比 `level_ratio`**。  
  若差异很大 → 必有二次重采样。
- 修法：让 wrapper 显式暴露 `contract_sr`，调用方一律  
  `resample(x, eval_sr, contract_sr)` → 推理 → `resample(y, contract_sr, eval_sr)`。
- **推论**：评测采样率**不能自由选择**。想跑 16 kHz 口径，必须  
  「原生率 → 契约率 → 模型 → 契约率 → 16 kHz」，而不是「原生率 → 16 kHz → 模型」。

🔴 **铁律 14 补充条款：修「输入侧改写」时，改写结果必须落到新变量，绝不原地覆盖。**

- 症状：修完第一个 bug 后，指标出现**荒谬但又不报错**的值  
  （本例 `si_sdr_in = −73 dB`、`ΔPESQ = +1.5`）。
- 破绽：`in_len` 与参考长度不成比例（76792 vs 27861，差 3 倍）。
- 检测手段：**看通道长度和**,而非只看指标值。任何 length mismatch 都先在  
  长度上拍死，再谈指标。
- 正确代码形态：`noisy_in = resample(noisy, ...)`，而不是 `noisy = resample(noisy, ...)`。

## 7. 复现

```bash
cd tools
PYTHONPATH=. <venv>/python.exe -X utf8 _scratch/_probe_sr_double.py   # 决定性问题复现
PYTHONPATH=. <venv>/python.exe -X utf8 _audit_sr_bug.py               # 两口径对比
```

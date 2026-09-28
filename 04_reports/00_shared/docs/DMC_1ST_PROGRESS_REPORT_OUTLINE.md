# DMC 1st Progress Report — Detailed Outline (v3, decisions locked)

> **Status**: Outline ready to write into prose. **Not the final prose yet.**
> **Structure**: 6 chapters — Introduction / Data / Methods / Results / Conclusion / References **(+ Literature Review, now included per B1)**
> **Language**: English
> **Decisions locked**: Q1 = 3-unit S1 ｜ Q2 = DMC structure ｜ **B1 = Literature Review INCLUDED** ｜ Q4 = results included ｜ Q5 = English ｜ Q6 = Gen-AI disclosure omitted for now ｜ Q7 = outline first ｜ A2 = title/name fixed ｜ A4 = Data + Methods split ｜ scope = separation + denoising models only ｜ **B2 = oBSRNN 4-ckpt (9.16) + a composite-best** ｜ **B3 = master64 + a composite-best** ｜ **B4 = reference table figure used, plus a locally-generated figure**

---

## 0. Locked Identity

| Field | Value |
|---|---|
| Project Title | **Real-Time Audio Separation and Noise Cancellation System** |
| Student | **Wang Sheng Jie** |
| Student ID | **25200887** |
| Supervisor | **Dr. XIAN, Poline Yin** |
| Concentration / Type | DMC ｜ 3-unit ｜ Semester 1 |
| Language | English |

---

## 0.1 Literature Review — CONFIRMED IN SCOPE ✅

`get_file.pdf` **§5.3.3 DMC 1st Progress Report**, item **2 of 7** (PDF p.16) explicitly requires it:
> *"A literature review should be included to demonstrate a good understanding of the relevant literature related to the problem or issue being addressed."*

**Decision (B1): INCLUDE.** Scope it tightly to the models you actually tested (separation families + denoising families), not a broad survey.

---

## 0.2 Scope Lock

**In scope — ONLY these two families, their measured performance and output quality:**

| # | Family | Deliverable |
|---|---|---|
| 1 | **Music source separation models** | Quality table, cost table, **best-quality model** + **composite-best model** |
| 2 | **Noise-cancellation models** | Quality table, cost table, **best-quality model** + **composite-best model** |

**Out of scope** (not written): cascade experiment, reverberation/dereverberation/echo, dashboards, reproduction tooling as a section, environment/provisioning section, mid-project bug narrative, any third board.

---

## 0.3 Chapter Map

| Ch | Title | Figures | Status |
|:--:|---|:--:|:--:|
| F | Front matter (Title / Declaration / Acknowledgement / TOC / Abstract) | 0 | ✅ |
| **1** | **Introduction** | 1–2 | ✅ |
| **2** | **Data** | 2 | ✅ |
| **3** | **Methods** | 2–3 | ✅ |
| **4** | **Results** | 3 | ✅ |
| **5** | **Conclusion** | 0 | ✅ |
| **6** | **References** | 0 | ✅ |
| **L** | **Literature Review** *(B1: include)* | 0–1 | ✅ |
| | **Total figures** | **8–11** | |

> **Placement note**: Handbook lists Literature Review as report item 2, so place it **after Introduction, before Data** → Ch1 Introduction → Ch2 Literature Review → Ch3 Data → Ch4 Methods → Ch5 Results → Ch6 Conclusion → Ch7 References. *(Renumbering applied below to the writing order; the outline keeps report order.)*

---

## 1. Front Matter

| # | Element | Content | Status |
|:--:|---|---|:--:|
| F1 | Title Page | Title + `Submitted in partial fulfillment...` + name, per §12 sample | ☐ |
| F2 | Declaration Page | Standard wording per §12 sample | ☐ (template) |
| F3 | Acknowledgement | Contributions + appreciation. **Gen-AI disclosure slot left EMPTY per Q6** | ☐ |
| F4 | Table of Contents | Mirror of the chapters below | ☐ |
| F5 | Abstract (≤1 page) | Draft points in §7 | ☐ |

---

## 2. Chapter 1 — Introduction

### 2.1 Background and Context
**Talking points:**
- **Audio source separation**: isolating vocals / drums / bass / other from a mixed music recording. Applications: karaoke, remixing, transcription, music education.
- **Noise cancellation (speech enhancement)**: removing background noise from a speech signal. Applications: calls, ASR front-ends, hearing aids.
- Both are core **media-data processing** problems — a high-rate audio stream must be turned into usable information by domain-specific models.
- This project builds a **unified local testbed** where models from both families run under one consistent protocol, so that **performance and output quality** can be compared fairly.

### 2.2 Problem Statement
**Talking points:**
- Public comparisons of these models are **not directly usable**: different papers use different datasets, segment lengths and metric definitions.
- **Output quality is usually reported as one aggregate number**, which hides per-source behaviour (e.g. "other" is much harder than "bass").
- There is no single study that shows, on **one machine and one protocol**, both the **quality** and the **running cost** of each candidate model for a real-time-oriented system.

### 2.3 Objectives
**Talking points (list):**
1. Run a set of **public pretrained separation models** and **noise-cancellation models** **locally** (no API / mirror inference).
2. Measure each separation model's **output quality** with BSS-Eval v4 — SDR per stem and average — against a mixture baseline.
3. Measure each noise-cancellation model's **output quality** with SI-SDR / PESQ / STOI under an explicitly stated sampling-rate regime.
4. Measure each model's **running cost**: parameters, model size, FLOPs, peak VRAM, latency, real-time factor.
5. **Select the best model of each family** on two grounds: **best quality** and **best overall (quality + cost)**.
6. Package the results as reusable figures and tables.

### 2.4 Scope and Boundaries
| In scope | Out of scope |
|---|---|
| Inference-only benchmarking of public pretrained models | Training / fine-tuning |
| Separation quality, denoising quality, running cost | Building the deployed real-time system |
| Best-quality and composite-best model per family | Unpublished / unavailable models |

### 📊 Figures (≤2)
| Fig | Source | Shows |
|---|---|---|
| 1.1 | `fig-acc-main-table.png` | **★ The reference-style comparison table** (see §9) — the report's anchor figure |
| 1.2 | *optional* `fig-spec-mixture.png` | Makes the separation task concrete |

---

## 3. Chapter 2 — Literature Review  *(B1: included, concise)*

> Keep it **tightly scoped** to the two model families you benchmarked. Target length: 0.5–1 page.

### 3.1 Separation models — literature
**Talking points (one short paragraph per family):**
- **Time-domain**: Conv-TasNet (direct waveform separation), Demucs / htdemucs (hybrid time-domain + spectrogram), DPRNN (dual-path recurrent).
- **Frequency-domain**: Open-Unmix (spectrogram NMF-style baseline), MDX-Net (challenge-derived), MMDenseLSTM, BSRNN (band-split RNN).
- **Transformer**: BS-RoFormer (band-split RoPE transformer) — the current strong performer.
- **Analytic baselines**: IRM/IBM Oracle (theoretical upper bound), RPCA (classical matrix decomposition).
- **Gap identified**: reported SDR values come from different protocols and segment choices → not comparable.

### 3.2 Noise-cancellation models — literature
**Talking points:**
- `facebookresearch/denoiser` (Demucs-based, waveform-domain, 16 kHz family: dns48 / dns64 / master64).
- **Mel-RoFormer-Denoise** (mel-band RoPE transformer, 44.1 kHz).
- Metric literature: SI-SDR, PESQ (valid only at 8/16 kHz), STOI.
- **Gap identified**: perceptual (PESQ) and signal-level (SI-SDR) conclusions can diverge, and domain (real vs synthetic noise) changes the conclusion by an order of magnitude.

### 3.3 Summary of the literature review
**Talking points:** the two families are mature but their published numbers are protocol-dependent; this project supplies a single-protocol comparison with cost, and selects a best model per family.

### 📊 Figures (≤1)
| Fig | Source | Shows |
|---|---|---|
| 2.1 | *optional* `fig-arch-bsrnn.png` or `fig-arch-demucs.png` | A representative architecture family tree |

🔶 Recommend **0 figures here** to keep the figure budget for Chapter 4.

---

## 4. Chapter 3 — Data

### 4.1 Datasets
| Dataset | Used for | Size | Reference? | Native rate |
|---|---|---|---|---|
| **MUSDB18-HQ** | Separation | 150 songs, 4 stems | ✅ | 44.1 kHz stereo |
| **DNS-Challenge subset** | Noise cancellation | dev_testset **921** ｜ clean **13,733** ｜ noise **2,308** | ⚠️ dev only | per-corpus |
| **Valentini** | Noise cancellation | testset **824** noisy/clean pairs | ✅ | 16 kHz |

### 4.2 Evaluation Segments and Input Contract
- **Separation quality**: 3 balanced 10 s segments — `ANiMAL - Clinic A` @140 s, `Creepoid - OldTree` @60 s, `Dark Ride - Burning Bridges` @180 s (medians, because a single segment misleads).
- **Cost measurement**: one fixed synthetic input — **44.1 kHz / stereo / 10 s (441,000 samples)** — identical for every model.
- **Denoising**: datasets used at their native rate; two sampling-rate regimes never mixed.

### 4.3 Data Quality, Limitations and Challenges ★ *(handbook asks explicitly)*
- **No clean reference on the DNS dev set** → SI-SDR / PESQ / STOI not computable; only a level-ratio proxy is reported.
- **Native rate differs across models** (16 kHz vs 44.1 kHz) → forced a two-regime reporting rule; PESQ/STOI valid only at 8/16 kHz.
- **Audio-integrity checks** (frame-count sanity) are applied before any file enters evaluation.
- **Truncated runs flagged**: one separation variant completed only **14/50** songs; one model uses **self-trained weights**. Both excluded from ranking and labelled.
- **All comparisons require identical rate / channel count / duration** — a contract mismatch silently corrupts audio.

### 📊 Figures (≤2)
| Fig | Source | Shows |
|---|---|---|
| 3.1 | `fig-spec-waveform.png` | What the raw audio data looks like |
| 3.2 | `fig-spec-mixture.png` | Mixture → stems, i.e. what the data encodes |

---

## 5. Chapter 4 — Methods

### 5.1 Models Under Test

#### 5.1.1 Separation models
| Model | Family | Targets | Params (M) | Native rate |
|---|---|---:|---:|---|
| oBSRNN-SIMO | Band-split RNN | 4-stem | 108.7 | 44.1 kHz |
| oBSRNN (4 ckpt) | Band-split RNN | 4-stem | 164.1 | 44.1 kHz |
| MDX-Net | Frequency-domain | 4-stem | 334.5 | 44.1 kHz |
| BSRNN large (4 ckpt) | Band-split RNN | 4-stem | 146.7 | 44.1 kHz |
| Demucs (htdemucs) | Time-domain hybrid | 4-stem | 42.0 | 44.1 kHz |
| Open-Unmix | Frequency-domain | 4-stem | 35.6 | 44.1 kHz |
| MMDenseLSTM | Frequency-domain | 4-stem | 5.5 | 44.1 kHz |
| Conv-TasNet | Time-domain | 4-stem | 13.4 | 44.1 kHz |
| IRM/IBM Oracle | Analytic | 4-stem | 0.0 | 44.1 kHz |
| BS-RoFormer L12 | Transformer | vocals-only | 159.8 | 44.1 kHz |
| DPRNN (self-trained) | Time-domain | 4-stem | 3.7 | 44.1 kHz |

#### 5.1.2 Noise-cancellation models
| Model | Native rate | Params (M) | Weights (MB) |
|---|---:|---:|---:|
| denoiser dns48 | 16 kHz | 18.9 | 75.5 |
| denoiser dns64 | 16 kHz | 33.5 | 134.1 |
| denoiser master64 | 16 kHz | 33.5 | 134.1 |
| Mel-RoFormer-Denoise | 44.1 kHz | 228.2 | 913.1 |
| Mel-RoFormer-Denoise (aggr) | 44.1 kHz | 228.2 | 913.1 |

### 5.2 Evaluation Metrics and Protocol

#### 5.2.1 Separation
- **`museval.metrics.bss_eval` (BSS-Eval v4)**, per-frame median, `compute_permutation=False`.
- Report **SDR per stem** (vocals / drums / bass / other) **and `avg4`**.
- **Baseline = the unseparated mixture** (avg4 **−5.30 dB**).
- Rule: only **ΔSDR** is comparable across datasets.

#### 5.2.2 Noise cancellation (two regimes, never mixed)
- **44.1 kHz contract rate** and **16 kHz native rate** reported separately.
- Metrics: **SI-SDR (dB)**, **PESQ**, **STOI**, plus log-spectral distance and a high-frequency energy ratio.
- **SNR bins by input SI-SDR**: `<5 dB` / `5–15 dB` / `>=15 dB` / `ALL`.
- **PESQ/STOI blank at 44.1 kHz is by design.**

#### 5.2.3 Running-cost measurement
- Parameters from the model instance; **FLOPs via `FlopCounterMode`, convention 2×MACs** (a **lower bound** — STFT and fused attention are not counted, so cost is also read from measured latency).
- Latency = median of 5 runs after 2 warm-ups; peak VRAM = `max_memory_allocated()`; model size = on-disk weights.
- **Each model runs in its own sub-process** (8 GiB card).

#### 5.2.4 Composite scoring (for the "best overall" selection)
> Define this explicitly so the composite ranking is transparent and reproducible.
- **Separation composite** = equal-weighted normalised score over: `avg4` quality, parameters, peak VRAM, latency (each min–max normalised; cost axes inverted so lower is better).
- **Denoising composite** = 30 % ΔSI-SDR + 30 % ΔPESQ + 40 % split evenly over parameters / VRAM / latency.
- Both scores are **relative to the tested set only** and stated as such.

### 📊 Figures (≤3)
| Fig | Source | Shows |
|---|---|---|
| 4.1 | `fig-arch-demucs.png` | Representative time-domain architecture |
| 4.2 | `fig-arch-bsrnn.png` | Representative frequency/band-split architecture |
| 4.3 | `fig-arch-denoiser.png` | Representative denoiser architecture |

---

## 6. Chapter 5 — Results ★ core of the report

### 6.1 Separation — Output Quality
**Table (medians, MUSDB18-HQ, 3 segments × 10 s):**

| Rank | Model | vocals | drums | bass | other | **avg4** |
|---:|---|---:|---:|---:|---:|---:|
| 1 | oBSRNN-SIMO ⚠️ 14/50 | 8.65 | 9.66 | 11.72 | 7.03 | **9.27** |
| 2 | **oBSRNN (4 ckpt)** | 9.17 | 9.19 | 11.92 | 6.37 | **9.16** |
| 3 | MDX-Net | 7.97 | 8.65 | 12.98 | 6.26 | 8.96 |
| 4 | BSRNN large (4 ckpt) | 8.28 | 9.24 | 10.66 | 5.49 | 8.42 |
| 5 | IRM/IBM Oracle | 10.03 | 8.48 | 8.55 | 6.15 | 8.30 |
| 6 | Demucs (htdemucs) | 7.11 | 8.96 | 10.87 | 5.49 | 8.11 |
| 7 | Open-Unmix | 6.05 | 7.31 | 8.35 | 4.90 | 6.65 |
| 8 | MMDenseLSTM | 5.60 | 7.15 | 7.36 | 4.96 | 6.27 |
| 9 | Conv-TasNet | 5.00 | 7.78 | 9.29 | 1.66 | 5.93 |
| — | DPRNN (self-trained) ⚠️ excluded | −2.18 | −1.86 | −0.82 | −2.02 | −1.72 |
| — | **mixture baseline** | −5.29 | −5.88 | −4.06 | −5.99 | **−5.30** |

**Talking points:**
- Every learned model beats the mixture baseline → the metric discriminates.
- **Best quality: oBSRNN (4 ckpt) at avg4 9.16.** *(oBSRNN-SIMO scores 9.27 but completed only 14/50 songs → not eligible as the fully-verified best.)*
- **Per-stem read: "bass" is easiest, "other" is hardest** across nearly all models.
- Single-target (BS-RoFormer) and self-trained (DPRNN) rows are **not ranked** — contract / provenance differences stated.

### 6.2 Separation — Running Cost
| Model | Params (M) | Size | FLOPs (G) | Peak VRAM (MB) | Latency (s) | RTF |
|---|---:|---:|---:|---:|---:|---:|
| oBSRNN (4 ckpt) | 164.1 | — | 3891.3 | 2637.4 | 5.733 | 0.5733 |
| MDX-Net | 334.5 | — | 777.2 | 1912.8 | 0.737 | 0.0737 |
| BSRNN large (4 ckpt) | 146.7 | — | 1126.9 | 2567.9 | 2.949 | 0.2949 |
| **Demucs (htdemucs)** | **42.0** | — | **508.1** | **599.7** | **0.275** | **0.0275** |
| Open-Unmix | 35.6 | — | 14.3 | 1227.9 | 0.200 | 0.0200 |
| MMDenseLSTM | 5.5 | — | 294.5 | 643.0 | 0.333 | 0.0333 |
| Conv-TasNet | 13.4 | — | 1171.7 | 606.6 | 1.522 | 0.1522 |

**Talking points:**
- Parameters span **3.7 M → 334.5 M**; FLOPs **14.3 G → 43,480.9 G** (incl. single-target); latency **0.085 s → 5.73 s**; peak VRAM **233 MB → 3,394 MB**.
- **Cost and quality rank differently** → read them jointly (see §6.5).
- **RTF is load-dependent** → report a range, never a single point.

### 6.3 Noise Cancellation — Output Quality
**Table (16 kHz regime, Valentini, `ALL`, n = 824):**

| Model | SI-SDR in | SI-SDR out | **ΔSI-SDR** | PESQ in | PESQ out | **ΔPESQ** |
|---|---:|---:|---:|---:|---:|---:|
| denoiser dns48 | 7.39 | 18.39 | **+9.86** | 1.798 | 2.542 | +0.551 |
| denoiser dns64 | 7.39 | 18.30 | +9.64 | 1.798 | 2.589 | +0.601 |
| **denoiser master64** | 7.39 | 18.25 | +9.49 | 1.798 | 3.015 | **+0.963** |
| Mel-RoFormer-Denoise | 7.39 | 17.60 | +6.65 | 1.801 | 2.295 | +0.239 |
| Mel-RoFormer-Denoise (aggr) | 7.39 | 18.36 | +8.16 | 1.801 | 2.297 | +0.256 |

**Talking points:**
- **Best quality: denoiser master64** — best perceptual gain (**ΔPESQ +0.963**) with an SI-SDR gain essentially equal to the other denoiser variants.
- **Metric split noted**: dns48 has the largest **ΔSI-SDR** (+9.86) while master64 has the largest **ΔPESQ** (+0.963). The report states that **perceptual quality (PESQ) drives the "best" choice** for a noise-cancellation product claim.
- **Domain sensitivity**: Mel-RoFormer gains **+6.65 dB** on real recorded noise (Valentini) but only **+0.23 dB** on synthetic transient noise — a **15× gap**; the denoiser family does not collapse (**+9.86 → +11.61 dB**).
- The **44.1 kHz** table is reported separately (optional appendix) to keep regimes unmixed.

### 6.4 Noise Cancellation — Running Cost
| Model | Params (M) | Size (MB) | FLOPs (G) | Peak VRAM (MB) | Latency (s) | RTF |
|---|---:|---:|---:|---:|---:|---:|
| **denoiser dns48** | 18.9 | **75.5** | **39.1** | **233.3** | **0.085** | **0.0084** |
| denoiser dns64 | 33.5 | 134.1 | 69.0 | 343.2 | 0.126 | 0.0126 |
| denoiser master64 | 33.5 | 134.1 | 69.0 | 343.2 | 0.127 | 0.0127 |
| Mel-RoFormer-Denoise | 228.2 | 913.1 | 4030.5 | 2011.2 | 0.980 | 0.0980 |
| Mel-RoFormer-Denoise (aggr) | 228.2 | 913.1 | 4030.5 | 2011.2 | 0.973 | 0.0973 |

**Talking points:**
- **Cheapest / fastest: denoiser dns48** (18.9 M, 75.5 MB, 0.085 s). **Most expensive: Mel-RoFormer-Denoise** (228.2 M, 913.1 MB, 0.98 s — about **12×** the parameters and **12×** the latency).
- **master64 costs essentially the same as dns64** (33.5 M / 134 MB / 0.127 s) while giving a much better PESQ gain → cost is not the deciding factor among the denoiser variants.

### 6.5 ★ Best-Model Selection
**Composite scores computed from §6.2 / §6.4 and the stated scoring rule (§5.2.4):**

**Separation** — normalised composite (equal weight over quality, parameters, VRAM, latency):

| Rank | Model | Composite | avg4 | Params | VRAM | Latency |
|---:|---|---:|---:|---:|---:|---:|
| **1** | **Demucs (htdemucs)** | **0.888** | 8.11 | 42.0 M | 599.7 MB | 0.275 s |
| 2 | MMDenseLSTM | 0.765 | 6.27 | 5.5 M | 643.0 MB | 0.333 s |
| 3 | Open-Unmix | 0.706 | 6.65 | 35.6 M | 1227.9 MB | 0.200 s |
| 4 | Conv-TasNet | 0.683 | 5.93 | 13.4 M | 606.6 MB | 1.522 s |
| 5 | MDX-Net | 0.549 | 8.96 | 334.5 M | 1912.8 MB | 0.737 s |
| 6 | BSRNN large (4 ckpt) | 0.470 | 8.42 | 146.7 M | 2567.9 MB | 2.949 s |
| 7 | oBSRNN (4 ckpt) | 0.379 | 9.16 | 164.1 M | 2637.4 MB | 5.733 s |

**Denoise** — composite (30 % ΔSI-SDR + 30 % ΔPESQ + 40 % cost):

| Rank | Model | Composite | ΔSI-SDR | ΔPESQ | Params | Latency |
|---:|---|---:|---:|---:|---:|---:|
| **1** | **denoiser master64** | **0.942** | +9.49 | **+0.963** | 33.5 M | 0.127 s |
| 2 | denoiser dns48 | 0.829 | **+9.86** | +0.551 | 18.9 M | 0.085 s |
| 3 | denoiser dns64 | 0.806 | +9.64 | +0.601 | 33.5 M | 0.126 s |
| 4 | Mel-RoFormer (aggr) | 0.149 | +8.16 | +0.256 | 228.2 M | 0.973 s |
| 5 | Mel-RoFormer | 0.000 | +6.65 | +0.239 | 228.2 M | 0.980 s |

**★ Recommendation table (the report's stated deliverable):**

| Decision | Model | Justification (measured) |
|---|---|---|
| **Best separation — quality** | **oBSRNN (4 ckpt)** | Highest avg4 among **fully-completed** runs: **9.16 dB**. |
| **Best separation — overall (quality + cost)** | **Demucs (htdemucs)** | Composite **0.888** — highest by a wide margin: **8.11 dB** avg4 (only 1.05 dB below the quality leader) at **42 M / 600 MB / 0.275 s**, i.e. **~4× fewer parameters, ~4.4× less VRAM and ~21× lower latency** than oBSRNN. |
| **Best noise cancellation — quality** | **denoiser master64** | Best perceptual gain: **ΔPESQ +0.963** (and ΔSI-SDR +9.49). |
| **Best noise cancellation — overall (quality + cost)** | **denoiser master64** *(same model)* | Composite **0.942** — it is *both* the quality leader and the cost-efficient choice (33.5 M / 134 MB / 0.127 s); the cheaper dns48 trades away a large PESQ margin. |

**Talking points:**
- State the trade-off explicitly: **quality-first vs overall-best are different answers for separation** (oBSRNN vs Demucs), and the report should say so rather than hide it.
- For denoising the two criteria **agree** — master64 wins on both.
- Note the composite score is **relative to the tested set** and depends on the stated weights; changing the weights can change the separation ranking (a sensitivity note).

### 📊 Figures (≤3)
| Fig | Source | Shows |
|---|---|---|
| 5.1 | `fig-acc-main-table.png` **or** `fig-acc-per-stem.png` | Separation quality per model / per stem |
| 5.2 | `fig-dn-suppression.png` **or** `fig-dn-domain-reversal.png` | Denoising quality and domain sensitivity |
| 5.3 | `fig-cost-vs-acc.png` **or** `fig-cost-pareto.png` | Quality vs cost → supports §6.5 |

---

## 7. Chapter 6 — Conclusion

### 7.1 Summary of Findings
- A consistent local testbed now benchmarks separation and noise-cancellation models under one protocol.
- Separation quality spans **5.93 → 9.27 dB** avg4 over a **−5.30 dB** baseline.
- Noise cancellation improves SI-SDR by **+6.65 → +9.86 dB**; **master64 gives the best perceptual improvement (+0.963 PESQ)**.
- **Robustness is family-dependent**: Mel-RoFormer collapses on synthetic transient noise (+0.23 dB) where the denoiser family does not (+11.61 dB).

### 7.2 Best Models (restated)
| Criterion | Separation | Noise cancellation |
|---|---|---|
| Best quality | oBSRNN (4 ckpt) — 9.16 dB | denoiser master64 — ΔPESQ +0.963 |
| Best overall (quality + cost) | Demucs (htdemucs) — 8.11 dB at 42 M / 0.275 s | denoiser master64 — 33.5 M / 0.127 s |

### 7.3 Expected Outcomes
- A final report with, for each family, a quality table, a cost table, and a justified best-model choice.
- A short design guideline for a real-time system: which model to choose under a latency / VRAM budget.

### 7.4 Recommendations / Future Work
- Extend the tested model set.
- Evaluate the two selected models **together** in one processing chain (as a **future step** — the cascade is *not* reported here).
- Investigate the Mel-RoFormer domain-sensitivity gap.

---

## 8. Chapter 7 — References

- Format with **ACM Citation Style and Reference Formats**, alphabetical, cited as (author, year).
- Core entries (one per model + per metric/dataset): Demucs ｜ BS-RoFormer ｜ BSRNN ｜ MDX-Net ｜ Open-Unmix ｜ Conv-TasNet ｜ MMDenseLSTM ｜ DPRNN ｜ `facebookresearch/denoiser` ｜ BSS-Eval v4 / museval ｜ PESQ ｜ STOI ｜ MUSDB18-HQ ｜ DNS-Challenge.
- 🔶 TO-CONFIRM which entries you have actually read / intend to cite.

---

## 9. ★ Figures — the reference image and the local figure

### 9.1 The reference image you supplied
The image is a **published comparison table** for MUSDB18:

| Model | SDR (dB) |
|---|---:|
| Demucs | 6.03 |
| DPRNN-TasNet (like) | 6.01 |
| Conv-TasNet | 5.73 |
| Open-Unmix | 5.30 |
| MMDenseLSTM | 6.00 |
| RPCA + DRNN | 5.80 (±1) |

and a parameter/FLOPs table (44 kHz, 20 frames): Demucs 128 M / 6.32 G ｜ DPRNN-TasNet 10.97 M / 9.72 G ｜ Conv-TasNet 13.31 M / 30.19 G ｜ Open-Unmix 35 M / 2.32 G ｜ MMDenseLSTM 5.45 M / 36.18 G.

**★ Key finding — this reference is exactly the "protocol problem" your Introduction describes:**
- It reports **Demucs at 6.03 dB** and **Conv-TasNet at 5.73 dB**; your local measurement gives **8.11 dB** and **5.93 dB** — different segment/protocol choices produce different absolute values.
- It reports **Demucs at 128 M parameters**; your local instance measures **42.0 M** — a **different checkpoint/configuration**, not a contradiction.
- **Use this table in Chapter 1 or Chapter 2 as the motivating contrast** — it is precisely why a single-protocol local comparison is needed.

**Figure plan for it:** reproduce it as **Figure 1.1 — "Reference comparison from prior work (protocol differs)"** placed next to your own table in §6.1, with a caption that states the protocol difference. *(Do **not** present it as a result of your work.)*

### 9.2 The local figure you want to add
- **Yes — the local figure is `04_reports/00_shared/figures/paper/fig-acc-main-table.png`**, generated from `01_separation/figures/comparison/fig_avg_sdr_table.png` (300 dpi, MUSDB18-HQ, 3 balanced segments × 10 s, BSS-Eval v4 medians).
- It already contains **Average SDR + all four stems + model size (M) + FLOPs (G)** and a footnote block — i.e. it covers both the quality and cost axes of your report in one table.
- **Recommended placement: Chapter 5 §6.1** as the primary separation results table.
- ⚠️ **Language note**: the current figure's headers and footnote are in **Chinese**. For an English report it should be **regenerated in English** (the generating script is `_make_sdr_table.py`). 🔶 **CONFIRM whether I should regenerate it in English.**

### 9.3 Total figure budget

| Chapter | Planned | Files |
|:--:|:--:|---|
| 1 Introduction | 2 | reference table (Fig 1.1) + local comparison table (Fig 1.2) |
| 2 Literature Review | 0 | — |
| 3 Data | 2 | `fig-spec-waveform` + `fig-spec-mixture` |
| 4 Methods | 3 | `fig-arch-demucs` + `fig-arch-bsrnn` + `fig-arch-denoiser` |
| 5 Results | 2 | `fig-acc-per-stem` + `fig-dn-suppression` or `fig-cost-vs-acc` |
| 6 Conclusion | 0 | — |
| **Total** | **9** | all in `04_reports/00_shared/figures/paper/` |

> Note: the local main table appears in Ch1 as motivation and again (per-stem variant) in Ch5 — if you prefer no repeat, keep it **only in Ch5** and use a small excerpt in Ch1.

---

## 10. DMC Data-Lifecycle Mapping (brief — required for DMC)

| Stage | Where delivered | Section |
|---|---|---|
| Data creation | Fixed-length synthetic cost input; noisy/clean test conditions | §4.2 |
| Data processing | Local inference pipelines; rate/channel/duration normalisation; integrity checks | §5.2.3 |
| Data analysis | BSS-Eval v4 medians; SI-SDR/PESQ/STOI in two regimes; per-stem breakdown; composite scoring | §5.2, §6 |
| Data storage & management | Single local model/weights store; version-controlled results | §5.2.3 |
| Data sharing (visualisation / interactive) | Figures and result tables in this report | §6 |
| Data re-use potentials | Reproducible entry point in the final report | §7.3 |

---

## 11. Open items for your decision

| # | Question |
|:--:|---|
| C1 | **Regenerate `fig-acc-main-table.png` in English** for the English report? (script exists) |
| C2 | Reference-table figure (Fig 1.1) — embed it, and cite the source paper? 🔶 need the citation |
| C3 | Chapter-2 (Literature Review) figure: none (recommended) or one architecture figure? |
| C4 | Approve the composite scoring rule (§5.2.4) — or you prefer different weights? |
| C5 | Approve this v3 outline → I write the full English prose |

---

## 12. Recommended next 3 actions

| # | Action | Owner | When |
|:--:|---|---|---|
| 1 | Confirm **C1** (English figure regeneration) and **C2** (reference citation) | You | Today |
| 2 | Confirm **C4** composite weights (or accept equal weights) | You | Today |
| 3 | Say "go" → I write **Ch1 + Ch5 (Results)** first, then Data / Methods / Literature Review / Conclusion | You → me | Next |

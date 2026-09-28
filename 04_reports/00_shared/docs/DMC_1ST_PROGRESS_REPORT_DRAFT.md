# Real-Time Audio Separation and Noise Cancellation System

### 1st Progress Report (Final Version)

|                  |                                                                     |
| ---------------- | ------------------------------------------------------------------- |
| **Student**      | Wang Sheng Jie                                                      |
| **Student ID**   | 25200887                                                            |
| **Supervisor**   | Dr. XIAN, Poline Yin                                                |
| **Programme**    | BSc (Hons) in Computer Science — Data and Media Communication (DMC) |
| **Project type** | 3-unit, Semester 1                                                  |
| **Date**         | 28 September 2026                                                   |

---

## Declaration

I hereby declare that all the work done in this Final Year Project is of my independent effort. I also certify that I have never submitted the idea and product of this Final Year Project for academic or employment credits.

---

Wang Sheng Jie

Date: \_________________

---

## Acknowledgement

I thank my supervisor, Dr. XIAN, Poline Yin, for her guidance during the first stage of this project.

### Disclosure of Generative AI Use

In accordance with the programme's policy on generative artificial intelligence, I declare the use of AI-based tools in the preparation of this report fully and as follows. I record this disclosure in the interest of accuracy, and I accept responsibility for the content of the report as submitted.

**Tools used.** A large language model assistant, accessed through a code-capable assistant interface, was used throughout the preparation of this report.

**Purpose and extent of use.** The assistance was substantial and is itemised in the table below. In particular, and stated plainly, the **English prose of the main body was drafted by the AI assistant** and was then reviewed, corrected and approved by me. The figures and tables were rendered by the assistant from the measurement data of my experiments, and the document was typeset by the assistant into the submitted format.

| Area of assistance | What was done | Extent |
|---|---|---|
| Drafting of the report text | The English wording of the main chapters was drafted by the AI assistant from my experimental results and from the outline that I specified | Substantial: the prose was AI-drafted, then reviewed and revised by me |
| Document formatting | Typesetting to the required layout (font size, line spacing, page margins, page numbering) and conversion into the submitted file format | Performed by the assistant |
| Figures and tables | Rendering the charts and comparison figures from my own measurement data, and re-drawing them in English to match the report language | Performed by the assistant on my data, without alteration of any value |
| Literature search | Locating the source papers for the models and datasets, and arranging them into a citation list | Performed by the assistant; each entry was checked against the published source |
| Evaluation code | Scripting for data processing, metric computation and benchmarking | Written with assistant support |

**What I did myself.** The research is my own. I selected the topic and the research questions; I assembled and ran the experiments on a local machine; I chose the separation models and the noise-cancellation models to be tested; I fixed the evaluation protocol, the datasets, the segments and the metrics; I produced the measurement data on which every table and figure in this report is based; and I reviewed, verified and revised the text of this report before submission, including checking every numerical value against my own results.

**Statement of responsibility.** I understand that the AI assistant did not determine the research questions, the experimental protocol, the model selection or the conclusions, all of which are my own work, and that all measurements reported here come from experiments that I designed and ran. I have read and checked the whole report as submitted and I take full responsibility for its correctness, its originality and its compliance with the programme's policy on the use of generative artificial intelligence.

---

## Table of Contents

| Chapter                      | Page |
| ---------------------------- | ---- |
| Declaration                  | i    |
| Acknowledgement              | ii   |
| Table of Contents            | iii  |
| Abstract                     | iv   |
| Chapter 1. Introduction      | 1    |
| Chapter 2. Literature Review | 3    |
| Chapter 3. Data              | 4    |
| Chapter 4. Methods           | 6    |
| Chapter 5. Results           | 8    |
| Chapter 6. Conclusion        | 12   |
| Chapter 7. References        | 13   |

*(Page numbers to be finalised after typesetting.)*

### List of Figures

| Figure     | Title                                                                     |
| ---------- | ------------------------------------------------------------------------- |
| Figure 3.1 | Waveform of a MUSDB18 mixture and of the vocals stem contained in it      |
| Figure 3.2 | Log-frequency spectrogram of the same mixture                             |
| Figure 4.1 | Architecture of the three candidate models                                |
| Figure 5.1 | Average SDR (in dB) for the four-stem separation models                   |
| Figure 5.2 | Running cost of every model: parameters against single-pass latency       |
| Figure 5.3 | Noise-cancellation gain over the noisy input (16 kHz protocol, Valentini) |

### List of Tables

| Table     | Title                                                                                |
| --------- | ------------------------------------------------------------------------------------ |
| Table 3.1 | Datasets used in this project                                                        |
| Table 4.1 | Separation models                                                                    |
| Table 4.2 | Noise-cancellation models                                                            |
| Table 5.1 | Separation quality (average SDR and per-stem SDR, in dB)                             |
| Table 5.2 | Separation running cost (fixed input: 44.1 kHz, stereo, 10 s)                        |
| Table 5.3 | Noise-cancellation quality (16 kHz, Valentini, all SNR bins, n = 824)                |
| Table 5.4 | Noise-cancellation running cost (fixed input: 44.1 kHz, stereo, 10 s)                |
| Table 5.5 | Separation composite score (equal weight over quality, parameters, VRAM and latency) |
| Table 5.6 | Noise-cancellation composite score (30 % ΔSI-SDR, 30 % ΔPESQ, 40 % cost)             |
| Table 5.7 | Selected best models                                                                 |

---

## Abstract

Audio source separation and noise cancellation are two widely used media-data processing tasks, yet the published comparisons of the underlying models are not directly usable: different studies evaluate on different datasets, different segment lengths and different metric definitions, so a practitioner cannot tell which model to deploy for a given quality and latency budget. This report describes the first stage of a project that builds a single local testbed in which public pretrained models from both families are run and measured under one consistent protocol, and then selects the best model of each family.

A set of separation models and a set of noise-cancellation models are executed locally on one machine with no API or mirror inference. Separation quality is measured with BSS-Eval v4 (SDR per stem and their average) against a mixture baseline; noise-cancellation quality is measured with SI-SDR, PESQ and STOI in two explicitly separated sampling-rate regimes; running cost is measured as parameters, model size, FLOPs, peak VRAM, latency and real-time factor on one fixed ten-second input.

Preliminary results show that separation quality spans 5.93 to 9.27 dB average SDR against a −5.30 dB baseline, and that noise cancellation improves SI-SDR by 6.65 to 9.86 dB. The separation model with the best measured quality is oBSRNN (four-checkpoint) at 9.16 dB, while the model with the best balance of quality and cost is Demucs (htdemucs), which reaches 8.11 dB with roughly a quarter of the parameters, a quarter of the peak VRAM and one-twentieth of the latency. For noise cancellation, the denoiser *master64* model is best on both criteria, achieving the largest perceptual gain (+0.963 PESQ) at 33.5 M parameters and 0.127 s latency. A marked robustness difference between model families is also found: the Mel-RoFormer family gains 6.65 dB on real recorded noise but only 0.23 dB on synthetic transient noise. These findings establish the benchmark and identify a recommended model for each task.

---

## Chapter 1. Introduction

### 1.1 Background and Context

**Audio source separation** is the task of isolating the individual sound sources that are mixed together in a single recording. In music, the standard targets are *vocals*, *drums*, *bass* and *other* (the remaining instruments). Good separation enables karaoke and remix applications, instrument-specific transcription, practice tools and music education software.

**Noise cancellation**, also called speech enhancement, is the task of removing background noise from a speech signal. It is a core component of voice calls, front-ends for automatic speech recognition, and hearing aids.

Both tasks are fundamentally *media-data* problems. An audio waveform is a high-rate data stream — a ten-second stereo clip at 44.1 kHz contains 882,000 samples per channel — and turning that stream into usable information requires models that understand the structure of sound. This project treats both tasks from a data-processing perspective: the goal is not only to run the models, but to measure what each one actually produces and at what cost.

### 1.2 Problem Statement

A practitioner who wants to build an audio processing system faces a practical difficulty. Although many pretrained models are publicly available, the comparisons published in the literature cannot be used directly, for three reasons.

First, different studies evaluate on different datasets, so the absolute numbers are not comparable. Second, even within the same dataset, the choice of evaluation segments changes the result substantially — a single quiet passage can make one instrument appear to separate far better than it does on average. Third, quality is usually reported as one aggregate number, which hides the fact that the individual sources are not equally difficult: in the results reported later, the bass line is consistently the easiest source to recover while the residual "other" category is the hardest.

A fourth gap is cost. Two models with similar quality may differ by a factor of ten in parameter count, memory footprint and latency, and that difference decides whether the model is usable in a real-time system. Published papers rarely report cost and quality together under one protocol.

### 1.3 Objectives

This project therefore has the following objectives.

1. To assemble a set of public pretrained **separation models** and **noise-cancellation models** and to run them **locally** on one machine, without relying on external APIs or mirror services for inference.
2. To measure the **output quality** of each separation model using BSS-Eval v4 — SDR for each individual stem as well as the average across stems — against a mixture baseline that represents "no separation".
3. To measure the **output quality** of each noise-cancellation model using SI-SDR, PESQ and STOI under an explicitly stated sampling-rate regime.
4. To measure the **running cost** of every model: parameter count, model size, FLOPs, peak VRAM, single-pass latency and real-time factor.
5. To **select the best model of each family** on two grounds — the best measured quality, and the best overall balance of quality against cost.
6. To package the results as reusable figures and tables suitable for the final report and for a system design decision.

### 1.4 Scope and Boundaries

The report is deliberately limited to the two model families and to their measured performance and output quality.

| In scope                                                        | Out of scope                                       |
| --------------------------------------------------------------- | -------------------------------------------------- |
| Inference-only benchmarking of public pretrained models         | Training or fine-tuning of models                  |
| Separation quality, noise-cancellation quality and running cost | Building the deployed real-time system itself      |
| Selection of the best model of each family                      | Comparison against models whose code is not public |

---

## Chapter 2. Literature Review

### 2.1 Source Separation Models

Research on music source separation falls into three broad families.

**Time-domain models** operate directly on the waveform. Conv-TasNet (Luo and Mesgarani, 2019) introduced a fully convolutional time-domain architecture that replaced the spectrogram with a learned encoder and a mask estimator, and it remains a standard low-parameter baseline. Demucs (Défossez et al., 2019) and its successor HTDemucs (Rouard et al., 2023) combine a time-domain branch with a spectrogram branch, which lets the model exploit both phase-sensitive waveform detail and frequency structure; HTDemucs is the model that made hybrid architectures the default choice for high-quality separation. Dual-path recurrent networks, such as DPRNN (Luo et al., 2020), arrange the time-frequency representation into two axes and model each with recurrent layers.

**Frequency-domain models** operate on a magnitude spectrogram. Open-Unmix (Stöter et al., 2019) is a compact, well-documented baseline that applies a recurrent network to each source; MDX-Net (Kim et al., 2021) originates from a community challenge and mixes convolutional and recurrent blocks; MMDenseLSTM (Takahashi et al., 2018) applies densely connected recurrent layers; and BSRNN, or Band-Split RNN (Luo and Yu, 2023), splits the frequency axis into bands and models each band with shared recurrent layers, which allows a single model to generalise across sources.

**Transformer-based models** such as BS-RoFormer (Lu et al., 2023) apply a rotary-position transformer over the band-split representation and currently define the strong end of the quality range. Alongside these learned models, **analytic baselines** are useful reference points: the ideal-ratio-mask (IRM) and ideal-binary-mask (IBM) oracles give a theoretical upper bound for a mask-based system under a fixed analysis window, while classical matrix decomposition methods such as RPCA require no training at all.

The gap that this project addresses is that the reported SDR values in these works come from different evaluation protocols and different segment choices, and they are therefore not comparable to one another.


### 2.2 Noise-Cancellation Models

The waveform-domain approach to speech enhancement is represented by the *denoiser* family (Défossez et al., 2020), which adapts the Demucs architecture to single-channel speech and is published in three widely used configurations of increasing capacity (dns48, dns64 and master64). More recently, the mel-band transformer (Wang et al., 2023) has been adapted from music separation to enhancement; this is the Mel-RoFormer-Denoise family, which operates at the full 44.1 kHz sampling rate.

The evaluation of these models relies on a small set of established metrics: SI-SDR (Le Roux et al., 2019) for signal-level fidelity, PESQ (Rix et al., 2001) for perceived speech quality and STOI (Taal et al., 2011) for intelligibility. An important practical point, which the literature acknowledges but which is easily overlooked in comparisons, is that PESQ is defined only at 8 kHz and 16 kHz; it cannot be applied at 44.1 kHz. A second point is that perceptual and signal-level metrics can rank models differently, and that the domain of the noise — recorded versus synthetic — can change the measured improvement by an order of magnitude.

### 2.3 Summary

Both model families are mature, but their published numbers are protocol-dependent and are rarely accompanied by cost measurements. This project supplies a single-protocol comparison of both families together with their cost, and selects a best model from each family on the basis of that measurement.

---

## Chapter 3. Data

### 3.1 Datasets

Three public datasets are used. They are summarised in Table 3.1.

**Table 3.1 — Datasets used in this project.**

| Dataset              | Used for           | Size                                          |       Reference signal | Native rate     |
| -------------------- | ------------------ | --------------------------------------------- | ---------------------: | --------------- |
| MUSDB18-HQ           | Music separation   | 150 songs, 4 stems                            |     Yes (source stems) | 44.1 kHz stereo |
| DNS-Challenge subset | Noise cancellation | 921 dev-test items; 13,733 clean; 2,308 noise | Only on the dev subset | Per corpus      |
| Valentini            | Noise cancellation | 824 noisy/clean pairs (test set)              |                    Yes | 16 kHz          |

**MUSDB18-HQ** (Rafii et al., 2019) is the standard dataset for music source separation. Each song is distributed as a mixture together with the four isolated stems, which are the reference signals against which separation quality is measured. Figure 3.1 shows what a separation task looks like on this data: the waveform of a mixture and the waveform of the vocals stem contained inside it, and Figure 3.2 shows the same mixture as a log-frequency spectrogram, in which the harmonic structure of the instruments is visible as horizontal bands.

**Figure 3.1 — Waveform of a MUSDB18 mixture and of the vocals stem contained in it.**

![Waveform of a mixture and of the vocals stem](04_reports/00_shared/figures/paper/fig-spec-waveform.png)

*The vocals are silent for long stretches of the track while the mixture is not, which is the situation that a separation model has to resolve.*

**Figure 3.2 — Log-frequency spectrogram of the same mixture.**

![Log-frequency spectrogram of a mixture](04_reports/00_shared/figures/paper/fig-spec-mixture.png)

*Energy is concentrated at low frequencies; the harmonic stacks of the instruments appear as horizontal lines. Frequency-domain models operate on representations of this kind.*

The **DNS-Challenge subset** (Reddy et al., 2020) is used for noise cancellation. Its development test set is the only part of the corpus that is accompanied by a reference signal, which limits what can be measured there; the clean-speech, noise and room-impulse-response pools are used to construct controlled test conditions.

**Valentini** (Valentini-Botinhao, 2017) is a speech enhancement set of real recordings with noisy/clean pairs, and it provides an independent, non-synthetic test condition.

### 3.2 Evaluation Segments and Input Contract

Three evaluation settings are used, and the choice is deliberate in each case.

For **separation quality**, three energy-balanced ten-second segments are used: *ANiMAL – Clinic A* at 140 s, *Creepoid – OldTree* at 60 s and *Dark Ride – Burning Bridges* at 180 s. A single segment is not sufficient, because the opening passages of many tracks contain a low-frequency introduction that inflates the apparent bass quality to an implausible level; a segment is therefore required to have each stem contributing between roughly 14 % and 43 % of the energy, and the median of the three segments is reported.

For **running cost**, one fixed synthetic input is used for every model without exception: 44.1 kHz, stereo, ten seconds (441,000 samples per channel). Using an identical input for all models is what makes the latency, FLOPs and memory figures comparable.

For **noise cancellation**, each dataset is used at its native sampling rate, and the two sampling-rate regimes are never mixed in a single table.

### 3.3 Data Quality, Limitations and Challenges

Several properties of the data constrain what can be concluded, and they are stated here rather than left implicit.

The **DNS development test set has no clean reference signal**. As a result, SI-SDR, PESQ and STOI cannot be computed on it; the only quantity that can be reported is the ratio between the output and input energy, which serves as a proxy for how strongly the model suppresses its input. This limitation is the reason the quantitative quality results in this report come from Valentini and from constructed noisy/clean conditions rather than from the DNS test set.

The **native sampling rate differs across models**. The denoiser models operate at 16 kHz while the Mel-RoFormer models operate at 44.1 kHz. This forces quality to be reported in two regimes: a contract rate of 44.1 kHz, which reflects the actual working rate, and a native rate of 16 kHz, in which PESQ and STOI are defined. The apparent absence of PESQ and STOI at 44.1 kHz is therefore a property of the metric, not missing data.

**Audio integrity must be verified before evaluation.** A partially written audio file can carry an incorrect sample count in its header; a cheap duration check is applied to every file so that a truncated file cannot silently enter the metric computation.

**Some runs are truncated and must be flagged.** One separation variant completed only 14 of the 50 test songs, and one model uses weights that were trained locally rather than released by the original authors. Neither is used in the ranking, and both are labelled wherever they appear.

Finally, **all comparisons require identical sampling rate, channel count and duration**. A mismatch between the rate a model expects and the rate it is given does not raise an error; it silently changes the signal, and the resulting metric is meaningless. This is treated as a hard contract in the pipeline.

---

## Chapter 4. Methods

### 4.1 Models Under Test

The two model families compared in this report have different internal structures, and the choice of architecture determines both the achievable quality and the running cost. Figure 4.1 shows the concept flow of the three models that the results later identify as the strongest candidates in their family.

**Figure 4.1 — Architecture of the three candidate models.**

![Concept flow of Demucs v4 (HTDemucs), BSRNN and the denoiser family, with measured cost](04_reports/00_shared/figures/progress_report/pr_fig_arch_compare_en.png)

*The concept flow is drawn from the source papers; the cost strip beneath each column is measured locally on the fixed ten-second input. The BSRNN strip sums four checkpoints because the four-stem configuration runs them in sequence.*

#### 4.1.1 Separation models

The separation models cover the three families described in Chapter 2, together with two analytic baselines. They are listed in Table 4.1.

**Table 4.1 — Separation models.**

| Model                       | Family             |     Targets | Params (M) | Native rate |
| --------------------------- | ------------------ | ----------: | ---------: | ----------- |
| oBSRNN-SIMO                 | Band-split RNN     |     4 stems |      108.7 | 44.1 kHz    |
| oBSRNN (4 checkpoints)      | Band-split RNN     |     4 stems |      164.1 | 44.1 kHz    |
| MDX-Net                     | Frequency domain   |     4 stems |      334.5 | 44.1 kHz    |
| BSRNN large (4 checkpoints) | Band-split RNN     |     4 stems |      146.7 | 44.1 kHz    |
| Demucs (htdemucs)           | Hybrid time domain |     4 stems |       42.0 | 44.1 kHz    |
| Open-Unmix                  | Frequency domain   |     4 stems |       35.6 | 44.1 kHz    |
| MMDenseLSTM                 | Frequency domain   |     4 stems |        5.5 | 44.1 kHz    |
| Conv-TasNet                 | Time domain        |     4 stems |       13.4 | 44.1 kHz    |
| IRM/IBM Oracle              | Analytic baseline  |     4 stems |        0.0 | 44.1 kHz    |
| BS-RoFormer L12             | Transformer        | vocals only |      159.8 | 44.1 kHz    |
| DPRNN                       | Time domain        |     4 stems |        3.7 | 44.1 kHz    |

Two entries require a note. **BS-RoFormer L12** produces a single target (vocals) and therefore cannot be ranked against the four-stem models, whose score is an average over four stems. **DPRNN** uses weights trained locally, because the original authors released only speech-domain weights; its quality is not comparable to the models that use released music-domain weights, and it is reported as a negative control rather than a contender.

#### 4.1.2 Noise-cancellation models

The noise-cancellation models are listed in Table 4.2.

**Table 4.2 — Noise-cancellation models.**

| Model                             | Native rate | Params (M) | Weights (MB) |
| --------------------------------- | ----------: | ---------: | -----------: |
| denoiser dns48                    |      16 kHz |       18.9 |         75.5 |
| denoiser dns64                    |      16 kHz |       33.5 |        134.1 |
| denoiser master64                 |      16 kHz |       33.5 |        134.1 |
| Mel-RoFormer-Denoise              |    44.1 kHz |      228.2 |        913.1 |
| Mel-RoFormer-Denoise (aggressive) |    44.1 kHz |      228.2 |        913.1 |

### 4.2 Evaluation Metrics and Protocol

#### 4.2.1 Separation quality

Separation quality is measured with the `museval` implementation of BSS-Eval v4 (Stöter et al., 2018), using the SDR component, with the SI-SDR formulation (Le Roux et al., 2019) reported alongside it. Frame-wise values are reduced with a median, and permutation is disabled so that each stem is compared against its fixed counterpart. The reported quantity is the SDR for each stem, and `avg4`, the arithmetic mean of the four stems.

The **baseline is the unseparated mixture itself**, that is, the mixture used directly as the estimate. It has an `avg4` of −5.30 dB. Reporting the models against this baseline is what shows that the metric is actually discriminating between better and worse separation, rather than merely producing plausible-looking numbers.


A cross-dataset rule is applied throughout: because absolute SDR depends on the dataset, only the *difference* in SDR may be compared between different datasets.

#### 4.2.2 Noise-cancellation quality

Noise-cancellation quality is measured in two sampling-rate regimes, which are reported separately and never combined.

The **contract rate of 44.1 kHz** is the actual working rate; it includes the cost of internal resampling. The **native rate of 16 kHz** is the rate at which PESQ and STOI are defined. The metrics are SI-SDR in decibels, PESQ, and STOI, together with the log-spectral distance and the fraction of energy above 4 kHz.

Results are additionally stratified into three bins by the input SI-SDR — below 5 dB, 5 to 15 dB, and above 15 dB — together with a combined row.

#### 4.2.3 Running-cost measurement

Parameters are counted from the model instance rather than read from a configuration file. FLOPs are measured with the PyTorch counter under a convention of twice the number of multiply-accumulate operations. This is a **lower bound**, because the counter records only the operations that PyTorch schedules and does not include the short-time Fourier transform or fused attention, so the cost figures are always read together with the measured latency rather than on their own.

Latency is the median of five runs after two warm-up runs, synchronised before and after each run. Peak VRAM is the maximum allocated memory reported by the runtime. Model size is the size of the weights on disk. Because the available GPU has 8 GiB of memory and the models cannot coexist in one process, **every model is measured in its own sub-process**; this is a requirement of the protocol, not an implementation detail.

#### 4.2.4 Composite scoring

To identify the model with the best overall balance of quality and cost, a composite score is defined for each family. Each axis is min–max normalised across the tested set, and the cost axes are inverted so that a lower cost scores higher.

For **separation**, the composite score is the equal-weighted mean of four normalised axes: quality (`avg4`), parameters, peak VRAM and latency.

For **noise cancellation**, the composite score is 30 % normalised ΔSI-SDR, 30 % normalised ΔPESQ, and 40 % distributed equally over parameters, peak VRAM and latency.

Both scores are **relative to the tested set only**, and the weights are stated explicitly so that the ranking can be recomputed under different preferences.

---

## Chapter 5. Results

### 5.1 Separation — Output Quality

The separation quality of every four-stem model is shown in Figure 5.1 and Table 5.1. In these and all following separation figures, the analysis is on MUSDB18-HQ with the three energy-balanced segments described in Section 3.2, and the median over segments is reported.

**Figure 5.1 — Average SDR (in dB) for the four-stem separation models.**

![Average SDR for every four-stem separation model, against the mixture baseline](04_reports/00_shared/figures/progress_report/pr_fig_accuracy_bars_en.png)

*The mixture baseline and the analytic IRM/IBM upper bound are shown but excluded from the ranking, as is the self-trained DPRNN negative control. The best ranked model is highlighted in green.*

**Table 5.1 — Separation quality (average SDR and per-stem SDR, in dB).**

| Rank | Model                  | Vocals | Drums |  Bass | Other |  **avg4** |
| ---: | ---------------------- | -----: | ----: | ----: | ----: | --------: |
|    1 | oBSRNN-SIMO †          |   8.65 |  9.66 | 11.72 |  7.03 |  **9.27** |
|    2 | **oBSRNN (4 ckpt)**    |   9.17 |  9.19 | 11.92 |  6.37 |  **9.16** |
|    3 | MDX-Net                |   7.97 |  8.65 | 12.98 |  6.26 |      8.96 |
|    4 | BSRNN large (4 ckpt)   |   8.28 |  9.24 | 10.66 |  5.49 |      8.42 |
|    5 | IRM/IBM Oracle ‡       |  10.03 |  8.48 |  8.55 |  6.15 |      8.30 |
|    6 | Demucs (htdemucs)      |   7.11 |  8.96 | 10.87 |  5.49 |      8.11 |
|    7 | Open-Unmix             |   6.05 |  7.31 |  8.35 |  4.90 |      6.65 |
|    8 | MMDenseLSTM            |   5.60 |  7.15 |  7.36 |  4.96 |      6.27 |
|    9 | Conv-TasNet            |   5.00 |  7.78 |  9.29 |  1.66 |      5.93 |
|    — | DPRNN (self-trained) ‡ |  −2.18 | −1.86 | −0.82 | −2.02 |     −1.72 |
|    — | **Mixture (baseline)** |  −5.29 | −5.88 | −4.06 | −5.99 | **−5.30** |

† Completed 14 of the 50 test songs in the cost sweep; see Section 3.3.  
‡ Reported for reference and excluded from the ranking (analytic bound; self-trained negative control).

Three observations follow from the table.

First, **every learned model clearly outperforms the mixture baseline**. The baseline sits at −5.30 dB, while the weakest learned model reaches 5.93 dB and the strongest reaches 9.16 dB. This confirms that the metric is measuring real separation ability and not an artefact of the protocol.

Second, the **best measured quality among fully-completed runs is oBSRNN (four-checkpoint), at `avg4` = 9.16 dB**. The oBSRNN-SIMO variant scores higher at 9.27 dB, but it completed only 14 of the 50 songs in the cost sweep, so it is not eligible as the fully-verified best model; it is nevertheless a strong candidate and is flagged wherever it appears.

Third, the **per-stem pattern is consistent across models**: the bass line is the easiest source to recover, and the residual "other" category is the hardest. For example, MDX-Net reaches 12.98 dB on bass but only 6.26 dB on "other"; Conv-TasNet shows the same pattern, at 9.29 dB and 1.66 dB respectively. This is a useful practical finding: an aggregate score conceals a large difference in per-source difficulty.

### 5.2 Separation — Running Cost

The running cost of the separation models is reported in Table 5.2 and Figure 5.2.

**Figure 5.2 — Running cost of every model: parameters against single-pass latency.**

![Parameters against latency for every model, with bubble area showing peak VRAM](04_reports/00_shared/figures/progress_report/pr_fig_cost_pareto_en.png)

*Bubble area is peak VRAM. A model in the lower-left corner is cheap on all three axes at once. The Mel-RoFormer and dereverberation weights share one architecture, so their points nearly coincide.*

**Table 5.2 — Separation running cost (fixed input: 44.1 kHz, stereo, 10 s).**

| Model                 | Params (M) | FLOPs (G) | Peak VRAM (MB) | Latency (s) |        RTF |
| --------------------- | ---------: | --------: | -------------: | ----------: | ---------: |
| oBSRNN (4 ckpt)       |      164.1 |    3891.3 |         2637.4 |       5.733 |     0.5733 |
| MDX-Net               |      334.5 |     777.2 |         1912.8 |       0.737 |     0.0737 |
| BSRNN large (4 ckpt)  |      146.7 |    1126.9 |         2567.9 |       2.949 |     0.2949 |
| **Demucs (htdemucs)** |   **42.0** | **508.1** |      **599.7** |   **0.275** | **0.0275** |
| Open-Unmix            |       35.6 |      14.3 |         1227.9 |       0.200 |     0.0200 |
| MMDenseLSTM           |        5.5 |     294.5 |          643.0 |       0.333 |     0.0333 |
| Conv-TasNet           |       13.4 |    1171.7 |          606.6 |       1.522 |     0.1522 |

Across the wider set of tested models, the parameter count ranges from 3.7 M to 334.5 M, the single-pass latency ranges from 0.085 s to 5.73 s, and the peak VRAM ranges from 233 MB to 3,394 MB. All models fit within the 8 GiB card individually, which is why per-model process isolation was required.

The important point is that **quality and cost do not rank the models in the same order**. The highest-quality model, oBSRNN, costs 164.1 M parameters and 5.733 s per ten-second input, whereas Demucs is only 1.05 dB behind on quality but uses about a quarter of the parameters, about a quarter of the peak VRAM and about one-twentieth of the latency. This divergence is the reason the selection in Section 5.5 considers both criteria.

One caveat applies to the RTF column: it is sensitive to machine load, and the same model can vary substantially between two measurements. The RTF figures are therefore intended as an order-of-magnitude guide rather than as a precise ranking.

### 5.3 Noise Cancellation — Output Quality

The noise-cancellation quality of the models is reported in Table 5.3 and Figure 5.3, measured at the native rate of 16 kHz on the Valentini set.

**Figure 5.3 — Noise-cancellation gain over the noisy input (16 kHz protocol, Valentini).**

![Improvement in SI-SDR, PESQ and STOI delivered by each noise-cancellation model](04_reports/00_shared/figures/progress_report/pr_fig_dn_gain_en.png)

*All three panels show the gain over the noisy input, computed per clip and then aggregated by median. The ΔSTOI panel is scaled by 100 for readability: the raw gain lies between 0.005 and 0.017 on a 0–1 scale.*

**Table 5.3 — Noise-cancellation quality (16 kHz, Valentini, all SNR bins, n = 824).**

| Model                             | SI-SDR in | SI-SDR out | **ΔSI-SDR** | PESQ in | PESQ out |  **ΔPESQ** |
| --------------------------------- | --------: | ---------: | ----------: | ------: | -------: | ---------: |
| denoiser dns48                    |      7.39 |      18.39 |   **+9.86** |   1.798 |    2.542 |     +0.551 |
| denoiser dns64                    |      7.39 |      18.30 |       +9.64 |   1.798 |    2.589 |     +0.601 |
| **denoiser master64**             |      7.39 |      18.25 |       +9.49 |   1.798 |    3.015 | **+0.963** |
| Mel-RoFormer-Denoise              |      7.39 |      17.60 |       +6.65 |   1.801 |    2.295 |     +0.239 |
| Mel-RoFormer-Denoise (aggressive) |      7.39 |      18.36 |       +8.16 |   1.801 |    2.297 |     +0.256 |

Two findings are important.

First, the **best perceptual quality is obtained by `denoiser master64`**, which improves PESQ by **+0.963**, the largest margin of any model, while its SI-SDR improvement (+9.49 dB) is essentially the same as that of the other denoiser variants. Note that the two metrics do not agree on the second place: the largest *signal-level* improvement is obtained by `dns48` (+9.86 dB SI-SDR) whereas the largest *perceptual* improvement is obtained by `master64`. For a noise-cancellation product, perceived quality is the more relevant criterion, and the selection in Section 5.5 therefore follows PESQ.

Second, the **Mel-RoFormer family is markedly more sensitive to the noise domain**. It improves SI-SDR by 6.65 dB on the real recorded noise of Valentini, but by only 0.23 dB on synthetic transient noise — a difference of roughly a factor of fifteen. The denoiser family does not show this collapse: its improvement rises from 9.86 dB on Valentini to 11.61 dB on the synthetic condition. This is a genuine robustness difference between the two families rather than a measurement artefact, and it is one of the more practically important results of this stage.

### 5.4 Noise Cancellation — Running Cost

The running cost of the noise-cancellation models is reported in Table 5.4.

**Table 5.4 — Noise-cancellation running cost (fixed input: 44.1 kHz, stereo, 10 s).**

| Model                             | Params (M) | Weights (MB) | FLOPs (G) | Peak VRAM (MB) | Latency (s) |        RTF |
| --------------------------------- | ---------: | -----------: | --------: | -------------: | ----------: | ---------: |
| **denoiser dns48**                |       18.9 |     **75.5** |  **39.1** |      **233.3** |   **0.085** | **0.0084** |
| denoiser dns64                    |       33.5 |        134.1 |      69.0 |          343.2 |       0.126 |     0.0126 |
| denoiser master64                 |       33.5 |        134.1 |      69.0 |          343.2 |       0.127 |     0.0127 |
| Mel-RoFormer-Denoise              |      228.2 |        913.1 |    4030.5 |         2011.2 |       0.980 |     0.0980 |
| Mel-RoFormer-Denoise (aggressive) |      228.2 |        913.1 |    4030.5 |         2011.2 |       0.973 |     0.0973 |


The cheapest and fastest model is `denoiser dns48`, at 18.9 M parameters, a 75.5 MB weight file and 0.085 s of latency. The most expensive is Mel-RoFormer-Denoise, at 228.2 M parameters, 913.1 MB of weights and 0.980 s of latency — roughly twelve times the parameters and twelve times the latency of the denoiser models, and about twenty times the latency of dns48.

An important observation is that **`master64` costs essentially the same as `dns64`** — 33.5 M parameters, 134.1 MB of weights and 0.127 s of latency — while delivering a substantially better perceptual improvement (+0.963 against +0.601 PESQ). Cost is therefore not the deciding factor among the denoiser variants.

### 5.5 Best-Model Selection

The composite scores defined in Section 4.2.4 are reported in Tables 5.5 and 5.6.

**Table 5.5 — Separation composite score (equal weight over quality, parameters, VRAM and latency).**

|  Rank | Model                 | Composite | avg4 |  Params |      VRAM | Latency |
| ----: | --------------------- | --------: | ---: | ------: | --------: | ------: |
| **1** | **Demucs (htdemucs)** | **0.888** | 8.11 |  42.0 M |  599.7 MB | 0.275 s |
|     2 | MMDenseLSTM           |     0.765 | 6.27 |   5.5 M |  643.0 MB | 0.333 s |
|     3 | Open-Unmix            |     0.706 | 6.65 |  35.6 M | 1227.9 MB | 0.200 s |
|     4 | Conv-TasNet           |     0.683 | 5.93 |  13.4 M |  606.6 MB | 1.522 s |
|     5 | MDX-Net               |     0.549 | 8.96 | 334.5 M | 1912.8 MB | 0.737 s |
|     6 | BSRNN large (4 ckpt)  |     0.470 | 8.42 | 146.7 M | 2567.9 MB | 2.949 s |
|     7 | oBSRNN (4 ckpt)       |     0.379 | 9.16 | 164.1 M | 2637.4 MB | 5.733 s |

**Table 5.6 — Noise-cancellation composite score (30 % ΔSI-SDR, 30 % ΔPESQ, 40 % cost).**

|  Rank | Model                     | Composite |   ΔSI-SDR |      ΔPESQ |  Params | Latency |
| ----: | ------------------------- | --------: | --------: | ---------: | ------: | ------: |
| **1** | **denoiser master64**     | **0.942** |     +9.49 | **+0.963** |  33.5 M | 0.127 s |
|     2 | denoiser dns48            |     0.829 | **+9.86** |     +0.551 |  18.9 M | 0.085 s |
|     3 | denoiser dns64            |     0.806 |     +9.64 |     +0.601 |  33.5 M | 0.126 s |
|     4 | Mel-RoFormer (aggressive) |     0.149 |     +8.16 |     +0.256 | 228.2 M | 0.973 s |
|     5 | Mel-RoFormer              |     0.000 |     +6.65 |     +0.239 | 228.2 M | 0.980 s |

The selection is summarised in Table 5.7.

**Table 5.7 — Selected best models.**

| Criterion                         | Separation                                                     | Noise cancellation                                  |
| --------------------------------- | -------------------------------------------------------------- | --------------------------------------------------- |
| **Best measured quality**         | **oBSRNN (4 ckpt)** — 9.16 dB avg4                             | **denoiser master64** — ΔPESQ +0.963                |
| **Best overall (quality + cost)** | **Demucs (htdemucs)** — 8.11 dB at 42.0 M / 599.7 MB / 0.275 s | **denoiser master64** — 33.5 M / 134.1 MB / 0.127 s |

For separation, the two criteria give **different** answers, and this is stated rather than hidden. If the priority is absolute quality and the latency budget is generous, **oBSRNN (four-checkpoint)** is the choice at 9.16 dB. If the model must run within a realistic memory and latency budget, **Demucs (htdemucs)** is the choice: it gives up only 1.05 dB of quality while requiring roughly a quarter of the parameters and the peak VRAM, and about one-twentieth of the latency of oBSRNN. The composite score of Demucs, 0.888, is the highest of any tested separation model by a wide margin.

For noise cancellation, the two criteria **agree**. **`denoiser master64`** achieves the best perceptual quality and the best overall balance at the same time: it delivers the largest PESQ improvement (+0.963) at 33.5 M parameters, a 134.1 MB weight file and 0.127 s of latency, all of which are close to the minimum for the family. The cheaper `dns48` is smaller and faster still, but the reduction in perceptual quality is large relative to the saving in cost.

Two caveats apply to the composite ranking. It is relative to the tested set only, so a model outside this set could change the ordering. And it depends on the stated weights: for separation, if quality were given a much larger weight, the ranking would move towards oBSRNN. Both are properties of the scoring rule and are recorded so that the choice can be recomputed under a different preference.

---

## Chapter 6. Conclusion

### 6.1 Summary of Findings

This report has established a consistent local testbed in which separation models and noise-cancellation models are benchmarked under one protocol, and it has produced the first set of measured results.

For separation, quality spans 5.93 to 9.27 dB average SDR against a −5.30 dB mixture baseline, and the per-stem difficulty is consistent across models, with the bass line being the easiest source and the residual "other" category the hardest.

For noise cancellation, the measured improvement in SI-SDR spans 6.65 to 9.86 dB, and the best perceptual improvement is +0.963 PESQ, obtained by `denoiser master64`.

The robustness of the two families differs markedly: the Mel-RoFormer family gains 6.65 dB on real recorded noise but only 0.23 dB on synthetic transient noise, whereas the denoiser family does not collapse.

### 6.2 Best Models

Based on the measurements, and distinguishing the two selection criteria, the recommended models are as follows.

For **separation**, the best measured quality is obtained by **oBSRNN (four-checkpoint)** at 9.16 dB average SDR, while the best overall balance of quality and cost is obtained by **Demucs (htdemucs)**, which reaches 8.11 dB with roughly a quarter of the parameters and peak memory and about one-twentieth of the latency.

For **noise cancellation**, **`denoiser master64`** is best on both criteria, combining the largest perceptual gain (+0.963 PESQ) with a small model (33.5 M parameters) and low latency (0.127 s).

### 6.3 Expected Outcomes

At the end of the project, the final report will present, for each of the two model families, a quality table measured under one protocol, a matching cost table, and a justified recommendation of the best model. It will also provide a short design guideline for a real-time system, indicating which model to choose under a given memory and latency budget.

### 6.4 Recommendations for Future Work

Three directions follow from this stage. First, the set of models under test can be extended, particularly within the transformer family. Second, the two selected models can be evaluated in a single processing chain, in which the noise-cancellation stage precedes the separation stage; this is a natural next step and will be reported separately. Third, the marked domain sensitivity of the Mel-RoFormer family deserves further investigation, since it determines whether that family is advisable when the noise characteristics are not known in advance.

---


## Chapter 7. References

References follow the ACM Citation Style and Reference Formats, are listed in alphabetical order, and are cited in the text by author and year of publication.

1. Steven F. Boll. 1979. Suppression of acoustic noise in speech using spectral subtraction. *IEEE Transactions on Acoustics, Speech, and Signal Processing* ASSP-27, 2 (April 1979), 113–120. <https://doi.org/10.1109/TASSP.1979.1163209>
2. Alexandre Défossez, Gabriel Synnaeve, and Yossi Adi. 2020. Real time speech enhancement in the waveform domain. In *Proceedings of INTERSPEECH 2020*. ISCA, 3291–3295. <https://doi.org/10.21437/Interspeech.2020-2409>
3. Alexandre Défossez, Nicolas Usunier, Léon Bottou, and Francis Bach. 2019. Music source separation in the waveform domain. *arXiv preprint* arXiv:1911.13254. <https://doi.org/10.48550/arXiv.1911.13254>
4. Minseok Kim, Woosung Choi, Jaehwa Chung, Daewon Lee, and Soonyoung Jung. 2021. KUIELab-MDX-Net: A two-stream neural network for music demixing. In *Proceedings of the MDX Workshop at ISMIR 2021*. <https://doi.org/10.48550/arXiv.2111.12203>
5. Jonathan Le Roux, Scott Wisdom, Hakan Erdogan, and John R. Hershey. 2019. SDR — half-baked or well done? In *Proceedings of the 2019 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP '19)*. IEEE, 626–630. <https://doi.org/10.1109/ICASSP.2019.8683855>
6. Yi Luo and Nima Mesgarani. 2019. Conv-TasNet: Surpassing ideal time–frequency magnitude masking for speech separation. *IEEE/ACM Transactions on Audio, Speech, and Language Processing* 27, 8 (August 2019), 1256–1266. <https://doi.org/10.1109/TASLP.2019.2915167>
7. Yi Luo, Zhuo Chen, and Takuya Yoshioka. 2020. Dual-path RNN: Efficient long sequence modeling for time-domain single-channel speech separation. In *Proceedings of the 2020 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP '20)*. IEEE, 46–50. <https://doi.org/10.1109/ICASSP40776.2020.9054266>
8. Yi Luo and Jianwei Yu. 2023. Music source separation with band-split RNN. *IEEE/ACM Transactions on Audio, Speech, and Language Processing* 31 (2023), 1893–1901. <https://doi.org/10.1109/TASLP.2023.3271145>
9. Wei-Tsung Lu, Ju-Chiang Wang, Qiuqiang Kong, and Yun-Ning Hung. 2023. Music source separation with band-split RoPE transformer. *arXiv preprint* arXiv:2309.02612. <https://doi.org/10.48550/arXiv.2309.02612>
10. Yuki Mitsufuji, Giorgio Fabbro, Stefan Uhlich, Fabian-Robert Stöter, Alexandre Défossez, Minseok Kim, Woosung Choi, Chin-Yun Yu, and Kin-Wai Cheuk. 2022. Music demixing challenge 2021. *Frontiers in Signal Processing* 1 (2022), 808395. <https://doi.org/10.3389/frsip.2021.808395>
11. Zafar Rafii, Antoine Liutkus, Fabian-Robert Stöter, Stylianos Ioannis Mimilakis, and Rachel Bittner. 2017. MUSDB18 — a corpus for music separation. Zenodo. <https://doi.org/10.5281/zenodo.1117372>
12. Zafar Rafii, Antoine Liutkus, Fabian-Robert Stöter, Stylianos Ioannis Mimilakis, and Rachel Bittner. 2019. MUSDB18-HQ — an uncompressed version of MUSDB18. Zenodo. <https://doi.org/10.5281/zenodo.3338373>
13. Chandan K. A. Reddy, Vishak Gopal, Ross Cutler, Ebrahim Beyrami, Roger Cheng, Harishchandra Dubey, Sergiy Matusevych, Robert Aichner, Ashkan Aazami, Sebastian Braun, Puneet Rana, Sriram Srinivasan, and Johannes Gehrke. 2020. The INTERSPEECH 2020 deep noise suppression challenge: Datasets, subjective testing framework, and challenge results. In *Proceedings of INTERSPEECH 2020*. ISCA, 2492–2496. <https://doi.org/10.21437/Interspeech.2020-3038>
14. Antony W. Rix, John G. Beerends, Michael P. Hollier, and Andries P. Hekstra. 2001. Perceptual evaluation of speech quality (PESQ) — a new method for speech quality assessment of telephone networks and codecs. In *Proceedings of the 2001 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP '01)*, Vol. 2. IEEE, 749–752. <https://doi.org/10.1109/ICASSP.2001.941023>
15. Simon Rouard, Francisco Massa, and Alexandre Défossez. 2023. Hybrid transformers for music source separation. In *Proceedings of the 2023 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP '23)*. IEEE, 1–5. <https://doi.org/10.48550/arXiv.2211.08553>
16. Fabian-Robert Stöter, Stefan Uhlich, Antoine Liutkus, and Yuki Mitsufuji. 2019. Open-Unmix — a reference implementation for music source separation. *Journal of Open Source Software* 4, 41 (September 2019), 1667. <https://doi.org/10.21105/joss.01667>
17. Fabian-Robert Stöter, Antoine Liutkus, and Nobutaka Ito. 2018. The 2018 signal separation evaluation campaign. In *Latent Variable Analysis and Signal Separation (LVA/ICA 2018)*, Lecture Notes in Computer Science, Vol. 10891. Springer, 293–305. <https://doi.org/10.48550/arXiv.1804.06267>
18. Cees H. Taal, Richard C. Hendriks, Richard Heusdens, and Jesper Jensen. 2011. An algorithm for intelligibility prediction of time–frequency weighted noisy speech. *IEEE Transactions on Audio, Speech, and Language Processing* 19, 7 (September 2011), 2125–2136. <https://doi.org/10.1109/TASL.2011.2114881>
19. Naoya Takahashi, Nabarun Goswami, and Yuki Mitsufuji. 2018. MMDenseLSTM: An efficient combination of convolutional and recurrent neural networks for audio source separation. In *Proceedings of the 2018 16th International Workshop on Acoustic Signal Enhancement (IWAENC)*. IEEE, 106–110. <https://doi.org/10.48550/arXiv.1805.02410>
20. Cassia Valentini-Botinhao. 2017. *Noisy Speech Database for Training Speech Enhancement Algorithms and TTS Models*. University of Edinburgh, School of Informatics, Centre for Speech Technology Research (CSTR). <https://doi.org/10.7488/ds/2117>
21. Ju-Chiang Wang, Wei-Tsung Lu, and Minz Won. 2023. Mel-band RoFormer for music source separation. In *Extended Abstracts of the Late-Breaking Demo Session of the 24th International Society for Music Information Retrieval Conference (ISMIR 2023)*. <https://doi.org/10.48550/arXiv.2310.01809>

> **Note on the Mel-RoFormer entry.** Entry 20 describes the architecture in its original music-separation setting. The noise-cancellation weights used in this project (the `aufr33` variants) are community-trained checkpoints for that architecture rather than models introduced by the paper; the entry is therefore cited as the source of the architecture and not as the source of the enhancement model.

> **Note on sampling-rate-dependent metrics.** PESQ (entry 13) is defined by ITU-T Recommendation P.862 and its wideband extension P.862.2; STOI (entry 17) and SI-SDR (entry 5) are used here in their standard published forms. All three are reported at the sampling rates at which they are defined, as required by the protocol in Section 4.2.

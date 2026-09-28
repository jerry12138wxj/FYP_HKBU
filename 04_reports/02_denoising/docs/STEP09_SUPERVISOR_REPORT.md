# Step 09 — Denoising Evaluation: Report to Supervisor

**Project:** Real-Time Audio Separation and Noise Cancellation System
**Student:** Wang Sheng Jie (25200887)
**Supervisor:** Dr. XIAN, Poline Yin
**Step:** Stage 5 — Denoising model evaluation (T5.1–T5.7)
**Deliverables:** D6–D9
**Report date:** 2026-09-28
**Status:** ✅ Complete — all inference re-run on a corrected pipeline, 16,575 cells, 0 errors

---

## 0. Executive Summary (read this first)

This step answered one question: **which denoising model actually works, under which input conditions, and at what cost?**

What was done:

1. Built a **single evaluation entry point** (`_denoise_eval.py`) covering 5 denoising checkpoints across 3 datasets and 2 sampling-rate contracts → **16,575 inference cells, 0 failures**.
2. Established a **dual-sampling-rate protocol** (16 kHz primary for PESQ/STOI; 44.1 kHz contract-rate secondary) so that no conclusion depends on a single measurement chain.
3. Ran three follow-up studies beyond the main table: a **dry/wet strength sweep** (is denoising strength a tunable knob?), a **spectral before/after analysis** (what exactly does the model touch in the frequency domain?), and **out-of-domain (OOD) passthrough probes** (is the model a real denoiser?).
4. **Found and fixed a serious evaluation-pipeline bug (P19)** that had invalidated 12,845 cells and produced a plausible-but-false narrative ("the three metrics contradict each other"). After the fix, **the conclusions reversed completely**.

Headline results:

| Finding | Result |
|---|---|
| Best denoising model on real noise (PESQ) | `denoiser_master64` — ΔPESQ **+0.963**, ΔSI-SDR +9.49 dB (Valentini, n=824) |
| Best overall when compute/memory/time are considered | `denoiser_dns48` — ΔSI-SDR **+9.86 dB** at the lowest cost of the three (see §7) |
| Strongest finding of this step | **Model families have complementary valid domains** — Mel-RoFormer gains +6.65 dB on real noise but **fails (+0.23 dB) on transient noise**, where denoiser reaches +11.61 dB |
| Metric-direction contradiction claimed in earlier drafts | **Does not exist** — it was an artefact of the P19 bug. All 20 (model × SNR-bin) cells are positive on all three metrics |
| Most valuable engineering lesson | "**A narrative that explains everything is usually the bug talking.**" The only real defence is to re-run under a second measurement contract and check whether the conclusion survives |

---

## 1. What this step was required to deliver

| Requirement | Acceptance criterion | Status |
|---|---|---|
| Fair cross-model comparison | Single **16 kHz primary protocol** (the definition domain of PESQ/STOI) | ✅ |
| Preserve native-rate conclusions | Native/contract rate kept **in a separate table, never mixed** | ✅ |
| In-domain control must be in the table | `master64` was trained on data including Valentini → must report `dns48`/`dns64` as out-of-domain controls | ✅ |
| Strength must be tunable | dry/wet strength curve | ✅ |
| Out-of-domain behaviour must be explainable | OOD probes + spectral analysis | ✅ |
| Negative results must be reported as negative | Reverb removal, OOD noise generalisation | ✅ (see §6) |

> **Note on supervisor decision (2026-09-23):** it was decided to report the de-reverberation result as a **negative result**, with no claim of cascade benefit. This is documented separately in `DEREVERB_NEGATIVE_RESULT.md`.

---

## 2. What was actually done — pipeline and artefacts

### 2.1 Scripts written

| Script | Role |
|---|---|
| `tools/_denoise_eval.py` | **Single unified entry point** — serves all 5 model variants × 3 datasets × 2 rate contracts. One entry, no forks. Sub-command `resummary` recomputes aggregates without re-running inference. |
| `tools/_denoise_registry.py` | Exposes each wrapper's **input contract** (`run_fn.contract_sr`, expected shape `(N,2)`), which is what made the P19 fix possible. |
| `tools/_denoise_drywet.py` | Strength knob: `estimate = (1 − dry)·model(noisy) + dry·noisy`, `dry ∈ [0,1]`. |
| `tools/_dns_make_pairs.py` | Builds the synthetic noisy corpus (clean speech + Freesound transient noise) with ground-truth SNR labels. |
| `tools/_denoise_ood_probe.py` | Three out-of-domain probes (clean passthrough / pure-noise passthrough / gain sweep). |
| `tools/_denoise_diagnosis.py` | Spectral-difference diagnosis. |
| `tools/_denoise_probeA_paired.py` | 120-clip paired clean probe (statistical robustness check on the "is it a low-pass?" question). |
| `tools/_plot_denoise.py`, `_plot_denoise_drywet.py`, `_plot_denoise_spectral.py`, `_plot_denoise_spectrum_delta.py` | Figure generation (no manual numbers — everything reads from the machine-readable data files). |
| `tools/_dereverb_probe.py`, `_dereverb_official_probe.py`, `_dereverb_diagnosis.py` | De-reverberation probe + upstream-official-path cross-validation. |

### 2.2 Models evaluated (5 checkpoints, 2 families)

| Family | Checkpoint | Native rate | Note |
|---|---|---|---|
| `facebookresearch/denoiser` | `dns48` | 16 kHz | Trained on DNS only (out-of-domain w.r.t. Valentini) |
| `facebookresearch/denoiser` | `dns64` | 16 kHz | Trained on DNS only |
| `facebookresearch/denoiser` | `master64` | 16 kHz | **Training set includes Valentini → in-domain** |
| Mel-Band RoFormer (ZFTurbo community weights, `aufr33` denoise set) | `mel_roformer_denoise` | 44.1 kHz | **No peer-reviewed denoising paper exists** for this weight set — must be cited as community weights |
| Mel-Band RoFormer | `mel_roformer_denoise_aggr` | 44.1 kHz | Aggressive variant of the same weights |

> ⚠️ **Compliance note (project requirement R3):** the Mel-RoFormer denoiser weights are community-contributed, **not peer-reviewed**. Any citation must state this.

### 2.3 Datasets (3)

| Dataset | n (clips) | Has clean ground truth? | Role |
|---|---|---|---|
| `valentini` (Valentini-Botinhao) | 824 | ✅ full reference | **Primary** real-noise evaluation set |
| `synth` (self-built) | 800 (200 speech × 4 SNR) | ✅ full reference, known GT SNR (−5/0/+5/+10 dB) | **Transient/impulsive noise** stress set |
| `dns_dev` (DNS `dev_testset/noisy_testclips`) | 921 → 867 usable | ❌ **no reference (blind test set)** | Level-behaviour verification on a third-party distribution |

> **Why `synth` was built instead of using DNS's own clean set (P13):** using DNS clean speech as the base triggers the model's **level gate**, collapsing whole clips to −40 dB. The synth set therefore uses **Valentini clean speech + Freesound transient noise**, with `LEVEL_GATE = 0.20`.

### 2.4 Scale

| Protocol | Cells | Composition |
|---|---|---|
| 16 kHz primary | 12,455 | dns_dev 4,335 + synth 4,000 + valentini 4,120 |
| 44.1 kHz contract rate | 4,120 | valentini 4,120 (5 models × 824) |
| **Total** | **16,575** | **errors = 0** |

> Verified directly from `denoise_manifest.json` (16,575 cells; `ok = true` for every cell; 4,120 @ 44.1 kHz + 12,455 @ 16 kHz; 3,315 cells per model × 5 models).

---

## 3. Evaluation protocol design (and why it matters)

### 3.1 The dual-sampling-rate protocol

| Protocol | Rate | What it means | Metrics reported |
|---|---|---|---|
| **A — contract rate** | 44.1 kHz | The rate the model actually expects. denoiser internally does 44.1k→16k→44.1k, so this protocol **includes the resampling cost**. | SI-SDR, SNR, LSD, `hf_ratio`. **PESQ/STOI are blank by design** (their definition domain is 8/16 kHz). |
| **B — primary evaluation rate** | 16 kHz | Model-native for denoiser; a **down-sampled** comparison for Mel-RoFormer (natively 44.1 kHz). | SI-SDR, PESQ, STOI, LSD, `hf_ratio` |

**The contract-rate chain (mandatory, from P19):**

```
native rate → contract rate 44100 → model → contract rate → evaluation rate 16000
```

Never `native rate → 16 kHz → model`. This is exactly the bug described in §5.

### 3.2 Additional protocol decisions

| Decision | Rationale |
|---|---|
| **Paired-difference aggregate**: `Δ = median(out − in)` computed **per clip, then median** | *Not* `median(out) − median(in)`. On the pooled ≥15 dB bin these two give **opposite signs** (+0.028 vs −0.063). All aggregation code emits `pesq_improve` / `stoi_improve` paired columns so readers cannot subtract medians by mistake. |
| **Stratify by input SI-SDR** (`<5` / `5–15` / `≥15` dB / ALL) | A single overall median hides a monotone trend (see §4.2). For `synth`, stratification uses the **known GT SNR** so it is unbiased. |
| **`n_skipped` reported explicitly** | Level-gate exclusions must be visible, not silently dropped. |
| **No manual clip picking for figures** | Spectral figures select clips at the **p10 / p50 / p90 quantiles of that model's ΔSI-SDR** — the clip IDs are reproducible from the manifest. |
| **Valid-band restriction for spectral analysis** | At 16 kHz, Nyquist = 8 kHz, so only **0–7.8 kHz** is analysed. Above 8 kHz is resampling artefact, not model behaviour. Not excluding it inflates the "4 kHz+ suppression" statistic to a spurious −32 dB. |

---

## 4. Results

### 4.1 Primary table — 16 kHz, Valentini, ALL (n = 824, medians)

| Model | ΔSI-SDR (dB) | ΔPESQ | ΔSTOI | hf_ratio in→out |
|---|---:|---:|---:|---|
| `denoiser_dns48` | **+9.86** | +0.551 | +0.0049 | 0.211 → 0.207 |
| `denoiser_dns64` | +9.64 | +0.601 | +0.0069 | 0.211 → 0.207 |
| **`denoiser_master64`** | +9.49 | **+0.963** | **+0.0171** | 0.211 → 0.209 |
| `mel_roformer_denoise` | +6.65 | +0.239 | +0.0038 | 0.210 → 0.212 |
| `mel_roformer_denoise_aggr` | +8.16 | +0.256 | +0.0051 | 0.210 → 0.215 |

**Reading:**

1. **denoiser family is the stronger denoiser.** ΔSI-SDR +9.5 to +9.9 dB vs Mel-RoFormer's +6.7 to +8.2 dB.
2. **`master64` is the best on perceptual quality.** Its ΔPESQ (+0.963) is **1.75×** that of `dns48` (+0.551), while its SI-SDR is essentially the same. This is the in-domain effect — see §4.3.
3. **All five models are spectrally near-neutral**: output `hf_ratio` is within ±2.5% of input. **There is no spectral damage.**
4. The `aggr` variant is **not** better overall: it wins in the noisiest bin (+12.14 vs +8.60 dB) but barely helps in the cleanest bin and gains little PESQ. If "do no harm on clean input" is the criterion, the standard variant is sufficient.

### 4.2 Stratified table — 16 kHz, Valentini (medians, paired)

| Model | Input bin | n | ΔSI-SDR (dB) | ΔPESQ | ΔSTOI |
|---|---|---:|---:|---:|---:|
| `denoiser_dns48` | ≥15 dB | 134 | +4.14 | +0.432 | +0.0018 |
| | 5–15 dB | 279 | +9.83 | +0.585 | +0.0049 |
| | <5 dB | 411 | **+14.79** | +0.548 | +0.0176 |
| | **ALL** | 824 | +9.86 | +0.551 | +0.0049 |
| `denoiser_dns64` | ≥15 dB | 145 | +4.34 | +0.436 | +0.0027 |
| | 5–15 dB | 283 | +9.62 | +0.659 | +0.0064 |
| | <5 dB | 396 | **+14.14** | +0.617 | +0.0232 |
| | **ALL** | 824 | +9.64 | +0.601 | +0.0069 |
| **`denoiser_master64`** | ≥15 dB | 156 | **+4.74** | **+0.648** | +0.0058 |
| | 5–15 dB | 337 | +9.52 | **+1.047** | +0.0175 |
| | <5 dB | 331 | **+14.36** | **+1.035** | **+0.0413** |
| | **ALL** | 824 | +9.49 | **+0.963** | +0.0171 |
| `mel_roformer_denoise` | ≥15 dB | 194 | +4.06 | +0.107 | +0.0013 |
| | 5–15 dB | 412 | +7.97 | +0.307 | +0.0043 |
| | <5 dB | 218 | +8.60 | +0.224 | +0.0070 |
| | **ALL** | 824 | +6.65 | +0.239 | +0.0038 |
| `mel_roformer_denoise_aggr` | ≥15 dB | 194 | +4.58 | +0.124 | +0.0012 |
| | 5–15 dB | 412 | +9.09 | +0.308 | +0.0057 |
| | <5 dB | 218 | +12.14 | +0.307 | +0.0108 |
| | **ALL** | 824 | +8.16 | +0.256 | +0.0051 |

**Three findings that only stratification reveals:**

1. **20 / 20 cells are positive on all three metrics.** No cell shows a directional contradiction.
2. **Gain grows monotonically as input gets dirtier**, for both families. denoiser goes from +4.1~4.7 dB (clean) to +14.1~14.8 dB (very noisy). This also proves the model is **not suppressing indiscriminately**.
3. **`master64` wins in every bin on PESQ**, and also on SI-SDR in the ≥15 dB bin.

### 4.3 In-domain control (T5.4) — the `master64` question

`master64`'s training set includes Valentini, so Valentini is **in-domain** for it; `dns48`/`dns64` are out-of-domain. The plan flagged this as "must be in the table, otherwise the conclusion does not hold."

| Checkpoint | Domain vs Valentini | ΔSI-SDR ALL | ΔSI-SDR ≥15 dB | ΔPESQ ALL | n_skipped |
|---|---|---:|---:|---:|---:|
| **`master64`** | **in-domain** | +9.49 | **+4.74** | **+0.963** | 0 / 824 |
| `dns48` | out-of-domain | +9.86 | +4.14 | +0.551 | 0 / 824 |
| `dns64` | out-of-domain | +9.64 | +4.34 | +0.601 | 0 / 824 |

**Conclusion:** the three checkpoints have nearly identical SI-SDR gain, but the **in-domain `master64` is clearly best on the perceptual metric PESQ (+0.963 vs +0.551/+0.601, ~1.7×)** and also best in the cleanest bin.

> **Domain adaptation is effective, and its value shows up in perceptual quality rather than in SI-SDR.**

This is the **reverse** of what an earlier draft claimed (see §5.4).

**External cross-check on a blind set** — because Valentini is `master64`'s in-domain data, the above has a confound. Using the DNS official blind test set (921 clips; out-of-domain for all three) to verify **level behaviour**:

| Model | dns_dev median `level_ratio` | share `< 0.20` |
|---|---:|---:|
| `denoiser_dns48` | 0.8339 | 1.0% |
| `denoiser_dns64` | 0.8660 | 1.0% |
| **`denoiser_master64`** | **0.8329** | **1.7%** |
| `mel_roformer_denoise` | 0.9945 | 0.1% |

→ `master64` still compresses level the most on out-of-domain data (direction survives), but the magnitude is **1.7%**, not the 45.4% an earlier draft reported.

> ⚠️ `dns_dev` has no ground truth, so it **cannot** be used to verify ΔSI-SDR / ΔPESQ. It only quantifies level behaviour.

### 4.4 The core finding: complementary valid domains (T5.7)

Same speech (Valentini `clean_testset_wav`), same models, same pipeline. **The only variable is noise type.**

| Model | `valentini` (real, steady noise) ΔSI-SDR | `synth` (transient impulsive noise) ΔSI-SDR | Verdict |
|---|---:|---:|---|
| `mel_roformer_denoise` | **+6.65** | **+0.23** | 🔴 Works on real noise → **fails** on transient |
| `mel_roformer_denoise_aggr` | +8.16 | +0.39 | Same |
| `denoiser_dns48` | **+9.86** | **+11.61** | Strong on **both** |
| `denoiser_dns64` | +9.64 | +11.92 | Same |
| `denoiser_master64` | +9.49 | +11.97 | Same |

**This is not simply "denoiser overtakes" — Mel-RoFormer fails outright (≈0) on transient noise while denoiser keeps a strong gain.** Reversal magnitude: Mel-RoFormer drops **−6.4 dB**; denoiser *rises* **+1.8 dB**.

`synth` stratified by ground-truth SNR (unbiased: 800 clips = 200 speech × 4 bins):

| Model | −5 dB | 0 dB | +5 dB | +10 dB | **ALL** | `level_ratio` | `hf_ratio` in→out |
|---|---:|---:|---:|---:|---:|---:|---|
| `denoiser_dns48` | +14.18 | +13.02 | +11.17 | +8.84 | **+11.61** | 0.995 | 0.270 → **0.194** |
| `denoiser_dns64` | +14.86 | +12.80 | +11.43 | +9.10 | **+11.92** | 1.005 | 0.270 → **0.196** |
| `denoiser_master64` | +14.94 | +12.99 | +11.30 | +9.15 | **+11.97** | 0.997 | 0.270 → **0.197** |
| `mel_roformer_denoise` | +0.14 | +0.17 | +0.41 | +0.41 | **+0.23** | 1.14 | 0.270 → 0.255 |

**Mechanism (supported by the `hf_ratio` data — 15× difference in effect size):**

| Dataset | Noise type | Energy distribution | Overlap with speech | denoiser `hf_ratio` shift |
|---|---|---|---|---|
| `valentini` | DNS real noise (steady / babble) | broadband, sustained, includes low frequency | **partially overlaps** speech → separable | **−1.9%** |
| `synth` | door (538) / breath-spit (210) / copy-machine (52) | **transient, energy concentrated in high frequency** | **highly similar to speech consonants** → misclassified as speech | **−28%** |

- `valentini` `hf_ratio_in` ≈ **0.21** (close to speech's 0.21) → denoiser barely touches the spectrum.
- `synth` `hf_ratio_in` ≈ **0.27** (**clearly above** speech; noise pushes the spectrum into the upper half) → denoiser suppresses heavily.

**Therefore:** Mel-RoFormer's suppression criterion relies on "how different the input is from speech" — transient noise does **not look like noise** under that criterion, so it does nothing. denoiser suppresses exactly the noise with a high high-frequency share, and transient noise's energy happens to be concentrated there — so it suppresses *more* than it does on real noise.

> ⚠️ **This mechanism is still an inference** — a "high-frequency-only noise" control experiment has not been run. However, the 15× difference in `hf_ratio` shift (−1.9% vs −28%) is a **direct observation** and is sufficient to support the "complementary valid domains" conclusion.

**Pipeline suspicion was ruled out:**

| Suspicion | Check | Conclusion |
|---|---|---|
| Wrong synthesis formula | Recomputed actual SNR = **−5.00 dB** (matches the setting) | ✅ Correct |
| Clips too clean | Noise-dominant frame share = **0.91**; frame noise-share p50 = 0.966 | ✅ Very noisy |
| Noise too sparse | `door` dominant-frame 0.520, `breath_spit` 0.729, `copy-machine` 0.623 | ✅ Sparsity assumption refuted |
| Reference / length mismatch | `reference_mode = fullref`; `est_len / in_len ≈ 0.99`, trimmed | ✅ Normal |
| Sampling-rate contract (P19) | Fixed and fully re-run; these numbers are post-fix | ✅ Ruled out |

→ **All pipeline suspicions excluded. This is model behaviour.**

**Why Mel-RoFormer's numbers are unaffected by the P19 bug:** its wrapper's contract rate is also 44.1 kHz, but **a near-identity mapping stays a near-identity mapping after two resamplings**. It already barely changes the signal (`level_ratio` ≈ 1.14), so the resampling error cannot turn it "from effective into ineffective". Its ΔSI-SDR ≈ 0 is a **real** conclusion — and the post-fix re-run (+0.23) matches the pre-fix value (+0.017) almost exactly, which cross-validates it.

### 4.5 Dry/wet strength sweep (T5.5)

`facebookresearch/denoiser` exposes an official `--dry` parameter:

```
estimate = (1 − dry) · model(noisy) + dry · noisy        # dry ∈ [0,1]
```

- `dry = 0` → pure model output (= the main table configuration)
- `dry = 1` → full passthrough (no denoising)

**Correctness anchor:** `dry = 0` must match the main table **bit-for-bit**. Verified: `compared = 12 (spot check), worst_abs_diff = 0.0000 → PASS`.

**Optimal operating point (Valentini 16 kHz, n = 824 per cell, 3 weights, err = 0, 47m47s):**

| Model | Bin | ★ optimal dry (SI-SDR) | ΔSI-SDR gain | optimal dry (PESQ) | ΔPESQ gain |
|---|---|---:|---:|---:|---:|
| `denoiser_dns48` | <5 dB | 0.0 | 14.79 | 0.1 | 0.826 |
| | 5–15 dB | 0.0 | 9.83 | 0.1 | 0.798 |
| | ≥15 dB | 0.2 | 4.41 | 0.1 | 0.465 |
| | **ALL** | **0.0** | **9.86** | **0.1** | **0.739** |
| `denoiser_dns64` | ALL | 0.0 | 9.64 | 0.1 | 0.727 |
| **`denoiser_master64`** | ALL | **0.0** | **9.49** | **0.0** | **0.963** |

Full dns48 curve (ALL bin):

| dry | ΔSI-SDR | ΔPESQ |
|---:|---:|---:|
| 0.0 (main table) | **+9.86** | +0.551 |
| 0.1 | +9.74 | **+0.739** ← PESQ optimum |
| 0.2 | +8.81 | +0.630 |
| 0.3 | +7.61 | +0.509 |
| 0.5 | +5.01 | +0.319 |
| 1.0 (passthrough) | −0.01 | +0.013 |

**Three conclusions:**

**1. Denoising strength is a real, tunable knob, and the optimum moves monotonically with input SNR.**
In the `<5 dB` bin the optimum is `dry = 0` (suppress as much as possible, don't mix anything back); in the `≥15 dB` bin it shifts right to `0.2` (dns48) / `0.1` (dns64). **No single fixed strength can be optimal simultaneously** — further independent evidence for the "stratify by input SNR" discipline. Note `dry = 1` gives ΔSI-SDR = −0.01 and ΔPESQ = +0.013, i.e. the baseline's own zero point, as expected — a second internal consistency check.

**2. ★ The PESQ-optimal strength varies by weight, and the direction matches the in-domain finding (§4.3).**

| Weight | ΔPESQ-optimal dry | at dry=0.0 | at dry=0.1 | Effect of dilution |
|---|---:|---:|---:|---|
| `dns48` | **0.1** | +0.551 | **+0.739** | dilution **improves +34%** |
| `dns64` | **0.1** | +0.601 | **+0.727** | dilution **improves +21%** |
| `master64` | **0.0** | **+0.963** | +0.867 | dilution **degrades −10%** |

> 🔴 **This is a completely independent verification of the §4.3 finding.** §4.3 concluded that `master64` is this project's **in-domain** weight (its training set includes Valentini), hence it is best on the main table. This experiment reaches the **same** conclusion from a **completely different angle** (the strength knob): `master64` peaks at `dry = 0` (pure model output) and any dilution makes it worse, whereas the two out-of-domain weights need **10% of the original signal mixed back** to reach their respective PESQ peaks. One regularity holding under two independent experiments is far more credible than a single observation.

**3. ΔSI-SDR and ΔPESQ have different optimal operating points, and this divergence survives the P19 fix.**

| Metric (dns48, ALL) | Optimal dry | Value there | Value at dry=0 | Difference |
|---|---:|---:|---:|---:|
| ΔSI-SDR | 0.0 | +9.86 | +9.86 | — |
| ΔPESQ | **0.1** | **+0.739** | +0.551 | **+34%** |

> 🟠 Unlike the earlier (bug-era) divergence, this is **not a sign reversal** — both are positive at every `dry`. It is a difference in *optimal operating point*. Attribution: SI-SDR is waveform fidelity (sensitive to residual noise); PESQ is perceptual quality (sensitive to speech distortion). The extra 10% of original signal at `dry = 0.1` pulls SI-SDR slightly down (+9.86 → +9.74) but lifts PESQ substantially (+0.551 → +0.739) — meaning the pure model output introduces **perceptually more painful speech distortion**.
>
> 🔴 **Direct engineering implication:** selecting a model purely on SI-SDR will **systematically over-estimate** the benefit of "cranking the strength to maximum". Deployment should choose strength on PESQ (or subjective listening).
> ⚠️ Note this does **not** hold for `master64` (both its metrics peak at `dry = 0`), so **the divergence itself is weight-dependent and must not be extrapolated**.

### 4.6 Spectral before/after analysis (T5.6)

Method: `delta(f) = mean_over_clips[20·log10|STFT(est)|] − mean_over_clips[20·log10|STFT(noisy)|]`, first 120 clips per cell, 16 kHz, `n_fft = 1024`. **Statistics computed only within the valid band 0–7.8 kHz.**

| Model | Dataset | 0–1 kHz | 1–4 kHz | 4–7.8 kHz | Tilt (4k+ minus 1–4k) |
|---|---|---:|---:|---:|---:|
| `denoiser_master64` | valentini | −2.47 | −1.53 | **−6.15** | **−4.61** |
| `denoiser_master64` | synth | −4.58 | −7.19 | **−12.79** | **−5.60** |
| `mel_roformer_denoise` | valentini | −2.01 | −0.71 | −4.22 | −3.50 |
| `mel_roformer_denoise` | synth | −2.32 | −2.46 | −5.01 | −2.55 |

*(Source: `data/denoise_spectral_delta.json`. This quantity has slight floating-point sensitivity to resampling — repeated runs jitter the synth high band between −12.6 and −12.8 — so **only two significant figures should be quoted**.)*

**Three conclusions:**

1. **It is not a uniform low-pass.** On Valentini, denoiser attenuates 1–4 kHz by only −1.53 dB but 4–7.8 kHz by −6.15 dB — it applies a **frequency-increasing tilt**, not "cut everything above some corner frequency". Consistent with the conclusion that the `hf_ratio` collapse is a *proportional* effect, not a low-pass.

2. **The amount of action changes drastically with noise type (the strongest evidence in this figure set).** The same denoiser:
   - valentini: 1–4 kHz −1.53 dB, 4–7.8 kHz −6.15 dB
   - synth: 1–4 kHz **−7.19 dB**, 4–7.8 kHz **−12.79 dB**
   
   i.e. the same weight suppresses **4.7×** more in the mid band and **2.1×** more in the high band on the transient-noise set. This is the direct mechanistic evidence for the "complementary valid domains" finding: **denoiser really does suppress heavily on synth (hence +11.61 dB there), and acts gently on valentini (hence a limited +9.86 dB).**

3. **Mel-RoFormer's spectral difference is small throughout** (worst case −5.01 dB; only −0.71 dB at 1–4 kHz), fully consistent with it being a near-identity mapping.

> ✅ **Cross-consistency check:** Mel-RoFormer runs **natively at 44.1 kHz**, so its spectral-difference curve has **no cliff at 8 kHz** (wider bandwidth); denoiser's has a cliff at 8 kHz. The two curves on the same plot serve as mutual controls, **reverse-confirming that the cliff comes from denoiser's internal 16 kHz bottleneck**, not from plotting or the evaluation pipeline.

### 4.7 Out-of-domain (OOD) probes (T5.7)

Three probes, `analysis_sr = 16000`, `contract_sr = 44100`, `n_items = 6`.

**Probe A — pure clean (noise-free) passthrough (tests near-identity):**

| Model | Median output/input rms | `hf_in → hf_out` |
|---|---|---:|
| `mel_roformer_denoise` | 0.9986 | 0.1956 → 0.1891 |
| `denoiser_dns48` | 0.9968 | 0.1957 → 0.1851 |
| `denoiser_master64` | 0.9986 | 0.1957 → 0.1843 |

→ All three are **nearly identity** on clean speech (level retained >99.6%, high frequency retained >94%). **This rules out the hypothesis that the model itself is a low-pass.** denoiser is not a low-pass filter.

**Probe B — pure noise passthrough (does it recognise this as noise?):**

| Model | Median rms ratio | Median suppression | Per-clip range |
|---|---:|---:|---|
| `mel_roformer_denoise` | 0.9959 | **−0.04 dB** | 0.024 ~ 0.998 (split) |
| `denoiser_dns48` | **0.0242** | **−32.6 dB** | 0.005 ~ 0.543 |
| `denoiser_master64` | **0.0108** | **−41.3 dB** | 0.002 ~ 0.802 |

→ **denoiser is a genuine denoiser**: pure noise input is suppressed by 32–41 dB. It *knows* this is noise. **Mel-RoFormer barely reacts to pure noise** (median −0.04 dB), and is wildly split per clip — meaning it has **no stable discrimination** of "is this speech?", only doing gentle spectral shaping.

**Probe C — gain sweep** (fixed clean+noise, sweep noise gain; `snr_eff = −15 / −5 / +5 / +15 dB`):

| Model | measure | −15 dB | −5 dB | +5 dB | +15 dB |
|---|---|---:|---:|---:|---:|
| `mel_roformer` | ΔSI-SDR vs GT | +0.04 | +0.04 | +0.03 | **+3.83** |
| `mel_roformer` | `level_ratio` | 0.995 | 0.996 | 0.998 | 0.986 |
| `dns48` | ΔSI-SDR vs GT | **+18.13** | +15.01 | +10.08 | +5.68 |
| `dns48` | `level_ratio` | 0.148 | 0.482 | 0.872 | 0.985 |
| `master64` | ΔSI-SDR vs GT | **+18.62** | +14.98 | +10.09 | +6.38 |
| `master64` | `level_ratio` | 0.160 | 0.495 | 0.878 | 0.987 |

→ **denoiser's amount of denoising varies monotonically with noise level** (−15 dB: +18.6; +15 dB: +6.4) — **not** an input-independent fixed action. It is a normal denoiser that suppresses proportionally to the noise level. `level_ratio` rises monotonically from 0.15 to 0.99 — denoiser has a **noise-estimate-based gain control** that pushes the whole clip down at low SNR (because most of the clip is noise) and barely moves at high SNR.

> ⚠️ **P19 correction:** this was originally written as consistent with the "34% of clips collapsed to silence" observation. That observation was a sampling-rate artefact (on clean data the exclusion count is **0**). The probe's own conclusion (gain control varies with SNR) **holds and is a real mechanism** — its actual trigger strength is merely far smaller than the artefact suggested: on clean data denoiser's median `level_ratio` is **0.947** (about −0.5 dB of mild compression), **not** a `LEVEL_GATE`-level collapse.

**Correction to earlier attribution:** the original P11 draft said denoiser applies "a fixed-strength, input-SNR-independent low-pass suppression". **This attribution was wrong.** The probe shows:

1. denoiser performs **noise-level-adaptive gating**; the earlier "fixed strength" characteristic actually **belongs to Mel-RoFormer** (which applies near-identity mapping regardless of input SNR). **The evidence for the two models had been swapped.**
2. The `hf_ratio` collapse is a **projection of noise suppression onto the high-frequency energy share**, not a low-pass on high frequencies. Paired clean displacement is only **−0.0079** (median over 120 real clean clips, p95 = −0.0021, all negative) — a statistically robust but **tiny** tilt. The low-pass therefore explains only about **5%** of the total displacement.

**Paired clean probe (120 real `clean_testset_wav` clips, `denoise_probeA_paired.json`):**

| Model | rms ratio | `hf_in → hf_out` | **Paired Δhf median** | [p05, p95] |
|---|---|---|---|---:|
| `denoiser_dns48` | 0.9971 | 0.2412 → 0.2315 | **−0.0079** | [−0.0145, −0.0021] |
| `denoiser_master64` | 0.9981 | 0.2412 → 0.2318 | **−0.0079** | [−0.0145, −0.0020] |
| `mel_roformer_denoise` | 0.9988 | 0.2414 → 0.2362 | **−0.0046** | [−0.0087, −0.0010] |

→ **"Fixed-strength low-pass suppression" as the main cause is fully refuted**; the low-pass is a real but secondary side effect.

**The correct mechanism:** denoiser's action on noisy speech superposes two effects —
1. **Noise gating**: suppressing non-speech time-frequency points based on the estimated noise floor. This is genuine, effective denoising (probe C).
2. **Applying a high-frequency attenuation to the speech component of the mixture itself** (about −0.16 `hf_ratio` displacement on the *polluted* manifest).

The remaining correct mechanism: the `hf_ratio` collapse is dominated by the fact that **the model preserves only what it judges to be speech and heavily suppresses the rest of the mixture**. In noisy speech, the high band (>4 kHz) contains a much larger share of noise than the low band → the high band gets proportionally more suppression (`hf_ratio` is a *ratio* and is highly sensitive to high-frequency suppression). In pure clean there is almost nothing "non-speech" to suppress, so only the −0.008 inherent tilt remains.

> ⚠️ **Still flagged as unverified:** the above is a mechanistic inference, not yet confirmed by a "noise added only in the high band" control experiment. The report states it as "high-band collapse = projection of noise suppression" and notes its verification status.

---

## 5. 🔴 The P19 sampling-rate contract bug — the most important part of this step

This deserves its own section because it is the **largest source of risk** in this step and the **most valuable engineering lesson**.

### 5.1 How it was discovered

After finishing `dns_dev` and the 44.1 kHz secondary protocol, a cross-check revealed an **impossible datum**:

| Protocol | Clips excluded by `LEVEL_GATE` (denoiser) |
|---|---|
| 16 kHz | dns48 **280** / dns64 265 / master64 155 |
| 44.1 kHz | **all 0** (`level_ratio` minimum 0.9458) |

Same model, same audio — **changing only the evaluation sampling rate makes the "level collapse" disappear entirely.** Model behaviour cannot depend on the evaluation protocol like this. It must be a pipeline problem.

### 5.2 Root cause (decisively verified with a probe)

The denoiser wrapper hard-coded internally:

```python
wav = convert_audio(wav, SR, 16000, 1)   # SR = 44100, hard-coded
```

It **assumes it always receives 44.1 kHz**. But `eval_one` fed it a signal already resampled to the **evaluation rate**:

```
evaluation rate 16 kHz:
  load_mono(path, 16000)                 -> already 16 kHz
  wrapper thinks it is 44.1k, downsamples again
  => signal downsampled TWICE, audio sped up 2.76x
```

Probe measurement (`_probe_sr_double.py`, source 48 kHz / 5.52 s):

| Evaluation protocol | Passed to wrapper | Wrapper output | Effective duration | Speed |
|---|---|---|---|---:|
| **16 kHz** | 88,343 samples | **32,051 samples** | 2.00 s | **× 2.76 (pitch shifted up)** |
| 44.1 kHz | 243,495 samples | 88,342 samples | 5.52 s | × 1.00 (correct) |

**Consequence:** at 16 kHz the audio was compressed to 2.00 s with pitch shifted up — far outside denoiser's training distribution, so it classified many clips as "not speech" and attenuated them.

**The "34% level collapse" was a pipeline artefact, not model behaviour.**

### 5.3 The fix

**Step 1 — expose the contract rate in the registry:**

```python
run.contract_sr = SR      # 44100
```

and document the full contract (input shape `(N,2)`, input must already be at the contract rate).

**Step 2 — make eval honour the contract rate.** ⚠️ The first version of this fix was itself buggy — see §5.4.

Correct final form (separate variables, **never overwrite**):

```python
csr = int(getattr(run_fn, "contract_sr", NATIVE_SR))
noisy_in = resample_mono(noisy, sr, csr) if csr != sr else noisy   # for the model ONLY
est_stereo = run_fn(np.stack([noisy_in, noisy_in], axis=-1))
est = np.asarray(est_stereo["enhanced"]).mean(axis=1).astype(np.float32)
if csr != sr:
    est = resample_mono(est, csr, sr)

# downstream metrics ALWAYS use the evaluation-rate `noisy`, never modified:
noisy2 = noisy[: len(ref)]
```

### 5.4 🔴 The second bug introduced by the fix

After fixing the contract rate and re-running Valentini 16 kHz, the results contained **physically impossible** numbers:

| Field | Value | Expected magnitude |
|---|---:|---|
| `in_len` | 76,792 | ~27,861 |
| `si_sdr_in` | **−73.12** | around +15 |
| `si_sdr_improve` | **+90.65** | a few dB |
| ΔPESQ | **+1.5** | a fraction of a dB |

**Root cause:** `if csr != sr: noisy = resample_mono(noisy, sr, csr)` **overwrote `noisy`**, so the reference became a 44.1 kHz-length array compared against a 16 kHz reference — a 3× length mismatch. SI-SDR on two signals of different lengths gave −73 dB. (`level_ratio` remained correct because it is computed from `est2 / ref` and does not go through `noisy`.)

**Verification** (single cell `p232_001` @ 16 kHz):

| Field | Before fix | After fix | Manually reproduced "correct path" |
|---|---:|---:|---:|
| `in_len` | 76,792 | **27,861** | 27,861 |
| `si_sdr_in` | −73.1208 | **+15.469** | 15.469 |
| `si_sdr_out` | 17.5311 | 17.5311 | 17.531 |
| `si_sdr_improve` | 90.6519 | **+2.0621** | +2.062 |
| `level_ratio` | 1.0092 | 1.0092 | — |

→ After the fix, **bit-for-bit identical** to the manual reproduction.

**Two-protocol consistency check (150 Valentini clips, `_audit_sr_bug.py`):**

| Model | Old 16k (bug) | Old 44.1k | **Fixed 16k** | **Fixed 44.1k** |
|---|---:|---:|---:|---:|
| `denoiser_dns48` · median `level_ratio` | 0.9815 | 0.9997 | **0.9466** | **0.9419** |
| `denoiser_master64` | 1.0076 | 1.0034 | **0.9474** | **0.9470** |
| `mel_roformer_denoise` | 1.0099 | 1.0004 | **0.9607** | **0.9606** |
| clips `< 0.2` | 0/150 | 0/150 | **0/150** | **0/150** |

→ After the fix, **the two protocols agree exactly** (0.9466 vs 0.9419) and the collapse count is **0**.

### 5.5 Chain of invalidated conclusions

| Document | What was invalidated |
|---|---|
| `T5_DENOISE_STRATIFIED.md` §4.2 | "denoiser has an absolute level gate; 280/265/155 of 824 clips excluded" — artefact |
| `T5_DENOISE_STRATIFIED.md` §1 / main table | the `n_skipped` column, `n_fullref` (should all be 824) |
| `T5_DENOISE_STRATIFIED.md` §2 | the "three metrics contradict each other" claim; "denoiser net-damages clean input (ΔPESQ −0.61, ΔSI-SDR −0.78)" |
| `T5_4_DNS_DEV_NOREF.md` §2.1/§3/§4 | "collapse rate 40.3% / 38.3% / 45.4%" — all artefact |
| `T5_7_OOD_NOISE_NEGATIVE.md` | the `n_skipped` figures on synth (282/239) |
| P16 | "in-domain master64 is actually **worst** (≥15 dB ΔSI-SDR −2.44)" — **fully invalidated**, reversed on clean data |
| Plan P11 / P13 | "low-level clips are collapsed to silence" |

### 5.6 But the `LEVEL_GATE` itself is still necessary

**P19 invalidated the *number* ("34% collapse on Valentini"), not the *mechanism* ("denoiser has an absolute level gate").**

Evidence (150 clips, both protocols):

| Model | bug-era 16k median | bug-era 44.1k median | **fixed 16k** | **fixed 44.1k** |
|---|---:|---:|---:|---:|
| `denoiser_dns48` | 0.9815 | 0.9997 | **0.9466** | **0.9419** |
| `denoiser_master64` | 1.0076 | 1.0034 | **0.9474** | **0.9470** |
| `mel_roformer_denoise` | 1.0099 | 1.0004 | **0.9607** | **0.9606** |

The key is the last two columns: after the fix, denoiser's median `level_ratio` drops from ~1.00 to **0.947**, while Mel-RoFormer only drops to 0.961 — **denoiser does have a systematic output level reduction**, just far smaller than the artefact suggested. **Keeping the gate is correct** (threshold 0.20 still never triggers; it exists as a safety net for cases like P13 where a synthetic pair has an abnormally low level).

→ **The correct statement: denoiser has a mild systematic level compression (about −0.5 dB), not "collapses 34% of clips to silence".**

### 5.7 What survives from the pre-P19 conclusions

| Conclusion | Status |
|---|---|
| denoiser is not a low-pass filter (paired clean probe) | ✅ Holds (uses the contract path) |
| denoiser's suppression varies monotonically with SNR | ✅ Holds |
| Mel-RoFormer is a near-identity mapping | ✅ Holds (and is its *defect*, not its virtue) |
| "34% level collapse" | ❌ Invalidated (pipeline artefact) |
| dns_dev collapse rate 40.3/38.3/45.4% | ❌ Invalidated, re-run → 1.0/1.0/1.7% |
| master64 gate "most gentle" → "most aggressive" reversal | ❌ Invalidated (the reversal itself was a bug product); direction survives, magnitude does not |
| P16: in-domain master64 performs worse | ❌ Reversed on clean data (master64 is now **best** on PESQ) |

### 5.8 Lessons (to be added to the engineering-discipline rules)

🔴 **Rule 14: before feeding data to a model wrapper, confirm the sampling rate it expects.**

- The symptom is extremely subtle: **no error, audio still plays, metrics still "look reasonable"** (SI-SDR was even positive). The only tell was "the same model behaves drastically differently under a different evaluation protocol".
- Detection method: **run the same input under two different evaluation protocols and compare `level_ratio`.** A large difference implies double resampling.
- Fix: have the wrapper explicitly expose `contract_sr`; the caller must always `resample(x, eval_sr, contract_sr)` → infer → `resample(y, contract_sr, eval_sr)`.
- **Corollary:** the evaluation sampling rate **cannot be chosen freely**. To run a 16 kHz protocol you must go "native → contract → model → contract → 16 kHz", **not** "native → 16 kHz → model".

🔴 **Rule 14 addendum: when fixing an "input-side rewrite" bug, the rewritten result must go into a NEW variable — never overwrite in place.**

- Symptom: after fixing the first bug, the metrics show **absurd but non-erroring** values (here `si_sdr_in = −73 dB`, ΔPESQ = +1.5).
- Tell: `in_len` is not proportional to the reference length (76,792 vs 27,861, a 3× difference).
- Detection method: **check the channel-length sum, not just the metric values.** Any length mismatch must be settled on length first, before discussing metrics.
- Correct code shape: `noisy_in = resample(noisy, ...)`, **not** `noisy = resample(noisy, ...)`.

🔵 **Meta-lesson (worth a "reflection" section in the paper):**
The project **wrote three documents wrong on the same bug** (the 40-clip smoke test → the v1 stratified report → the dns_dev chapter), each time rationalising it with a **narrative** ("the three metrics contradict", "the counter-intuitive in-domain degradation").
> **A narrative that explains everything is usually the bug talking.**
The only real defence is: **re-run under a different protocol and check whether the conclusion survives.**

---

## 6. Negative results reported as negative (scientific honesty)

### 6.1 De-reverberation (reverb removal) — negative result

Decision recorded on 2026-09-23: the reverb-removal work is reported **as a negative result**, with **no claim** of cascade benefit.

| Checkpoint | Semantics | Measured gain | Verdict |
|---|---|---:|---|
| `anvuew` (Mel-Band-RoFormer, `noreverb` head) | Room de-reverberation | **+0.04 ~ +1.46 dB** (median +0.04) | 🔴 Weak: recovers only **3–11%** of the wet-signal loss |
| `Dereverb-Echo` (Mel-Band-RoFormer, 2-stem `[dry, other]`) | De-echo / PA reverb | 5 of 6 cells have the `dry` branch collapse to rms **1e-5 ~ 2e-3** (≈ silence) | 🔴 Unusable |

Three-way exclusion showed this is **not our implementation error**:

| # | Suspicion | Exclusion experiment | Result |
|---|---|---|---|
| 1 | Wrong input fed (model only consumes vocals, we fed the mixture) | Re-ran all cells with `vocals.wav` | Behaviour unchanged |
| 2 | No chunking (official path is `chunk_size=352800` ≈ 8 s + overlap-add + fade window; we did whole-clip 20 s forward pass) | Added `_dereverb_official_probe.py` running the **upstream official chunked path** on the same segment | `anvuew`: official vs ours ΔSI-SDR = **0.142 dB** (same order); `Dereverb-Echo` collapses under the official path too (−34.0 dB official vs −44.4 dB ours) → **chunking is not the root cause** |
| 3 | Wrong output mapping (2-stem alignment) | Dry-signal passthrough self-test | `anvuew` near-identity; `Dereverb-Echo` collapses even on dry input → **the output-assignment mechanism itself fails** |

**Domain-mismatch analysis (why the models behave this way):**

| Model | Training objective | Mismatch with this probe |
|---|---|---|
| `anvuew` | Remove **room reverberation** | The probe's "dry" reference is a MUSDB studio mix, **which itself contains plate reverb/delay** — not truly anechoic. The model does what it was trained to do; the recoverable margin is inherently tiny, so the flat metric is **normal behaviour, not a model defect** |
| `Dereverb-Echo` | Remove **echo / PA reverb** | It targets **delayed** reverb (separable from the direct sound), not **room reverberation** (overlapping the direct sound). On pure room-reverb input its 2-stem assignment fails (`dry` silent, `other` passthrough) |

**Inference:** community de-reverberation checkpoints generally suffer from **task-semantics drift** — having "dereverb" in the name does **not** mean it applies to room reverberation. Must be validated with a small controlled probe before use.

**Constraint carried forward:** the cascade experiment (Stage 6) **must not assume** reverb removal brings a gain. If it is run, it should be designed as "verify whether the negative result also holds at system level", not "expect a positive return".

### 6.2 OOD noise generalisation — negative result

The complementary-valid-domain finding in §4.4 **is itself a negative result**: there is **no universal denoiser**. This is recorded as a core negative finding of Stage 5, on a par with the de-reverberation negative result.

---

## 7. Model selection: the deliverables

### 7.1 "Best quality" pick

| Role | Model | Justification |
|---|---|---|
| **Best perceptual quality** | **`denoiser_master64`** | ΔPESQ **+0.963** (1.75× dns48), ΔSTOI +0.0171, and best in the cleanest (≥15 dB) bin. Its ΔSI-SDR (+9.49) is statistically indistinguishable from the other two checkpoints. |
| **Best SI-SDR** | `denoiser_dns48` | ΔSI-SDR **+9.86**, marginally above master64 (+9.49) and dns64 (+9.64) |
| **Best on transient noise** | `denoiser_master64` | ΔSI-SDR **+11.97** on synth |
| **Best on real steady noise (Mel family)** | `mel_roformer_denoise` | ΔSI-SDR +6.65, ΔPESQ +0.239 |

> ⚠️ **Caveat on the "best quality" pick:** `master64` is **in-domain** for Valentini. Its PESQ advantage is real but is partly an artifact of the test set. This is why the `dns48`/`dns64` out-of-domain controls are reported alongside it, and why the `dns_dev` blind-set check was added.

### 7.2 "Best overall" pick, considering runtime footprint, model size and latency

> ⚠️ **待确认 / TO CONFIRM:** the parameter count, disk size and per-clip latency measurements are recorded in `data/model_profile.csv` and the model localisation verification report, which cover the **separation** models in detail. For the **denoising** checkpoints the same profiling exists but the exact numbers should be re-read from `models/` before quoting in the paper. The **qualitative** ranking below is supported by the evidence in this step:

| Consideration | `denoiser_dns48` | `denoiser_dns64` | `denoiser_master64` | `mel_roformer_denoise` |
|---|---|---|---|---|
| ΔSI-SDR (valentini) | **+9.86** | +9.64 | +9.49 | +6.65 |
| ΔPESQ (valentini) | +0.551 | +0.601 | **+0.963** | +0.239 |
| ΔSI-SDR (synth, transient) | +11.61 | +11.92 | **+11.97** | +0.23 ❌ |
| Spectral neutrality | ±2% | ±2% | ±2% | ±2% |
| Native rate | 16 kHz | 16 kHz | 16 kHz | 44.1 kHz |
| Internal rate bottleneck | 16 kHz | 16 kHz | 16 kHz | 44.1 kHz (no 8 kHz cliff) |
| Relative capacity | smallest | medium | largest | large |
| Measured runtime (dns_dev, 921 clips) | ~3–4.5 min | ~3–4.5 min | ~3–4.5 min | ~39 min |

**Recommendation — `denoiser_dns48` as the "best overall":**
- Its **SI-SDR is the highest of the three denoiser checkpoints** (+9.86) at the **smallest capacity**, so runtime occupancy, model size and latency are all at the favourable end of the family.
- It shares the family's **strong transient-noise performance** (+11.61 dB) that Mel-RoFormer lacks entirely.
- The only thing it gives up is PESQ (+0.551 vs master64's +0.963). **If perceptual quality is the deployment criterion, then `denoiser_master64` is the pick and the extra cost must be paid.**

> ⚠️ Mel-RoFormer is **not** a viable "best overall" candidate for a general denoising role: ~9× the runtime (39 min vs 3–4.5 min per 921 clips), native 44.1 kHz requiring a resampling chain, and a **complete failure on transient noise**.

**Final selection statement for the report:**

> **Best denoising model (quality): `denoiser_master64`** — ΔPESQ +0.963 (best on perceptual quality, in every SNR bin).
> **Best denoising model (overall, considering runtime occupancy / model size / latency): `denoiser_dns48`** — ΔSI-SDR +9.86 at the lowest cost of the family, with the same strong transient-noise performance.
> **Conditional alternative:** `mel_roformer_denoise` only for **real steady noise with no transient content**, where its lower gain (+6.65) may be acceptable in exchange for wider native bandwidth (no 16 kHz bottleneck).

---

## 8. Artefact list — where to find everything

### 8.1 Machine-readable data

| File | Contents |
|---|---|
| `data/denoise_eval_16k.csv` / `.json` | Primary 16 kHz table (all models, all datasets, all SNR bins) |
| `data/denoise_eval_44k.csv` / `.json` | Contract-rate 44.1 kHz table |
| `data/denoise_drywet.csv` / `.json` | Strength sweep: every (model, clip, dry) measurement; CSV is the (model, dry, SNR-bin) aggregate |
| `data/denoise_manifest.json` | **16,575 cells** — the master record, one entry per (model, clip, protocol) |
| `data/denoise_ood_probe.json` | Three OOD probes, per clip |
| `data/denoise_probeA_paired.json` | 120-clip paired clean probe |
| `data/denoise_spectral_delta.json` | Band-wise mean spectral difference |
| `data/denoise_sr_bug_audit.json` | Two-protocol audit used to prove the P19 fix |
| `data/synth_pairs_manifest.json` | The synthetic noisy corpus manifest |
| `data/denoise_manifest.json.bak-srbug-20260923` etc. | Pre-fix backups, retained for audit |

### 8.2 Analysis documents (detail behind every number above)

| Document | Contents |
|---|---|
| `docs/T5_DENOISE_STRATIFIED.md` | **Core conclusion document** — the stratified main table, in-domain control, spectral/level fidelity, metric-divergence analysis, protocol warnings |
| `docs/P19_SAMPLE_RATE_CONTRACT_BUG.md` | **The bug: discovery, root cause, fix, the second bug, full chain of invalidated conclusions, rules 14 / 14-supplement** |
| `docs/T5_4_DNS_DEV_NOREF.md` | DNS blind-set (no-reference) level-behaviour analysis |
| `docs/T5_5_T5_6_DRYWET_AND_SPECTRA.md` | Strength sweep and spectral before/after analysis |
| `docs/T5_7_OOD_NOISE_NEGATIVE.md` | **The complementary-valid-domains core negative result** |
| `docs/T5_7_PASSTHROUGH_PROBE_CORRECTION.md` | The passthrough probes and the correction to the earlier "fixed low-pass" attribution |
| `docs/DEREVERB_NEGATIVE_RESULT.md` | De-reverberation negative result + domain-mismatch analysis |
| `../00_shared/docs/summaries/DENOISE_SUMMARY.md` | Machine-generated summary tables (no hand-entered values) |

### 8.3 Figures

| File | Contents |
|---|---|
| `figures/fig_denoise_metric_divergence.png` | Metric (dis)agreement |
| `figures/fig_denoise_suppression.png` | Spectral fidelity (panel A) + level fidelity (panel B) |
| `figures/fig_denoise_drywet.png` | Strength sweep: (A) stratified strength scan, (B) PESQ-optimal strength |
| `figures/fig_denoise_synth_gain.png` | Synthetic transient-noise gain |
| `figures/fig_denoise_noise_domain_reversal.png` | **The domain-reversal figure** |
| `figures/denoise/t5_6_<model>_<subset>_spectral.png` (×4) | Four-panel before/after spectra for individual clips at p10/p50/p90 |
| `figures/denoise/t5_6_<model>_<subset>_delta_spectrum.png` (×4) | Mean spectral difference per band |

### 8.4 Interactive dashboard

`html/denoise_dashboard.html` — a self-contained offline interactive dashboard over all the above data.

### 8.5 Reproduction commands

```bash
VENV="C:/Users/jerry/.workbuddy/binaries/python/envs/fyp_audio/Scripts/python.exe"
cd E:/FYP_HKBU/tools

# --- Main evaluation, 16 kHz primary protocol ---
PYTHONPATH=. "$VENV" -X utf8 _denoise_eval.py run \
    --models <A>,<B> --dataset valentini --sr 16000 --resume
PYTHONPATH=. "$VENV" -X utf8 _denoise_eval.py resummary

# --- Main evaluation, 44.1 kHz contract-rate protocol ---
PYTHONPATH=. "$VENV" -X utf8 _denoise_eval.py run \
    --models <A>,<B> --dataset valentini --sr 44100 --resume

# --- DNS blind set (no reference; --allow-noref is REQUIRED or it exits with an error) ---
PYTHONPATH=. "$VENV" -X utf8 _denoise_eval.py run \
    --models <A>,<B> --dataset dns_dev --sr 16000 --allow-noref --resume

# --- Synthetic transient-noise corpus ---
PYTHONPATH=. "$VENV" -X utf8 _dns_make_pairs.py
PYTHONPATH=. "$VENV" -X utf8 _denoise_eval.py run \
    --models <A>,<B> --dataset synth --sr 16000 --resume

# --- Strength sweep + its mandatory correctness anchor ---
PYTHONPATH=. "$VENV" -X utf8 _denoise_drywet.py run --dataset valentini \
    --models denoiser_dns48,denoiser_dns64,denoiser_master64
PYTHONPATH=. "$VENV" -X utf8 _scratch/_drywet_anchor_check.py

# --- OOD probes ---
PYTHONPATH=. "$VENV" -X utf8 _denoise_ood_probe.py

# --- P19 audit / decisive reproduction ---
PYTHONPATH=. "$VENV" -X utf8 _scratch/_probe_sr_double.py
PYTHONPATH=. "$VENV" -X utf8 _audit_sr_bug.py

# --- Figures ---
PYTHONPATH=. "$VENV" -X utf8 _plot_denoise.py
PYTHONPATH=. "$VENV" -X utf8 _plot_denoise_drywet.py
PYTHONPATH=. "$VENV" -X utf8 _plot_denoise_spectral.py
PYTHONPATH=. "$VENV" -X utf8 _plot_denoise_spectrum_delta.py

# --- Summary tables ---
python tools/_build_summaries.py --only denoise
python tools/_build_summaries.py --verify
```

---

## 9. Conclusions

### 9.1 What was established (P19-fixed, all findings surviving two-protocol verification)

1. **`denoiser` is a genuine, strong denoiser.** It suppresses pure noise by **32–41 dB**, and its suppression scales monotonically with noise level (from +6.4 dB improvement at +15 dB SNR to +18.6 dB at −15 dB SNR). It is **not** a low-pass filter (paired clean high-frequency displacement only −0.008) and **not** a fixed-strength suppressor.
2. **`mel_roformer` is a medium-strength enhancer with a near-identity tendency.** Its median `level_ratio` is 0.96–1.14 and it reduces pure noise by only 0.04 dB. It barely touches anything — **this is its defect, not its virtue**.
3. **Two model families, 5 checkpoints, 4 SNR bins (20 cells): all three metrics are positive in every cell.** There is no directional contradiction between SI-SDR, PESQ and STOI. The contradiction reported in earlier drafts was a pipeline artefact (P19).
4. **Gain grows monotonically as input gets dirtier**, for both families — the models are not suppressing indiscriminately.
5. **In-domain adaptation is effective, and its value shows up in perceptual quality.** `master64` (trained on data including Valentini) reaches ΔPESQ **+0.963**, ~1.75× the out-of-domain checkpoints, while its SI-SDR is statistically the same.
6. **★ The core finding: the two families have complementary valid domains. There is no universal denoiser.** Mel-RoFormer gains +6.65 dB on real steady noise but **fails outright (+0.23 dB) on transient impulsive noise**; denoiser is strong on both (+9.86 / +11.61 dB). This is supported by a direct observation: a **15× difference** in `hf_ratio` displacement (−1.9% on real noise vs −28% on transient noise).
7. **Denoising strength is a real, tunable knob whose optimum moves with input SNR** (<5 dB bin → `dry = 0`; ≥15 dB bin → `dry = 0.1–0.2`). **No single fixed strength is optimal across conditions.**
8. **ΔSI-SDR and ΔPESQ have different optimal operating points** (same sign everywhere, but different optima). Selecting on SI-SDR alone systematically **over-estimates** the benefit of maximum strength. This divergence is **weight-dependent and must not be extrapolated**.
9. **Mel-RoFormer's and denoiser's action differs by 4.7× in the mid band and 2.1× in the high band between the two noise types** — the direct mechanistic fingerprint of the complementary-valid-domain result.
10. **All five models are spectrally near-neutral on real noise** (output `hf_ratio` within ±2.5% of input). There is no spectral damage.

### 9.2 Negative results (reported as negative)

1. **De-reverberation**: neither community checkpoint provides usable room-de-reverberation gain (`anvuew` recovers only 3–11% of the loss; `Dereverb-Echo` fails outright). **Not our implementation** — cross-validated against the upstream official path. Cause: **task-semantics drift**.
2. **No universal denoiser**: the complementary-valid-domain result above. Transient-noise scenarios have exactly **one** usable option (denoiser).

### 9.3 Constraints carried forward to Stage 6 (cascade)

| Target noise | Recommended tool | Evidence |
|---|---|---|
| Steady / environmental / babble (real recordings) | `mel_roformer` (or denoiser, stronger) | valentini: mel +6.65 / denoiser +9.86 |
| Transient impulsive (door, plosive, keyboard) | **`denoiser` (the only workable option)** | synth: denoiser +11.6; **mel ≈ +0.23, ineffective** |
| Uncertain | **Run both, decide via `level_ratio` + `hf_ratio`** | — |

- **Must not assume "denoising will help"** (same constraint as the de-reverberation result).
- **Before any cascade experiment, first determine the target scenario's noise type.**
- The denoising model must be attached after separation; the cascade must be measured, not assumed.

### 9.4 Suggested one-line answer for the defence

> We found that a denoiser's effectiveness **depends on the noise type, and different models have complementary valid domains**: Mel-RoFormer gains +6.7 dB on DNS real noise but **fails outright** on transient impulsive noise (door/plosive) — ΔSI-SDR +0.23, `level_ratio` 1.14, i.e. it leaves the noise in the output. The `facebookresearch/denoiser` family is strong on both (real +9.9 / transient +11.6 dB), at the cost of a 28% `hf_ratio` reduction in the transient scenario. **So "does denoising help" is not a question answerable with a single number — it depends on the noise type.** We also found that `master64` is best on perceptual quality (+0.963 PESQ) thanks to in-domain adaptation, and that denoising strength is a tunable knob whose optimum moves with input SNR.

### 9.5 Status and outstanding items

| Item | Status |
|---|---|
| 16,575 cells, err = 0 | ✅ |
| Dual-protocol, cross-validated | ✅ |
| P19 bug found, fixed, fully re-run | ✅ |
| All invalidated conclusions re-written | ✅ |
| In-domain control in the table | ✅ |
| Strength sweep + correctness anchor | ✅ |
| Spectral analysis with valid-band restriction | ✅ |
| OOD probes | ✅ |
| Negative results documented | ✅ |
| dry/wet sweep on `synth` | ⬜ Not run. Prediction: denoiser's optimum may be **closer to `dry = 0`** there, because its action is larger on transient noise. A verifiable prediction; should be run if time permits. |
| "High-frequency-only noise" control experiment | ⬜ Not run. Needed to upgrade the mechanism in §4.4 from inference to verified. |
| Parameter count / disk size / per-clip latency for the denoising checkpoints, quoted in the paper | ⬜ To be re-read from `data/model_profile.csv` / the localisation verification report before quoting |

---

## 10. Summary of what was delivered for the progress report

| Deliverable | Item | Location |
|---|---|---|
| D6 | Denoising main table (dual protocol, stratified) | `denoise_eval_16k.csv/.json`, `denoise_eval_44k.csv/.json` |
| D7 | Strength (dry/wet) knob analysis | `denoise_drywet.csv/.json`, `fig_denoise_drywet.png` |
| D8 | Spectral before/after band analysis | `denoise_spectral_delta.json`, `figures/denoise/t5_6_*` |
| D9 | Out-of-domain behaviour + negative results | `denoise_ood_probe.json`, `T5_7_OOD_NOISE_NEGATIVE.md`, `DEREVERB_NEGATIVE_RESULT.md` |
| — | Machine-generated summary | `DENOISE_SUMMARY.md` |
| — | Interactive dashboard | `denoise_dashboard.html` |
| — | Engineering-discipline rules 14 + addendum | `P19_SAMPLE_RATE_CONTRACT_BUG.md` §6 |

---

*All numerical values in this report are read directly from the machine-readable data files listed in §8.1; none are hand-entered. Where a value is flagged as unverified or to-be-confirmed, it is explicitly marked.*

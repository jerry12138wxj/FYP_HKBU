# 盲跑产物审计表（机读版同源）

> 本文件由 `audit_blind_runs.csv` 直接生成，数字零手抄。生成时间 2026-10-30。

> 判定：A 可用 / B 部分可用（需补证）/ C 无用 / D 有污染风险

## 汇总

| 判定 | 份数 | 占比 |
|---|---|---|
| A | 2 | 5.0% |
| B | 27 | 67.5% |
| C | 9 | 22.5% |
| D | 2 | 5.0% |
| **合计** | **40** | 100% |

产物总量：**42.1 GB**（按目录去重统计，含重复计数）


## D 类：有污染风险（必须重跑）

| id | path | model | 证据 | 建议动作 |
|---|---|---|---|---|
| S12 | `03_outputs/DPRNN` | DPRNN | 🔴 验证集泄漏：VAL_CLIPS 三首 subset='train'，与训练集同为 MUSDB train 100 首；best.pt 由该验证集选出 → 模型选择污染。证据：train_dprnn_musdb.py L78-82；日志 L4 '训练集: 100 首歌'；验证 best=+2.745 dB 而测试 -1.72 dB（差 4.5 dB）。另有削波：抽样 20 flac peak=1.0000、clipped 0.0168% | 重跑（改按歌曲划分 + 独立验证集） |
| T01 | `01_models/_weights/dprnn_musdb` | DPRNN | checkpoint 元数据完整(step31700/best2.745/cfg/targets/sr/val)，last.pt 含 opt；但 best 由 train 子集验证选出 → 模型选择污染；JSON total_min=3.0 与日志 250.7 min 矛盾 | 重跑（修划分 + 修元数据） |

## C 类：无用（建议作废）

| id | path | model | 证据 | 建议动作 |
|---|---|---|---|---|
| S13 | `03_outputs/RPCA` | RPCA | 🔴 目录存在但 find 计数 0 文件（0 MB）。MODEL_REGISTRY 标 ✅ 可运行，与磁盘不符。稀疏分量无 stem 归属，注册表只报区间 1.8~3.5 dB | 重跑（或标为不产出 stem 的解析基线） |
| D01 | `03_outputs/denoiser-dns48` | denoiser-dns48 | 目录仅 1 个 wav(112 KB)，是单条冒烟产物，不是评测输出；真正评测在 04_reports/02_denoising/data/denoise_eval_*.csv | 作废（保留少量样音） |
| D02 | `03_outputs/denoiser-dns64` | denoiser-dns64 | 目录仅 1 个 wav(112 KB)，是单条冒烟产物，不是评测输出；真正评测在 04_reports/02_denoising/data/denoise_eval_*.csv | 作废（保留少量样音） |
| D03 | `03_outputs/denoiser-master64` | denoiser-master64 | 目录仅 1 个 wav(112 KB)，是单条冒烟产物，不是评测输出；真正评测在 04_reports/02_denoising/data/denoise_eval_*.csv | 作废（保留少量样音） |
| D04 | `03_outputs/Mel-RoFormer-Denoise` | Mel-RoFormer-Denoise | 仅 1-2 个 wav（600 KB-1.2 MB），是单条抽查；非全量评测。mel 两变体(aufr33/aggr)结果差异极大(+0.96 vs +21.17)，不能混报 | 作废（评测走另一路径） |
| D05 | `03_outputs/Mel-RoFormer-Dereverb` | Mel-RoFormer-Dereverb | 仅 1-2 个 wav（600 KB-1.2 MB），是单条抽查；非全量评测。mel 两变体(aufr33/aggr)结果差异极大(+0.96 vs +21.17)，不能混报 | 作废（评测走另一路径） |
| D06 | `03_outputs/Mel-RoFormer-Dereverb-Echo` | Mel-RoFormer-Dereverb-Echo | 仅 1-2 个 wav（600 KB-1.2 MB），是单条抽查；非全量评测。mel 两变体(aufr33/aggr)结果差异极大(+0.96 vs +21.17)，不能混报 | 作废（评测走另一路径） |
| C04 | `03_outputs/_eval_test` | 冒烟评测 | 冒烟测试残留，样本数极小，不能作为结果引用 | 作废 |
| X03 | `03_outputs/_wiener_pkg` | Wiener 打包 | 8 KB 空壳目录，无音频产物 | 作废 |

## A 类：可用

| id | path | model | 证据 | 建议动作 |
|---|---|---|---|---|
| X04 | `03_outputs/rerun_20261030_1700` | demucs+bsroformer_l12 | ✅ 全项目唯一有完整 meta 的产物：command/python3.13.14/torch2.14.0+cu126/cuda12.6/git commit 1107b16/git_dirty=111/时间戳齐全 | 保留（作为可追溯范式模板） |
| M05 | `04_reports/00_shared/data/model_analysis/model_profile.csv` | 22 模型 | ✅ 22 模型齐全，含 params_M/rtf/peak_vram_infer_mb/native_sr/native_ch，可直接作为训练配置卡依据 | 保留 |

## B 类：部分可用（需补证）

| id | path | model | 证据 | 建议动作 |
|---|---|---|---|---|
| S01 | `03_outputs/Demucs` | Demucs | 音频有效(246.7s/44.1k/2ch/rms0.083)；无 run manifest、无命令行、无日志绑定；仅靠 MODEL_REGISTRY 表格引用，无法逐条追溯；200 flac, 50曲x4stem | 补证后保留（补 run manifest） |
| S02 | `03_outputs/MDX-Net` | MDX-Net | 音频有效(179.6s/44.1k/rms0.069)；无 manifest/命令；200 flac | 补证后保留（补 run manifest） |
| S03 | `03_outputs/Conv-TasNet` | Conv-TasNet | 音频有效(212.3s/44.1k/rms0.063)；无 manifest/命令；200 flac | 补证后保留（补 run manifest） |
| S04 | `03_outputs/MMDenseLSTM` | MMDenseLSTM | 音频存在；无 manifest/命令；权重来源为 paper 版 MUSDB18；200 flac | 补证后保留（补 run manifest） |
| S05 | `03_outputs/Open-Unmix` | Open-Unmix | 音频存在；umxhq 权重许可未声明(README 只对 umxl 声明 CC BY-NC-SA)；200 flac | 补证后保留（补 run manifest） |
| S06 | `03_outputs/BS-RoFormer-L12` | BS-RoFormer-L12 | 单目标模型(vocals only)，不能与四轨模型均值直接比；无 run manifest；200 flac | 补证后保留（补 run manifest） |
| S07 | `03_outputs/BS-RoFormer-L6` | BS-RoFormer-L6 | 🔴 语义陷阱：yaml 写 target=other，实测输出 mixture-drums-bass(vocals+other)，直接与纯 other 比会误判失效；200 flac | 补证后保留（补 run manifest） |
| S08 | `03_outputs/BSRNN-opt` | BSRNN-opt | 仅 50 flac(单轨输出)，非 200；四 ckpt 按位置对齐，顺序错会静默互换；50 flac | 补证后保留（补 run manifest） |
| S09 | `03_outputs/BSRNN-large` | BSRNN-large | 仅 50 flac；与 opt 变体需分开报；50 flac | 补证后保留（补 run manifest） |
| S10 | `03_outputs/BSRNN-SIMO` | BSRNN-SIMO | 四轨 SIMO，官方 P1 推荐；无 run manifest；200 flac | 补证后保留（补 run manifest） |
| S11 | `03_outputs/Oracle-IRM` | Oracle-IRM | 音频有效；oracle 是理论上界，不是模型，禁止进入模型排名；200 flac | 补证后保留（补 run manifest） |
| S14 | `03_outputs/mdx_q` | MDX-Net-mdx_q | 12 MB，非全量；量化版仅作参考（属 demucs mdx 另一权重族） | 作废或补全量 |
| S15 | `03_outputs/mdx_extra_q` | MDX-Net-mdx_extra_q | 13 MB，非全量；量化损失 -0.59 dB 有记录 | 补证后保留 |
| D07 | `03_outputs/_valentini_denoise` | denoiser+mel 全家桶 | 🔴 采样率不统一：抽样见 denoiser_dns64/p232_292.wav=16kHz/1ch，mel_roformer_dereverb/p257_153.wav=44.1kHz/2ch。跨模型不能直接横比。mtime 2026-10-13 00:31-00:49，无 manifest、无命令 | 补证后保留（按模型分目录已隔离，可逐模型用） |
| D08 | `03_outputs/_denoise_ab` | A/B 试听 | 试听用途，非评测；无 manifest | 保留（非指标用途） |
| D09 | `03_outputs/_denoise_live` | 实时服务 | 本地三页服务的实时输出，非评测产物 | 保留 |
| C01 | `03_outputs/_cascade` | 级联 4x4 | 🔴 小样本：4 模型 x 4 SNR = 16 格，非全量；负结果为主（40/48 前置格为负）；已用 _cascade_regate.py 重判 680/680 PASS | 补证后保留（标注 n=16） |
| C02 | `03_outputs/_cascade_live` | 级联试听 | 试听产物 | 保留（非指标） |
| C03 | `03_outputs/_eval` | 级联评测图 | 图与 json 齐全，但 16200 png 是可视化(每格 1 png + 1 done)，非指标源；36 个目录=x 组合 | 补证后保留 |
| C05 | `03_outputs/_reverb` | 混响/回声实验 | 音频有效(20.00s/44.1k/2ch)；无 run manifest；结论见 STAGE4_SUMMARY | 补证后保留 |
| X01 | `03_outputs/TableSample_Audio` | 演示样音包 | 🔴 manifest 只剩 1 条，但有 25 个目录/933 wav —— 清单与磁盘严重不匹配（933 wav 对应几百条记录，manifest 只有 1 条） | 补证后保留（必须重建 manifest） |
| X02 | `03_outputs/_sep_live` | 逐模型试听服务 | 服务缓存 | 保留（非指标） |
| T02 | `04_reports/01_separation/data/dprnn_training.json` | DPRNN | 🔴 total_min=3.0 但日志显示 250.7 min（最后一轮 --minutes 3，续跑 14.5h）；batch 字段=8 而日志启动行 batch=4（元数据被后续轮次覆盖） | 补证后保留（修元数据） |
| M01 | `04_reports/01_separation/data/comparison/comparison_results.csv` | 多模型 | 只有 100 行（抽样，非 50曲x4stem 全量）；delta_SDR 以 mixture 为基线，口径正确 | 补证后保留（标注抽样） |
| M02 | `04_reports/02_denoising/data/denoise_eval_16k.csv` | denoiser+mel | 🔴 dns_dev 6 行 si_sdr_in/out/improve 全为 0.00（noref 模式空值被写成 0）；synth 行正常(4.83->15.35,+11.61)；n_skipped 全 0（已是 P19 修复后版本） | 补证后保留（dns_dev 行改 null，不能写 0） |
| M03 | `04_reports/02_denoising/data/denoise_eval_44k.csv` | denoiser+mel | Valentini fullref 824 条，口径正确；与 16k 表不可混表 | 保留 |
| M04 | `04_reports/03_cascade/data/cascade_eval.csv` | 级联 | n=16 小样本；L1=L1b+(L1-L1b) 逐格恒等；负结果为主 | 补证后保留（标注 n=16） |
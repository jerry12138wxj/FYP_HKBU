# BS-RoFormer-L12 · 逐 output 分析图集

- 图集格式参照 `figures/demucs/`（`tools/run_demucs_deepdive.py`）
- 产物根目录：`figures/_model_figs/BS-RoFormer-L12/`（A1 隔离，不与参照同层）
- 窗长档位：128, 512, 1024, 2048
- 每单元 **11** 张图（fig1 / fig2 / fig3×2 / fig4×4 / fig5 / fig6×2）
- 窗口口径：能源最大化 30 s（B2；以参考信号能源峰定位，est/ref 同窗；每单元实际 t_start 见 caption.json）
- 歌曲数：50 ｜ stem：vocals ｜ 单元数：50

## 目录结构

```
figures/_model_figs/BS-RoFormer-L12/<song>/<stem>/fig*.png
```

## 单元清单

| 歌曲 | stem | 参考信号 | 口径 |
|---|---|---|---|
| Al James - Schoolboy Facination | vocals | MUSDB18-HQ/test/Al James - Schoolboy Facination/vocals.wav | 同口径 |
| AM Contra - Heart Peripheral | vocals | MUSDB18-HQ/test/AM Contra - Heart Peripheral/vocals.wav | 同口径 |
| Angels In Amplifiers - I'm Alright | vocals | MUSDB18-HQ/test/Angels In Amplifiers - I'm Alright/vocals.wav | 同口径 |
| Arise - Run Run Run | vocals | MUSDB18-HQ/test/Arise - Run Run Run/vocals.wav | 同口径 |
| Ben Carrigan - We'll Talk About It All Tonight | vocals | MUSDB18-HQ/test/Ben Carrigan - We'll Talk About It All Tonight/vocals.wav | 同口径 |
| BKS - Bulldozer | vocals | MUSDB18-HQ/test/BKS - Bulldozer/vocals.wav | 同口径 |
| BKS - Too Much | vocals | MUSDB18-HQ/test/BKS - Too Much/vocals.wav | 同口径 |
| Bobby Nobody - Stitch Up | vocals | MUSDB18-HQ/test/Bobby Nobody - Stitch Up/vocals.wav | 同口径 |
| Buitraker - Revo X | vocals | MUSDB18-HQ/test/Buitraker - Revo X/vocals.wav | 同口径 |
| Carlos Gonzalez - A Place For Us | vocals | MUSDB18-HQ/test/Carlos Gonzalez - A Place For Us/vocals.wav | 同口径 |
| Cristina Vane - So Easy | vocals | MUSDB18-HQ/test/Cristina Vane - So Easy/vocals.wav | 同口径 |
| Detsky Sad - Walkie Talkie | vocals | MUSDB18-HQ/test/Detsky Sad - Walkie Talkie/vocals.wav | 同口径 |
| Enda Reilly - Cur An Long Ag Seol | vocals | MUSDB18-HQ/test/Enda Reilly - Cur An Long Ag Seol/vocals.wav | 同口径 |
| Forkupines - Semantics | vocals | MUSDB18-HQ/test/Forkupines - Semantics/vocals.wav | 同口径 |
| Georgia Wonder - Siren | vocals | MUSDB18-HQ/test/Georgia Wonder - Siren/vocals.wav | 同口径 |
| Girls Under Glass - We Feel Alright | vocals | MUSDB18-HQ/test/Girls Under Glass - We Feel Alright/vocals.wav | 同口径 |
| Hollow Ground - Ill Fate | vocals | MUSDB18-HQ/test/Hollow Ground - Ill Fate/vocals.wav | 同口径 |
| James Elder & Mark M Thompson - The English Actor | vocals | MUSDB18-HQ/test/James Elder & Mark M Thompson - The English Actor/vocals.wav | 同口径 |
| Juliet's Rescue - Heartbeats | vocals | MUSDB18-HQ/test/Juliet's Rescue - Heartbeats/vocals.wav | 同口径 |
| Little Chicago's Finest - My Own | vocals | MUSDB18-HQ/test/Little Chicago's Finest - My Own/vocals.wav | 同口径 |
| Louis Cressy Band - Good Time | vocals | MUSDB18-HQ/test/Louis Cressy Band - Good Time/vocals.wav | 同口径 |
| Lyndsey Ollard - Catching Up | vocals | MUSDB18-HQ/test/Lyndsey Ollard - Catching Up/vocals.wav | 同口径 |
| M.E.R.C. Music - Knockout | vocals | MUSDB18-HQ/test/M.E.R.C. Music - Knockout/vocals.wav | 同口径 |
| Moosmusic - Big Dummy Shake | vocals | MUSDB18-HQ/test/Moosmusic - Big Dummy Shake/vocals.wav | 同口径 |
| Motor Tapes - Shore | vocals | MUSDB18-HQ/test/Motor Tapes - Shore/vocals.wav | 同口径 |
| Mu - Too Bright | vocals | MUSDB18-HQ/test/Mu - Too Bright/vocals.wav | 同口径 |
| Nerve 9 - Pray For The Rain | vocals | MUSDB18-HQ/test/Nerve 9 - Pray For The Rain/vocals.wav | 同口径 |
| PR - Happy Daze | vocals | MUSDB18-HQ/test/PR - Happy Daze/vocals.wav | 同口径 |
| PR - Oh No | vocals | MUSDB18-HQ/test/PR - Oh No/vocals.wav | 同口径 |
| Punkdisco - Oral Hygiene | vocals | MUSDB18-HQ/test/Punkdisco - Oral Hygiene/vocals.wav | 同口径 |
| Raft Monk - Tiring | vocals | MUSDB18-HQ/test/Raft Monk - Tiring/vocals.wav | 同口径 |
| Sambasevam Shanmugam - Kaathaadi | vocals | MUSDB18-HQ/test/Sambasevam Shanmugam - Kaathaadi/vocals.wav | 同口径 |
| Secretariat - Borderline | vocals | MUSDB18-HQ/test/Secretariat - Borderline/vocals.wav | 同口径 |
| Secretariat - Over The Top | vocals | MUSDB18-HQ/test/Secretariat - Over The Top/vocals.wav | 同口径 |
| Side Effects Project - Sing With Me | vocals | MUSDB18-HQ/test/Side Effects Project - Sing With Me/vocals.wav | 同口径 |
| Signe Jakobsen - What Have You Done To Me | vocals | MUSDB18-HQ/test/Signe Jakobsen - What Have You Done To Me/vocals.wav | 同口径 |
| Skelpolu - Resurrection | vocals | MUSDB18-HQ/test/Skelpolu - Resurrection/vocals.wav | 同口径 |
| Speak Softly - Broken Man | vocals | MUSDB18-HQ/test/Speak Softly - Broken Man/vocals.wav | 同口径 |
| Speak Softly - Like Horses | vocals | MUSDB18-HQ/test/Speak Softly - Like Horses/vocals.wav | 同口径 |
| The Doppler Shift - Atrophy | vocals | MUSDB18-HQ/test/The Doppler Shift - Atrophy/vocals.wav | 同口径 |
| The Easton Ellises (Baumi) - SDRNR | vocals | MUSDB18-HQ/test/The Easton Ellises (Baumi) - SDRNR/vocals.wav | 同口径 |
| The Easton Ellises - Falcon 69 | vocals | MUSDB18-HQ/test/The Easton Ellises - Falcon 69/vocals.wav | 同口径 |
| The Long Wait - Dark Horses | vocals | MUSDB18-HQ/test/The Long Wait - Dark Horses/vocals.wav | 同口径 |
| The Mountaineering Club - Mallory | vocals | MUSDB18-HQ/test/The Mountaineering Club - Mallory/vocals.wav | 同口径 |
| The Sunshine Garcia Band - For I Am The Moon | vocals | MUSDB18-HQ/test/The Sunshine Garcia Band - For I Am The Moon/vocals.wav | 同口径 |
| Timboz - Pony | vocals | MUSDB18-HQ/test/Timboz - Pony/vocals.wav | 同口径 |
| Tom McKenzie - Directions | vocals | MUSDB18-HQ/test/Tom McKenzie - Directions/vocals.wav | 同口径 |
| Triviul feat. The Fiend - Widow | vocals | MUSDB18-HQ/test/Triviul feat. The Fiend - Widow/vocals.wav | 同口径 |
| We Fell From The Sky - Not You | vocals | MUSDB18-HQ/test/We Fell From The Sky - Not You/vocals.wav | 同口径 |
| Zeno - Signs | vocals | MUSDB18-HQ/test/Zeno - Signs/vocals.wav | 同口径 |

## 图说明

| 文件 | 内容 |
|---|---|
| `fig1_waveform_est_ref_diff.png` | 波形三联：输出 / 参考 / 差值 |
| `fig2_waveform_sr_compare.png` | 输出重采样 44.1k / 22.05k / 16k |
| `fig3_spectrogram_est.png` | 输出频谱（log 频率轴, n_fft=1024） |
| `fig3_spectrogram_ref.png` | 参考频谱（同参数） |
| `fig4_spectrogram_win128.png` | 输出频谱, 窗长 128（线性频率轴） |
| `fig4_spectrogram_win512.png` | 输出频谱, 窗长 512（线性频率轴） |
| `fig4_spectrogram_win1024.png` | 输出频谱, 窗长 1024（线性频率轴） |
| `fig4_spectrogram_win2048.png` | 输出频谱, 窗长 2048（线性频率轴） |
| `fig5_trim_before_after.png` | trim(top_db=30) 前后 |
| `fig6_mfcc_est.png` | 输出 MFCC 13 维 |
| `fig6_mfcc_ref.png` | 参考 MFCC 13 维 |
| `caption.json` | 该单元的元数据 |

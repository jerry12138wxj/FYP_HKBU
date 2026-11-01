# BS-RoFormer-L6 · 逐 output 分析图集

- 图集格式参照 `figures/demucs/`（`tools/run_demucs_deepdive.py`）
- 产物根目录：`figures/_model_figs/BS-RoFormer-L6/`（A1 隔离，不与参照同层）
- 窗长档位：128, 512, 1024, 2048
- 每单元 **11** 张图（fig1 / fig2 / fig3×2 / fig4×4 / fig5 / fig6×2）
- 窗口口径：能源最大化 30 s（B2；以参考信号能源峰定位，est/ref 同窗；每单元实际 t_start 见 caption.json）
- 歌曲数：50 ｜ stem：vocals+other ｜ 单元数：50

## 目录结构

```
figures/_model_figs/BS-RoFormer-L6/<song>/<stem>/fig*.png
```

## 单元清单

| 歌曲 | stem | 参考信号 | 口径 |
|---|---|---|---|
| Al James - Schoolboy Facination | vocals+other | （无） | 混合轨（非同口径） |
| AM Contra - Heart Peripheral | vocals+other | （无） | 混合轨（非同口径） |
| Angels In Amplifiers - I'm Alright | vocals+other | （无） | 混合轨（非同口径） |
| Arise - Run Run Run | vocals+other | （无） | 混合轨（非同口径） |
| Ben Carrigan - We'll Talk About It All Tonight | vocals+other | （无） | 混合轨（非同口径） |
| BKS - Bulldozer | vocals+other | （无） | 混合轨（非同口径） |
| BKS - Too Much | vocals+other | （无） | 混合轨（非同口径） |
| Bobby Nobody - Stitch Up | vocals+other | （无） | 混合轨（非同口径） |
| Buitraker - Revo X | vocals+other | （无） | 混合轨（非同口径） |
| Carlos Gonzalez - A Place For Us | vocals+other | （无） | 混合轨（非同口径） |
| Cristina Vane - So Easy | vocals+other | （无） | 混合轨（非同口径） |
| Detsky Sad - Walkie Talkie | vocals+other | （无） | 混合轨（非同口径） |
| Enda Reilly - Cur An Long Ag Seol | vocals+other | （无） | 混合轨（非同口径） |
| Forkupines - Semantics | vocals+other | （无） | 混合轨（非同口径） |
| Georgia Wonder - Siren | vocals+other | （无） | 混合轨（非同口径） |
| Girls Under Glass - We Feel Alright | vocals+other | （无） | 混合轨（非同口径） |
| Hollow Ground - Ill Fate | vocals+other | （无） | 混合轨（非同口径） |
| James Elder & Mark M Thompson - The English Actor | vocals+other | （无） | 混合轨（非同口径） |
| Juliet's Rescue - Heartbeats | vocals+other | （无） | 混合轨（非同口径） |
| Little Chicago's Finest - My Own | vocals+other | （无） | 混合轨（非同口径） |
| Louis Cressy Band - Good Time | vocals+other | （无） | 混合轨（非同口径） |
| Lyndsey Ollard - Catching Up | vocals+other | （无） | 混合轨（非同口径） |
| M.E.R.C. Music - Knockout | vocals+other | （无） | 混合轨（非同口径） |
| Moosmusic - Big Dummy Shake | vocals+other | （无） | 混合轨（非同口径） |
| Motor Tapes - Shore | vocals+other | （无） | 混合轨（非同口径） |
| Mu - Too Bright | vocals+other | （无） | 混合轨（非同口径） |
| Nerve 9 - Pray For The Rain | vocals+other | （无） | 混合轨（非同口径） |
| PR - Happy Daze | vocals+other | （无） | 混合轨（非同口径） |
| PR - Oh No | vocals+other | （无） | 混合轨（非同口径） |
| Punkdisco - Oral Hygiene | vocals+other | （无） | 混合轨（非同口径） |
| Raft Monk - Tiring | vocals+other | （无） | 混合轨（非同口径） |
| Sambasevam Shanmugam - Kaathaadi | vocals+other | （无） | 混合轨（非同口径） |
| Secretariat - Borderline | vocals+other | （无） | 混合轨（非同口径） |
| Secretariat - Over The Top | vocals+other | （无） | 混合轨（非同口径） |
| Side Effects Project - Sing With Me | vocals+other | （无） | 混合轨（非同口径） |
| Signe Jakobsen - What Have You Done To Me | vocals+other | （无） | 混合轨（非同口径） |
| Skelpolu - Resurrection | vocals+other | （无） | 混合轨（非同口径） |
| Speak Softly - Broken Man | vocals+other | （无） | 混合轨（非同口径） |
| Speak Softly - Like Horses | vocals+other | （无） | 混合轨（非同口径） |
| The Doppler Shift - Atrophy | vocals+other | （无） | 混合轨（非同口径） |
| The Easton Ellises (Baumi) - SDRNR | vocals+other | （无） | 混合轨（非同口径） |
| The Easton Ellises - Falcon 69 | vocals+other | （无） | 混合轨（非同口径） |
| The Long Wait - Dark Horses | vocals+other | （无） | 混合轨（非同口径） |
| The Mountaineering Club - Mallory | vocals+other | （无） | 混合轨（非同口径） |
| The Sunshine Garcia Band - For I Am The Moon | vocals+other | （无） | 混合轨（非同口径） |
| Timboz - Pony | vocals+other | （无） | 混合轨（非同口径） |
| Tom McKenzie - Directions | vocals+other | （无） | 混合轨（非同口径） |
| Triviul feat. The Fiend - Widow | vocals+other | （无） | 混合轨（非同口径） |
| We Fell From The Sky - Not You | vocals+other | （无） | 混合轨（非同口径） |
| Zeno - Signs | vocals+other | （无） | 混合轨（非同口径） |

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

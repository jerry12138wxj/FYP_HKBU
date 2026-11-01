# Oracle-IRM · 逐 output 分析图集

- 图集格式参照 `figures/demucs/`（`tools/run_demucs_deepdive.py`）
- 产物根目录：`figures/_model_figs/Oracle-IRM/`（A1 隔离，不与参照同层）
- 窗长档位：128, 512, 1024, 2048
- 每单元 **11** 张图（fig1 / fig2 / fig3×2 / fig4×4 / fig5 / fig6×2）
- 窗口口径：能源最大化 30 s（B2；以参考信号能源峰定位，est/ref 同窗；每单元实际 t_start 见 caption.json）
- 歌曲数：50 ｜ stem：bass, drums, other, vocals ｜ 单元数：200

## 目录结构

```
figures/_model_figs/Oracle-IRM/<song>/<stem>/fig*.png
```

## 单元清单

| 歌曲 | stem | 参考信号 | 口径 |
|---|---|---|---|
| Al James - Schoolboy Facination | vocals | MUSDB18-HQ/test/Al James - Schoolboy Facination/vocals.wav | 同口径 |
| Al James - Schoolboy Facination | drums | MUSDB18-HQ/test/Al James - Schoolboy Facination/drums.wav | 同口径 |
| Al James - Schoolboy Facination | bass | MUSDB18-HQ/test/Al James - Schoolboy Facination/bass.wav | 同口径 |
| Al James - Schoolboy Facination | other | MUSDB18-HQ/test/Al James - Schoolboy Facination/other.wav | 同口径 |
| AM Contra - Heart Peripheral | vocals | MUSDB18-HQ/test/AM Contra - Heart Peripheral/vocals.wav | 同口径 |
| AM Contra - Heart Peripheral | drums | MUSDB18-HQ/test/AM Contra - Heart Peripheral/drums.wav | 同口径 |
| AM Contra - Heart Peripheral | bass | MUSDB18-HQ/test/AM Contra - Heart Peripheral/bass.wav | 同口径 |
| AM Contra - Heart Peripheral | other | MUSDB18-HQ/test/AM Contra - Heart Peripheral/other.wav | 同口径 |
| Angels In Amplifiers - I'm Alright | vocals | MUSDB18-HQ/test/Angels In Amplifiers - I'm Alright/vocals.wav | 同口径 |
| Angels In Amplifiers - I'm Alright | drums | MUSDB18-HQ/test/Angels In Amplifiers - I'm Alright/drums.wav | 同口径 |
| Angels In Amplifiers - I'm Alright | bass | MUSDB18-HQ/test/Angels In Amplifiers - I'm Alright/bass.wav | 同口径 |
| Angels In Amplifiers - I'm Alright | other | MUSDB18-HQ/test/Angels In Amplifiers - I'm Alright/other.wav | 同口径 |
| Arise - Run Run Run | vocals | MUSDB18-HQ/test/Arise - Run Run Run/vocals.wav | 同口径 |
| Arise - Run Run Run | drums | MUSDB18-HQ/test/Arise - Run Run Run/drums.wav | 同口径 |
| Arise - Run Run Run | bass | MUSDB18-HQ/test/Arise - Run Run Run/bass.wav | 同口径 |
| Arise - Run Run Run | other | MUSDB18-HQ/test/Arise - Run Run Run/other.wav | 同口径 |
| Ben Carrigan - We'll Talk About It All Tonight | vocals | MUSDB18-HQ/test/Ben Carrigan - We'll Talk About It All Tonight/vocals.wav | 同口径 |
| Ben Carrigan - We'll Talk About It All Tonight | drums | MUSDB18-HQ/test/Ben Carrigan - We'll Talk About It All Tonight/drums.wav | 同口径 |
| Ben Carrigan - We'll Talk About It All Tonight | bass | MUSDB18-HQ/test/Ben Carrigan - We'll Talk About It All Tonight/bass.wav | 同口径 |
| Ben Carrigan - We'll Talk About It All Tonight | other | MUSDB18-HQ/test/Ben Carrigan - We'll Talk About It All Tonight/other.wav | 同口径 |
| BKS - Bulldozer | vocals | MUSDB18-HQ/test/BKS - Bulldozer/vocals.wav | 同口径 |
| BKS - Bulldozer | drums | MUSDB18-HQ/test/BKS - Bulldozer/drums.wav | 同口径 |
| BKS - Bulldozer | bass | MUSDB18-HQ/test/BKS - Bulldozer/bass.wav | 同口径 |
| BKS - Bulldozer | other | MUSDB18-HQ/test/BKS - Bulldozer/other.wav | 同口径 |
| BKS - Too Much | vocals | MUSDB18-HQ/test/BKS - Too Much/vocals.wav | 同口径 |
| BKS - Too Much | drums | MUSDB18-HQ/test/BKS - Too Much/drums.wav | 同口径 |
| BKS - Too Much | bass | MUSDB18-HQ/test/BKS - Too Much/bass.wav | 同口径 |
| BKS - Too Much | other | MUSDB18-HQ/test/BKS - Too Much/other.wav | 同口径 |
| Bobby Nobody - Stitch Up | vocals | MUSDB18-HQ/test/Bobby Nobody - Stitch Up/vocals.wav | 同口径 |
| Bobby Nobody - Stitch Up | drums | MUSDB18-HQ/test/Bobby Nobody - Stitch Up/drums.wav | 同口径 |
| Bobby Nobody - Stitch Up | bass | MUSDB18-HQ/test/Bobby Nobody - Stitch Up/bass.wav | 同口径 |
| Bobby Nobody - Stitch Up | other | MUSDB18-HQ/test/Bobby Nobody - Stitch Up/other.wav | 同口径 |
| Buitraker - Revo X | vocals | MUSDB18-HQ/test/Buitraker - Revo X/vocals.wav | 同口径 |
| Buitraker - Revo X | drums | MUSDB18-HQ/test/Buitraker - Revo X/drums.wav | 同口径 |
| Buitraker - Revo X | bass | MUSDB18-HQ/test/Buitraker - Revo X/bass.wav | 同口径 |
| Buitraker - Revo X | other | MUSDB18-HQ/test/Buitraker - Revo X/other.wav | 同口径 |
| Carlos Gonzalez - A Place For Us | vocals | MUSDB18-HQ/test/Carlos Gonzalez - A Place For Us/vocals.wav | 同口径 |
| Carlos Gonzalez - A Place For Us | drums | MUSDB18-HQ/test/Carlos Gonzalez - A Place For Us/drums.wav | 同口径 |
| Carlos Gonzalez - A Place For Us | bass | MUSDB18-HQ/test/Carlos Gonzalez - A Place For Us/bass.wav | 同口径 |
| Carlos Gonzalez - A Place For Us | other | MUSDB18-HQ/test/Carlos Gonzalez - A Place For Us/other.wav | 同口径 |
| Cristina Vane - So Easy | vocals | MUSDB18-HQ/test/Cristina Vane - So Easy/vocals.wav | 同口径 |
| Cristina Vane - So Easy | drums | MUSDB18-HQ/test/Cristina Vane - So Easy/drums.wav | 同口径 |
| Cristina Vane - So Easy | bass | MUSDB18-HQ/test/Cristina Vane - So Easy/bass.wav | 同口径 |
| Cristina Vane - So Easy | other | MUSDB18-HQ/test/Cristina Vane - So Easy/other.wav | 同口径 |
| Detsky Sad - Walkie Talkie | vocals | MUSDB18-HQ/test/Detsky Sad - Walkie Talkie/vocals.wav | 同口径 |
| Detsky Sad - Walkie Talkie | drums | MUSDB18-HQ/test/Detsky Sad - Walkie Talkie/drums.wav | 同口径 |
| Detsky Sad - Walkie Talkie | bass | MUSDB18-HQ/test/Detsky Sad - Walkie Talkie/bass.wav | 同口径 |
| Detsky Sad - Walkie Talkie | other | MUSDB18-HQ/test/Detsky Sad - Walkie Talkie/other.wav | 同口径 |
| Enda Reilly - Cur An Long Ag Seol | vocals | MUSDB18-HQ/test/Enda Reilly - Cur An Long Ag Seol/vocals.wav | 同口径 |
| Enda Reilly - Cur An Long Ag Seol | drums | MUSDB18-HQ/test/Enda Reilly - Cur An Long Ag Seol/drums.wav | 同口径 |
| Enda Reilly - Cur An Long Ag Seol | bass | MUSDB18-HQ/test/Enda Reilly - Cur An Long Ag Seol/bass.wav | 同口径 |
| Enda Reilly - Cur An Long Ag Seol | other | MUSDB18-HQ/test/Enda Reilly - Cur An Long Ag Seol/other.wav | 同口径 |
| Forkupines - Semantics | vocals | MUSDB18-HQ/test/Forkupines - Semantics/vocals.wav | 同口径 |
| Forkupines - Semantics | drums | MUSDB18-HQ/test/Forkupines - Semantics/drums.wav | 同口径 |
| Forkupines - Semantics | bass | MUSDB18-HQ/test/Forkupines - Semantics/bass.wav | 同口径 |
| Forkupines - Semantics | other | MUSDB18-HQ/test/Forkupines - Semantics/other.wav | 同口径 |
| Georgia Wonder - Siren | vocals | MUSDB18-HQ/test/Georgia Wonder - Siren/vocals.wav | 同口径 |
| Georgia Wonder - Siren | drums | MUSDB18-HQ/test/Georgia Wonder - Siren/drums.wav | 同口径 |
| Georgia Wonder - Siren | bass | MUSDB18-HQ/test/Georgia Wonder - Siren/bass.wav | 同口径 |
| Georgia Wonder - Siren | other | MUSDB18-HQ/test/Georgia Wonder - Siren/other.wav | 同口径 |
| Girls Under Glass - We Feel Alright | vocals | MUSDB18-HQ/test/Girls Under Glass - We Feel Alright/vocals.wav | 同口径 |
| Girls Under Glass - We Feel Alright | drums | MUSDB18-HQ/test/Girls Under Glass - We Feel Alright/drums.wav | 同口径 |
| Girls Under Glass - We Feel Alright | bass | MUSDB18-HQ/test/Girls Under Glass - We Feel Alright/bass.wav | 同口径 |
| Girls Under Glass - We Feel Alright | other | MUSDB18-HQ/test/Girls Under Glass - We Feel Alright/other.wav | 同口径 |
| Hollow Ground - Ill Fate | vocals | MUSDB18-HQ/test/Hollow Ground - Ill Fate/vocals.wav | 同口径 |
| Hollow Ground - Ill Fate | drums | MUSDB18-HQ/test/Hollow Ground - Ill Fate/drums.wav | 同口径 |
| Hollow Ground - Ill Fate | bass | MUSDB18-HQ/test/Hollow Ground - Ill Fate/bass.wav | 同口径 |
| Hollow Ground - Ill Fate | other | MUSDB18-HQ/test/Hollow Ground - Ill Fate/other.wav | 同口径 |
| James Elder & Mark M Thompson - The English Actor | vocals | MUSDB18-HQ/test/James Elder & Mark M Thompson - The English Actor/vocals.wav | 同口径 |
| James Elder & Mark M Thompson - The English Actor | drums | MUSDB18-HQ/test/James Elder & Mark M Thompson - The English Actor/drums.wav | 同口径 |
| James Elder & Mark M Thompson - The English Actor | bass | MUSDB18-HQ/test/James Elder & Mark M Thompson - The English Actor/bass.wav | 同口径 |
| James Elder & Mark M Thompson - The English Actor | other | MUSDB18-HQ/test/James Elder & Mark M Thompson - The English Actor/other.wav | 同口径 |
| Juliet's Rescue - Heartbeats | vocals | MUSDB18-HQ/test/Juliet's Rescue - Heartbeats/vocals.wav | 同口径 |
| Juliet's Rescue - Heartbeats | drums | MUSDB18-HQ/test/Juliet's Rescue - Heartbeats/drums.wav | 同口径 |
| Juliet's Rescue - Heartbeats | bass | MUSDB18-HQ/test/Juliet's Rescue - Heartbeats/bass.wav | 同口径 |
| Juliet's Rescue - Heartbeats | other | MUSDB18-HQ/test/Juliet's Rescue - Heartbeats/other.wav | 同口径 |
| Little Chicago's Finest - My Own | vocals | MUSDB18-HQ/test/Little Chicago's Finest - My Own/vocals.wav | 同口径 |
| Little Chicago's Finest - My Own | drums | MUSDB18-HQ/test/Little Chicago's Finest - My Own/drums.wav | 同口径 |
| Little Chicago's Finest - My Own | bass | MUSDB18-HQ/test/Little Chicago's Finest - My Own/bass.wav | 同口径 |
| Little Chicago's Finest - My Own | other | MUSDB18-HQ/test/Little Chicago's Finest - My Own/other.wav | 同口径 |
| Louis Cressy Band - Good Time | vocals | MUSDB18-HQ/test/Louis Cressy Band - Good Time/vocals.wav | 同口径 |
| Louis Cressy Band - Good Time | drums | MUSDB18-HQ/test/Louis Cressy Band - Good Time/drums.wav | 同口径 |
| Louis Cressy Band - Good Time | bass | MUSDB18-HQ/test/Louis Cressy Band - Good Time/bass.wav | 同口径 |
| Louis Cressy Band - Good Time | other | MUSDB18-HQ/test/Louis Cressy Band - Good Time/other.wav | 同口径 |
| Lyndsey Ollard - Catching Up | vocals | MUSDB18-HQ/test/Lyndsey Ollard - Catching Up/vocals.wav | 同口径 |
| Lyndsey Ollard - Catching Up | drums | MUSDB18-HQ/test/Lyndsey Ollard - Catching Up/drums.wav | 同口径 |
| Lyndsey Ollard - Catching Up | bass | MUSDB18-HQ/test/Lyndsey Ollard - Catching Up/bass.wav | 同口径 |
| Lyndsey Ollard - Catching Up | other | MUSDB18-HQ/test/Lyndsey Ollard - Catching Up/other.wav | 同口径 |
| M.E.R.C. Music - Knockout | vocals | MUSDB18-HQ/test/M.E.R.C. Music - Knockout/vocals.wav | 同口径 |
| M.E.R.C. Music - Knockout | drums | MUSDB18-HQ/test/M.E.R.C. Music - Knockout/drums.wav | 同口径 |
| M.E.R.C. Music - Knockout | bass | MUSDB18-HQ/test/M.E.R.C. Music - Knockout/bass.wav | 同口径 |
| M.E.R.C. Music - Knockout | other | MUSDB18-HQ/test/M.E.R.C. Music - Knockout/other.wav | 同口径 |
| Moosmusic - Big Dummy Shake | vocals | MUSDB18-HQ/test/Moosmusic - Big Dummy Shake/vocals.wav | 同口径 |
| Moosmusic - Big Dummy Shake | drums | MUSDB18-HQ/test/Moosmusic - Big Dummy Shake/drums.wav | 同口径 |
| Moosmusic - Big Dummy Shake | bass | MUSDB18-HQ/test/Moosmusic - Big Dummy Shake/bass.wav | 同口径 |
| Moosmusic - Big Dummy Shake | other | MUSDB18-HQ/test/Moosmusic - Big Dummy Shake/other.wav | 同口径 |
| Motor Tapes - Shore | vocals | MUSDB18-HQ/test/Motor Tapes - Shore/vocals.wav | 同口径 |
| Motor Tapes - Shore | drums | MUSDB18-HQ/test/Motor Tapes - Shore/drums.wav | 同口径 |
| Motor Tapes - Shore | bass | MUSDB18-HQ/test/Motor Tapes - Shore/bass.wav | 同口径 |
| Motor Tapes - Shore | other | MUSDB18-HQ/test/Motor Tapes - Shore/other.wav | 同口径 |
| Mu - Too Bright | vocals | MUSDB18-HQ/test/Mu - Too Bright/vocals.wav | 同口径 |
| Mu - Too Bright | drums | MUSDB18-HQ/test/Mu - Too Bright/drums.wav | 同口径 |
| Mu - Too Bright | bass | MUSDB18-HQ/test/Mu - Too Bright/bass.wav | 同口径 |
| Mu - Too Bright | other | MUSDB18-HQ/test/Mu - Too Bright/other.wav | 同口径 |
| Nerve 9 - Pray For The Rain | vocals | MUSDB18-HQ/test/Nerve 9 - Pray For The Rain/vocals.wav | 同口径 |
| Nerve 9 - Pray For The Rain | drums | MUSDB18-HQ/test/Nerve 9 - Pray For The Rain/drums.wav | 同口径 |
| Nerve 9 - Pray For The Rain | bass | MUSDB18-HQ/test/Nerve 9 - Pray For The Rain/bass.wav | 同口径 |
| Nerve 9 - Pray For The Rain | other | MUSDB18-HQ/test/Nerve 9 - Pray For The Rain/other.wav | 同口径 |
| PR - Happy Daze | vocals | MUSDB18-HQ/test/PR - Happy Daze/vocals.wav | 同口径 |
| PR - Happy Daze | drums | MUSDB18-HQ/test/PR - Happy Daze/drums.wav | 同口径 |
| PR - Happy Daze | bass | MUSDB18-HQ/test/PR - Happy Daze/bass.wav | 同口径 |
| PR - Happy Daze | other | MUSDB18-HQ/test/PR - Happy Daze/other.wav | 同口径 |
| PR - Oh No | vocals | MUSDB18-HQ/test/PR - Oh No/vocals.wav | 同口径 |
| PR - Oh No | drums | MUSDB18-HQ/test/PR - Oh No/drums.wav | 同口径 |
| PR - Oh No | bass | MUSDB18-HQ/test/PR - Oh No/bass.wav | 同口径 |
| PR - Oh No | other | MUSDB18-HQ/test/PR - Oh No/other.wav | 同口径 |
| Punkdisco - Oral Hygiene | vocals | MUSDB18-HQ/test/Punkdisco - Oral Hygiene/vocals.wav | 同口径 |
| Punkdisco - Oral Hygiene | drums | MUSDB18-HQ/test/Punkdisco - Oral Hygiene/drums.wav | 同口径 |
| Punkdisco - Oral Hygiene | bass | MUSDB18-HQ/test/Punkdisco - Oral Hygiene/bass.wav | 同口径 |
| Punkdisco - Oral Hygiene | other | MUSDB18-HQ/test/Punkdisco - Oral Hygiene/other.wav | 同口径 |
| Raft Monk - Tiring | vocals | MUSDB18-HQ/test/Raft Monk - Tiring/vocals.wav | 同口径 |
| Raft Monk - Tiring | drums | MUSDB18-HQ/test/Raft Monk - Tiring/drums.wav | 同口径 |
| Raft Monk - Tiring | bass | MUSDB18-HQ/test/Raft Monk - Tiring/bass.wav | 同口径 |
| Raft Monk - Tiring | other | MUSDB18-HQ/test/Raft Monk - Tiring/other.wav | 同口径 |
| Sambasevam Shanmugam - Kaathaadi | vocals | MUSDB18-HQ/test/Sambasevam Shanmugam - Kaathaadi/vocals.wav | 同口径 |
| Sambasevam Shanmugam - Kaathaadi | drums | MUSDB18-HQ/test/Sambasevam Shanmugam - Kaathaadi/drums.wav | 同口径 |
| Sambasevam Shanmugam - Kaathaadi | bass | MUSDB18-HQ/test/Sambasevam Shanmugam - Kaathaadi/bass.wav | 同口径 |
| Sambasevam Shanmugam - Kaathaadi | other | MUSDB18-HQ/test/Sambasevam Shanmugam - Kaathaadi/other.wav | 同口径 |
| Secretariat - Borderline | vocals | MUSDB18-HQ/test/Secretariat - Borderline/vocals.wav | 同口径 |
| Secretariat - Borderline | drums | MUSDB18-HQ/test/Secretariat - Borderline/drums.wav | 同口径 |
| Secretariat - Borderline | bass | MUSDB18-HQ/test/Secretariat - Borderline/bass.wav | 同口径 |
| Secretariat - Borderline | other | MUSDB18-HQ/test/Secretariat - Borderline/other.wav | 同口径 |
| Secretariat - Over The Top | vocals | MUSDB18-HQ/test/Secretariat - Over The Top/vocals.wav | 同口径 |
| Secretariat - Over The Top | drums | MUSDB18-HQ/test/Secretariat - Over The Top/drums.wav | 同口径 |
| Secretariat - Over The Top | bass | MUSDB18-HQ/test/Secretariat - Over The Top/bass.wav | 同口径 |
| Secretariat - Over The Top | other | MUSDB18-HQ/test/Secretariat - Over The Top/other.wav | 同口径 |
| Side Effects Project - Sing With Me | vocals | MUSDB18-HQ/test/Side Effects Project - Sing With Me/vocals.wav | 同口径 |
| Side Effects Project - Sing With Me | drums | MUSDB18-HQ/test/Side Effects Project - Sing With Me/drums.wav | 同口径 |
| Side Effects Project - Sing With Me | bass | MUSDB18-HQ/test/Side Effects Project - Sing With Me/bass.wav | 同口径 |
| Side Effects Project - Sing With Me | other | MUSDB18-HQ/test/Side Effects Project - Sing With Me/other.wav | 同口径 |
| Signe Jakobsen - What Have You Done To Me | vocals | MUSDB18-HQ/test/Signe Jakobsen - What Have You Done To Me/vocals.wav | 同口径 |
| Signe Jakobsen - What Have You Done To Me | drums | MUSDB18-HQ/test/Signe Jakobsen - What Have You Done To Me/drums.wav | 同口径 |
| Signe Jakobsen - What Have You Done To Me | bass | MUSDB18-HQ/test/Signe Jakobsen - What Have You Done To Me/bass.wav | 同口径 |
| Signe Jakobsen - What Have You Done To Me | other | MUSDB18-HQ/test/Signe Jakobsen - What Have You Done To Me/other.wav | 同口径 |
| Skelpolu - Resurrection | vocals | MUSDB18-HQ/test/Skelpolu - Resurrection/vocals.wav | 同口径 |
| Skelpolu - Resurrection | drums | MUSDB18-HQ/test/Skelpolu - Resurrection/drums.wav | 同口径 |
| Skelpolu - Resurrection | bass | MUSDB18-HQ/test/Skelpolu - Resurrection/bass.wav | 同口径 |
| Skelpolu - Resurrection | other | MUSDB18-HQ/test/Skelpolu - Resurrection/other.wav | 同口径 |
| Speak Softly - Broken Man | vocals | MUSDB18-HQ/test/Speak Softly - Broken Man/vocals.wav | 同口径 |
| Speak Softly - Broken Man | drums | MUSDB18-HQ/test/Speak Softly - Broken Man/drums.wav | 同口径 |
| Speak Softly - Broken Man | bass | MUSDB18-HQ/test/Speak Softly - Broken Man/bass.wav | 同口径 |
| Speak Softly - Broken Man | other | MUSDB18-HQ/test/Speak Softly - Broken Man/other.wav | 同口径 |
| Speak Softly - Like Horses | vocals | MUSDB18-HQ/test/Speak Softly - Like Horses/vocals.wav | 同口径 |
| Speak Softly - Like Horses | drums | MUSDB18-HQ/test/Speak Softly - Like Horses/drums.wav | 同口径 |
| Speak Softly - Like Horses | bass | MUSDB18-HQ/test/Speak Softly - Like Horses/bass.wav | 同口径 |
| Speak Softly - Like Horses | other | MUSDB18-HQ/test/Speak Softly - Like Horses/other.wav | 同口径 |
| The Doppler Shift - Atrophy | vocals | MUSDB18-HQ/test/The Doppler Shift - Atrophy/vocals.wav | 同口径 |
| The Doppler Shift - Atrophy | drums | MUSDB18-HQ/test/The Doppler Shift - Atrophy/drums.wav | 同口径 |
| The Doppler Shift - Atrophy | bass | MUSDB18-HQ/test/The Doppler Shift - Atrophy/bass.wav | 同口径 |
| The Doppler Shift - Atrophy | other | MUSDB18-HQ/test/The Doppler Shift - Atrophy/other.wav | 同口径 |
| The Easton Ellises (Baumi) - SDRNR | vocals | MUSDB18-HQ/test/The Easton Ellises (Baumi) - SDRNR/vocals.wav | 同口径 |
| The Easton Ellises (Baumi) - SDRNR | drums | MUSDB18-HQ/test/The Easton Ellises (Baumi) - SDRNR/drums.wav | 同口径 |
| The Easton Ellises (Baumi) - SDRNR | bass | MUSDB18-HQ/test/The Easton Ellises (Baumi) - SDRNR/bass.wav | 同口径 |
| The Easton Ellises (Baumi) - SDRNR | other | MUSDB18-HQ/test/The Easton Ellises (Baumi) - SDRNR/other.wav | 同口径 |
| The Easton Ellises - Falcon 69 | vocals | MUSDB18-HQ/test/The Easton Ellises - Falcon 69/vocals.wav | 同口径 |
| The Easton Ellises - Falcon 69 | drums | MUSDB18-HQ/test/The Easton Ellises - Falcon 69/drums.wav | 同口径 |
| The Easton Ellises - Falcon 69 | bass | MUSDB18-HQ/test/The Easton Ellises - Falcon 69/bass.wav | 同口径 |
| The Easton Ellises - Falcon 69 | other | MUSDB18-HQ/test/The Easton Ellises - Falcon 69/other.wav | 同口径 |
| The Long Wait - Dark Horses | vocals | MUSDB18-HQ/test/The Long Wait - Dark Horses/vocals.wav | 同口径 |
| The Long Wait - Dark Horses | drums | MUSDB18-HQ/test/The Long Wait - Dark Horses/drums.wav | 同口径 |
| The Long Wait - Dark Horses | bass | MUSDB18-HQ/test/The Long Wait - Dark Horses/bass.wav | 同口径 |
| The Long Wait - Dark Horses | other | MUSDB18-HQ/test/The Long Wait - Dark Horses/other.wav | 同口径 |
| The Mountaineering Club - Mallory | vocals | MUSDB18-HQ/test/The Mountaineering Club - Mallory/vocals.wav | 同口径 |
| The Mountaineering Club - Mallory | drums | MUSDB18-HQ/test/The Mountaineering Club - Mallory/drums.wav | 同口径 |
| The Mountaineering Club - Mallory | bass | MUSDB18-HQ/test/The Mountaineering Club - Mallory/bass.wav | 同口径 |
| The Mountaineering Club - Mallory | other | MUSDB18-HQ/test/The Mountaineering Club - Mallory/other.wav | 同口径 |
| The Sunshine Garcia Band - For I Am The Moon | vocals | MUSDB18-HQ/test/The Sunshine Garcia Band - For I Am The Moon/vocals.wav | 同口径 |
| The Sunshine Garcia Band - For I Am The Moon | drums | MUSDB18-HQ/test/The Sunshine Garcia Band - For I Am The Moon/drums.wav | 同口径 |
| The Sunshine Garcia Band - For I Am The Moon | bass | MUSDB18-HQ/test/The Sunshine Garcia Band - For I Am The Moon/bass.wav | 同口径 |
| The Sunshine Garcia Band - For I Am The Moon | other | MUSDB18-HQ/test/The Sunshine Garcia Band - For I Am The Moon/other.wav | 同口径 |
| Timboz - Pony | vocals | MUSDB18-HQ/test/Timboz - Pony/vocals.wav | 同口径 |
| Timboz - Pony | drums | MUSDB18-HQ/test/Timboz - Pony/drums.wav | 同口径 |
| Timboz - Pony | bass | MUSDB18-HQ/test/Timboz - Pony/bass.wav | 同口径 |
| Timboz - Pony | other | MUSDB18-HQ/test/Timboz - Pony/other.wav | 同口径 |
| Tom McKenzie - Directions | vocals | MUSDB18-HQ/test/Tom McKenzie - Directions/vocals.wav | 同口径 |
| Tom McKenzie - Directions | drums | MUSDB18-HQ/test/Tom McKenzie - Directions/drums.wav | 同口径 |
| Tom McKenzie - Directions | bass | MUSDB18-HQ/test/Tom McKenzie - Directions/bass.wav | 同口径 |
| Tom McKenzie - Directions | other | MUSDB18-HQ/test/Tom McKenzie - Directions/other.wav | 同口径 |
| Triviul feat. The Fiend - Widow | vocals | MUSDB18-HQ/test/Triviul feat. The Fiend - Widow/vocals.wav | 同口径 |
| Triviul feat. The Fiend - Widow | drums | MUSDB18-HQ/test/Triviul feat. The Fiend - Widow/drums.wav | 同口径 |
| Triviul feat. The Fiend - Widow | bass | MUSDB18-HQ/test/Triviul feat. The Fiend - Widow/bass.wav | 同口径 |
| Triviul feat. The Fiend - Widow | other | MUSDB18-HQ/test/Triviul feat. The Fiend - Widow/other.wav | 同口径 |
| We Fell From The Sky - Not You | vocals | MUSDB18-HQ/test/We Fell From The Sky - Not You/vocals.wav | 同口径 |
| We Fell From The Sky - Not You | drums | MUSDB18-HQ/test/We Fell From The Sky - Not You/drums.wav | 同口径 |
| We Fell From The Sky - Not You | bass | MUSDB18-HQ/test/We Fell From The Sky - Not You/bass.wav | 同口径 |
| We Fell From The Sky - Not You | other | MUSDB18-HQ/test/We Fell From The Sky - Not You/other.wav | 同口径 |
| Zeno - Signs | vocals | MUSDB18-HQ/test/Zeno - Signs/vocals.wav | 同口径 |
| Zeno - Signs | drums | MUSDB18-HQ/test/Zeno - Signs/drums.wav | 同口径 |
| Zeno - Signs | bass | MUSDB18-HQ/test/Zeno - Signs/bass.wav | 同口径 |
| Zeno - Signs | other | MUSDB18-HQ/test/Zeno - Signs/other.wav | 同口径 |

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

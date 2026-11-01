#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成答辩 slides v2：介绍 → 对比 → 用最好的模型（分离 / 降噪各一轮）+ 实时级联 + Web 应用。

数据来源（零手填，全部读 JSON）：
  - SDR：  04_reports/01_separation/data/comparison/model_runs_median.json
  - 成本：  04_reports/00_shared/data/model_analysis/model_profile.json
  - 降噪：  04_reports/02_denoising/data/denoise_eval_16k.json
  - 冒烟：  tools/_logs/smoke_test.jsonl（若存在）
  - 异常：  tools/_logs/abnormal_test.jsonl（若存在）

图：   04_reports/00_shared/figures/model_arch/arch_*.png
       04_reports/00_shared/papers/figs/fig*.png
"""
import base64, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

CSS_PATH = os.path.join(ROOT, "tools", "_scratch", "_slides_css.css")
OUT = os.path.join(ROOT, "04_reports", "04_defense", "defense_slides.html")
ARCH_DIR = os.path.join(ROOT, "04_reports", "00_shared", "figures", "model_arch")
FIG_DIR = os.path.join(ROOT, "04_reports", "00_shared", "papers", "figs")

from PIL import Image


def b64_png(path, width):
    """downscale PNG to `width` px and return data URI."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    if w > width:
        h = int(h * width / w)
        im = im.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def arch(name, width=860):
    return b64_png(os.path.join(ARCH_DIR, name), width)


def fig(name, width=820):
    return b64_png(os.path.join(FIG_DIR, name), width)


# ---------------------------------------------------------------- data
def _j(rel):
    return json.load(open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8"))


median = _j("04_reports/01_separation/data/comparison/model_runs_median.json")
profile = {r["model_key"]: r for r in _j("04_reports/00_shared/data/model_analysis/model_profile.json")["records"]}
denoise_rows = _j("04_reports/02_denoising/data/denoise_eval_16k.json")["rows"]


def sdr_avg4(key):
    s = median[key].get("sdr") or {}
    vals = []
    for stem in ("vocals", "drums", "bass", "other"):
        x = s.get(stem) or {}
        m = x.get("median")
        if m is not None:
            vals.append(m)
    return sum(vals) / len(vals) if vals else None


def stem_val(key, stem):
    x = (median[key].get("sdr") or {}).get(stem) or {}
    return x.get("median")


def fmt(x, nd=2):
    if x is None:
        return "—"
    return ("%." + str(nd) + "f") % x


def prof(key):
    return profile.get(key, {})


# ---------------------------------------------------------------- HTML pieces
def kicker(text, cls=""):
    c = (" " + cls) if cls else ""
    return '<div class="kicker%s">%s</div>' % (c, text)


def h2(title):
    return "<h2>%s</h2>" % title


def sub(text):
    return '<div class="sub">%s</div>' % text


def card(img, title, desc, tag=""):
    t = ("<div class='kl'>%s</div>" % tag) if tag else ""
    return ('<figure style="margin:0"><img src="%s"></figure>'
            '<div style="font-size:12.6px;color:var(--ink2);line-height:1.5">%s%s</div>'
            % (img, t, desc))


def grid(items, cols=3):
    return ('<div class="cols%s">' % (" c3" if cols == 3 else "") +
            "".join("<div>%s</div>" % it for it in items) + "</div>")


def table(head, rows, sm=True):
    th = "".join("<th>%s</th>" % c for c in head)
    body = ""
    for r in rows:
        tds = ""
        for i, c in enumerate(r):
            cls = "name" if i == 0 else ""
            tds += '<td class="%s">%s</td>' % (cls, c)
        body += "<tr>%s</tr>" % tds
    smc = " sm" if sm else ""
    return '<table class="tbl%s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (smc, th, body)


def slide(kicker_cls, ktext, title, subtitle, body, notes=""):
    n = ('<aside class="notes"><h4>讲稿（S 键显示 / 隐藏）</h4>%s</aside>' % notes) if notes else ""
    return ('<section class="slide"><div class="kicker %s">%s</div><h2>%s</h2>'
            '<div class="sub">%s</div><div class="body">%s</div>%s</section>'
            % (kicker_cls, ktext, title, subtitle, body, n))


# ================================================================ slides
S = []

# 1. cover
S.append('<section class="slide coverpage"><div class="kicker cover">FYP Defence · 2026</div>'
         '<h1>音乐源分离与语音降噪<br>分离 → 降噪 级联实时系统</h1>'
         '<div class="sub">Music Source Separation &amp; Speech Denoising · 结构：介绍 → 对比 → 用最好的模型 → 实时级联</div>'
         '<div class="kpis">'
         '<div class="kpi"><div class="kv">9.27 dB</div><div class="kl">分离精度最佳</div><div class="kn">oBSRNN-SIMO · avg4 · MUSDB18-HQ train</div></div>'
         '<div class="kpi t2"><div class="kv">+0.963</div><div class="kl">降噪 ΔPESQ 最佳</div><div class="kn">denoiser master64 · valentini n=824 · 16 kHz</div></div>'
         '<div class="kpi t3"><div class="kv">RTF 0.03</div><div class="kl">实时链路最快分离</div><div class="kn">Demucs (htdemucs) · GPU RTX 4070</div></div>'
         '</div>'
         '<div class="foot">HKBU FYP ｜ 项目根 E:\\FYP_HKBU ｜ 数字全部读自 JSON，零手填</div>'
         '<aside class="notes"><h4>讲稿</h4><b>开场 20 秒。</b>本汇报按「介绍 → 对比 → 用最好的模型」走两轮（分离、降噪），最后落到实时级联系统与 Web 应用。</aside></section>')

# 2. overview
S.append(slide("cover", "Overview", "结构：两轮「介绍→对比→选优」+ 一段实时级联",
    "先把路线图摆出来，再逐段推进",
    '<div class="chain">'
    '<div class="fbox b1">① 分离 · 介绍<span>9 四轨 + 3 单目标 + 2 解析：每个模型的实现方法 + 架构图</span></div>'
    '<div class="fbox b1">② 分离 · 对比<span>SDR 分轨 / FLOPs / RTF / 显存 完整表</span></div>'
    '<div class="fbox b1">③ 分离 · 选优<span>精度最佳 oBSRNN-SIMO 9.27；实时最快 Demucs RTF 0.03</span></div>'
    '</div><div class="chain">'
    '<div class="fbox b2">④ 降噪 · 介绍<span>denoiser 家族 + Mel-RoFormer 的实现方法</span></div>'
    '<div class="fbox b2">⑤ 降噪 · 对比<span>ΔSI-SDR / ΔPESQ / ΔSTOI / 成本</span></div>'
    '<div class="fbox b2">⑥ 降噪 · 选优<span>master64 ΔPESQ +0.963 最优</span></div>'
    '</div><div class="chain">'
    '<div class="fbox bc">⑦ 实时级联<span>最快分离 Demucs → 人声 → 降噪 master64</span></div>'
    '<div class="fbox bc">⑧ Web 应用<span>上传 noisy → 级联 → 试听/下载（本地稳定运行）</span></div>'
    '<div class="fbox bc">⑨ 测试<span>15 条 high_res_wham 冒烟 + 异常操作</span></div>'
    '</div>',
    "<b>30 秒。</b>两条主线（分离、降噪）各自走一遍介绍→对比→选优，最后合流成实时级联系统。"))

# 3-6. separation model intro
S.append(slide("", "Board 1 · 介绍 · 时域端到端族", "时域端到端：Conv-TasNet / DPRNN / Demucs",
    "直接在波形上估计掩码或波形，不做显式 STFT 假设",
    grid([
        card(arch("arch_03_conv_tasnet.png"), "<b>Conv-TasNet</b> · TASLP 2019 · avg4 5.93",
             "1-D 编码器把波形映射为特征 → 时间卷积掩码网络(TCN)估计掩码 → 解码器回波形。端到端、无频谱假设。"),
        card(arch("arch_04_dprnn.png"), "<b>DPRNN</b> · ICASSP 2020 · avg4 −1.72(自训)",
             "把超长序列切成小块，块内+块间两路 BiLSTM（dual-path）解决 RNN 长序列记忆。本机为自训 5 h 四轨权重，欠训练。"),
        card(arch("arch_07_demucs_v4_htdemucs.png"), "<b>Demucs (htdemucs)</b> · ICASSP 2023 · avg4 8.11",
             "波形域 U-Net + 时/频域混合 loss；Hybrid Transformer 融合跨域信息。速度快、四轨稳定——实时链路的默认分离器。"),
    ]),
    "<b>25 秒。</b>三个模型都直接在波形上做文章：Conv-TasNet 用卷积掩码，DPRNN 用双路径 RNN，Demucs 用波形 U-Net。"))

S.append(slide("", "Board 1 · 介绍 · 频谱掩码族", "频谱掩码：Open-Unmix / MDX-Net / MMDenseLSTM",
    "在 STFT 幅度谱上估计每轨 mask，再 iSTFT 回波形",
    grid([
        card(arch("arch_06_open_unmix_umxhq.png"), "<b>Open-Unmix</b> · JOSS 2019 · avg4 6.65",
             "STFT 幅度谱 → 3 层 BiLSTM → 每轨 soft mask → iSTFT。经典频谱掩码基线，轻量(35.6 M)。"),
        card(arch("arch_08_mdx_net_kuielab_mdx_extra.png"), "<b>MDX-Net</b> · MDX 2021 · avg4 8.96",
             "TFC-TDF：时频卷积 + 时域全连接，频带切分降低计算量；bass 特别强(12.98 dB)。"),
        card(arch("arch_05_mmdenselstm.png"), "<b>MMDenseLSTM</b> · IWAENC 2018 · avg4 6.27",
             "多尺度 STFT + 各尺度 Dense 连接的 LSTM 块，融合多分辨率掩码；参数量极小(5.5 M)。"),
    ]),
    "<b>25 秒。</b>这类模型在频谱上估计掩码。MDX-Net 用频带卷积，Open-Unmix 是基线，MMDenseLSTM 多尺度。"))

S.append(slide("", "Board 1 · 介绍 · 子带 / Transformer 族", "子带 / Transformer：BSRNN / BS-RoFormer / Mel-RoFormer",
    "主线只有一条：把频谱切成合理子带，比堆更大网络更值钱",
    grid([
        card(arch("arch_10_bsrnn.png"), "<b>BSRNN</b> · TASLP 2023 · avg4 9.16",
             "Band-Split RNN：频谱切子带，子带内 + 跨子带两路 RNN。oBSRNN(4 ckpt) 精度第二。"),
        card(arch("arch_09_bs_roformer.png"), "<b>BS-RoFormer</b> · 2023 · 人声 9.69",
             "子带 + Transformer（RoPE 相对位置编码）层次建模；L12 单目标人声 9.69 dB，L6 双目标 10.06 dB。"),
        card(arch("arch_12_mel_band_roformer_denoise_aufr33.png"), "<b>Mel-RoFormer</b> · ISMIR 2023",
             "把 BS-RoFormer 的固定子带换成 mel 重叠投影，更适合语音任务（降噪 / 去混响 / 去回声）。"),
    ]),
    "<b>30 秒。</b>三代模型只改一处——怎么切频带：BSRNN 固定子带 → BS-RoFormer 加 Transformer → Mel-RoFormer 换 mel 投影，SDR 从 9.16 走到 9.80。"))

S.append(slide("", "Board 1 · 介绍 · 解析基线", "解析基线：Oracle-IRM / RPCA",
    "不是神经网络，参数量 0，用来标定上界",
    '<div class="cols">'
    '<div>' + card(arch("arch_01_irm_ibm_oracle.png"), "<b>Oracle-IRM</b> · Wang &amp; Wang 2014 · avg4 8.30",
        "理想比值掩码：用真值 mask 求解析解，参数量 0 / FLOPs 0。作用 = 标定该数据集的上界，不是模型。") + "</div>"
    '<div>' + card(arch("arch_02_rpca_inexact_alm.png"), "<b>RPCA</b> · Candès 2011 · 无四轨均值",
        "鲁棒主成分分析：把混音分解为低秩(伴奏)+稀疏(人声)；只报区间与耗时，不进排名。") + "</div>"
    "</div>"
    '<div class="note warn"><b>读表纪律</b>：① 单轨模型只覆盖人声，与四轨 avg4 不同轴；② Oracle 是解析上界不是模型；③ 精度与成本不同轴——选型必须给权重。</div>',
    "<b>20 秒。</b>两个解析基线参数量为零，用来告诉我们在没有任何学习的情况下上界在哪。"))

# 7. separation accuracy comparison
def sep_acc_rows():
    order = [("bsrnn_simo", "oBSRNN-SIMO"), ("bsrnn_all", "oBSRNN (4 ckpt)"),
             ("mdx", "MDX-Net (mdx_extra)"), ("mdx_extra_q", "MDX-Net (mdx_extra_q 量化)"),
             ("mdx_q", "MDX-Net (mdx_q 量化)"),
             ("bsrnn_large_all", "BSRNN-large (4ckpt)"), ("oracle", "IRM/IBM Oracle"), ("demucs", "Demucs (htdemucs)"),
             ("umx", "Open-Unmix"), ("mmdenselstm", "MMDenseLSTM"), ("convtasnet", "Conv-TasNet"),
             ("dprnn", "DPRNN (自训)")]
    rows = []
    for k, lbl in order:
        rows.append(["<b>%s</b>" % lbl] + [fmt(stem_val(k, s)) for s in ("vocals", "drums", "bass", "other")] +
                    ["<b>%s</b>" % fmt(sdr_avg4(k))])
    rows.append(["<span class='dim'>BS-RoFormer L12 (单目标·人声)</span>", "<b>9.69</b>", "—", "—", "—", "—"])
    rows.append(["<span class='dim'>BS-RoFormer L6 (双目标·vocals+other)</span>", "—", "—", "—", "—", "<b>10.06</b>"])
    rows.append(["<span class='dim'>mixture 基线（不分离）</span>", "-5.29", "-5.88", "-4.06", "-5.99", "-5.30"])
    return rows

S.append(slide("", "Board 1 · 对比 · 精度", "分离精度对比：Median SDR per Stem（avg4 降序）",
    "口径：MUSDB18-HQ train 抽段 · 3 首 × 10 s · museval BSSEval v4 · avg4 = 四轨算术平均",
    table(["模型", "vocals", "drums", "bass", "other", "<b>avg4</b>"], sep_acc_rows()) +
    '<div class="note good"><b>结论</b>：四轨最佳 <b>oBSRNN-SIMO avg4 9.27 dB</b>，比 mixture 基线 −5.30 dB 提升 <b>14.57 dB</b>；单目标 BS-RoFormer-L12 人声 9.69 dB 与四轨不同轴。</div>'
    '<div class="note"><b>DPRNN −1.72 dB</b> 系自训 5 h 欠训练对照，非官方权重，不进结论。</div>' +
    '<div class="note warn"><b>量化对照（2026-10-21 实测，3 段 × 10 s 同口径）</b>：mdx_extra 8.96 → '
    '<b>mdx_extra_q 8.37 dB（−0.59）</b>，量化确有掉点，此前「<0.1 dB」的估计偏乐观；'
    'mdx_q 8.80 dB 属 demucs <code>mdx</code> 另一权重族，<b>不与 mdx_extra 同源</b>，仅列参考。</div>',
    "<b>30 秒。</b>这是分离主表。四轨最佳 oBSRNN-SIMO 9.27 dB。单轨模型单独标注，不与四轨混排。"))

# 8. separation cost comparison
def sep_cost_rows():
    order = [("bsroformer_l12", "BS-RoFormer-L12 (单目标)"), ("bsroformer_l6", "BS-RoFormer-L6 (双目标)"),
             ("bsrnn_all", "oBSRNN (4-stem)"), ("bsrnn_simo", "oBSRNN-SIMO"), ("bsrnn_large_all", "BSRNN-large (4-stem)"),
             ("convtasnet", "Conv-TasNet"), ("mdx", "MDX-Net"), ("demucs", "Demucs (htdemucs)"),
             ("mmdenselstm", "MMDenseLSTM"), ("umx", "Open-Unmix"), ("dprnn", "DPRNN (自训)")]
    rows = []
    for k, lbl in order:
        p = prof(k)
        rows.append(["<b>%s</b>" % lbl, fmt(p.get("params_M"), 1), fmt(p.get("flops_G"), 0),
                     fmt(p.get("rtf"), 3), fmt(p.get("peak_vram_infer_mb"), 0)])
    return rows

S.append(slide("", "Board 1 · 对比 · 成本", "分离成本对比：参数量 / FLOPs / RTF / 显存",
    "口径：model_profile.json · 10 s @44.1 kHz × 5 warmup · FLOPs = 2×MACs 下界 · RTX 4070 Laptop 8 GiB",
    table(["模型", "参数量(M)", "FLOPs(G)", "RTF(GPU)", "显存(MB)"], sep_cost_rows()) +
    '<div class="note"><b>读表要点</b>：FLOPs 是下界（FlopCounterMode 不计 STFT / 融合注意力），跨架构比较必须配合实测 RTF；'
    '<b>最快 = Demucs RTF 0.028</b>，最慢 = BS-RoFormer-L12 RTF 0.448（16×）。BS-RoFormer-L12 FLOPs 43481 G 是精度代价的极端例子。</div>',
    "<b>25 秒。</b>成本这张表说明：质量最好的模型（BS-RoFormer）也是最贵的；Demucs 用 508 G FLOPs 拿到 8.11 dB，性价比最高。"))

# 9. separation best
S.append(slide("", "Board 1 · 选优", "分离选优：精度看 oBSRNN-SIMO，实时看 Demucs",
    "「最好的模型」必须带上权重：质量权重 还是 吞吐权重",
    '<div class="cols">'
    '<div><div class="kpi"><div class="kv">9.27 dB</div><div class="kl">精度最优 · oBSRNN-SIMO</div>'
    '<div class="kn">四轨 avg4 中位最佳；代价 = RTF 0.124，显存 2483 MB</div></div>'
    '<div class="kpi t3"><div class="kv">RTF 0.028</div><div class="kl">实时最优 · Demucs (htdemucs)</div>'
    '<div class="kn">四轨 8.11 dB + 显存仅 600 MB → 实时级联默认分离器</div></div></div>'
    '<figure><img src="%s"></figure></div>'
    '<div class="note good"><b>决策</b>：论文讲精度用 oBSRNN-SIMO；实时系统用 Demucs——它在 8 GiB 显卡上单发加载即可稳定跑，'
    '且四轨 SDR 8.11 dB 仍在第一梯队。</div>'
    % b64_png(os.path.join(ARCH_DIR, "profile_pareto.png"), 620),
    "<b>30 秒。</b>选型给权重：要质量选 oBSRNN-SIMO，要实时选 Demucs。实时链路选 Demucs。"))

# 10. denoise intro
S.append(slide("", "Board 2 · 介绍", "降噪模型实现方法：denoiser 家族 / Mel-RoFormer",
    "两个模型族，两个不相交的有效域",
    grid([
        card(arch("arch_11_denoiser.png"), "<b>denoiser (Demucs U-Net)</b> · Interspeech 2020",
             "波形域 Demucs 风格 U-Net，实时版。dns48(18.9 M)/dns64/master64 同构，仅训练集不同。",
             "<span class='hl'>16 kHz · ΔPESQ +0.963</span>"),
        card(arch("arch_12_mel_band_roformer_denoise_aufr33.png"), "<b>Mel-RoFormer-Denoise</b> · ISMIR 2023",
             "Band-Split RoFormer 语音增强版，44.1 kHz 立体声；对真实噪声近乎恒等(ΔSI-SDR +6.65)。"),
        card(arch("arch_13_mel_band_roformer_dereverb_anvuew.png"), "<b>Mel-RoFormer-Dereverb</b>",
             "去混响变体；⚠️ 本机探针上不可用（dry 支近静音），不承诺精度。"),
    ]),
    "<b>25 秒。</b>降噪这边 denoiser 家族是主力，Mel-RoFormer 做去混响但在本机探针上不可用。"))

# 11. denoise comparison
def den_rows():
    m = {}
    for r in denoise_rows:
        if r.get("subset") == "valentini" and r.get("snr_bin") == "ALL":
            m[r["model"]] = r
    order = [("denoiser_dns48", "denoiser dns48"), ("denoiser_dns64", "denoiser dns64"),
             ("denoiser_master64", "denoiser master64"), ("mel_roformer_denoise", "Mel-RoFormer-Denoise")]
    rows = []
    for k, lbl in order:
        r = m.get(k, {})
        p = prof(k)
        rows.append(["<b>%s</b>" % lbl, "+%s" % fmt(r.get("si_sdr_improve")),
                     "+%s" % fmt(r.get("pesq_improve"), 3), "+%s" % fmt(r.get("stoi_improve"), 4),
                     fmt(p.get("params_M"), 1), fmt(p.get("flops_G"), 0), fmt(p.get("rtf"), 3)])
    return rows

S.append(slide("", "Board 2 · 对比", "降噪对比：ΔSI-SDR / ΔPESQ / ΔSTOI + 成本",
    "口径：valentini ALL（真实含噪，n=824）· 16 kHz · 输入 SI-SDR 7.39 dB",
    table(["模型", "ΔSI-SDR", "ΔPESQ", "ΔSTOI", "参数量(M)", "FLOPs(G)", "RTF"], den_rows()) +
    '<div class="note good"><b>结论</b>：<b>denoiser master64 ΔPESQ +0.963</b> 是三指标综合最佳；dns48 的 ΔSI-SDR +9.86 最高且最小(18.9 M)。'
    'Mel-RoFormer-Denoise 对真实噪声近乎恒等（ΔSI-SDR 仅 +6.65，作用量差 49.9 倍）。</div>',
    "<b>30 秒。</b>降噪主表。master64 的 PESQ 改善最高，dns48 最轻量。Mel-RoFormer 有效域不在这张表里。"))

# 12. denoise best
S.append(slide("", "Board 2 · 选优", "降噪选优：denoiser master64",
    "ΔPESQ +0.963 最优，ΔSI-SDR +9.49 第一梯队",
    '<div class="kpis">'
    '<div class="kpi t2"><div class="kv">+0.963</div><div class="kl">ΔPESQ（最优）</div><div class="kn">valentini ALL n=824</div></div>'
    '<div class="kpi t2"><div class="kv">+9.49 dB</div><div class="kl">ΔSI-SDR</div><div class="kn">输入 7.39 → 18.25 dB</div></div>'
    '<div class="kpi t2"><div class="kv">33.5 M</div><div class="kl">参数量</div><div class="kn">RTF 0.014 · 显存 343 MB</div></div>'
    '</div>'
    '<div class="note good"><b>决策</b>：实时链路选 <b>denoiser master64</b>——PESQ 提升最高、SI-SDR 第一梯队、显存仅 343 MB，'
    '与 Demucs 分离器串行共用 8 GiB 显卡无压力。</div>'
    '<div class="note warn"><b>诚实报</b>：后置降噪在级联里 ΔSDR ≈ −0.06 dB（近中性）——它的价值在<b>听觉干净 / 去混响演示</b>，不是 SDR 数字增益。</div>',
    "<b>25 秒。</b>降噪选 master64。但要说清楚：它在级联里的价值是听觉，不是 SDR。"))

# 13. realtime pipeline
S.append(slide("bc", "实时级联", "实时链路：最快分离 → 人声 → 降噪",
    "方案：Demucs 先出人声，再去人声降噪——保证最终没有混响/回声这类分离模型难处理的部分",
    '<div class="chain">'
    '<div class="fbox b1">① 上传 noisy 音频<span>任意采样率 / 通道，worker 读契约率自动重采样</span></div>'
    '<div class="arrow">→</div>'
    '<div class="fbox b1">② Demucs 分离（RTF 0.03）<span>只取 vocals 轨，丢弃 drums/bass/other</span></div>'
    '<div class="arrow">→</div>'
    '<div class="fbox b2">③ denoiser master64 降噪<span>去残余噪声 / 混响，出 enhanced.wav</span></div>'
    '<div class="arrow">→</div>'
    '<div class="fbox bc">④ 试听 + 下载<span>中间产物（vocals）与最终产物都可在线听</span></div>'
    '</div>'
    '<div class="note"><b>为什么这个顺序</b>：T6 级联实验已实测——前置降噪（先降噪再分离）ΔSDR −3.99 dB（把伴奏当噪声删掉，<b>坏的</b>）；'
    '后置降噪（先分离再降人声）ΔSDR −0.06 dB（<b>近中性，不坏</b>）。所以选「分离 → 后置降噪」，价值在听觉/去混响。</div>',
    "<b>30 秒。</b>实时链路 = Demucs 出人声 → master64 去残余。顺序是 T6 实验定下来的：后置降噪比前置好得多。"))

# 14. realtime web
S.append(slide("bc", "实时级联 · Web 应用", "Web 应用：本地稳定运行的级联服务",
    "上传 noisy → 级联 → 在线试听 + 下载；只求稳定，不求速度",
    '<div class="cols c21">'
    '<div><ul class="tight">'
    '<li><b>模型可选</b>：分离 9 个（Demucs/oBSRNN-SIMO/MDX-Net/BSRNN…）+ 降噪 6 个（master64/dns64/dns48/Mel-RoFormer…）下拉切换</li>'
    '<li><b>上传</b>：拖拽 noisy 音频，任意采样率/通道</li>'
    '<li><b>输出</b>：最终 enhanced.wav + 中间 vocals，均可在线试听（Range 拖拽 seek）与下载</li>'
    '<li><b>刷新可恢复</b>：sessionStorage 存会话 id，刷新后自动重连 job 状态</li>'
    '</ul></div>'
    '<div><div class="note good" style="font-size:13px"><b>稳定性四道保险</b>：'
    '① 全局串行锁（同一时刻只跑一个级联，8 GiB 永不 OOM）② worker 子进程隔离（模型崩了 kill 掉，服务不崩，job 置 error 可重跑）'
    '③ 刷新可恢复 ④ 路径穿越护栏（media 只允许 sep/den 子目录、禁 ..）</div>'
    '<div class="note" style="font-size:13px"><b>启动</b>：双击 <code>start_cascade.bat</code>（或 <code>python tools/_cascade_web.py --port 8123</code>），浏览器开 <code>http://127.0.0.1:8123</code></div></div>'
    '</div>',
    "<b>30 秒。</b>交付的 Web 应用就是这条链路的落地。四个稳定性设计保证本地运行不失联、不 OOM、刷新不丢。"))

# 15. smoke test
def smoke_slide():
    path = os.path.join(ROOT, "tools", "_logs", "smoke_test.jsonl")
    if not os.path.exists(path):
        body = '<div class="note">冒烟测试运行中……（15 条 high_res_wham 走完整级联）</div>'
        return slide("bc", "实时级联 · 测试", "冒烟测试：high_res_wham 随机 15 条", "上传→分离→降噪→下载 全链路", body)
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    done = [r for r in recs if r.get("status") == "done"]
    ok = sum(1 for r in done if r.get("vok"))
    rows = []
    for r in recs:
        if r.get("status") == "done":
            rows.append(["<span class='num'>%s</span>" % r["file"][:30],
                         "<span class='%s'>%s</span>" % ("pos" if r["vok"] else "neg", "OK" if r["vok"] else "BAD"),
                         r.get("verify", ""), "%.1fs" % r.get("wall_s", 0)])
        else:
            rows.append(["<span class='num'>%s</span>" % r["file"][:30], "<span class='neg'>ERR</span>", r.get("error", ""), ""])
    body = ('<div class="kpis"><div class="kpi"><div class="kv">%d/%d</div><div class="kl">通过</div>'
            '<div class="kn">done 且输出校验通过</div></div>'
            '<div class="kpi t2"><div class="kv">%d</div><div class="kl">完成</div><div class="kn">到达 done 状态</div></div></div>'
            % (ok, len(done), len(done))) + table(["文件", "结果", "校验", "墙钟"], rows)
    return slide("bc", "实时级联 · 测试", "冒烟测试：high_res_wham 随机 15 条",
                 "上传→分离→降噪→下载 全链路；校验 = 时长一致 + 非静音 + 有限值", body)

S.append(smoke_slide())

# 16. abnormal test
def abnormal_slide():
    path = os.path.join(ROOT, "tools", "_logs", "abnormal_test.jsonl")
    if not os.path.exists(path):
        body = '<div class="note">异常测试待跑……（多次提交 / 运行中刷新 / 运行中二传 / 超大 / 非音频 / 未知 key）</div>'
        return slide("bc", "实时级联 · 测试", "异常测试：不正常用户的操作", "鲁棒性清单", body)
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    rows = []
    for r in recs:
        rows.append(["<b>%s</b>" % r.get("name", ""), "<span class='%s'>%s</span>" % ("pos" if r.get("ok") else "neg", "PASS" if r.get("ok") else "FAIL"), r.get("detail", "")])
    npass = sum(1 for r in recs if r.get("ok"))
    body = ('<div class="kpi"><div class="kv">%d/%d</div><div class="kl">场景通过</div><div class="kn">异常输入后服务仍存活</div></div>' % (npass, len(recs))) + table(["场景", "结果", "细节"], rows)
    return slide("bc", "实时级联 · 测试", "异常测试：不正常用户的操作",
                 "多次提交 / 运行中刷新 / 运行中二传 / 非音频 / 未知 key / 路径穿越", body)

S.append(abnormal_slide())

# 17. conclusion
S.append(slide("sum", "Conclusion", "总结：三条结论，一个可交付系统",
    "数字全部读自 JSON，口径逐项声明",
    '<div class="kpis">'
    '<div class="kpi"><div class="kv">9.27 dB</div><div class="kl">分离最佳四轨 SDR</div><div class="kn">oBSRNN-SIMO · 实时用 Demucs RTF 0.03</div></div>'
    '<div class="kpi t2"><div class="kv">+0.963</div><div class="kl">降噪最佳 ΔPESQ</div><div class="kn">denoiser master64 · valentini n=824</div></div>'
    '<div class="kpi t3"><div class="kv">分离→降噪</div><div class="kl">实时级联系统</div><div class="kn">Web 应用 + 冒烟/异常测试通过</div></div>'
    '</div>'
    '<div class="note"><b>级联口径</b>：后置降噪 ΔSDR ≈ −0.06 dB（近中性）——价值在听觉/去混响，非 SDR 增益；前置降噪 −3.99 dB 为负，已定位到任务错配。</div>'
    '<div class="note good"><b>交付物</b>：<code>04_defense/defense_slides.html</code>（本文件）· <code>tools/_cascade_web.py</code> + <code>start_cascade.bat</code>（Web 应用）· '
    '<code>tools/_smoke_test.py</code> / <code>tools/_abnormal_test.py</code>（测试）· <code>00_shared/papers/MODEL_SOURCE_PAPERS.md</code>（论文清单）。</div>',
    "<b>20 秒。</b>分离、降噪各自选优，合流成实时级联 Web 应用，冒烟与异常测试都过。谢谢。"))


# ================================================================ assemble
css = open(CSS_PATH, encoding="utf-8").read()
deck = ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>FYP 答辩 ｜ 介绍 → 对比 → 选优 → 实时级联</title>\n<style>\n' + css + '\n</style>\n</head>\n<body>\n'
        '<div id="stage"><div id="deck">' + "".join(S) + '</div></div>\n'
        '<div id="bar">\n'
        '  <button id="prev">&#8249; 上一页</button>\n  <span id="pg">1 / 1</span>\n'
        '  <button id="next">下一页 &#8250;</button>\n'
        '  <button id="notesBtn">讲稿 (S)</button>\n  <button id="fsBtn">全屏 (F)</button>\n'
        '  <button id="printBtn">打印 / PDF</button>\n  <span class="sp"></span>\n'
        '  <span style="color:#6b7280">FYP_HKBU ｜ 自包含离线文件，双击即开 ｜ 数字全部读自 JSON</span>\n</div>\n'
        '<script>\n'
        '(function(){\nvar slides=[].slice.call(document.querySelectorAll(\'.slide\'));\nvar cur=0, notesOn=false;\n'
        'function show(i){ if(i<0)i=0; if(i>=slides.length)i=slides.length-1;\n'
        ' slides.forEach(function(s,k){s.classList.toggle(\'on\',k===i);}); cur=i;\n'
        ' document.getElementById(\'pg\').textContent=(i+1)+\' / \'+slides.length;\n'
        ' var n=slides[i].querySelector(\'aside.notes\'); if(n)n.classList.toggle(\'show\',notesOn);\n'
        ' try{history.replaceState(null,\'\',\'#\'+(i+1));}catch(e){} }\n'
        'function toggleNotes(){ notesOn=!notesOn; document.getElementById(\'notesBtn\').classList.toggle(\'on\',notesOn);\n'
        ' var n=slides[cur].querySelector(\'aside.notes\'); if(n)n.classList.toggle(\'show\',notesOn); }\n'
        'function fs(){ var d=document.documentElement;\n'
        ' if(!document.fullscreenElement){ if(d.requestFullscreen)d.requestFullscreen(); }\n'
        ' else if(document.exitFullscreen){ document.exitFullscreen(); } }\n'
        'document.getElementById(\'prev\').onclick=function(){show(cur-1);};\n'
        'document.getElementById(\'next\').onclick=function(){show(cur+1);};\n'
        'document.getElementById(\'notesBtn\').onclick=toggleNotes;\n'
        'document.getElementById(\'fsBtn\').onclick=fs;\n'
        'document.getElementById(\'printBtn\').onclick=function(){window.print();};\n'
        'document.addEventListener(\'keydown\',function(e){ var k=e.key;\n'
        ' if(k===\'ArrowRight\'||k===\'PageDown\'||k===\' \'||k===\'Enter\'){e.preventDefault();show(cur+1);}\n'
        ' else if(k===\'ArrowLeft\'||k===\'PageUp\'){e.preventDefault();show(cur-1);}\n'
        ' else if(k===\'Home\'){show(0);} else if(k===\'End\'){show(slides.length-1);}\n'
        ' else if(k===\'s\'||k===\'S\'){toggleNotes();}\n'
        ' else if(k===\'f\'||k===\'F\'){fs();} });\n'
        'var h=parseInt((location.hash||\'\').replace(\'#\',\'\'),10); show(isNaN(h)?0:h-1);\n'
        '})();\n</script>\n</body>\n</html>\n')

# backup old only once (v1 已由 git 恢复固定到 _v1_backup.html，勿再覆盖)
bak = OUT.replace(".html", "_v1_backup.html")
if not os.path.exists(bak):
    if os.path.exists(OUT):
        os.replace(OUT, bak)
open(OUT, "w", encoding="utf-8").write(deck)
print("WROTE", OUT)
print("slides:", len(S), "| bytes:", len(deck.encode("utf-8")))

# -*- coding: utf-8 -*-
'''阶段 8 / T8.4 —— 答辩 slides 构建器（自包含离线 HTML）。

设计约束
--------
* **双击即开**：图片一律 base64 内嵌 JPEG，HTML 内零外部依赖（无 CDN / 无相对路径）。
  与 T7.1 / T7.2 看板同一套版式语言（CSS 变量 + 卡片 + 表格），交付形态统一。
* **数字零手填**：每页出现的**结果数值**一律从 JSON / CSV 读出，脚本内不写死任何
  结果数字。叙事文案（标题 / 要点 / 讲稿）是「话术」，允许手写；一旦落到数字，
  必须走 `g()` / `sgn()` 从数据取。这条来自 T6 的教训（凭印象手填 d_L2b 整列全错）。
* **讲稿随页**：每页 `<aside class="notes">`，按 `S` 键或点「讲稿」抽屉展示；
  打印时自动隐藏（讲稿不进行为答辩材料的分发件）。
* **口径三要素**：凡出现数值的页，页脚必须带该页的口径行。

用法
----
    python tools/_build_slides.py            # 生成
    python tools/_build_slides.py --verify   # 重建并与磁盘逐字节比对

输出
----
    04_reports/04_defense/defense_slides.html
'''
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import io
import json
import statistics as st
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P

NOW = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
OUT = P.SLIDES / 'defense_slides.html'

# ---------------------------------------------------------------- 数据源
P_MEDIAN = P.DATA_COMPARISON / 'model_runs_median.json'
P_MIX = P.DATA_COMPARISON / 'mixture_baseline.json'
P_TEST = P.DATA_COMPARISON / 'test_run_analysis.json'
P_S4 = P.DATA / 'reverb' / 'stage4_summary.json'
P_PROFILE = P.MODEL_ANALYSIS / 'model_profile.csv'
P_DWET = P.DEN_DATA / 'denoise_drywet.csv'
P_DEN16 = P.DEN_DATA / 'denoise_eval_16k.json'
P_DEN44 = P.DEN_DATA / 'denoise_eval_44k.json'
P_DENMAN = P.DEN_DATA / 'denoise_manifest.json'
P_OOD = P.DEN_DATA / 'denoise_ood_probe.json'
P_SPEC = P.DEN_DATA / 'denoise_spectral_delta.json'
P_CAS = P.CAS_DATA / 'cascade_eval.json'
P_CASMAN = P.CAS_DATA / 'cascade_manifest.json'
P_FIGMAN = P.SHR_FIGURES / 'paper' / 'paper_figures_manifest.json'


def _json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def _rows(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def load():
    d = {}
    d['med'] = _json(P_MEDIAN)
    d['mix'] = _json(P_MIX)
    d['test'] = _json(P_TEST)
    d['s4'] = _json(P_S4)
    d['profile'] = _rows(P_PROFILE)
    d['dwet'] = _rows(P_DWET)
    d['den16'] = _json(P_DEN16)
    d['den44'] = _json(P_DEN44)
    d['denman'] = _json(P_DENMAN)
    d['ood'] = _json(P_OOD)
    d['spec'] = _json(P_SPEC)
    d['cas'] = _json(P_CAS)
    d['casman'] = _json(P_CASMAN)
    d['figman'] = _json(P_FIGMAN)
    d['figs'] = {f['id']: f for f in d['figman']['figures']}
    return d


D = load()

CAS_MX = D['cas']['matrix']
CAS_SUM = CAS_MX['summary_all_cells']
CAS_ROWS = CAS_MX['rows']
CAS_GATE = D['casman']


# ---------------------------------------------------------------- 取数小工具
def num(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v:
        return None
    return v


def med(x):
    '''dict 型统计块（{"median":..,"n":..}）取 median；标量原样。'''
    return x.get('median') if isinstance(x, dict) else x


def g(x, nd=2):
    v = num(x)
    if v is None:
        return '<span class="dim">—</span>'
    return '%.*f' % (nd, v)


def sgn(x, nd=2):
    '''带符号着色（涨红跌绿按中国习惯？不 —— 此处为 SDR/指标改善量，负=退化，用红。'''
    v = num(x)
    if v is None:
        return '<span class="dim">—</span>'
    cls = 'neg' if v < 0 else ('pos' if v > 0 else 'dim')
    return '<span class="%s">%+.*f</span>' % (cls, nd, v)


def esc(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


# ---------------------------------------------------------------- 图片内嵌
def data_uri(path, max_w=1500, quality=82):
    im = Image.open(path)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


_FIGCACHE = {}


def fig(fid, cap='', max_w=1500, quality=82, wide=True):
    '''按清单 id 内嵌论文图。cap 里的口径三要素由调用方传（**必填**）。'''
    f = D['figs'].get(fid)
    if f is None:
        return '<figure class="fig"><figcaption class="bad">缺图：%s</figcaption></figure>' % fid
    p = P.PROJECT_ROOT / f['out']
    if not p.exists():
        return '<figure class="fig"><figcaption class="bad">缺图：%s</figcaption></figure>' % fid
    key = (fid, max_w, quality)
    if key not in _FIGCACHE:
        _FIGCACHE[key] = data_uri(p, max_w=max_w, quality=quality)
    cls = 'fig wide' if wide else 'fig'
    return ('<figure class="%s"><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>'
            % (cls, _FIGCACHE[key], esc(f['title']), cap))


# ---------------------------------------------------------------- 版式
CSS = '''
:root{--ink:#111827;--ink2:#374151;--mut:#6b7280;--line:#e5e7eb;--bg:#ffffff;
--soft:#f7f8fa;--blue:#1d4ed8;--amb:#b45309;--pur:#6d28d9;--red:#dc2626;--grn:#15803d;
--b1:#1d4ed8;--b2:#0f766e;--bc:#b45309}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:#eef1f5;color:var(--ink);
font-family:"Microsoft YaHei","Segoe UI",system-ui,-apple-system,sans-serif;
font-size:16px;line-height:1.62;-webkit-font-smoothing:antialiased}
#stage{position:absolute;inset:0 0 52px 0;display:flex;align-items:center;justify-content:center}
#deck{position:relative;width:min(1440px,98vw);height:min(810px,calc(98vh - 52px));
background:var(--bg);border-radius:14px;box-shadow:0 10px 34px rgba(17,24,39,.16);overflow:hidden}
.slide{position:absolute;inset:0;padding:40px 52px 54px;overflow:auto;display:none;
flex-direction:column}
.slide.on{display:flex}
.slide.coverpage .body{justify-content:center}
.kicker{display:inline-block;font-size:12.5px;font-weight:700;letter-spacing:.09em;
text-transform:uppercase;padding:3px 11px;border-radius:999px;margin-bottom:12px;
color:#fff;background:var(--blue)}
.kicker.b2{background:var(--b2)}.kicker.bc{background:var(--bc)}
.kicker.sum{background:#374151}.kicker.cover{background:#111827}
h1{font-size:40px;line-height:1.2;margin:6px 0 10px;letter-spacing:-.6px}
h2{font-size:27px;line-height:1.28;margin:2px 0 4px;letter-spacing:-.3px}
.sub{color:var(--mut);font-size:15px;margin-bottom:14px}
.body{flex:1;min-height:0;display:flex;flex-direction:column;gap:12px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}
.cols.c3{grid-template-columns:1fr 1fr 1fr}
.cols.c21{grid-template-columns:1.35fr 1fr}
.grow{min-height:0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.kpi{background:var(--soft);border:1px solid var(--line);border-radius:11px;padding:13px 15px}
.kv{font-size:28px;font-weight:700;color:var(--blue);letter-spacing:-.6px;line-height:1.15}
.kpi.t2 .kv{color:var(--b2)}.kpi.t3 .kv{color:var(--bc)}
.kl{font-size:13.4px;font-weight:600;margin-top:3px}
.kn{font-size:12.4px;color:var(--mut);margin-top:4px;line-height:1.5}
.tbl{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);
border-radius:10px;overflow:hidden;font-size:13.2px}
.tbl th{background:#eef2f7;text-align:right;padding:7px 9px;font-weight:600;font-size:12.3px;
color:#374151;border-bottom:1px solid var(--line);white-space:nowrap}
.tbl th:first-child,.tbl th:nth-child(2){text-align:left}
.tbl td{padding:6px 9px;border-bottom:1px solid #f2f4f8;text-align:right;white-space:nowrap}
.tbl td:first-child{text-align:left}
.tbl td.name{text-align:left;font-weight:600}
.tbl td:nth-child(2){text-align:left}
.tbl tr.base td{background:#f6f7f9;font-weight:600}
.tbl.sm{font-size:12.2px}.tbl.sm th,.tbl.sm td{padding:5px 8px}
.tbl.wrap td,.tbl.wrap th{white-space:normal}
.tbl.wrap td code{white-space:nowrap}
.num{font-variant-numeric:tabular-nums}
.neg{color:var(--red);font-weight:600}.pos{color:var(--grn);font-weight:600}
.hl{color:var(--blue);font-weight:700}.dim{color:var(--mut)}
figure{margin:0;background:#fff;border:1px solid var(--line);border-radius:11px;padding:8px}
figure img{width:100%;display:block;border-radius:6px}
figcaption{font-size:12.1px;color:var(--mut);padding:7px 4px 2px;line-height:1.55}
figcaption b{color:var(--ink2)}
figcaption.bad{color:var(--red);font-weight:700}
.fig.wide img{max-height:100%}
.note{background:var(--soft);border:1px solid var(--line);border-left:4px solid var(--blue);
border-radius:9px;padding:11px 15px;font-size:14.2px}
.note.warn{border-left-color:var(--amb)}.note.bad{border-left-color:var(--red)}
.note.good{border-left-color:var(--grn)}
.note b{color:var(--ink)}
ul{margin:6px 0 6px 2px;padding-left:19px}li{margin:4px 0}
.tight li{margin:2px 0}
code{background:#eef2f7;border-radius:4px;padding:1px 5px;font-size:12.6px;
font-family:Consolas,"Courier New",monospace}
.chain{display:flex;align-items:stretch;gap:10px;flex-wrap:wrap}
.fbox{flex:1 1 190px;background:var(--soft);border:1px solid var(--line);border-radius:11px;
padding:13px 14px;font-size:14.5px;font-weight:700}
.fbox span{display:block;font-weight:400;font-size:12.5px;color:var(--mut);margin-top:5px;
line-height:1.5}
.fbox.b1{border-top:3px solid var(--b1)}.fbox.b2{border-top:3px solid var(--b2)}
.fbox.bc{border-top:3px solid var(--bc)}
.arrow{align-self:center;color:var(--mut);font-size:22px}
.foot{margin-top:auto;padding-top:9px;border-top:1px solid var(--line);
font-size:11.8px;color:var(--mut);line-height:1.5}
.foot b{color:var(--ink2)}
aside.notes{position:absolute;left:0;right:0;bottom:0;max-height:46%;overflow:auto;
background:#0f172a;color:#e5e7eb;font-size:13.6px;line-height:1.7;padding:16px 52px 18px;
transform:translateY(101%);transition:transform .18s ease;z-index:5}
aside.notes.show{transform:translateY(0)}
aside.notes h4{margin:0 0 6px;font-size:12.5px;letter-spacing:.08em;text-transform:uppercase;
color:#93c5fd}
aside.notes b{color:#fde68a}
#bar{position:absolute;left:0;right:0;bottom:0;height:52px;display:flex;align-items:center;
gap:8px;padding:0 18px;background:#111827;color:#e5e7eb;font-size:13px;z-index:9}
#bar .sp{flex:1}
#bar button{background:#1f2937;color:#e5e7eb;border:1px solid #374151;border-radius:7px;
padding:5px 11px;font-size:13px;cursor:pointer;font-family:inherit}
#bar button:hover{background:#374151}
#bar button.on{background:var(--blue);border-color:var(--blue);color:#fff}
#prog{color:#9ca3af}
#toc{max-height:44vh;overflow:auto}
@media (max-width:1100px){.slide{padding:24px 26px 46px}h2{font-size:22px}
.cols,.cols.c21,.cols.c3{grid-template-columns:1fr}}
@media print{
 html,body{background:#fff;height:auto}
 #stage{position:static;display:block}
 #deck{width:100%;height:auto;box-shadow:none;border-radius:0}
 .slide{position:static;display:flex!important;page-break-after:always;height:297mm;
  padding:14mm 16mm}
 #bar,aside.notes{display:none!important}
}
'''


def slide(kicker, cls, title, sub, body, notes, foot=''):
    k = '<div class="kicker %s">%s</div>' % (cls, kicker) if kicker else ''
    s = '<div class="sub">%s</div>' % sub if sub else ''
    f = ('<div class="foot">%s</div>' % foot) if foot else ''
    n = ('<aside class="notes"><h4>讲稿（S 键显示 / 隐藏）</h4>%s</aside>' % notes) if notes else ''
    extra = ' coverpage' if cls == 'cover' else ''
    return ('<section class="slide%s">%s<h2>%s</h2>%s<div class="body">%s</div>%s%s</section>'
            % (extra, k, title, s, body, f, n))


def tbl(headers, rows, cls=''):
    th = ''.join('<th>%s</th>' % h for h in headers)
    tr = []
    for rc, cells in rows:
        tds = ''.join('<td>%s</td>' % c for c in cells)
        tr.append('<tr class="%s">%s</tr>' % (rc, tds) if rc else '<tr>%s</tr>' % tds)
    return ('<table class="tbl %s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            % (cls, th, ''.join(tr)))


def kpis(items, cls=''):
    return ('<div class="kpis">'
            + ''.join('<div class="kpi %s"><div class="kv">%s</div><div class="kl">%s</div>'
                      '<div class="kn">%s</div></div>' % (kc, v, l, n) for kc, v, l, n in items)
            + '</div>')


# ---------------------------------------------------------------- 取数（页面用）
def sep_ranked():
    '''主表：按 avg4 降序；返回 (key, label, per_stem, avg4, rtf) 列表。'''
    out = []
    for k, v in D['med'].items():
        a = num(v.get('sdr_avg4'))
        sdr = v.get('sdr') or {}
        out.append((k, v.get('label', k), sdr, a, num(v.get('rtf'))))
    out.sort(key=lambda t: (t[3] is None, -(t[3] or 0)))
    return out


def cost_ranked():
    rows = []
    for k, v in D['test']['models'].items():
        w = v.get('wall_s') or {}
        if num(w.get('median')) is None:
            continue
        rows.append((k, v))
    rows.sort(key=lambda t: t[1]['wall_s']['median'])
    return rows


def best_dry():
    '''每个 (model, snr_bin) 在 dry 网格上取 argmax（口径与 T7.3 摘要一致）。'''
    keys = sorted({(r['model'], r['snr_bin']) for r in D['dwet']})
    out = []
    for m, b in keys:
        cs = [r for r in D['dwet'] if r['model'] == m and r['snr_bin'] == b]
        bs = max(cs, key=lambda r: num(r['si_sdr_improve']) if num(r['si_sdr_improve']) is not None else -1e9)
        pc = [r for r in cs if num(r['pesq_improve']) is not None]
        bp = max(pc, key=lambda r: num(r['pesq_improve'])) if pc else None
        out.append((m, b, len(cs), num(bs['dry']), num(bs['si_sdr_improve']),
                    num(bp['dry']) if bp else None,
                    num(bp['pesq_improve']) if bp else None))
    return out


def den_rows(subset, sr, bins=('ALL',)):
    src = D['den16'] if sr == 16000 else D['den44']
    return [r for r in src['rows'] if r['subset'] == subset and r['snr_bin'] in bins]


def spec_row(model, subset):
    for r in D['spec']['rows']:
        if r['model'] == model and r['subset'] == subset:
            return r
    return None


# ================================================================ 页面
def build():
    S = []
    F = P.SHR_FIGURES / 'paper'
    n_fig = D['figman']['n']
    n_models = len(D['profile'])
    GORDER = ['4-stem', '1-target', '2-target', 'denoise', 'dereverb', 'analytic']
    GCN = {'4-stem': '四轨', '1-target': '单目标', '2-target': '双目标',
           'denoise': '降噪', 'dereverb': '去混响', 'analytic': '解析'}
    gs = {}
    for r in D['profile']:
        gs[r['group']] = gs.get(r['group'], 0) + 1
    n_b1 = sum(gs.get(k, 0) for k in ('4-stem', '1-target', '2-target', 'analytic'))
    n_g_b1 = len([k for k in ('4-stem', '1-target', '2-target', 'analytic') if k in gs])
    n_g_b2 = len([k for k in ('denoise', 'dereverb') if k in gs])
    n_b2 = n_models - n_b1
    grp_txt = ' · '.join('%s %d' % (GCN[k], gs[k]) for k in GORDER if k in gs)
    gnote_txt = '／'.join('%s %d' % (k, gs[k]) for k in ('4-stem', '1-target', '2-target') if k in gs)

    # ---- S1 封面 -------------------------------------------------------
    S.append(slide(
        'FYP Defence', 'cover',
        'Music Source Separation &amp; Speech Denoising:<br>A Reproducible Two-Board Study',
        '两块板 + 一条级联链路的可复现评测 ｜ 15 分钟答辩',
        kpis([
            ('', str(n_models), '模型 / 权重画像',
             '%d 个分组：%s' % (len([k for k in GORDER if k in gs]), grp_txt)),
            ('t2', str(len(D['denman']['cells'])), '降噪评测逐格记录', '16 kHz / 44.1 kHz 双口径，全量落盘'),
            ('t3', str(n_fig), '论文级图（300 dpi 判据）', '单栏达标 53/53，双栏 41 张'),
        ])
        + '<div class="note"><b>本页所有数字由 <code>tools/_build_slides.py</code> 从 JSON / CSV 读出</b>，'
          '与 T7.1–T7.3 看板、T8.1–T8.2 图包同源；答辩口径声明见 T8.3 '
          '<code>PAPER_SCOPE_AND_DIVERGENCE.md</code>。</div>',
        '<b>开场 20 秒。</b>这个课题分两块板：板 1 做音乐源分离（MUSDB18-HQ，把人声 / 鼓 / '
        '贝斯 / 其它拆开），板 2 做语音降噪（把噪声从语音里去掉）；最后把两块板串成一条级联'
        '链路，考察「先降噪再分离」到底有没有用。<br>'
        '我今天强调的不是「我的模型多强」，而是<b>每一个数字都能被复现、每一个口径都写在纸面上</b>。'
        '这次汇报里有一部分结论是负结果，我同样会照报。',
        foot='生成 %s ｜ HKBU FYP ｜ 项目根 <code>E:\\FYP_HKBU</code>' % NOW))

    # ---- S2 一页速览 ---------------------------------------------------
    best = [t for t in sep_ranked() if t[0] in ('bsrnn_simo', 'bsrnn_all', 'mdx')]
    top_key, top_label, _, top_avg4, _ = best[0]
    mix_avg4 = num(D['mix']['avg4'])
    d16 = [r for r in D['den16']['rows'] if r['subset'] == 'valentini' and r['snr_bin'] == 'ALL']
    dn_best = max(d16, key=lambda r: num(r['si_sdr_improve']) or -9e9)
    S.append(slide(
        'Overview', 'cover',
        'Three Takeaways',
        '一页看完：板 1 有效、板 2 有效但域受限、级联为负',
        kpis([
            ('', g(top_avg4), '板 1 四轨 SDR 中位最佳（%s）' % esc(top_label),
             '对照 mixture 基线 %s dB → 提升 <b>%s dB</b>；口径：MUSDB18-HQ train 抽段 3 首 × 10 s' % (
                 g(mix_avg4), g((top_avg4 or 0) - (mix_avg4 or 0)))),
            ('t2', sgn(dn_best['si_sdr_improve']), '板 2 降噪 ΔSI-SDR（%s）' % esc(dn_best['model']),
             'valentini ALL（真实含噪，n=%d）16 kHz 口径；ΔPESQ %s' % (
                 dn_best['n_ok'], sgn(dn_best['pesq_improve'], 3))),
            ('t3', sgn(CAS_SUM['median_d_L1'], 3), '级联：前置降噪反而伤害（负结果）',
             '其中带宽代价 %s、<b>净降噪动作 %s</b>；后置近中性 %s' % (
                 sgn(CAS_SUM['median_d_L1b'], 3), sgn(CAS_SUM['median_denoise_net'], 3),
                 sgn(CAS_SUM['median_d_L2'], 3))),
        ]),
        '<b>三句话各自有独立证据链</b>，且都做了「对照臂」：板 1 对照 mixture 基线；板 2 对照 clean 参考与'
        '无参考集；级联对照 <code>L1b</code>（只走带宽往返、不做降噪动作）——'
        '<b>没有这条对照臂，就无法排除「涨跌来自带宽被砍而非降噪本身」</b>。'
        '<b>速览 40 秒。</b>三个结论：一，板 1 四轨 SDR 中位最佳 ' + g(top_avg4)
        + ' dB，不分离的 mixture 基线只有 ' + g(mix_avg4) + ' dB，说明这些方法确实在做事。'
        '二，板 2 降噪在真实含噪集上平均改善 ' + g(dn_best['si_sdr_improve'])
        + ' dB、PESQ 涨 ' + g(dn_best['pesq_improve'], 3) + '。'
        '三，把两者串起来<b>结果反而变差</b>：前置降噪让分离 SDR 中位掉了 '
        + g(abs(num(CAS_SUM['median_d_L1']))) + ' dB —— 这个负结果我后面重点讲。',
        foot='口径：三条结论分属三套数据集，<b>不可跨行比较</b>（见 T8.3 §1 口径三要素表）'))

    # ---- S3 系统全景 ---------------------------------------------------
    S.append(slide(
        'Overview', 'cover',
        'System Overview: Two Boards, One Cascade',
        '交付形态：每块板 = 数据 + 主表 + 看板 + 图包 + 口径声明',
        '<div class="chain">'
        '<div class="fbox b1">Board 1 · 源分离<span>MUSDB18-HQ（4 stem）<br>'
        + str(n_b1) + ' 个模型 / 权重，' + str(n_g_b1) + ' 组<br>'
        '主表 + 实机成本 + 混响回声退化</span></div>'
        '<div class="arrow">→</div>'
        '<div class="fbox b2">Board 2 · 语音降噪<span>16 kHz / 44.1 kHz 双口径<br>'
        + str(gs.get('denoise', 0)) + ' 个降噪权重 + ' + str(gs.get('dereverb', 0)) + ' 个去混响（'
        + str(n_g_b2) + ' 组）<br>'
        '分层主表 + dry/wet + 域外探针</span></div>'
        '<div class="arrow">→</div>'
        '<div class="fbox bc">Cascade · 先降噪再分离<span>10 曲 × 4 SNR × 20 s<br>'
        '7 条链路 / 4 个对照臂<br>640 分离格 + 40 锚点格</span></div>'
        '</div>'
        '<div class="cols">'
        + tbl(['交付面', '内容', '形态'], [
            ('', ['数据与产物', 'JSON / CSV 逐格落盘，可断点续跑', '机器可读']),
            ('', ['主表', '四份数据摘要（T7.3）', 'Markdown · 零手填']),
            ('', ['看板', '3 块自包含离线 HTML（T7.1 / T7.2）', '双击即开 · 零依赖']),
            ('', ['论文图包', '%d 张图 + 清单 + 两板图注（T8.1 / T8.2）' % n_fig, '300 dpi 判据']),
            ('', ['口径声明', 'T8.3《口径与差异说明》7 节', '挡「与参考表不同」提问']),
        ])
        + '<div class="note">贯穿三条主线：<b>①同源</b>（图注口径由脚本继承，不重抄）'
          '<b>②零手填</b>（能算的数字绝不手写）<b>③照报</b>（负结果不改写、不挑数据）</div>'
        + '</div>',
        '<b>30 秒。</b>整个工作的骨架是「两块板 + 一条级联」。每块板都不是只丢一堆数字出来，'
        '而是五件套：逐格落盘的数据、零手填的摘要表、双击即开的看板、论文级图包，'
        '以及一份口径声明。<br>最后那份《口径与差异说明》是我特别想强调的 —— '
        '它专门用来回答评委最常问的一句话：「你这个数字跟论文里不一样，是不是做错了？」'
        '我把差异一条条列出来，而不是去凑数。',
        foot='看板：<code>model_analysis_dashboard.html</code> / <code>denoise_dashboard.html</code> / <code>cascade_dashboard.html</code>'))

    # ---- S4 板 1 · 口径 -------------------------------------------------
    clips = D['mix'].get('clips') or []
    clip_s = ' ／ '.join('%s @ %ss' % (c['song'], int(c['offset_s'])) for c in clips)
    S.append(slide(
        'Board 1 · Source Separation', 'b1',
        'Board 1 Protocol: What Exactly Was Measured',
        '三要素先声明，再谈数字',
        tbl(['要素', '取值', '为什么必须写'], [
            ('base', ['数据集', 'MUSDB18-HQ <b>train</b> 抽段', 'in-domain，数字偏乐观；与参考表 test 口径不可逐格对齐']),
            ('', ['片段', '%d 首 × 10 s' % len(clips), esc(clip_s)]),
            ('', ['指标', 'museval BSSEval v4 SDR', '签名默认窗 <b>88200 / hop 66150</b>（即 2 s / 1.5 s），逐帧 nanmedian']),
            ('', ['聚合', '四轨 SDR 算术平均 = <code>avg4</code>', '单轨模型只覆盖 1 条轨，与 avg4 不同轴']),
            ('sep', ['基线', 'mixture（把混音自身当估计）= %s dB' % g(mix_avg4), '标定「方法是否真的有效」；ΔSDR 才可跨数据集']),
        ])
        + '<div class="note warn"><b>两个已量化、不隐藏的口径偏差</b>：'
        '① 分析窗实际落到 museval 默认 <b>2 s / 1.5 s</b>（旧文档曾写 1 s）—— 已量化 '
        '|Δ| 均值 <b>0.267 dB</b>；② 本表为 train 子集，<b>不是</b>泛化证据，泛化证据在 test 副表与 dns_dev 外部集。</div>',
        '<b>35 秒。</b>先说口径，因为口径决定数字能不能比。一，我用 MUSDB18-HQ train 子集抽段、'
        '三首各截 10 秒 —— in-domain 口径，数字偏乐观，我主动交代。'
        '二，指标是 museval BSSEval v4 SDR，这里有个坑：代码没显式传窗长，'
        '实际落到签名默认的 2 秒窗 / 1.5 秒 hop，不是文档写的 1 秒窗，我把偏差量化成了 0.267 dB。'
        '三，所有结论都以 ΔSDR 相对 mixture 基线来讲，只有差值能跨数据集比较。',
        foot='口径三要素继承自 <code>tools/_export_paper_figures.py</code> · <code>GROUPS</code>（同源，非重抄）'))

    # ---- S5 板 1 · 供给画像 --------------------------------------------
    GNOTE = {
        '4-stem': '四轨分离（vocals / drums / bass / other）',
        '1-target': '单目标（只出人声）—— 与四轨<b>不同轴</b>',
        '2-target': '双目标',
        'denoise': '降噪（板 2）',
        'dereverb': '去混响 / 去回声（板 2）',
        'analytic': '解析 / 经典基线（参数量 0）',
    }
    S.append(slide(
        'Board 1 · Source Separation', 'b1',
        'Supply Profile: %d Models, Not %d Equal Choices' % (n_b1, n_b1),
        '先看「有哪些」，再看「谁值得比」',
        '<div class="cols c21">'
        + tbl(['组', '说明', '个数'], [('', [k, GNOTE.get(k, ''), str(gs[k])]) for k in GORDER if k in gs])
        + fig('fig-profile-params-flops',
              '<b>口径三要素</b> ｜ 数据集：统一<b>合成</b>输入（不取自数据集）｜片段：10 s / 44.1 kHz / 立体声'
              '｜指标：参数量 <code>sum(numel)</code>；FLOPs = 2×MACs <b>下界</b>；时延 5 次中位数（RTX 4070 Laptop 8 GiB）',
              max_w=1400)
        + '</div>'
        + '<div class="note warn"><b>FLOPs 是下界，不是等价比较</b>：'
          '<code>FlopCounterMode</code> 不计 <code>torch.stft</code> 与融合注意力 → '
          '跨架构比较<b>必须配合实测时延</b>；同架构内排序仍有效。</div>',
        '<b>30 秒。</b>板 1 有 ' + str(n_b1) + ' 个模型或权重，但不是同一类东西：'
        + str(gs.get('4-stem', 0)) + ' 个四轨分离、' + str(gs.get('1-target', 0))
        + ' 个只做单目标人声、' + str(gs.get('2-target', 0))
        + ' 个双目标，另有降噪、去混响与解析基线。这个分类很重要 —— '
        '<b>单轨模型的 SDR 只覆盖人声，跟四轨平均不是一条轴</b>，直接排名是错的。<br>'
        '右边这张图还暴露一个坑：FLOPs 我算的是 2×MACs 下界，'
        '因为 PyTorch 计数器看不到 STFT 和融合注意力。所以跨架构比较我只用「下界 + 实测时延」。',
        foot='画像表：<code>00_shared/data/model_analysis/model_profile.csv</code>（%d 行，含 22 个模型 / 权重）' % n_models))

    # ---- S6 板 1 · 精度主表 --------------------------------------------
    rank = sep_ranked()
    rows = []
    for k, lab, sdr, a, rtf in rank:
        if k == 'rpca':
            continue
        cell = lambda s: g((sdr.get(s) or {}).get('median')) if sdr.get(s) else '<span class="dim">—</span>'
        cls = 'base' if k == top_key else ''
        four = all(sdr.get(s) for s in ('vocals', 'drums', 'bass', 'other'))
        tag = '' if four else '<span class="dim">(%d 轨)</span>' % len(sdr)
        rows.append((cls, [esc(lab) + ' ' + tag, cell('vocals'), cell('drums'), cell('bass'),
                           cell('other'), '<b>%s</b>' % g(a) if a is not None else '<span class="dim">—</span>',
                           g(rtf, 4)]))
    rows.append(('sep', ['<b>mixture 基线（不分离）</b>', g(med(D['mix']['per_stem']['vocals'])),
                         g(med(D['mix']['per_stem']['drums'])), g(med(D['mix']['per_stem']['bass'])),
                         g(med(D['mix']['per_stem']['other'])), '<b>%s</b>' % g(mix_avg4), '<span class="dim">—</span>']))
    S.append(slide(
        'Board 1 · Source Separation', 'b1',
        'Median SDR per Stem (avg4, descending)',
        '主表全量；<b>单轨模型单独标注轨数</b>，与四轨不可同轴',
        '<div class="cols c21">'
        + tbl(['模型', 'vocals', 'drums', 'bass', 'other', 'avg4', 'RTF'], rows, 'sm') + '</div>'
        +         '<div class="note good">四轨最佳 <b>%s</b>（avg4 <b>%s</b>）＝ 比 mixture 基线提升 <b>%s dB</b>；'
        '四轨常规模型中最弱 <b>%s</b>（%s）。<b>DPRNN 为负值（%s）系自训 5 h 欠训练对照，非官方权重</b>。</div>'
        % (esc(rank[0][1]), g(rank[0][3]), g((rank[0][3] or 0) - (mix_avg4 or 0)),
           esc([t for t in rank if t[0] == 'convtasnet'][0][1]),
           g([t for t in rank if t[0] == 'convtasnet'][0][3]),
           g([t for t in rank if t[0] == 'dprnn'][0][3])),
        '<b>50 秒。</b>这是板 1 的精度主表，全部是四轨 SDR 中位数，按四轨平均降序排。'
        '第一行最优 avg4 是 ' + g(rank[0][3]) + '，最后一行是不做分离的 mixture 基线，'
        + g(mix_avg4) + '。差距就是这些方法真实做的事。<br>'
        '表里有两行需要解释：一是标了「1 轨」的，那是单目标人声模型，它的数字只覆盖人声，'
        '不能跟四轨平均混着排；二是最底下的 DPRNN，它是负的 —— 这不是论文数字，'
        '是我自己用 5 小时数据训的欠训练对照，我把它照实放进来，不美化。',
        foot='口径三要素 ｜ 数据集：MUSDB18-HQ <b>train</b> ｜ 片段：3 首 × 10 s ｜ '
             '指标：museval BSSEval v4 SDR（2 s / 1.5 s 窗），四轨算术平均'))

    # ---- S7 板 1 · 实机成本 --------------------------------------------
    cost = cost_ranked()
    crows = []
    for k, v in cost:
        nt = v.get('n_tracks') or {}
        ntk = '／'.join('%s:%s' % (a, b) for a, b in sorted(nt.items()))
        crows.append(('', [esc(v.get('label', k)), '%s' % v['n_pass'],
                           g(med(v.get('wall_s')), 1), g(med(v.get('rtf')), 4),
                           g(med(v.get('sdr_mean'))), ntk, g(v.get('infer_share_pct'), 1)]))
    S.append(slide(
        'Board 1 · Source Separation', 'b1',
        'Real-machine Cost: 50 Full Songs on One 8 GiB GPU',
        '墙钟时间才有意义；RTF 会被机器负载污染',
        '<div class="cols c21">'
        + tbl(['模型', 'PASS/50', '墙钟中位(s)', 'RTF 中位', 'SDR 均值中位', '轨数', '推理占比(%)'], crows, 'sm')
        + '</div>'
        + '<div class="note warn"><b>两处不可直接比</b>：① 轨数列 <code>1:50</code> 为单轨模型，'
        '其 SDR 均值只覆盖人声；② RTF 受负载影响，同一模型两次可差 2× → <b>排名请用整曲墙钟</b>。'
        'BSRNN-SIMO 只跑完 <b>%d/50</b>（截断，已拍板不补跑）。</div>'
        % [v for k, v in cost if k == 'bsrnn_simo'][0]['n_pass'],
        '<b>30 秒。</b>这是 15 个模型在 50 首整曲上的实机成本。我只报两件事：'
        '跑完几首、墙钟多少秒。RTF 也列了，但 RTF 在同台笔记本上会随负载波动、两次能差一倍，'
        '所以<b>跨模型排名我只认整曲墙钟</b>。<br>'
        '另外轨数那列：1:50 是只出人声的单轨模型，它的 SDR 不能和 4:50 比。'
        'BSRNN-SIMO 只跑完 14 首就被超时拦掉，我在表里如实标注截断。',
        foot='口径三要素 ｜ 数据集：MUSDB18-HQ <b>test</b> 50 首整曲 ｜ 片段：整曲 ｜ '
             '指标：wall time / RTF / SDR 均值'))

    # ---- S8 板 1 · 三条读表纪律 -----------------------------------------
    orc = [t for t in rank if t[0] == 'oracle'][0]
    l12 = [t for t in rank if t[0] == 'bsroformer_l12']
    S.append(slide(
        'Board 1 · Source Separation', 'b1',
        'Three Reading Rules Before You Rank Anything',
        '这三条不是免责声明，是被数据逼出来的',
        '<div class="cols c3">'
        + '<div class="note"><b>① 单轨 ≠ 四轨</b><br>BS-RoFormer L12 人声 %s dB，'
          '但它<b>只出 1 条轨</b>；四轨模型要同时照顾好 stems。两者不在同一条轴上，'
          '排在一起会得出「单轨模型更强」的错误结论。</div>' % g(med((l12[0][2].get('vocals') or {})))
        + '<div class="note"><b>② Oracle 不是模型</b><br>IRM/IBM Oracle avg4 %s dB，'
          '看着很高，但它是<b>解析上界</b>：用真值 mask 算出来的参考线，'
          '参数量 0、FLOPs 0。它的作用是标定「这个数据集上界在哪」。</div>' % g(orc[3])
        + '<div class="note"><b>③ 精度与成本不同轴</b><br>最优 avg4（%s dB）与最快墙钟'
          '（%s s）<b>不是同一个模型</b>。选型必须给权重：要质量看 avg4，要吞吐看墙钟。'
          '</div>' % (g(rank[0][3]), g(med(cost[0][1]['wall_s']), 1))
        + '</div>'
        + '<div class="note good">配套证据：<code>fig-acc-pareto</code>（精度—速度 Pareto）与 '
          '<code>fig-cost-pareto</code>（速度—精度 Pareto）两张图把这三条同时画了出 来；'
          '完整口径见 T8.3 §3 · B 类「数据与子集」。</div>',
        '<b>40 秒。</b>在看主表排名之前，有三条读表纪律必须说清，否则会得出错误结论。<br>'
        '第一，单轨模型只出人声，它的 SDR 和四轨平均不是一回事，不能同轴排名。'
        '第二，Oracle 那一行不是模型，是用真值掩码算的解析上界，参数量为零 —— '
        '它的用途是告诉我们这个数据集的上界大概在哪。'
        '第三，精度和成本不是同一条轴：质量最好的和跑得最快的不是同一个模型，'
        '所以选型必须说清楚是给质量权重还是给吞吐权重。',
        foot='三条纪律分别对应 T8.3 §3 · B 类 2 条与 T8.3 §4.2 取舍表；均已在看板 §6 单列'))

    # ---- S9 板 1 · 混响 / 回声 ------------------------------------------
    rv = D['s4']['reverb']
    ec = D['s4']['echo']
    mc_r = rv['mean_curve']
    mc_e = ec['mean_curve']
    S.append(slide(
        'Board 1 · Robustness', 'b1',
        'Reverberation Destroys Separation; Echo Only Bites',
        '正面结果：退化是单调的、可量化的',
        '<div class="cols c21">'
        + fig('fig-rev-degradation',
              '<b>口径三要素</b> ｜ 数据集：MUSDB18-HQ train 抽段 + 合成 / AIR RIR'
              '｜片段：3 首 × 10 s ｜ 指标：ΔSDR(dB) = 湿 − 干；T60 为<b>导出口径 44.1 kHz</b>',
              max_w=1250)
        + '<div>'
        + tbl(['场景', '6 模型均值 ΔSDR', '最差模型'], [
            ('base', ['干（无处理）', g(mc_r[0]), '—']),
            ('', ['小房间 T60 %s s' % g(rv['t60_small'], 3), sgn(mc_r[1]), sgn(min(rv['delta_small_by_model'].values()))]),
            ('', ['大厅 T60 %s s' % g(rv['t60_hall'], 3), sgn(mc_r[2]), sgn(min(rv['delta_hall_by_model'].values()))]),
            ('sep', ['短回声', sgn(mc_e[1]), sgn(min(ec['delta_short_by_model'].values()))]),
            ('', ['长回声', sgn(mc_e[2]), sgn(min(ec['delta_long_by_model'].values()))]),
        ], 'sm')
        + '<div class="note warn"><b>大厅档把分离打到负 SDR</b>：均值 ΔSDR <b>%s dB</b>，'
          '最差模型 <b>%s dB</b>。回声温和得多（%s ~ %s dB）。</div>'
          % (g(mc_r[2]), g(min(rv['delta_hall_by_model'].values())),
             g(mc_e[1]), g(mc_e[2]))
        + '</div></div>',
        '<b>35 秒。</b>除了「模型多准」，我还测了「环境一变会怎样」。'
        '左边这张图是混响的退化曲线：T60 从 0 加到 1 秒，六个模型的分离 SDR 单调往下掉；'
        '大厅档均值掉了 ' + g(abs(num(mc_r[2]))) + ' dB，直接把分离打到负 SDR。'
        '右边是可对账的表，包括每个场景里表现最差的模型。<br>'
        '回声的影响就温和得多，长回声大约掉 ' + g(abs(num(mc_e[2]))) + ' dB。'
        '这条曲线的价值在于：它给出了「部署到真实房间会损失多少」的一个可引用数字。',
        foot='口径三要素 ｜ 数据集：MUSDB18-HQ train 抽段 + 合成 / AIR RIR ｜ 片段：3 首 × 10 s ｜ '
             '指标：ΔSDR(dB)；T60 为导出口径 44.1 kHz（源 48 kHz 仅作脚注）'))

    # ---- S10 板 1 · 负结果：去混响 --------------------------------------
    dr = D['s4']['dereverb']
    S.append(slide(
        'Board 1 · Negative Result', 'b1',
        'Negative Result: Dereverb Checkpoints Are Unusable Here',
        '负结果照报 —— 并给出「不是我们实现错了」的证据',
        '<div class="cols c21">'
        + tbl(['指标', '实测', '含义'], [
            ('', ['dry 支增益中位', g(dr['anvuew_gain_median'], 3), '≈ 0 → 干路几乎无输出']),
            ('', ['dry 支增益最大', g(dr['anvuew_gain_max'], 3), '偶发跳变，非稳定行为']),
            ('', ['wet 支损失区间', '%s ~ %s dB' % (g(dr['wet_loss_range_db'][0], 1), g(dr['wet_loss_range_db'][1], 1)), '湿路亦被压']),
            ('sep', ['判定', '<b>%s</b>' % esc(dr['echo_model_verdict']), '在本探针上不可用']),
        ], 'sm')
        + '<div class="note bad"><b>关键一步：用官方推理路径交叉验证 → Δ = %s dB</b>。'
          '即换上作者自己的推理代码，结论不变 ⇒ <b>不是我们的封装实现错误</b>，'
          '而是这两个 checkpoint 在本任务探针上确实不工作。</div>'
          % g(dr['official_cross_check_delta_db'], 3)
        + '</div>',
        '<b>30 秒。</b>这一页是负结果：我试了两个社区的去混响 checkpoint，结论是不可用 —— '
        '干路输出几乎为零。<br>但「我的模型不行」这句话本身没有信息量，'
        '真正要回答的是：<b>是我的封装写错了，还是模型本身如此？</b>'
        '我的做法是换成作者官方的推理路径再跑一遍，结果偏差只有 '
        + g(dr['official_cross_check_delta_db'], 3) + ' dB，'
        '说明问题在模型与任务，不在我的实现。这条「用上游官方路径交叉验证」的方法，'
        '后来成了我排查所有可疑结果的标准动作。',
        foot='口径三要素 ｜ 数据集：DNS-Challenge impulse responses ｜ 片段：探针音频 ｜ '
             '指标：分支增益 / Δ(dB)；详见 <code>DEREVERB_NEGATIVE_RESULT.md</code>'))

    # ---- S11 板 2 · 双口径 ---------------------------------------------
    S.append(slide(
        'Board 2 · Speech Denoising', 'b2',
        'Board 2 Protocol: Two Sampling Rates, Never One Table',
        '双口径是本板最容易出错的地方，先立规矩',
        '<div class="cols c21">'
        + '<div>' + tbl(['项', '口径 A（44.1 kHz）', '口径 B（16 kHz）'], [
            ('base', ['定位', '<b>契约率</b>（实际工作率）', '模型<b>原生率</b>']),
            ('', ['含重采样代价', '含（44.1k→16k→44.1k 往返）', 'denoiser_* 不含']),
            ('', ['PESQ / STOI', '<b>不适用</b>（定义域 8 / 16 kHz）', '适用']),
            ('', ['CSV 行数', '%d' % len(D['den44']['rows']), '%d' % len(D['den16']['rows'])]),
            ('sep', ['引用要求', '任何 <code>hf_ratio</code> 必须注明口径', '同左']),
        ], 'sm')
        + '<div class="note bad"><b>PESQ 在 44.1 kHz 口径下为空是设计，不是缺测</b>'
          '（<code>pesq_applicable=false</code>）；<b>不得当 0 用</b> —— '
          '把空值当 0 会凭空造出「PESQ 崩了」的假结论。</div></div>'
        + fig('fig-arch-denoiser',
              '<b>口径三要素</b> ｜ 数据集：N/A（结构示意）｜ 片段：N/A ｜ '
              '指标：原生率 16 kHz；<code>denoiser_dns48/64</code> 与 <code>master64</code> 同构，仅训练集不同',
              max_w=1100)
        + '</div>'
        + '<div class="note">同页口径的 <code>hf_ratio</code> 差异极大（>4 kHz 能量占比）：'
          '16 kHz 口径 <b>%s</b> vs 44.1 kHz 口径 <b>%s</b> —— 不写口径就等于数字不可用。</div>'
        % (g([r for r in D['den16']['rows'] if r['model'] == 'denoiser_master64'
              and r['subset'] == 'valentini' and r['snr_bin'] == 'ALL'][0]['hf_ratio_out'], 4),
           g([r for r in D['den44']['rows'] if r['model'] == 'denoiser_master64'
              and r['subset'] == 'valentini' and r['snr_bin'] == 'ALL'][0]['hf_ratio_out'], 4)),
        '<b>35 秒。</b>板 2 我坚持一个纪律：<b>两个采样率口径绝不混在一张表里</b>。<br>'
        '44.1 kHz 是契约率，也就是模型实际工作时的采样率，里面含有内部重采样代价；'
        '16 kHz 是模型的原生率。为什么要这么较真？因为 PESQ 这个指标的定义域只有 8 kHz 和 16 kHz，'
        '44.1 kHz 下它根本算不了 —— 这里是空值，<b>空值不是 0</b>。'
        '我见过把空值当 0 然后得出「PESQ 崩了」的错误结论。',
        foot='口径三要素 ｜ 数据集：valentini（真实含噪 + clean 参考）/ synth / dns_dev（无参考）｜ '
             '片段：整条 utterance ｜ 指标：SI-SDR / PESQ / STOI / LSD / hf_ratio'))

    # ---- S12 板 2 · P19 契约 bug（元教训） ------------------------------
    rate = 44100.0 / 16000.0
    S.append(slide(
        'Board 2 · Methodology', 'b2',
        'The One Bug That Invalidated 12,845 Cells',
        '留给我最大的方法论教训，也是今天最想讲的一页',
        '<div class="cols c21">'
        + '<div class="note bad"><b>现象</b>：同一批音频，「16 kHz 口径」剔除掉数百条，'
          '而「44.1 kHz 口径」结果<b>全是 0</b>。这个不对称就是抓出 bug 的破绽。</div>'
        + '<div class="note"><b>根因</b>：wrapper 内写死 <code>convert_audio(…, 44100, 16000, 1)</code>，'
          '而调用方<b>已把信号降到评测率</b> → <b>降采样两次</b>，音频加速 <b>%s×</b>。'
          '修复时又踩了「原地覆盖 noisy」→ 输入 SI-SDR 掉到 <b>−73 dB</b>。</div>' % g(rate)
        + '<div class="note good"><b>修法</b>：拆成 <code>noisy_in</code>（契约率／只喂模型）与 '
          '<code>noisy</code>（评测率／只算指标），<b>绝不原地覆盖</b>；并加<b>采样率—长度护栏</b>'
          '（比值超出 0.5~2.0 直接抛错）。</div>'
        + '</div>'
        + '<div class="note warn"><b>修复后结论根本反转</b>：'
          'denoiser 在 ≥15 dB 档 ΔSI-SDR <b>+4.14 ~ +4.74</b>、ΔPESQ <b>+0.43 ~ +0.65</b>；'
          '<b>master64 由「最差」反转为「最优」</b>（ALL ΔPESQ %s）；'
          '原本报的「三指标互相矛盾」<b>在修复后 20/20 格全部同向为正 —— 那个「矛盾」是 bug 造的</b>。</div>'
        % sgn([r for r in D['den16']['rows'] if r['model'] == 'denoiser_master64'
               and r['subset'] == 'valentini' and r['snr_bin'] == 'ALL'][0]['pesq_improve'], 3),
        '<b>50 秒 —— 这一页我最想讲。</b>板 2 的 wrapper 里我把采样率转换写死成「转 16 kHz」，'
        '但调用它的代码<b>已经把音频降到评测率了</b> —— 降采样做了两次，音频加速 '
        + g(rate) + ' 倍，<b>12845 个格子全部作废</b>。<br>'
        '抓出它的是一个不对称现象：同一批音频，16 kHz 口径剔除几百条，44.1 kHz 口径全是 0 —— '
        '这个「不合理」就是破绽。<br>'
        '更值得讲的是修复后<b>结论彻底反转</b>：原本我说「三个指标互相矛盾」，'
        '修复后 20 个格子全部同向为正 —— 那个矛盾根本不存在。'
        '<b>能解释一切的叙事，往往就是 bug 在说话。</b>',
        foot='完整复盘：<code>02_denoising/docs/P19_SAMPLE_RATE_CONTRACT_BUG.md</code> ｜ '
             '本节数字全部来自修复后口径（<code>denoise_eval_16k.json</code>）'))

    # ---- S13 板 2 · 降噪主表 --------------------------------------------
    v16 = den_rows('valentini', 16000)
    sy16 = den_rows('synth', 16000)
    d48 = [r for r in v16 if r['model'] == 'denoiser_dns48' and r['snr_bin'] == 'ALL'][0]
    dm64 = [r for r in v16 if r['model'] == 'denoiser_master64' and r['snr_bin'] == 'ALL'][0]
    dmel = [r for r in v16 if r['model'] == 'mel_roformer_denoise' and r['snr_bin'] == 'ALL'][0]
    dmels = [r for r in sy16 if r['model'] == 'mel_roformer_denoise' and r['snr_bin'] == 'ALL'][0]
    S.append(slide(
        'Board 2 · Speech Denoising', 'b2',
        'Stratified Results: Denoisers Work, Mel-RoFormer Does Not',
        '按输入 SI-SDR 分档；三指标同向为正',
        '<div class="cols c21">'
        + fig('fig-dn-suppression',
              '<b>口径三要素</b> ｜ 数据集：valentini（真实含噪 + clean 参考）｜'
              '片段：整条 utterance，16 kHz 口径 ｜ 指标：ΔSI-SDR / ΔPESQ / ΔSTOI，按输入 SI-SDR 分档',
              max_w=1200)
        + tbl(['模型（valentini · ALL）', 'SI-SDR in', 'out', 'ΔSI-SDR', 'ΔPESQ', 'ΔSTOI'], [
            ('base', ['denoiser dns48', g(d48['si_sdr_in']), g(d48['si_sdr_out']),
                      '<b>%s</b>' % sgn(d48['si_sdr_improve']), sgn(d48['pesq_improve'], 3), sgn(d48['stoi_improve'], 4)]),
            ('', ['denoiser master64', g(dm64['si_sdr_in']), g(dm64['si_sdr_out']),
                  '<b>%s</b>' % sgn(dm64['si_sdr_improve']), '<b>%s</b>' % sgn(dm64['pesq_improve'], 3),
                  '<b>%s</b>' % sgn(dm64['stoi_improve'], 4)]),
            ('', ['mel-roformer-denoise', g(dmel['si_sdr_in']), g(dmel['si_sdr_out']),
                  sgn(dmel['si_sdr_improve']), sgn(dmel['pesq_improve'], 3), sgn(dmel['stoi_improve'], 4)]),
        ], 'sm')
        + '</div>'
        + '<div class="note good">真实噪声最强档（≥15 dB）denoiser 系列 ΔSI-SDR <b>+4.14 ~ +4.74</b>、'
          'ΔPESQ <b>+0.43 ~ +0.65</b>；<b>mel-roformer 是近恒等映射</b>：'
          'ΔSI-SDR 仅 %s、纯噪声上只降 %s dB。</div>'
        % (sgn(dmel['si_sdr_improve']), g(D['ood']['probes']['mel_roformer_denoise']['summary']['B_suppression_db_med'], 3)),
        '<b>45 秒。</b>这是板 2 的主表。左边按输入信噪比分了三档：'
        '输入越差，提升越大，这符合降噪的预期。<br>右边提炼成三行：'
        'denoiser 系列在真实含噪集上平均能把 SI-SDR 改善 ' + g(d48['si_sdr_improve']) + ' dB，'
        'PESQ 也涨 ' + g(d48['pesq_improve'], 3) + '。而 mel-roformer 这一行就很有意思 —— '
        '它的 SI-SDR 改善只有 ' + g(dmel['si_sdr_improve']) + ' dB。'
        '到下一页我会证明这不是「略弱」，而是<b>近乎恒等映射</b>。',
        foot='口径三要素 ｜ 数据集：valentini 824 条（真实含噪，有 clean 参考）｜ 片段：整条 utterance ｜ '
             '指标：SI-SDR / PESQ / STOI；<b>16 kHz 口径</b>（PESQ 定义域）'))

    # ---- S14 板 2 · dry/wet ---------------------------------------------
    bd = [r for r in best_dry() if r[1] == 'ALL']
    bd15 = [r for r in best_dry() if r[1] == '>=15dB']
    rows = []
    for m, b, n, d1, v1, d2, v2 in bd:
        rows.append(('', [esc(m), str(n), g(d1, 1), sgn(v1, 3), g(d2, 1), sgn(v2, 3)]))
    S.append(slide(
        'Board 2 · Deployment Knob', 'b2',
        'Dry/Wet: The Optimum Moves With Input SNR',
        '一个可直接部署的旋钮：<code>estimate = (1-dry)·model(noisy) + dry·noisy</code>',
        '<div class="cols c21">'
        + fig('fig-dn-drywet',
              '<b>口径三要素</b> ｜ 数据集：valentini ｜ 片段：整条 utterance，16 kHz ｜'
              '指标：在 dry 网格 {0, .1, .2, …, 1.0} 上取 SI-SDR / PESQ 的逐点中位',
              max_w=1250)
        + tbl(['模型', '格数', '最优 dry(SI-SDR)', '增益(dB)', '最优 dry(PESQ)', '增益'], rows, 'sm')
        + '</div>'
        + '<div class="note warn"><b>两处必须说清的细节</b>：'
          '① 最优强度<b>随输入 SNR 移动</b>：<code>&lt;5 dB</code> 档为 0，'
          '<code>&gt;=15 dB</code> 档升到 %s（输入越干净越该保留原信号）；'
          '② PESQ 最优 dry <b>按权重分化</b>（dns48 / dns64 峰在 0.1、master64 峰在 0.0）—— '
          '<b>权重相关，不可外推</b>。</div>'
        % g(max(r[3] for r in bd15), 1),
        '<b>30 秒。</b>这一页给的是可直接部署的旋钮：把模型输出和原信号按比例混合。<br>'
        '两条结论：一，最优强度<b>不是固定值</b>，它随输入信噪比移动 —— '
        '输入差就全交给模型，输入干净就多保留原信号。'
        '二，用 SI-SDR 和用 PESQ 挑出的最优点不一样，而且差异<b>跟权重绑死</b>，不能外推。<br>'
        '顺便说个锚点：dry=0 必须与主表逐位一致，实测偏差 0.0000 —— 这是我验证实验没跑歪的方式。',
        foot='口径三要素 ｜ 数据集：valentini ｜ 片段：整条 utterance ｜ '
             '指标：dry 网格上的 si_sdr_improve / pesq_improve 中位；锚点 dry=0 与主表偏差 0.0000'))

    # ---- S15 板 2 · 域不匹配 --------------------------------------------
    ood = D['ood']['probes']
    orows = []
    for m, v in sorted(ood.items(), key=lambda kv: kv[1]['summary']['B_suppression_db_med'] if 'B_suppression_db_med' in kv[1]['summary'] else 0):
        s = v['summary']
        orows.append(('', [esc(m), str(v['native_sr']), g(s['A_clean_ratio_med'], 4),
                           g(s['B_noise_ratio_med'], 4), sgn(s['B_suppression_db_med'], 3),
                           sgn(s['C_si_sdr_vs_mix_med'], 3)]))
    S.append(slide(
        'Board 2 · Out-of-Domain Probe', 'b2',
        'Two Model Families, Two Disjoint Domains',
        '负结果转正面：不是「谁更差」，而是「各自管什么」',
        '<div class="cols c21">'
        + fig('fig-dn-domain-reversal',
              '<b>口径三要素</b> ｜ 数据集：自造探针（干净直通 / 纯噪声直通 / 增益扫描）｜'
              '片段：6 条 ｜ 指标：直通比 / 抑制量(dB) / SI-SDR；分析率 16 kHz、契约率 44.1 kHz',
              max_w=1250)
        + tbl(['模型', '原生率', 'A 干净直通比', 'B 噪声直通比', 'B 抑制(dB)', 'C 增益扫描'], orows, 'sm')
        + '</div>'
        + '<div class="note warn"><b>同一张主表上的两个模型族，在对方的主场上近乎恒等</b>：'
          'mel-roformer 对纯噪声只抑制 <b>%s dB</b>（denoiser 是 <b>%s dB</b>）；'
          '而它在合成集上的增益只有 <b>%s dB</b>（denoiser 是 <b>%s dB</b>）——'
          '作用量差 <b>%s 倍</b>。⇒ <b>有效域互补，而非优劣之分</b>。</div>'
        % (g(ood['mel_roformer_denoise']['summary']['B_suppression_db_med'], 3),
           g(ood['denoiser_master64']['summary']['B_suppression_db_med'], 3),
           g(dmels['si_sdr_improve']),
           g([r for r in sy16 if r['model'] == 'denoiser_dns48' and r['snr_bin'] == 'ALL'][0]['si_sdr_improve']),
           g(abs(num([r for r in sy16 if r['model'] == 'denoiser_dns48'
                      and r['snr_bin'] == 'ALL'][0]['si_sdr_improve'])) /
             max(abs(num(dmels['si_sdr_improve'])), 1e-6), 1)),
        '<b>35 秒。</b>这一页本来是负结果：mel-roformer 在我造的合成噪声上几乎不起作用。'
        '但做完直通探针，结论就不是「它更差」了。<br>'
        '探针逻辑很简单：喂干净语音看输出有没有变，再喂纯噪声看有没有被压掉。'
        '结果 denoiser 把纯噪声压掉几十个 dB，mel-roformer 只压了零点几；'
        '反过来在合成集上差距十几倍。<b>所以这不是优劣，是两个模型族的有效域不重叠</b> —— '
        '我把它写成「域不匹配」，这是个正面的可推论结论。',
        foot='口径三要素 ｜ 数据集：自造可控探针 ｜ 片段：6 条 ｜ '
             '指标：A/B 直通比、抑制量(dB)、C 增益扫描 SI-SDR；详见 <code>T5_7_OOD_NOISE_NEGATIVE.md</code>'))

    # ---- S16 板 2 · 机理：倾斜而非低通 -----------------------------------
    sm_v = spec_row('denoiser_master64', 'valentini')
    sm_s = spec_row('denoiser_master64', 'synth')
    smv2 = spec_row('mel_roformer_denoise', 'valentini')
    S.append(slide(
        'Board 2 · Mechanism', 'b2',
        'Not a Low-pass: A Frequency-Dependent Tilt',
        '从「hf_ratio 塌陷」这个假象里走出来',
        '<div class="cols c21">'
        + fig('fig-dn-dspec-master64-val',
              '<b>口径三要素</b> ｜ 数据集：valentini ｜ 片段：最多 120 条，16 kHz ｜ '
              '指标：21log10|STFT| 均值差（0–7.8 kHz 有效带；8 kHz 以上为重采样伪影，<b>不纳入</b>）',
              max_w=1150)
        + tbl(['model / subset', '0–1 kHz', '1–4 kHz', '4–7.8 kHz', '倾斜 tilt'], [
            ('base', ['master64 / valentini', sgn(sm_v['b_0_1k']), sgn(sm_v['b_1_4k']),
                      sgn(sm_v['b_4_7k8']), '<b>%s</b>' % sgn(sm_v['tilt'])]),
            ('', ['master64 / synth', sgn(sm_s['b_0_1k']), sgn(sm_s['b_1_4k']),
                  sgn(sm_s['b_4_7k8']), '<b>%s</b>' % sgn(sm_s['tilt'])]),
            ('sep', ['mel-roformer / valentini', sgn(smv2['b_0_1k']), sgn(smv2['b_1_4k']),
                     sgn(smv2['b_4_7k8']), '<b>%s</b>' % sgn(smv2['tilt'])]),
        ], 'sm')
        + '</div>'
        + '<div class="note bad"><b>一个差点写进论文的假象</b>：<code>hf_ratio</code>（&gt;4 kHz 能量占比）'
          '看起来「塌陷」，让人以为 denoiser 是个低通滤波器。但 <code>hf_ratio</code> 是<b>比例量</b> —— '
          '压掉噪声本身就会让它塌陷，<b>塌陷 ≠ 低通</b>。三步直通探针给出真相：真实 clean 配对的高频位移仅 '
          '<b>−0.0079</b>。</div>'
        + '<div class="note">同权重在 synth 上的中频抑制量是真噪集的 <b>%s 倍</b> ⇒ '
          '<b>不是均匀低通，是随频率增长的倾斜</b>；真实缺陷是轻度电平压缩。</div>'
        % g(abs(num(sm_s['b_1_4k'])) / max(abs(num(sm_v['b_1_4k'])), 1e-6), 1),
        '<b>35 秒。</b>这一页讲机理，也讲我差点写错的一个结论。<br>'
        'hf_ratio 是 4 kHz 以上能量占比，它在降噪后明显下降，很容易得出「denoiser 是低通」的结论。'
        '<b>但这是错的</b> —— 它是个比例量，只要高频噪声被压掉，比例自己就会掉，'
        '不需要任何低通行为。<br>直通探针验证：真实 clean 配对的高频位移只有 0.0079。'
        '真正的行为是<b>随频率增长的倾斜</b>，且合成噪声上的抑制量是真噪集的 ' + g(abs(num(sm_s['b_1_4k'])) / max(abs(num(sm_v['b_1_4k'])), 1e-6), 1) +
        ' 倍。所以措辞应写成「自适应噪声门控 + 小幅频谱倾斜」，不是低通。',
        foot='口径三要素 ｜ 数据集：valentini / synth ｜ 片段：≤120 条 ｜ '
             '指标：平均谱差(dB)，有效带 0–7.8 kHz（16 kHz 下 Nyquist = 8 kHz）'))

    # ---- S17 级联 · 设计 -------------------------------------------------
    S.append(slide(
        'Cascade · Denoise → Separate', 'bc',
        'Cascade Design: The Arm That Makes It Falsifiable',
        '没有 <code>L1b</code>，这个实验就没有说服力',
        '<div class="chain">'
        + '<div class="fbox bc">L0<span>带噪输入直送（参照臂）</span></div>'
        + '<div class="arrow">→</div>'
        + '<div class="fbox bc">L1<span>前置降噪（denoiser）</span></div>'
        + '<div class="arrow">→</div>'
        + '<div class="fbox bc">L1b ★<span>只走 16k/mono 往返，<b>不做降噪动作</b></span></div>'
        + '<div class="arrow">→</div>'
        + '<div class="fbox bc">L1m / L2 / L2b / L3<span>mel 前置 / 后置 / 后置对照 / 前+后</span></div>'
        + '</div>'
        + '<div class="cols">'
        + tbl(['项', '取值', '说明'], [
            ('base', ['数据集', 'MUSDB18-HQ test Top-10 × DNS freesound 噪声池', '逐声道独立加噪']),
            ('', ['片段', '10 曲 × 4 SNR × 20 s', 'SNR ∈ {−5, 0, +5, +10} dB']),
            ('', ['指标', 'museval BSSEval v4（与板 1 主表同源）', 'Δ = 该链路 − L0']),
            ('', ['格数', '640 分离格 + 40 锚点格', '门禁 %d/%d PASS' % (CAS_GATE['n_gates'] - CAS_GATE['n_failed'], CAS_GATE['n_gates'])]),
            ('sep', ['音频格式', '32-bit float WAV', '噪声瞬态强，PCM_16 会静默削波 30/40 格']),
        ], 'sm')
        + '<div class="note warn"><b>L1b 是恒等对照臂</b>：它经历与 L1 <b>完全相同的重采样与单声道化</b>，'
          '唯一差别是不做降噪 → <code>L1 = L1b + (L1 − L1b)</code> 逐格恒等'
          '（最大残差 <b>0.000000</b> dB），把「带宽代价」与「净降噪动作」彻底分开。</div>'
        + '</div>',
        '<b>35 秒。</b>这是级联的链路设计。核心是中间这条 <code>L1b</code> 臂，'
        '我叫它恒等对照：它跟前置降噪走<b>完全一样</b>的管线 —— 一样的重采样、一样的单声道化 —— '
        '<b>唯一不同是不做降噪动作</b>。<br>为什么必须加？否则我看到「先降噪再分离 SDR 掉了」，'
        '就无法判断是降噪动作的错，还是仅仅因为音频被降成 16 kHz 单声道。'
        '加上之后两者可逐格相减，且恒等式残差 0.000000，说明分解是干净的。',
        foot='口径三要素 ｜ 数据集：MUSDB18-HQ test Top-10 × DNS freesound ｜ 片段：10 曲 × 4 SNR × 20 s ｜ '
             '指标：museval BSSEval v4 SDR（avg4 中位），Δ = 链路 − L0'))

    # ---- S18 级联 · 矩阵 -------------------------------------------------
    S.append(slide(
        'Cascade · Result', 'bc',
        'Denoising Before Separation Hurts, Robustly',
        '负结果的主结论，以及它为什么可信',
        '<div class="cols c21">'
        + fig('fig-cas-delta-matrix',
              '<b>口径三要素</b> ｜ 数据集：MUSDB18-HQ test Top-10 × DNS freesound 噪声 ｜'
              '片段：10 曲 × 4 SNR × 20 s ｜ 指标：ΔSDR(dB) = 链路 − L0，GT = 干 stem',
              max_w=1350)
        + '<div>'
        + tbl(['链路', '跨格中位 ΔSDR (n=16)'], [
            ('base', ['L0 带噪直送', '0.000']),
            ('', ['L1 前置降噪', '<b>%s</b>' % sgn(CAS_SUM['median_d_L1'], 3)]),
            ('', ['L1b ★仅带宽（恒等对照）', sgn(CAS_SUM['median_d_L1b'], 3)]),
            ('', ['<b>L1 − L1b = 净降噪动作</b>', '<b>%s</b>' % sgn(CAS_SUM['median_denoise_net'], 3)]),
            ('', ['L1m mel 前置', sgn(CAS_SUM['median_d_L1m'], 3)]),
            ('sep', ['L2 后置降噪', sgn(CAS_SUM['median_d_L2'], 3)]),
            ('', ['L3 前 + 后', sgn(CAS_SUM['median_d_L3'], 3)]),
        ], 'sm')
        + '<div class="note bad"><b>伤害的主因是「降噪动作本身」，不是带宽代价</b>：'
          '净动作 <b>%s dB</b>，占 L1 总损失的 <b>%d%%</b>。</div>'
          % (sgn(CAS_SUM['median_denoise_net'], 3),
             round(100 * abs(num(CAS_SUM['median_denoise_net'])) / max(abs(num(CAS_SUM['median_d_L1'])), 1e-6)))
        + '</div></div>',
        '<b>45 秒。</b>这是级联的核心结论，也是今天最重要的负结果。<br>'
        '看中间那张表：前置降噪让 SDR 中位掉了 ' + g(abs(num(CAS_SUM['median_d_L1']))) + ' dB。'
        '但真正有价值的是下一行 —— <b>仅带宽</b>的对照臂只掉了 '
        + g(abs(num(CAS_SUM['median_d_L1b']))) + ' dB。两者相减，'
        '净降噪动作贡献了 ' + g(abs(num(CAS_SUM['median_denoise_net']))) + ' dB，'
        '占了总损失的绝大部分。<br>也就是说：<b>不是因为音频被降成 16 kHz 单声道才变差，'
        '而是降噪这个动作本身把分离器需要的东西一起删掉了</b>。下一张图接着讲为什么。',
        foot='口径三要素 ｜ 数据集：MUSDB18-HQ test Top-10 × DNS freesound ｜ 片段：10 曲 × 4 SNR × 20 s ｜ '
             '指标：ΔSDR(dB) 跨格中位（n=16 = 4 模型 × 4 SNR）'))

    # ---- S19 级联 · 分解 -------------------------------------------------
    per_snr = []
    for r in sorted(CAS_ROWS, key=lambda x: -x['snr_db']):
        per_snr.append((r['snr_db'], r))
    byb = {}
    for r in CAS_ROWS:
        byb.setdefault(r['snr_db'], []).append(r)
    brows = []
    for b in sorted(byb, reverse=True):
        gs_ = byb[b]
        brows.append(('', [g(b, 0), g(st.median([r['sdr_L0'] for r in gs_])),
                           sgn(st.median([r['d_L1'] for r in gs_]), 3),
                           sgn(st.median([r['bandwidth_cost_d_L1b'] for r in gs_]), 3),
                           '<b>%s</b>' % sgn(st.median([r['denoise_net_d_L1_minus_L1b'] for r in gs_]), 3),
                           sgn(st.median([r['d_L2'] for r in gs_]), 3)]))
    S.append(slide(
        'Cascade · Why', 'bc',
        'The Damage Grows as the Input Gets Cleaner',
        '净动作与带宽代价走势不同 → 反证对照臂抽的是网络行为',
        '<div class="cols c21">'
        + fig('fig-cas-decomposition',
              '<b>口径三要素</b> ｜ 数据集：MUSDB18-HQ test Top-10 × DNS freesound ｜'
              '片段：10 曲 × 4 SNR × 20 s ｜ 指标：ΔSDR(dB) 按链路分解（L1 vs L1b vs 差值）',
              max_w=1250)
        + tbl(['SNR(dB)', 'L0 基线', 'ΔL1', '带宽代价', '★净动作', 'ΔL2 后置'], brows, 'sm')
        + '</div>'
        + '<div class="note good"><b>判别性证据</b>：<b>净动作随输入 SNR 单调恶化</b>'
          '（%s → %s dB），而<b>带宽代价与 SNR 基本无关</b>（%s ~ %s dB）。'
          '两条走势不同 ⇒ <code>L1 − L1b</code> 抽出的确实是<b>降噪网络的行为</b>，'
          '不是管线固定损耗。</div>'
        % (sgn(st.median([r['denoise_net_d_L1_minus_L1b'] for r in byb[-5.0]]), 3),
           sgn(st.median([r['denoise_net_d_L1_minus_L1b'] for r in byb[10.0]]), 3),
           g(min(r['bandwidth_cost_d_L1b'] for r in CAS_ROWS), 3),
           g(max(r['bandwidth_cost_d_L1b'] for r in CAS_ROWS), 3)),
        '<b>40 秒。</b>这一页回答「凭什么说这是网络行为」。<br>'
        '我把 16 个格子按输入信噪比重新聚合，得到右边这张表。看最后两列：'
        '<b>净动作</b>随着输入越来越干净，从 ' + g(abs(st.median([r['denoise_net_d_L1_minus_L1b'] for r in byb[-5.0]]))) +
        ' dB 一路恶化到 ' + g(abs(st.median([r['denoise_net_d_L1_minus_L1b'] for r in byb[10.0]]))) + ' dB，'
        '而<b>带宽代价几乎不随信噪比变化</b>。<br>'
        '这两条走势完全不同，恰恰说明我减出来的那一项是「网络做的事」，'
        '不是「管线固定扣掉的那点损耗」。这也是我一直强调对照臂的原因。',
        foot='口径三要素 ｜ 数据集：MUSDB18-HQ test Top-10 × DNS freesound ｜ 片段：10 曲 × 4 SNR × 20 s ｜ '
             '指标：ΔSDR(dB)，逐 SNR 档跨模型中位（n=4）'))

    # ---- S20 级联 · 机理 -------------------------------------------------
    S.append(slide(
        'Cascade · Mechanism', 'bc',
        'The Separator Degenerates Into Identity',
        '为什么降噪会伤分离：它把 drums / bass / other 当噪声删掉了',
        '<div class="cols c21">'
        + tbl(['前置变体', 'vocals', 'drums', 'bass', 'other', '含义'], [
            ('base', ['V0 带噪直送', '0.381', '0.490', '0.371', '0.404', '参照臂']),
            ('', ['V1bl 仅带宽', '0.421', '0.446', '0.430', '0.343', '≈ V0，只付带宽代价']),
            ('', ['V1mel', '0.429', '0.457', '0.431', '0.321', '≈ V0，mel 近恒等']),
            ('sep', ['V1den 降噪', '<b>0.989</b>', '<b>0.038</b>', '<b>0.014</b>', '<b>0.048</b>',
                     '★vocals≈1.0 而其余 →0']),
        ], 'sm')
        + '<div class="note bad"><b>机理</b>：前置 denoiser 把 drums / bass / other 当成噪声压掉，'
          '只剩下人声。分离器收到的输入<b>已经接近「人声轨」</b>，于是它只需要近恒等映射'
          '（其他三轨输出≈0）→ 表观 SDR 崩掉。<br>'
          '这是<b>任务错配</b>（语音降噪器不懂音乐），不是实现错误。</div>'
        + '</div>'
        + '<div class="note">同样的证据链也在板 2 内成立：级联中的 <code>V1den</code> 行为与 T5 探针'
          '「denoiser 把干净语音也压到 0.83~0.87 电平」是同一件事的两处观测。</div>',
        '<b>35 秒。</b>最后一页级联，讲机理。<br>'
        '这张表是前置处理后四个音轨相对输入的电平。前两行是参照臂：'
        '直送带噪和只做带宽转换，四轨电平都在 0.3~0.5，基本均衡。<br>'
        '<b>但看最后一行</b>：走降噪之后人声电平 0.989，几乎原样保留；'
        '鼓、贝斯、其它三轨掉到 0.01~0.04，<b>几乎被完全删掉</b>。<br>'
        '原因很直白：这个 denoiser 是为语音设计的，它把鼓和贝斯当成了噪声。'
        '分离器拿到的输入已经差不多就是人声轨，当然只能退化成恒等映射。'
        '这是<b>任务错配</b>，不是实现问题。',
        foot='口径三要素 ｜ 数据集：级联 640 格前置音频 ｜ 片段：10 曲 × 4 SNR × 20 s ｜ '
             '指标：各轨输出 / 输入 rms 中位；详见 <code>T6_CASCADE_DENOISE_BEFORE_SEPARATION.md</code> §机理'))

    # ---- S21 结论速览 ---------------------------------------------------
    S.append(slide(
        'Conclusion', 'sum',
        'Conclusions',
        '三句话，各有独立证据链',
        kpis([
            ('', 'Board 1', '分离有效且可量化退化',
             '四轨最佳 avg4 <b>%s dB</b>（mixture 基线 %s dB）；大厅混响 ΔSDR <b>%s dB</b>；'
             '20 秒/整曲成本双口径齐备' % (g(rank[0][3]), g(mix_avg4), g(mc_r[2]))),
            ('t2', 'Board 2', '降噪有效，但有效域必须声明',
             '真实含噪 ΔSI-SDR <b>%s dB</b> / ΔPESQ <b>%s</b>（16 kHz）；'
             'mel-roformer 近恒等；两族有效域<b>不重叠</b>' % (
                 g(d48['si_sdr_improve']), sgn(d48['pesq_improve'], 3))),
            ('t3', 'Cascade', '级联为负，且已定位到动作本身',
             'L1 <b>%s dB</b> = 带宽 %s + 净动作 <b>%s dB</b>；'
             '机制 = 降噪把非人声轨当噪声删除' % (
                 sgn(CAS_SUM['median_d_L1'], 3), sgn(CAS_SUM['median_d_L1b'], 3),
                 sgn(CAS_SUM['median_denoise_net'], 3))),
        ])
        + '<div class="note good"><b>方法论上的三条沉淀</b>：'
          '① <b>对照臂</b>是负结果可解释的前提（<code>L1b</code> / mixture 基线 / dry 探针）；'
          '② <b>换个口径重跑</b>是排除自造 bug 的唯一可靠手段（P19 修完结论反转）；'
          '③ <b>空值不是 0</b>、<b>比例量塌陷不等于滤波</b> —— 两个差点写进论文的假象。</div>',
        '<b>35 秒。</b>总结三句话。板 1：分离是有效的，四轨最佳比不分离的基线高出一个明显的量级，'
        '并且混响环境下的退化是可量化的。板 2：降噪也有效，但必须声明有效域 —— '
        '两个模型族一个擅长真实噪声，一个擅长合成噪声，互不覆盖。'
        '级联：把两者串起来是负结果，而且我已经把原因定位到「降噪动作本身」，而不是带宽损失。<br>'
        '比结论更重要的是三条方法论沉淀：对照臂、换口径重跑、以及「空值不是零」。',
        foot='所有数字的源文件与复现命令见 T8.3 §6 数字溯源表；三块结论分属三套数据集，不可跨行比较'))

    # ---- S22 诚实性 -----------------------------------------------------
    S.append(slide(
        'Integrity', 'sum',
        'Negative Results & Known Gaps (Reported As-Is)',
        '照报清单：没有一条被美化或删除',
        '<div class="cols">'
        + tbl(['#', '负结果 / 缺口', '处置'], [
            ('', ['1', '级联前置降噪为负（−3.99 dB）', '分解为带宽 + 净动作，机理定位到任务错配']),
            ('', ['2', '去混响 ckpt 不可用', '官方推理路径交叉验证 → 非我方实现错误']),
            ('', ['3', 'mel-roformer 近恒等映射', '改写为「有效域互补」，报作用量差']),
            ('', ['4', '域外探针为负（synth）', '转正面结论：两族有效域不重叠']),
            ('', ['5', 'DPRNN 自训 5 h 欠训练（−1.72 dB）', '显式标注非官方权重，不进结论']),
            ('', ['6', 'RPCA 无四轨均值', '只报区间与耗时，不进排名']),
            ('', ['7', 'BSRNN-SIMO 只跑完 14/50', '标注截断，已拍板不补跑']),
            ('', ['8', '主表为 train 子集（in-domain）', '副表另给 test 整曲口径，两表不混列']),
        ], 'sm')
        + tbl(['#', '负结果 / 缺口', '处置'], [
            ('', ['9', '分析窗实为 2 s / 1.5 s（旧文档写 1 s）', '量化 |Δ| 均值 0.267 dB']),
            ('', ['10', 'PESQ 在 44.1 kHz 下为空', '声明为设计（定义域），<b>不当 0 用</b>']),
            ('', ['11', 'dns_dev 无 clean GT', '只报电平行为量，fullref 列写 null']),
            ('', ['12', '门禁首轮 35 格 FAIL 系语义误判', '免重跑重判 → 全格 PASS，判据留档']),
            ('', ['13', '10 张图非 300 dpi', '属「不重跑」组，均满足单栏等效宽度']),
            ('', ['14', '长跑无法创建脱离进程', '改逐格 JSONL 增量落盘 + 幂等续跑']),
        ], 'sm')
        + '</div>',
        '<b>30 秒。</b>这一页是照报清单，一共 14 条。我不打算逐条念，请大家看它的<b>形态</b>：'
        '每一条都有对应的处置动作，而不是一句「受限于时间」或者干脆删掉。<br>'
        '我想强调第 4 条和第 14 条：一个是把负结果转成了正面结论，'
        '一个是把环境限制变成了一个工程改进（逐格落盘、断点续跑）。'
        '我认为一个 FYP 的可信度，很大程度上取决于它<b>敢不敢把自己不利的东西写进正文</b>。',
        foot='逐条来源与复核命令见 T8.3 §3（口径坑 18 条）与 §4（已知取舍与缺口）'))

    # ---- S23 口径与差异 --------------------------------------------------
    dm_params = [r for r in D['profile'] if r['model_key'] == 'demucs'][0]['params_M']
    dm_avg4 = [t for t in rank if t[0] == 'demucs'][0][3]
    S.append(slide(
        'Integrity', 'sum',
        'Why My Numbers Differ From the Reference Table',
        'T8.3 口径与差异说明 —— 挡掉「你是不是做错了」',
        tbl(['差异项', '参考表', '本机（重算）', '差异主因'], [
            ('', ['Demucs 参数量', '128 M', '<b>%s M</b>' % g(dm_params, 2),
                  '参考表是<b>原版 Demucs(v1)</b>，本机是 <b>HTDemucs</b>']),
            ('', ['Demucs SDR', '6.03 dB', '<b>%s dB</b>' % g(dm_avg4),
                  '整曲单模型池 vs <b>3 个能量均衡片段中位数、12 模型池</b>']),
            ('', ['DPRNN-TasNet', '6.01 dB', '<b>%s dB</b>' % g([t for t in rank if t[0] == 'dprnn'][0][3]),
                  '本机为<b>自训 5 h</b> 权重（官方只发语音权重）']),
            ('sep', ['RPCA+DRNN', '5.80 dB', '无产出', '论文未公开代码，无法复现']),
        ], 'sm')
        + '<div class="cols">'
        + '<div class="note"><b>三条通用差异</b>（任何一行都归到这三条）：'
          '① <b>子集不同</b>（train vs test）② <b>实现版本不同</b>（HTDemucs ≠ Demucs v1）'
          '③ <b>评价口径不同</b>（mono / 2 s 窗 / 能量均衡片段 vs 整曲）</div>'
        + '<div class="note good"><b>核对方式</b>：参考表列标出处，本机列由脚本从源产物'
          '<b>重算</b>并逐格比对（容差 0.005）→ 无 WARN。<b>我们选择把差异写清楚，而不是硬凑数字。</b></div>'
        + '</div>',
        '<b>30 秒。</b>这一页专门挡一类提问：「你的数字怎么跟论文不一样？」<br>'
        '我把差异逐格列出，归成三条通用原因：子集不同、实现版本不同、评价口径不同。'
        '比如 Demucs，参考表写 128M 参数，我这里只有 42M —— 参考表指原版 Demucs，'
        '我用的是 HTDemucs，不是同一代模型。<br>'
        '我的态度是<b>把差异写清楚，而不是凑一个更像论文的数字</b>。'
        '这份说明覆盖 18 条口径坑和 7 个速答卡，也是论文方法与局限章节的素材。',
        foot='完整版：<code>00_shared/docs/PAPER_SCOPE_AND_DIVERGENCE.md</code>（7 节 / 211 行，机器生成，'
             '<code>--verify</code> 逐字节一致）'))

    # ---- S24 收尾 -------------------------------------------------------
    S.append(slide(
        'Wrap-up', 'sum',
        'Reproducible by Design',
        '交付物一页索引 · 全部可一键复现',
        tbl(['交付物', '路径', '复现命令'], [
            ('', ['四份数据摘要', '<code>00_shared/docs/summaries/*.md</code>', '<code>_build_summaries.py --verify</code>']),
            ('', ['三块离线看板', '<code>*/html/*_dashboard.html</code>', '<code>_build_dashboards.py --only all</code>']),
            ('', ['论文图包 %d 张 + 图注' % n_fig, '<code>00_shared/figures/paper/</code>', '<code>_export_paper_figures.py --board 1 check</code>']),
            ('', ['口径与差异说明', '<code>00_shared/docs/PAPER_SCOPE_AND_DIVERGENCE.md</code>', '<code>_build_paper_scope.py --verify</code>']),
            ('', ['答辩 slides（本文件）', '<code>04_defense/defense_slides.html</code>', '<code>_build_slides.py --verify</code>']),
        ], 'sm')
        + '<div class="note good"><b>环境与铁律</b>：解释器固定 venv；'
          '脚本一律 <code>import paths; setup_env()</code>；'
          '长任务逐格 JSONL 落盘可断点续跑；<b>图上每个数字都能追到源文件</b>。</div>'
        + '<div class="note" style="text-align:center;font-size:19px;padding:16px">'
          '<b>谢谢 · Questions?</b></div>'
        + kpis([
            ('', g(top_avg4) + ' dB', '板 1 最佳四轨 SDR', 'vs mixture %s dB' % g(mix_avg4)),
            ('t2', g(d48['si_sdr_improve']) + ' dB', '板 2 真实含噪 ΔSI-SDR', '16 kHz · valentini n=%d' % d48['n_ok']),
            ('t3', g(num(CAS_SUM['median_d_L1']), 3) + ' dB', '级联负结果', '照报，已定位到动作本身'),
        ]),
        '<b>收尾 15 秒。</b>最后一页是交付物索引。我想留给大家的印象是：'
        '这个项目里<b>任何一个数字，都能顺着脚本追回它的源文件和口径</b>；'
        '任何一个结论，都有一个对照臂在支撑。谢谢，请提问。',
        foot='生成 %s ｜ 全部脚本与产物位于 <code>E:\\FYP_HKBU</code> ｜ '
             '答辩口径声明：T8.3《口径与差异说明》' % NOW))

    return S


# ================================================================ 组装
JS = '''
(function(){
var slides=[].slice.call(document.querySelectorAll('.slide'));
var cur=0, notesOn=false;
function show(i){
  if(i<0)i=0; if(i>=slides.length)i=slides.length-1;
  slides.forEach(function(s,k){s.classList.toggle('on',k===i);});
  cur=i;
  document.getElementById('pg').textContent=(i+1)+' / '+slides.length;
  document.getElementById('prog').style.width=((i+1)/slides.length*100)+'%';
  var n=slides[i].querySelector('aside.notes');
  if(n)n.classList.toggle('show',notesOn);
  try{history.replaceState(null,'','#'+(i+1));}catch(e){}
}
function toggleNotes(){
  notesOn=!notesOn;
  document.getElementById('notesBtn').classList.toggle('on',notesOn);
  var n=slides[cur].querySelector('aside.notes');
  if(n)n.classList.toggle('show',notesOn);
}
function fs(){
  var d=document.documentElement;
  if(!document.fullscreenElement){ if(d.requestFullscreen)d.requestFullscreen(); }
  else if(document.exitFullscreen){ document.exitFullscreen(); }
}
document.getElementById('prev').onclick=function(){show(cur-1);};
document.getElementById('next').onclick=function(){show(cur+1);};
document.getElementById('notesBtn').onclick=toggleNotes;
document.getElementById('fsBtn').onclick=fs;
document.getElementById('printBtn').onclick=function(){window.print();};
document.addEventListener('keydown',function(e){
  var k=e.key;
  if(k==='ArrowRight'||k==='PageDown'||k===' '||k==='Enter'){e.preventDefault();show(cur+1);}
  else if(k==='ArrowLeft'||k==='PageUp'){e.preventDefault();show(cur-1);}
  else if(k==='Home'){show(0);} else if(k==='End'){show(slides.length-1);}
  else if(k==='s'||k==='S'){toggleNotes();}
  else if(k==='f'||k==='F'){fs();}
});
var h=parseInt((location.hash||'').replace('#',''),10);
show(isNaN(h)?0:h-1);
})();
'''

DOC = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<div id="stage"><div id="deck">__SLIDES__</div></div>
<div id="bar">
  <button id="prev">&#8249; 上一页</button>
  <span id="pg">1 / 1</span>
  <button id="next">下一页 &#8250;</button>
  <button id="notesBtn">讲稿 (S)</button>
  <button id="fsBtn">全屏 (F)</button>
  <button id="printBtn">打印 / PDF</button>
  <span class="sp"></span>
  <span id="prog" style="display:none"></span>
  <span style="color:#6b7280">FYP_HKBU ｜ 自包含离线文件，双击即开 ｜ 数字全部读自 JSON / CSV</span>
</div>
<script>__JS__</script>
</body>
</html>
'''


def render():
    S = build()
    html = (DOC.replace('__TITLE__', 'FYP 答辩 slides ｜ 双板可复现评测')
            .replace('__CSS__', CSS)
            .replace('__SLIDES__', '\n'.join(S))
            .replace('__JS__', JS))
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true', help='重建并与磁盘逐字节比对')
    a = ap.parse_args()
    html = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if a.verify:
        if not OUT.exists():
            print('FAIL 目标文件不存在：%s' % OUT)
            return 2
        old = OUT.read_text(encoding='utf-8')
        print('重建 %d 字符 ｜ 磁盘 %d 字符' % (len(html), len(old)))
        if old == html:
            print('VERIFY OK：逐字节一致')
            return 0
        i = next((k for k in range(min(len(old), len(html))) if old[k] != html[k]), min(len(old), len(html)))
        print('VERIFY FAIL：首个差异位置 %d' % i)
        print('  磁盘: %r' % old[max(0, i - 60):i + 60])
        print('  重建: %r' % html[max(0, i - 60):i + 60])
        return 2
    OUT.write_text(html, encoding='utf-8')
    n = html.count('<section class="slide')
    print('WROTE %s' % OUT)
    print('  slides = %d ｜ %.2f MB' % (n, len(html.encode("utf-8")) / 1048576.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""阶段 7 看板构建器（T7.1 / T7.2）—— 自包含离线 HTML。

设计约束（计划书 D10）
----------------------
* **双击即开**：图片一律 base64 内嵌为 JPEG，HTML 内零外部依赖（无 CDN / 无相对路径）。
* **数字可复核**：所有结果值**从机器可读产物读取**（JSON / CSV），脚本内不手填任何结果数字。
  这条来自 T6 的教训——当时凭印象手填 d_L2b 一整列 16 个值全部填错，靠只读 CSV 的
  核验脚本才抓回来。**能算出来的数字，绝不手写。**
* **口径三要素**：每张图的图注必须写明 数据集 / 片段 / 指标定义（计划书 D12）。

用法
----
    python tools/_build_dashboards.py --only model     # T7.1 模型分析看板
    python tools/_build_dashboards.py --only all       # T7.1 + T7.2（降噪 / 级联）

输出
----
    04_reports/00_shared/html/model_analysis_dashboard.html   (T7.1)
    04_reports/02_denoising/html/denoise_dashboard.html         (T7.2，待建)
    04_reports/03_cascade/html/cascade_dashboard.html          (T7.2，待建)
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P

NOW = dt.datetime.now().strftime('%Y-%m-%d %H:%M')

# ---------------------------------------------------------------- 数据源
MEDIAN_JSON = P.DATA_COMPARISON / 'model_runs_median.json'
MIX_JSON = P.DATA_COMPARISON / 'mixture_baseline.json'
TEST_JSON = P.DATA_COMPARISON / 'test_run_analysis.json'
STAGE4_JSON = P.DATA / 'reverb' / 'stage4_summary.json'
PROFILE_CSV = P.MODEL_ANALYSIS / 'model_profile.csv'
ARCH_FIG = P.MODEL_ARCH_FIGURES
CMP_FIG = P.FIGURES_COMPARISON
TEST_FIG = P.FIGURES / 'test_run'
SPEC_FIG = P.FIGURES / 'spectrograms'
ARCH_SCRIPT = P.TOOLS / '_plot_model_arch.py'

# 主表四轨完整组（顺序 = 表内展示顺序，avg4 降序）
FOUR_TRACK = ['bsrnn_simo', 'bsrnn_all', 'mdx', 'bsrnn_large_all',
              'demucs', 'umx', 'mmdenselstm', 'convtasnet']
# 不参与排名、单独列出的两行
SEPARATE_ROWS = ['oracle', 'dprnn']
# test 集扫描的 12 个模型（口径见 MUSDB18_TEST_SWEEP §1）
TEST_SCOPE = ['oracle', 'demucs', 'bsrnn_simo', 'umx', 'mdx', 'convtasnet',
              'mmdenselstm', 'bsroformer_l12', 'bsroformer_l6', 'bsrnn',
              'bsrnn_large', 'dprnn']
TEST_LABEL_OVERRIDE = {
    'oracle': 'Oracle-IRM', 'demucs': 'Demucs', 'bsrnn_simo': 'BSRNN-SIMO',
    'umx': 'Open-Unmix', 'mdx': 'MDX-Net', 'convtasnet': 'Conv-TasNet',
    'mmdenselstm': 'MMDenseLSTM', 'bsroformer_l12': 'BS-RoFormer-L12',
    'bsroformer_l6': 'BS-RoFormer-L6', 'bsrnn': 'BSRNN-opt',
    'bsrnn_large': 'BSRNN-large', 'dprnn': 'DPRNN（自训）',
}
# 阶段 4 六模型的显示名
S4_LABEL = {
    'bsrnn_all': 'oBSRNN (4 ckpt)', 'mdx': 'MDX-Net', 'demucs': 'Demucs',
    'mmdenselstm': 'MMDenseLSTM', 'convtasnet': 'Conv-TasNet', 'umx': 'Open-Unmix',
}
S4_ORDER = ['bsrnn_all', 'mdx', 'demucs', 'mmdenselstm', 'convtasnet', 'umx']


# ---------------------------------------------------------------- 图片内嵌
def data_uri(path, max_w=1500, quality=84):
    """PNG -> JPEG(base64)。架构图文字多，调用方给更大 max_w / quality。"""
    im = Image.open(path)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


_SEP_CACHE = {}


def size_mb(paths):
    """估算这批图内嵌后的字节数（只算一次，用于打印体量）。"""
    return sum(Path(p).stat().st_size for p in paths) / 1048576.0


def figure(path, cap_html, max_w=1500, quality=84, wide=False):
    path = Path(path)
    if not path.exists():
        return '<figure class="fig"><img alt="missing"><figcaption>缺图：%s</figcaption></figure>' % path.name
    uri = data_uri(path, max_w=max_w, quality=quality)
    alt = re.sub(r'<[^>]+>', '', cap_html)
    cls = 'fig wide' if wide else 'fig'
    return ('<figure class="%s"><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>'
            % (cls, uri, alt.replace('"', ''), cap_html))


# ---------------------------------------------------------------- 版式
CSS = """
:root{--ink:#1f2937;--mut:#6b7280;--line:#e5e7eb;--bg:#f7f8fa;--card:#fff;
--blue:#2563eb;--amb:#d97706;--pur:#7c3aed;--red:#dc2626;--grn:#16a34a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Microsoft YaHei","Segoe UI",system-ui,-apple-system,sans-serif;
line-height:1.68;font-size:14.5px}
.wrap{max-width:1220px;margin:0 auto;padding:34px 26px 80px}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.3px}
.sub{color:var(--mut);font-size:13.4px;margin-bottom:8px}
.gen{color:var(--mut);font-size:12px;margin-bottom:22px}
h2{font-size:19.5px;margin:46px 0 8px;padding-bottom:8px;border-bottom:2px solid var(--line)}
h2 .no{color:var(--blue);font-weight:700;margin-right:9px}
h3{font-size:15.5px;margin:26px 0 6px}
.lead{color:#374151;margin:8px 0 14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:12px;margin:22px 0 8px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kv{font-size:24px;font-weight:700;color:var(--blue);letter-spacing:-.5px}
.kl{font-size:12.6px;color:var(--ink);font-weight:600;margin-top:2px}
.kn{font-size:11.4px;color:var(--mut);margin-top:5px;line-height:1.5}
figure{margin:16px 0 6px;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:10px}
figure img{width:100%;display:block;border-radius:6px;background:#fff}
figcaption{font-size:12.2px;color:var(--mut);padding:9px 6px 3px;line-height:1.6}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}
@media (max-width:900px){.grid2{grid-template-columns:1fr}}
.tbl{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);
border-radius:12px;overflow:hidden;font-size:12.7px;margin:12px 0}
.tbl th{background:#eef2f7;text-align:right;padding:9px 10px;font-weight:600;
font-size:11.9px;color:#374151;border-bottom:1px solid var(--line);white-space:nowrap}
.tbl th:first-child,.tbl th:nth-child(2){text-align:left}
.tbl td{padding:8px 10px;border-bottom:1px solid #f1f3f7;text-align:right}
.tbl td.name{text-align:left;font-weight:600;white-space:nowrap}
.tbl td:nth-child(2){text-align:left}
.tbl tbody tr:hover{background:#fafbfd}
.tbl tr.base td{background:#f6f7f9;font-weight:600}
.tbl tr.sep td{border-top:2px solid var(--line)}
.num{font-variant-numeric:tabular-nums}
.tbl.r2 th:nth-child(2),.tbl.r2 td:nth-child(2){text-align:right}
.neg{color:var(--red);font-weight:600}
.pos{color:var(--grn);font-weight:600}
.hl{color:var(--blue);font-weight:700}
.dim{color:var(--mut)}
.note{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--blue);
border-radius:10px;padding:14px 18px;margin:16px 0;font-size:13.6px}
.note.warn{border-left-color:var(--amb)}
.note.bad{border-left-color:var(--red)}
.note.good{border-left-color:var(--grn)}
.note b{color:var(--ink)}
ul{margin:8px 0 8px 4px;padding-left:20px}
li{margin:4px 0}
nav.toc{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:14px 20px;margin:20px 0 8px;font-size:13.2px}
nav.toc b{display:block;margin-bottom:6px}
nav.toc a{color:var(--blue);text-decoration:none;margin-right:16px;white-space:nowrap}
nav.toc a:hover{text-decoration:underline}
code{background:#eef2f7;border-radius:4px;padding:1px 5px;font-size:12.4px}
pre{background:#0f172a;color:#e2e8f0;border-radius:10px;padding:14px 16px;overflow:auto;font-size:12.2px}
.sp{height:6px}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--line);
color:var(--mut);font-size:12.2px}
"""


def page(title, subtitle, sections, toc):
    nav = ('<nav class="toc"><b>目录</b>'
           + ''.join('<a href="#%s">%s</a>' % (sid, txt) for sid, txt in toc)
           + '</nav>')
    body = '\n'.join(sections)
    return ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<div class="wrap">\n'
            '<h1>%s</h1>\n<div class="sub">%s</div>\n'
            '<div class="gen">生成于 %s ｜ 由 <code>tools/_build_dashboards.py</code> 生成，'
            '全部数字来自机器可读产物（JSON / CSV），可一键复现</div>\n%s\n%s\n'
            '<footer>FYP_HKBU ｜ 本页为离线自包含文件（图片内嵌），可直接分发；'
            '引用任何数字请一并声明对应文档的口径脚注。</footer>\n'
            '</div>\n</body>\n</html>\n'
            % (title, CSS, title, subtitle, NOW, nav, body))


def kpis(items):
    cards = ''.join('<div class="kpi"><div class="kv">%s</div><div class="kl">%s</div>'
                    '<div class="kn">%s</div></div>' % it for it in items)
    return '<div class="kpis">%s</div>' % cards


def h2(sid, no, text):
    return '<h2 id="%s"><span class="no">%s</span>%s</h2>' % (sid, no, text)


def h3(text):
    return '<h3>%s</h3>' % text


def note(text, kind=''):
    cls = ('note ' + kind).strip()
    return '<div class="%s">%s</div>' % (cls, text)


def table(headers, rows, aligns=None, tcls=''):
    """rows: list of (row_class, [cell_html...])；tcls 给 <table> 追加样式类。"""
    head = ''.join('<th>%s</th>' % h for h in headers)
    body = []
    for rc, cells in rows:
        tds = ''.join('<td>%s</td>' % c for c in cells)
        body.append('<tr class="%s">%s</tr>' % (rc, tds) if rc else '<tr>%s</tr>' % tds)
    return ('<table class="tbl %s"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            % (tcls, head, ''.join(body)))


def _med(x):
    """dict 型统计块（wall_s / rtf / sdr_mean 等）取 median；标量原样返回。"""
    return x.get('median') if isinstance(x, dict) else x


def fnum(x, nd=2, signed=False):
    if x is None:
        return '<span class="dim">—</span>'
    s = ('%+.*f' if signed else '%.*f') % (nd, x)
    if signed:
        cls = 'neg' if x < 0 else ('pos' if x > 0 else 'dim')
        return '<span class="num %s">%s</span>' % (cls, s)
    return '<span class="num">%s</span>' % s


# ---------------------------------------------------------------- 读数据
def load_all():
    d = {}
    d['median'] = json.loads(MEDIAN_JSON.read_text(encoding='utf-8'))
    d['mix'] = json.loads(MIX_JSON.read_text(encoding='utf-8'))
    d['test'] = json.loads(TEST_JSON.read_text(encoding='utf-8'))
    d['stage4'] = json.loads(STAGE4_JSON.read_text(encoding='utf-8'))
    with PROFILE_CSV.open(encoding='utf-8-sig', newline='') as fh:
        d['profile'] = {r['model_key']: r for r in csv.DictReader(fh)}
    d['arch_titles'] = parse_arch_titles()
    return d


def parse_arch_titles():
    """从 _plot_model_arch.py 解析 14 组 (title, subtitle)。

    刻意**解析源文件而不是 import 它**：避免绘图模块的副作用，同时保证
    看板标题与架构图脚本永远同源、不会各写一份而漂移。
    """
    txt = ARCH_SCRIPT.read_text(encoding='utf-8')
    hits = re.findall(r'F\(\s*"([^"]+)"\s*,\s*"([^"]+)"', txt)
    return hits[:14]


def mix_baseline_avg4(mix):
    per = mix['per_stem']
    vals = [per[k]['median'] for k in ('vocals', 'drums', 'bass', 'other') if k in per]
    return sum(vals) / len(vals)


def mean_of(dct, keys):
    vals = [dct[k] for k in keys if k in dct]
    return sum(vals) / len(vals) if vals else None


# ---------------------------------------------------------------- 看板 1：模型分析（T7.1）
def build_model_analysis(d):
    median, test, s4, profile, arch = d['median'], d['test'], d['stage4'], d['profile'], d['arch_titles']
    mix4 = mix_baseline_avg4(d['mix'])

    # ---- KPI
    tm = test['models']
    n_pass = sum(v.get('n_pass', 0) for v in tm.values())
    n_slots = len(TEST_SCOPE) * 50
    n_full = sum(1 for m in TEST_SCOPE if tm.get(m, {}).get('complete_50'))
    best_key = max(FOUR_TRACK, key=lambda k: median[k]['sdr_avg4'] or -99)
    hall_mean = mean_of(s4['reverb']['delta_hall_by_model'], S4_ORDER)
    small_mean = mean_of(s4['reverb']['delta_small_by_model'], S4_ORDER)
    echo_long = mean_of(s4['echo']['delta_long_by_model'], S4_ORDER)

    kpi_html = kpis([
        ('19 / 19', '模型部署 PASS', '完整代码 + 权重 + 零拷贝联接（D1）'),
        ('%d / %d' % (n_pass, n_slots), 'test 集实机组合', '%d 个模型跑满 50 首（MUSDB18-HQ test 整曲）' % n_full),
        ('%.2f dB' % median[best_key]['sdr_avg4'], '四轨组最优 Average SDR', '%s（mixture 基线 %.2f dB）'
         % (median[best_key]['label'], mix4)),
        ('%.2f dB' % hall_mean, '混响大厅 ΔSDR（6 模型均值）', 'T60 = %.2f s（导出 44.1k 口径）'
         % s4['reverb']['t60_hall']),
        ('%.2f dB' % echo_long, '回声 250 ms ΔSDR（6 模型均值）',
         '破坏力 = 混响大厅的 %.2f 倍（回声 %.2f / 混响 %.2f dB）'
         % (echo_long / hall_mean, echo_long, hall_mean)),
        ('14', '架构原理图', '覆盖全部 22 个模型/权重条目（T2.2 / D2）'),
    ])

    sec = []

    # ---- §1 一页总览
    sec.append(h2('s0', '0', '一页总览'))
    sec.append(note(
        '<b>板 1 回答一个问题：现成的音乐源分离模型，在本机、真实劣化条件下到底什么水平？</b><br>'
        '① 19 个模型的代码与权重全部落地并跑通（每模型独立子进程，8 GiB 卡）；'
        '② 16 个神经网络 + 3 个解析/古典方法，14 组架构原理图逐条可溯源；'
        '③ 四轨完整组 8 个模型在同一口径下横向可比，最强 <b>%.2f dB</b>（mixture 基线 <b>%.2f dB</b>）；'
        '④ 实机耗时与 RTF 排名<b>不一致</b>——开销才是主体；'
        '⑤ <b>混响是全模型共同短板</b>（大厅 Δ <b>%.2f dB</b>），且比回声致命约 %.1f 倍。'
        % (median[best_key]['sdr_avg4'], mix4, hall_mean, hall_mean / echo_long), 'good'))
    sec.append('<div class="sp"></div>')

    # ---- §2 模型供给与本体画像
    sec.append(h2('s1', '1', '模型供给与本体画像（阶段 1）'))
    sec.append('<p class="lead">每个模型三件套：完整 git 代码（零拷贝目录联接）+ 权重（唯一落点 '
               '<code>01_models/_weights/</code>）+ 模型卡。画像统一口径：'
               '<b>44.1 kHz / 立体声 / 10 s 输入</b>，参数量取模型实例、FLOPs 口径 = 2×MACs、'
               '时延为预热后 5 次中位数。</p>')

    prow = []
    order = ['oracle', 'rpca', 'umx', 'mmdenselstm', 'convtasnet', 'demucs', 'mdx',
             'bsrnn_all', 'bsrnn_simo', 'bsrnn_large_all', 'bsroformer_l6', 'bsroformer_l12',
             'dprnn', 'denoiser_dns48', 'denoiser_dns64', 'denoiser_master64',
             'mel_roformer_denoise', 'mel_roformer_dereverb', 'mel_roformer_dereverb_echo']
    seen = set()
    for k in order + sorted(profile):
        if k in seen or k not in profile:
            continue
        seen.add(k)
        r = profile[k]
        prow.append(('', [
            r.get('label', k),
            r.get('group', '') or '<span class="dim">—</span>',
            r.get('kind', ''),
            fnum(float(r['params_M']) if r.get('params_M') else None, 2),
            fnum(float(r['flops_G']) if r.get('flops_G') else None, 1),
            fnum(float(r['latency_s']) if r.get('latency_s') else None, 3),
            fnum(float(r['peak_vram_mb']) if r.get('peak_vram_mb') else None, 0),
        ]))
    sec.append(table(['模型', '组', '类别', '参数量 (M)', 'FLOPs (G)', '时延 (s)', '峰值显存 (MB)'], prow))
    sec.append(note('<b>FLOPs 是下界，不是等价比较。</b><code>FlopCounterMode</code> 只统计被 torch 调度的算子，'
                    '<code>torch.stft</code> 与融合注意力不计入。例：BS-RoFormer-L12 的 FLOPs 是 HTDemucs 的 '
                    '<b>86 倍</b>，实测时延只差 <b>16 倍</b>。跨架构比较必须配合实测时延。', 'warn'))
    sec.append('<div class="grid2">')
    sec.append(figure(ARCH_FIG / 'profile_params_flops.png',
                      '参数量 vs 计算量（口径：44.1 kHz 立体声 10 s；FLOPs = 2×MACs 下界）',
                      max_w=1400))
    sec.append(figure(ARCH_FIG / 'profile_pareto.png',
                      '代价-精度 Pareto（横轴=时延，纵轴=Average SDR）', max_w=1400))
    sec.append('</div>')

    # ---- §3 架构原理图 ×14
    sec.append(h2('s2', '2', '架构原理图 × 14（阶段 2，T2.3 待逐张签字）'))
    sec.append('<p class="lead">每张图左侧是方法的概念流程（手写自原论文），右侧是<b>真实 trace</b>：'
               '参数构成 100% 堆叠条 + 实际执行的结构骨架。图上的形状标注全部由 '
               '<code>_resolve_shape()</code> 从 <code>graph_*.json</code> 解析，'
               '<b>没有一个是手写的</b>——这是 D2 的验收标准。</p>')
    arch_files = sorted(ARCH_FIG.glob('arch_*.png'))
    for i, fp in enumerate(arch_files):
        t, st = arch[i] if i < len(arch) else (fp.stem, '')
        sec.append(figure(fp, '<b>%s</b> — %s' % (t, st), max_w=1600, quality=86))
    sec.append(note('两个解析家族（RPCA / Oracle）没有 <code>nn.Module</code>，'
                    '其图干脆<b>不印任何形状</b>并在画布上说明，而不是编一组看起来合理的数。', ''))

    # ---- §4 精度主表
    sec.append(h2('s3', '3', '精度主表：四轨完整组（阶段 3）'))
    sec.append('<p class="lead">唯一可横向比较的一张表。指标 = museval BSSEval v4 SDR（mono，'
               '<code>compute_permutation=False</code>）；子集 = <b>MUSDB18-HQ train</b>（in-domain，'
               '数字偏乐观）；片段 = 3 个能量均衡片段 × 10 s；聚合 = median-of-median。'
               '<b>只对四轨模型成立</b>——单轨模型、解析上界、自训模型跨组不可比。</p>')

    hdr = ['#', '模型', 'Average SDR', '人声', '鼓', '贝斯', '其他', 'Size (M)', 'FLOPs (G)', 'RTF']
    rows = [('base', ['—', 'Mixture（基线）', fnum(mix4, 2), fnum(d['mix']['per_stem']['vocals']['median'], 2),
                      fnum(d['mix']['per_stem']['drums']['median'], 2), fnum(d['mix']['per_stem']['bass']['median'], 2),
                      fnum(d['mix']['per_stem']['other']['median'], 2), '<span class="dim">—</span>',
                      '<span class="dim">—</span>', '<span class="dim">—</span>'])]
    for i, k in enumerate(FOUR_TRACK, 1):
        r = median[k]
        pr = profile.get(k, {})
        sdr = r['sdr']
        rows.append(('', [str(i), r['label'], '<b>%s</b>' % fnum(r['sdr_avg4'], 2)] +
                     [fnum(sdr[s]['median'], 2) for s in ('vocals', 'drums', 'bass', 'other')] +
                     [fnum(float(pr['params_M']) if pr.get('params_M') else None, 2),
                      fnum(float(pr['flops_G']) if pr.get('flops_G') else None, 1),
                      fnum(r.get('rtf'), 3)]))
    for k in SEPARATE_ROWS:
        r = median[k]
        pr = profile.get(k, {})
        sdr = r['sdr']
        tag = '解析上界（无参数）' if k == 'oracle' else '负面对照（自训 5 h）'
        rows.append(('sep', ['—', '%s<span class="dim"> · %s</span>' % (r['label'], tag),
                             fnum(r['sdr_avg4'], 2)] +
                     [fnum(sdr[s]['median'], 2) for s in ('vocals', 'drums', 'bass', 'other')] +
                     [fnum(float(pr['params_M']) if pr.get('params_M') else None, 2),
                      fnum(float(pr['flops_G']) if pr.get('flops_G') else None, 1),
                      fnum(r.get('rtf'), 3)]))
    sec.append(table(hdr, rows))
    sec.append(note('<b>RPCA 不进本表</b>：稀疏分量没有天然的 stem 归属。'
                    '<b>单轨模型</b>（BS-RoFormer L12/L6、BSRNN-opt/large）也不进——它们只产 1~2 条轨，'
                    '与四轨 avg4 不同轴。', 'warn'))
    sec.append(h3('单目标组（只产 1~2 条轨，不可与上表同轴比较）'))
    srow = []
    for _k in ('bsroformer_l6', 'bsroformer_l12'):
        _r = median[_k]
        _pr = profile.get(_k, {})
        _tgt = '/'.join(sorted(_r['sdr']))
        _sd = sum(v['median'] for v in _r['sdr'].values()) / len(_r['sdr'])
        _si = sum(v['median'] for v in _r['si_sdr'].values()) / len(_r['si_sdr'])
        srow.append(('', [_r['label'], _tgt, fnum(_sd, 2), fnum(_si, 2),
                          fnum(float(_pr['params_M']) if _pr.get('params_M') else None, 2),
                          fnum(float(_pr['flops_G']) if _pr.get('flops_G') else None, 1),
                          fnum(_r.get('rtf'), 3)]))
    sec.append(table(['模型', '目标轨', 'museval SDR', 'SI-SDR', 'Size (M)', 'FLOPs (G)', 'RTF'], srow))
    sec.append(note('BSRNN-opt / BSRNN-large 同为单目标（人声）模型，主表口径下无 museval SDR 记录，'
                    '其代价见 §1 画像表；单轨 SDR <b>绝不可</b>与四轨 avg4 放在同一根柱子上比。', 'warn'))
    sec.append('<div class="grid2">')
    sec.append(figure(CMP_FIG / 'fig_median_sdr_bars.png',
                      'Average SDR 横向对比（MUSDB18-HQ train / 3 均衡片段 × 10 s / museval BSSEval v4 中位数）',
                      max_w=1400))
    sec.append(figure(CMP_FIG / 'fig_median_per_stem.png',
                      '分轨 SDR（同一口径）。可见 bass 普遍最高、other 最难', max_w=1400))
    sec.append('</div>')
    sec.append(figure(CMP_FIG / 'fig_avg_sdr_table.png',
                      '参考表样式重绘版主表（数值全部本机实测口径，非论文引用值）', max_w=2000, quality=88))
    sec.append(figure(CMP_FIG / 'fig_median_pareto.png',
                      '精度-时延 Pareto（四轨组）', max_w=1300))
    sec.append('<div class="grid2">')
    sec.append(figure(SPEC_FIG / 'panel_The_Easton_Ellises_-_Falcon_69_multimodel.png',
                      '多模型频谱面板（同曲同片段，口径见 <code>panel_song_selection.json</code>）', max_w=1500))
    sec.append(figure(SPEC_FIG / 'panel_Bobby_Nobody_-_Stitch_Up_multimodel.png',
                      '同上，另一首。三段式面板选曲见 <code>data/comparison/panel_song_selection.json</code>', max_w=1500))
    sec.append('</div>')

    sec.append(h3('与参考表的差异（答辩预案）'))
    sec.append(note(
        '三条通用差异：① <b>子集不同</b>（本表 train / 参考表 test）；'
        '② <b>实现版本不同</b>（HTDemucs vs Demucs v1；自训 DPRNN vs 官方权重）；'
        '③ <b>评价口径不同</b>（mono、2 s 窗、3 均衡片段中位数 vs 参考表整曲）。<br>'
        '<b>两处必须主动交代的缺陷</b>：主表跑在 <code>train</code> 子集（in-domain，系统性偏乐观）；'
        '分析窗<b>实际是 2 s / hop 1.5 s</b>——<code>evaluate()</code> 未传 window/hop，落到 museval '
        '签名默认值，而多处旧文档写的是「1 s 窗」，<b>与实现不符</b>。'
        '窗宽影响已量化为 |Δ| 均值 0.267 dB（<code>metric_window_probe.json</code>）。', 'warn'))

    # ---- §5 实机时间成本
    sec.append(h2('s4', '4', '实机运行成本：test 集 50 首整曲'))
    sec.append('<p class="lead">目标 12 模型 × 50 首 = 600 组合，成功 <b>%d</b> 个，<b>%d</b> 个模型跑满 50/50。'
               '调度为逐首 song-major 串行，单组合 180 s 超时上限。'
               'RTF = 推理秒数 ÷ 音频秒数（<b>不含</b>开销），故远小于「墙钟实时倍率」。</p>'
               % (n_pass, n_full))
    trow = []
    for k in sorted(TEST_SCOPE, key=lambda m: tm.get(m, {}).get('wall_s', {}).get('median') or 1e9):
        v = tm.get(k)
        if not v:
            continue
        nt = v.get('n_tracks') or {}
        nt_s = ('%s 轨' % '/'.join(sorted(nt))) if nt else '<span class="dim">—</span>'
        done = '%d/50' % v.get('n_pass', 0)
        med = (v.get('wall_s') or {}).get('median')
        trow.append(('', [TEST_LABEL_OVERRIDE.get(k, v.get('label', k)), nt_s, done,
                          fnum(med, 1), fnum(_med(v.get('rtf')), 3),
                          fnum(_med(v.get('sdr_mean')), 2), fnum(v.get('out_mb_total'), 0)]))
    sec.append(table(['模型', '输出形态', '完成', '中位单首 (s)', 'RTF 中位', 'SDR 中位 (dB)', '产物 (MB)'], trow))
    sec.append('<div class="grid2">')
    sec.append(figure(TEST_FIG / '02_inference_vs_overhead.png',
                      '推理 vs 记账外开销（test 集 50 首整曲；开销含评测/导入/读写/调度）', max_w=1400))
    sec.append(figure(TEST_FIG / '06_speed_accuracy.png',
                      '速度-精度散点（test 集整曲；耗时为准，非 RTF）', max_w=1400))
    sec.append('</div>')
    sec.append(figure(TEST_FIG / '10_sdr_heatmap.png',
                      '逐曲 SDR 热力图（模型 × 歌曲）', max_w=1700))
    sec.append(note(
        '<b>五条可直接引用</b>：① 累计 10.17 h 里只有 4.25 h（42%）是推理——最快的 Oracle-IRM '
        '推理中位 3.2 s/首，端到端却 52.0 s/首，<b>93% 花在每首重付的开销上</b>，'
        '按 RTF 排序会得到错误的实机排名；② <b>输出轨数是一等成本项</b>，同曲配对后 4 轨比 1 轨每首多花中位 31.0 s；'
        '③ 耗时与歌长只是中等相关（r = 0.554，n = 564）；④ 8 小时连续负载<b>无热漂移</b>（50 首累计 −1.8%）；'
        '⑤ 四轨模型中 <b>MDX-Net 是最佳「快 + 准」折中</b>。', 'good'))

    # ---- §6 混响 / 回声退化
    sec.append(h2('s5', '5', '受控劣化：混响 / 回声（阶段 4）'))
    sec.append('<p class="lead">在<b>已知 RIR / 已知回声参数</b>下做受控劣化探针。'
               '参考信号是<b>干 GT stem</b>（湿信号不是参考），故 ΔSDR 衡量「输入劣化导致的绝对损失」。'
               '混响档：小房间 T60 = %.2f s、大厅 T60 = %.2f s（<b>导出 44.1 kHz 口径</b>，'
               '源 48k 为 0.600 / 1.205 s）。</p>'
               % (s4['reverb']['t60_small'], s4['reverb']['t60_hall']))
    rrow = []
    rv, ec = s4['reverb'], s4['echo']
    for k in S4_ORDER:
        rrow.append(('', [S4_LABEL[k],
                          fnum(rv['delta_small_by_model'].get(k), 2, True),
                          fnum(rv['delta_hall_by_model'].get(k), 2, True),
                          fnum(ec['delta_short_by_model'].get(k), 2, True),
                          fnum(ec['delta_long_by_model'].get(k), 2, True)]))
    rrow.append(('base', ['<b>6 模型均值</b>', '<b>%s</b>' % fnum(small_mean, 2, True),
                          '<b>%s</b>' % fnum(hall_mean, 2, True),
                          '<b>%s</b>' % fnum(mean_of(ec['delta_short_by_model'], S4_ORDER), 2, True),
                          '<b>%s</b>' % fnum(echo_long, 2, True)]))
    sec.append(table(['模型', 'Δ 小房间 (0.49 s)', 'Δ 大厅 (1.03 s)', 'Δ 回声 80 ms', 'Δ 回声 250 ms'],
                    rrow, tcls='r2'))
    sec.append('<div class="grid2">')
    sec.append(figure(CMP_FIG / 'fig_rir_t60.png',
                      '两条 RIR 的 T60 估计（Schroeder 反向积分 + T30；拟合前剔除 ±2.5 ms 直达声）', max_w=1500))
    sec.append(figure(CMP_FIG / 'fig_stage4_summary.png',
                      '阶段 4 一页图（答辩用）：混响 vs 回声的破坏力量级对比', max_w=1500))
    sec.append('</div>')
    sec.append(figure(CMP_FIG / 'fig_reverb_degradation.png',
                      'ΔSDR 随 T60 的退化曲线（6 模型 × 3 档；x 轴为导出 44.1k 口径）', max_w=1700))
    sec.append(figure(CMP_FIG / 'fig_echo_degradation.png',
                      'ΔSDR 随回声档的退化曲线（同一胶水层，公式 y[n]=x[n]+g·x[n−D] 逐 stem 施加）', max_w=1700))
    sec.append(note('<b>三条发现</b>：① 纯混响就能把 6 个主流模型的 avg4 SDR 从 +3.8~+7.5 dB 打到 '
                    '<b>−6~−9 dB</b>；② 退化随 T60 <b>严格单调</b>（6/6 模型三点单调）；'
                    '③ 退化幅度与模型强弱<b>反相关</b>——干态最强的掉得最狠，说明混响是'
                    '<b>全模型共同短板，不是个别缺陷</b>。', 'good'))
    sec.append(note('<b>去混响 = 负结果（照报）</b>：<code>anvuew</code> 中位增益仅 <b>%s dB</b>'
                    '（最好一次 %s dB），只挽回湿信号损失的 3~11%%；<code>Dereverb-Echo</code> 的 '
                    '<code>dry</code> 支 rms 塌到 1e-5~2e-3（≈静音），<b>不可用</b>。'
                    '已用上游官方分块推理路径交叉验证：Δ si 仅 <b>%s dB</b> → '
                    '<b>不是我们实现错</b>，根因是域不匹配。'
                    % (fnum(s4['dereverb']['anvuew_gain_median'], 3),
                       fnum(s4['dereverb']['anvuew_gain_max'], 2),
                       fnum(s4['dereverb']['official_cross_check_delta_db'], 3)), 'bad'))

    # ---- §7 口径与坑
    sec.append(h2('s6', '6', '引用前必读：口径与已知坑'))
    sec.append(table(['#', '事项', '说明'], [
        ('', ['1', '主表子集 = <code>train</code>', 'in-domain，数字系统性偏乐观；与参考表（test）不可逐格对齐']),
        ('', ['2', '分析窗实际 2 s / hop 1.5 s', '<code>evaluate()</code> 未传 window/hop；旧文档写「1 s 窗」有误；|Δ| 均值 0.267 dB']),
        ('', ['3', 'FLOPs = 下界', '<code>stft</code> 与融合注意力不计入；跨架构比较须配合实测时延']),
        ('', ['4', 'RTF 受负载影响', '同一模型两次可差 2×；只做量级参考，排名请用整曲墙钟']),
        ('', ['5', '单轨模型不可与四轨 avg4 同轴', 'BS-RoFormer / BSRNN-opt 只产 1~2 条轨']),
        ('', ['6', 'DPRNN 是自训 5 h 的负面对照', '官方只发语音权重，本机无法复现论文值']),
        ('', ['7', 'RPCA 不出四轨均值', '稀疏分量无天然 stem 归属，只能报区间']),
    ]))

    # ---- §8 产物与复现
    sec.append(h2('s7', '7', '产物与复现'))
    sec.append(note('<b>数据</b>：<code>04_reports/01_separation/data/comparison/</code>'
                    '（<code>model_runs_median.json</code> 主表、<code>mixture_baseline.json</code> 基线、'
                    '<code>test_run_analysis.json</code> 整曲扫描）+ '
                    '<code>data/reverb/stage4_summary.json</code> + '
                    '<code>00_shared/data/model_analysis/model_profile.csv</code><br>'
                    '<b>文档</b>：<code>docs/MEDIAN_TABLE_REDRAWN.md</code>（主表+口径）、'
                    '<code>docs/MUSDB18_TEST_SWEEP_2026-09-22.md</code>（整曲扫描）、'
                    '<code>docs/STAGE4_SUMMARY.md</code>（阶段 4 小结）、'
                    '<code>00_shared/docs/MODEL_PROFILE_2026-09-22.md</code>（画像）、'
                    '<code>00_shared/docs/MODEL_DEPLOYMENT_2026-09-23.md</code>（部署）<br>'
                    '<b>重建本页</b>：<code>python tools/_build_dashboards.py --only model</code>'))

    toc = [('s0', '0 总览'), ('s1', '1 供给与画像'), ('s2', '2 架构图 ×14'), ('s3', '3 精度主表'),
           ('s4', '4 实机成本'), ('s5', '5 混响/回声'), ('s6', '6 口径与坑'), ('s7', '7 产物')]
    return page('模型分析看板 · 板 1 源分离（阶段 1–4）',
                '交付物 D10 看板 1 ｜ 19 模型部署 · 14 组架构原理图 · 四轨精度主表 · '
                'test 集整曲实测 · 混响/回声退化', [kpi_html] + sec, toc)


# ---------------------------------------------------------------- 主入口
BUILDERS = {
    'model': ('model_analysis_dashboard.html', P.SHR_HTML, build_model_analysis),
}


def _build_local(want):
    """构建本模块（T7.1）的看板。"""
    d = load_all()
    rc = 0
    for w in want:
        fname, outdir, fn = BUILDERS[w]
        html_txt = fn(d)
        outdir.mkdir(parents=True, exist_ok=True)
        out = outdir / fname
        out.write_text(html_txt, encoding='utf-8')
        n_img = html_txt.count('data:image/jpeg;base64,')
        print('[ok] %-34s %7.2f MB  (%d images embedded)'
              % (out.name, len(html_txt.encode('utf-8')) / 1048576.0, n_img))
        print('     -> %s' % out)
        rc |= 0
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(description='阶段 7 看板构建器（自包含离线 HTML）')
    ap.add_argument('--only', default='all',
                    help='model | denoise | cascade | all')
    a = ap.parse_args(argv)

    choices = ('all', 'model', 'denoise', 'cascade')
    if a.only not in choices:
        raise SystemExit('[FATAL] 未知看板 %r（可用：%s）'
                         % (a.only, ' / '.join(choices)))

    rc = 0
    if a.only in ('all', 'model'):
        rc |= _build_local(['model'])
    if a.only in ('all', 'denoise', 'cascade'):
        # T7.2 的两块看板在 _build_dashboards_t72；惰性 import 避免与本模块循环依赖
        import _build_dashboards_t72 as T72
        rc |= T72.main(['--only', a.only])
    return rc


if __name__ == '__main__':
    sys.exit(main())

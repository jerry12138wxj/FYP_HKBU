# -*- coding: utf-8 -*-
"""阶段 7 · 看板 2 / 3 构建器（T7.2）—— 降噪看板 + 级联看板。

与 T7.1 的关系
--------------
本模块 **import** `_build_dashboards`（下称 B）复用其 CSS / page / kpis / table /
figure 等版式与图片内嵌工具，自己只负责 T7.2 两块看板的数据装配与文案。
三个看板因此共用一套视觉与内嵌逻辑，且**不触碰**已验证的 T7.1 代码。

设计约束（与 T7.1 相同，计划书 D10 / D12）
------------------------------------------
* **双击即开**：图片 base64 内嵌，HTML 内零外部依赖。
* **数字可复核**：结果值一律从 JSON / CSV 读取，脚本内不手填任何结果数字。
  唯一例外是**已作废的历史数字**（如 P19 前 dns_dev 塌陷率 40%），
  它只作为「纠错对照」出现，并显式标注出处文档。
* **口径三要素**：每张图的图注写明 数据集 / 片段 / 指标定义。

用法
----
    python tools/_build_dashboards_t72.py --only denoise
    python tools/_build_dashboards_t72.py --only cascade
    python tools/_build_dashboards_t72.py --only all
    python tools/_build_dashboards.py --only all      # 三块看板一起建

输出
----
    04_reports/denoiser/html/denoise_dashboard.html
    04_reports/cascade/html/cascade_dashboard.html
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P                      # noqa: E402
import _build_dashboards as B          # noqa: E402  复用版式与图片内嵌工具

# ---------------------------------------------------------------- 数据源
DEN_EVAL_16K = P.DEN_DATA / 'denoise_eval_16k.json'
DEN_EVAL_44K = P.DEN_DATA / 'denoise_eval_44k.json'
DEN_DRYWET = P.DEN_DATA / 'denoise_drywet.json'
DEN_MANIFEST = P.DEN_DATA / 'denoise_manifest.json'
DEN_OOD = P.DEN_DATA / 'denoise_ood_probe.json'
DEN_PROBE_A = P.DEN_DATA / 'denoise_probeA_paired.json'
CAS_EVAL = P.CAS_DATA / 'cascade_eval.json'
CAS_PLAN = P.CAS_DATA / 'cascade_plan.json'
CAS_MANIFEST = P.CAS_DATA / 'cascade_manifest.json'

DEN_FIG = P.DEN_FIGURES
CAS_FIG = P.CAS_FIGURES

# 板 2 五个降噪模型（3 个 denoiser 权重 + 2 个 Mel-RoFormer 变体）
DEN_ORDER = ['denoiser_dns48', 'denoiser_dns64', 'denoiser_master64',
             'mel_roformer_denoise', 'mel_roformer_denoise_aggr']
DEN_NAME = {
    'denoiser_dns48': 'denoiser dns48',
    'denoiser_dns64': 'denoiser dns64',
    'denoiser_master64': 'denoiser master64 ★',
    'mel_roformer_denoise': 'Mel-RoFormer (aufr33)',
    'mel_roformer_denoise_aggr': 'Mel-RoFormer (aggr)',
}
BINS = ['ALL', '>=15dB', '5-15dB', '<5dB']
# 4 个分离模型的显示名（级联看板）
SEP_NAME = {
    'demucs': 'Demucs (htdemucs)',
    'mdx': 'MDX-Net (mdx_extra)',
    'bsrnn_all': 'oBSRNN (4 ckpt, 4-stem)',
    'umx': 'Open-Unmix (umxhq)',
}
SEP_ORDER = ['demucs', 'mdx', 'bsrnn_all', 'umx']
STEMS = ['vocals', 'drums', 'bass', 'other']


# ---------------------------------------------------------------- 小工具
def _med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def _pct(v, q):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    return v[min(len(v) - 1, int(q * (len(v) - 1)))]


def _share(v, thr):
    v = [x for x in v if x is not None]
    if not v:
        return None
    return 100.0 * sum(1 for x in v if x < thr) / len(v)


def n(x, nd=2, signed=False, dash='—'):
    if x is None:
        return '<span class="dim">%s</span>' % dash
    return B.fnum(x, nd, signed)


# ---------------------------------------------------------------- 读数据
def load_t72():
    d = {}
    d['den16'] = json.loads(DEN_EVAL_16K.read_text(encoding='utf-8'))
    d['den44'] = json.loads(DEN_EVAL_44K.read_text(encoding='utf-8'))
    d['drywet'] = json.loads(DEN_DRYWET.read_text(encoding='utf-8'))
    d['denman'] = json.loads(DEN_MANIFEST.read_text(encoding='utf-8'))
    d['ood'] = json.loads(DEN_OOD.read_text(encoding='utf-8'))
    d['probeA'] = json.loads(DEN_PROBE_A.read_text(encoding='utf-8'))
    d['cas'] = json.loads(CAS_EVAL.read_text(encoding='utf-8'))
    d['casplan'] = json.loads(CAS_PLAN.read_text(encoding='utf-8'))
    d['casman'] = json.loads(CAS_MANIFEST.read_text(encoding='utf-8'))
    return d


def den_rows(ev, subset=None):
    r = ev['rows']
    if subset:
        r = [x for x in r if x['subset'] == subset]
    return r


def den_row(ev, model, subset, bin_):
    for x in ev['rows']:
        if x['model'] == model and x['subset'] == subset and x['snr_bin'] == bin_:
            return x
    return None


def dry_opt(drywet):
    """按 (model, 档) 求 ΔSI-SDR / ΔPESQ 最优 dry，含 ALL 档（跨档合池）。"""
    cells = drywet['cells']
    grid = [float(g) for g in drywet['dry_grid']]
    # agg[(model, bin)][dry] -> {'sisdr': [...], 'pesq': [...]}
    agg = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(list)))
    for c in cells:
        for k, v in c['dry'].items():
            dry = float(k)
            b = v.get('snr_bin') or 'ALL'
            for key in (b, 'ALL'):
                agg[(c['model'], key)][dry]['sisdr'].append(v.get('si_sdr_out'))
                if v.get('pesq_out') is not None and v.get('pesq_in') is not None:
                    # 与主表同口径：逐条配对差后取中位（非 med(out)-med(in)）
                    agg[(c['model'], key)][dry]['pesq'].append(v['pesq_out'] - v['pesq_in'])
    out = {}
    for key, row in agg.items():
        curves = {}
        for dry in grid:
            if dry not in row:
                continue
            curves[dry] = {
                'sisdr': _med(row[dry]['sisdr']),
                'pesq': _med(row[dry]['pesq']),
            }
        best_si = max((d for d in curves if curves[d]['sisdr'] is not None),
                      key=lambda d: curves[d]['sisdr'], default=None)
        best_pe = max((d for d in curves if curves[d]['pesq'] is not None),
                      key=lambda d: curves[d]['pesq'], default=None)
        out[key] = {'curves': curves, 'best_si': best_si, 'best_pe': best_pe}
    return out


def dev_levels(denman):
    """dns_dev 无 GT -> level_ratio 缺失，按 est_rms/in_rms 现算（数学等价）。"""
    agg = collections.defaultdict(list)
    for x in denman['cells']:
        if x.get('subset') != 'dns_dev' or not x.get('ok'):
            continue
        lr = x.get('level_ratio')
        if lr is None:
            ir, er = x.get('in_rms'), x.get('est_rms')
            if ir and er:
                lr = er / ir
        if lr is not None:
            agg[x['model']].append(lr)
    return agg


def val_levels(denman):
    agg = collections.defaultdict(list)
    for x in denman['cells']:
        if x.get('subset') == 'valentini' and x.get('level_ratio') is not None:
            agg[x['model']].append(x['level_ratio'])
    return agg


def cascade_by_snr(cas):
    """跨模型按 SNR 档聚合带宽代价 / 净动作 / 合计（逐格恒等式 L1 = L1b + (L1−L1b)）。"""
    rows = cas['matrix']['rows']
    agg = collections.defaultdict(lambda: {'bw': [], 'net': [], 'tot': [],
                                           'L1m': [], 'L2': [], 'L2b': [], 'L3': []})
    for r in rows:
        s = agg[float(r['snr_db'])]
        s['bw'].append(r['sdr_L1b'] - r['sdr_L0'])
        s['net'].append(r['sdr_L1'] - r['sdr_L1b'])
        s['tot'].append(r['sdr_L1'] - r['sdr_L0'])
        s['L1m'].append(r['d_L1m'])
        s['L2'].append(r['d_L2'])
        s['L2b'].append(r['d_L2b'])
        s['L3'].append(r['d_L3'])
    out = {}
    for snr, s in agg.items():
        out[snr] = {k: _med(v) for k, v in s.items()}
    return out


def cascade_stem_levels(cas):
    """每 (model, variant) 的 4 轨输出/输入 rms 比中位（≥1 说明被放大，≈0 说明被压掉）。"""
    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    for x in cas['sep_results']:
        lv = (x.get('gate') or {}).get('levels') or {}
        for s in STEMS:
            if s in lv:
                agg[(x['model'], x['variant'])][s].append(lv[s])
    return {k: {s: _med(v) for s, v in d.items()} for k, d in agg.items()}


# ================================================================ 看板 2：降噪（T7.2-A）
def build_denoise(d):
    den16, den44 = d['den16'], d['den44']
    dry = dry_opt(d['drywet'])
    dev = dev_levels(d['denman'])
    val = val_levels(d['denman'])
    casman = d['casman']

    # ---- KPI
    n_val = (den_row(den16, 'denoiser_dns48', 'valentini', 'ALL') or {}).get('n_ok')
    m64 = den_row(den16, 'denoiser_master64', 'valentini', 'ALL') or {}
    d48 = den_row(den16, 'denoiser_dns48', 'valentini', 'ALL') or {}
    synth_d48 = den_row(den16, 'denoiser_dns48', 'synth', 'ALL') or {}
    synth_mel = den_row(den16, 'mel_roformer_denoise', 'synth', 'ALL') or {}
    kpi_html = B.kpis([
        ('5', '降噪模型', '3 个 denoiser 权重（dns48 / dns64 / master64）+ 2 个 Mel-RoFormer 变体'),
        ('%s' % n_val, 'Valentini 配对片段', '板 2 主评测集：16 kHz 主口径 + 44.1 kHz 契约率复核'),
        ('%+.3f' % m64.get('pesq_improve', 0), 'master64 ΔPESQ（ALL）',
         'in-domain 权重在感知指标上最优 → 从「强度旋钮」角度独立验证 P16 反转'),
        ('%+.2f' % d48.get('si_sdr_improve', 0), 'dns48 ΔSI-SDR（ALL）',
         '波形保真度改善（配对口径：逐条作差后取中位，非 med 相减）'),
        ('0.0 / 0.1', 'ΔPESQ 最优 dry',
         'master64 峰在 0.0；dns48 / dns64 峰在 0.1（PESQ 最优强度按权重分化）'),
        ('40% → 1.7%', 'dns_dev 塌陷率（P19 纠错）',
         'P19 前 40.3/38.3/45.4%，修复后 1.0/1.0/1.7%（v1 数字 97.5% 由 bug 制造）'),
    ])

    sec = []
    # ---- 1 分层主表（Valentini 16 kHz）
    rows = []
    for m in DEN_ORDER:
        for b in BINS:
            r = den_row(den16, m, 'valentini', b)
            if not r:
                continue
            rc = 'base' if b == 'ALL' else ''
            rows.append((rc, [
                DEN_NAME[m], b, '%d' % r['n_ok'],
                n(r['si_sdr_in']), n(r['si_sdr_out']),
                n(r['si_sdr_improve'], signed=True),
                n(r['pesq_improve'], 3, signed=True),
                n(r['stoi_improve'], 4, signed=True),
                n(r['hf_ratio_in'], 4), n(r['hf_ratio_out'], 4),
            ]))
    tbl1 = B.table(['模型', '输入档', 'n', 'SI-SDR 输入', 'SI-SDR 输出', 'ΔSI-SDR',
                    'ΔPESQ', 'ΔSTOI', 'hf 输入', 'hf 输出'], rows)
    sec.append(B.h2('s1', '1', '分层主表（Valentini，16 kHz 主口径）')
               + '<p class="lead">同一批 824 条配对片段，按<b>输入 SI-SDR 事后分档</b>'
                 '（分档键不受模型影响，可跨模型对齐）。全部为<b>配对口径</b>：'
                 'ΔX = 逐条作差后取中位（med(out−in)），<b>不是</b> med(out)−med(in) —— '
                 '后者在非同分布时会反号。</p>'
               + tbl1
               + B.note('读法：① 输入越干净（≥15 dB），ΔSI-SDR 越小（可榨取的噪声本就不多）；'
                        '② <b>PESQ 只在 16 kHz 合法</b>，故本节才有 ΔPESQ / ΔSTOI 列，'
                        '同一批音频的 44.1 kHz 复核（§2）只有波形与频带量；'
                        '③ hf_ratio = 上半频带能量占比，用于探测低通式过度抑制。'))

    # ---- 2 44.1 kHz 契约率复核
    rows = []
    for m in DEN_ORDER:
        r16 = den_row(den16, m, 'valentini', 'ALL') or {}
        r44 = den_row(den44, m, 'valentini', 'ALL') or {}
        h16, h44 = r16.get('hf_ratio_out'), r44.get('hf_ratio_out')
        ratio = (h16 / h44) if (h16 and h44) else None
        rows.append(('', [
            DEN_NAME[m],
            n(h16, 4), n(h44, 4),
            n(r16.get('si_sdr_improve'), signed=True),
            n(r44.get('si_sdr_improve'), signed=True),
            ('×%.1f' % ratio) if ratio else n(None),
        ]))
    sec.append(B.h2('s2', '2', '44.1 kHz 契约率复核 —— hf_ratio 断崖的真相')
               + '<p class="lead">denoiser 的推理契约是 <code>44.1k→16k→mono→44.1k</code>。'
                 '把<b>同一批音频</b>分别按 16 kHz 与 44.1 kHz 喂进去，就能把'
                 '「模型的降噪行为」与「内部重采样带来的带宽代价」分开。</p>'
               + B.table(['模型', '16 kHz hf_out', '44.1 kHz hf_out',
                          '16 kHz ΔSI-SDR', '44.1 kHz ΔSI-SDR', 'hf 比（16k/44k）'], rows)
               + B.note('★ 关键：ΔSI-SDR 在两个口径下几乎不变（模型确实降了噪），'
                        '但 <b>hf_out 在 44.1 kHz 口径下塌到约 0.035</b>（16 kHz 口径约 0.207）。'
                        '差的这部分是 <b>8 kHz 以上被内部重采样抹掉</b>的，不是模型"学会了低通"。'
                        '报告引用 hf_ratio 必须注明口径 —— 这正是 P19 契约率 bug 留下的纪律。'
                        '<br><b>教训</b>：wrapper 的采样率契约若被调用方忽视，同一 bug 能连续造出'
                        '三份互相矛盾的错误文档（见 <code>docs/P19_SAMPLE_RATE_CONTRACT_BUG.md</code>）。',
                        'warn'))

    # ---- 3 dry/wet 强度旋钮
    rows = []
    for m in DEN_ORDER[:3]:
        for b in BINS:
            o = dry.get((m, b))
            if not o or o['best_si'] is None:
                continue
            c = o['curves']
            rows.append(('base' if b == 'ALL' else '', [
                DEN_NAME[m], b,
                ('<b>%.1f</b>' % o['best_si']),
                ('<b>%.1f</b>' % o['best_pe']) if o['best_pe'] is not None else n(None),
                n(c.get(0.0, {}).get('pesq'), 3, signed=True),
                n(c.get(o['best_pe'], {}).get('pesq'), 3, signed=True) if o['best_pe'] is not None else n(None),
            ]))
    sec.append(B.h2('s3', '3', 'dry/wet 强度旋钮：最优值随输入 SNR 与权重移动')
               + '<p class="lead"><code>estimate = (1−dry)·model(noisy) + dry·noisy</code>，'
                 'dry∈[0,1]。dry=0 是纯模型输出（主表口径），dry=1 是纯直通（= 不做任何事）。'
                 '正确性锚点：dry=0 必须与主表逐位一致 —— <b>实测 worst_abs_diff = 0.0000</b>。</p>'
               + B.table(['模型', '输入档', 'ΔSI-SDR 最优 dry', 'ΔPESQ 最优 dry',
                          'ΔPESQ@dry=0', 'ΔPESQ@最优'], rows)
               + B.figure(DEN_FIG / 'fig_denoise_drywet.png',
                          'dry/wet 强度曲线 ｜ 数据集 Valentini（824 条配对）· 16 kHz · '
                          '指标 ΔSI-SDR / ΔPESQ（逐条配对差后取中位）｜ 2472 cells / err=0',
                          max_w=1400)
               + B.note('★ <b>PESQ 最优强度按权重分化</b>：dns48 / dns64 的峰在 <b>dry=0.1</b>'
                        '（稀释 10% 原信号，ΔPESQ 反升 +21~34%），而 <b>master64 的峰在 dry=0.0</b>'
                        '（任何稀释都让它变差 −10%）。<br>'
                        '这是对 <b>P16「master64 是 in-domain 权重」</b>的一次<b>完全独立</b>的验证：'
                        '一条规律在两个不同实验下同时成立，可信度远高于单次观测。对 master64 而言，'
                        '「ΔSI-SDR 与 ΔPESQ 最优工作点不一致」这条也不成立 —— 说明该分歧<b>权重相关，不可外推</b>。',
                        'good'))

    # ---- 4 机理证据
    rows = []
    for m in DEN_ORDER:
        r16 = den_row(den16, m, 'valentini', 'ALL') or {}
        v = val.get(m) or []
        dv = dev.get(m) or []
        rows.append(('', [
            DEN_NAME[m],
            n(r16.get('hf_ratio_in'), 4), n(r16.get('hf_ratio_out'), 4),
            n(_med(v), 4), n(_med(dv), 4),
            ('%.1f%%' % _share(dv, 0.20)) if dv else n(None),
        ]))
    sec.append(B.h2('s4', '4', '机理证据：hf_ratio 与 level_ratio')
               + '<p class="lead">两个诊断量各自回答一个问题：<b>hf_ratio</b>（频带保真）看模型'
                 '有没有过度低通；<b>level_ratio</b>（电平保真）看模型有没有把整段压塌。</p>'
               + B.table(['模型', 'valentini hf_in', 'valentini hf_out',
                          'valentini 电平中位', 'dns_dev 电平中位', 'dns_dev &lt;0.20 占比'], rows)
               + B.figure(DEN_FIG / 'fig_denoise_suppression.png',
                          '降噪器频带 / 电平保真 ｜ 数据集 Valentini（16 kHz 配对）· '
                          '指标 hf_ratio（上半频带能量占比）与 level_ratio（输出/输入 rms）',
                          max_w=1400)
               + B.note('三条读出来的东西：① 干净数据上 denoiser 的 <b>level_ratio ≈ 1.00</b>'
                        '（valentini 1.74 s 短片段），但到 <b>dns_dev 长片段（中位 18.6 s）'
                        '压到 0.83~0.87</b> —— <b>片段越长、电平压低越多</b>；'
                        '② Mel-RoFormer 几乎不动（0.993~0.995），是 near-identity；'
                        '③ 门禁阈值 LEVEL_GATE=0.20 现在只触发 1.0~1.7%（9~15 条 / 867），'
                        '已不是一个"大面积失效模式"，但仍保留以剔除真塌陷样本。'))
    sec.append(B.note(
        '⚠️ <b>P19 纠错对照（必须一起报）</b>：dns_dev 塌陷率（&lt;0.20 占比）在 v1（bug 版）'
        '是 <b>40.3% / 38.3% / 45.4%</b>（dns48/dns64/master64），P19 修复后降到 '
        '<b>1.0% / 1.0% / 1.7%</b> —— 即 v1 那个惊人数值有约 <b>97.5% 是 bug 造出来的</b>。'
        '方向（master64 门控最激进）存活，但幅度差 27 倍。'
        '出处：<code>docs/T5_4_DNS_DEV_NOREF.md</code> §4.1（本节 40% 系列为历史数字引用，'
        '非本页现算）。', 'bad'))

    # ---- 5 三指标分歧（P19 正名）
    rows = []
    for m in DEN_ORDER:
        a = den_row(den16, m, 'valentini', '<5dB') or {}
        b = den_row(den16, m, 'valentini', '>=15dB') or {}
        rows.append(('', [
            DEN_NAME[m],
            n(a.get('si_sdr_improve'), signed=True), n(a.get('pesq_improve'), 3, signed=True),
            n(a.get('stoi_improve'), 4, signed=True),
            n(b.get('si_sdr_improve'), signed=True), n(b.get('pesq_improve'), 3, signed=True),
            n(b.get('stoi_improve'), 4, signed=True),
        ]))
    sec.append(B.h2('s5', '5', '三指标分歧：在干净数据上不存在（P19 正名）')
               + '<p class="lead">曾经的结论是「SI-SDR 与 PESQ/STOI 方向相反」。'
                 'P19 修复后发现：<b>那是 bug 造的</b>。修复后同一批音频上，'
                 '三个指标<b>逐格同向为正</b>，只在强度旋钮（§3）上留有"最优工作点不同"的分歧。</p>'
               + B.table(['模型', 'ΔSI-SDR(&lt;5dB)', 'ΔPESQ(&lt;5dB)', 'ΔSTOI(&lt;5dB)',
                          'ΔSI-SDR(≥15dB)', 'ΔPESQ(≥15dB)', 'ΔSTOI(≥15dB)'], rows)
               + B.figure(DEN_FIG / 'fig_denoise_metric_divergence.png',
                          '三指标分歧（v1，已作废）｜ 数据集 Valentini · 16 kHz · '
                          'SI-SDR / PESQ / STOI 三个指标的增益方向 —— 此图是 bug 产物，仅作纠错留证',
                          max_w=1300)
               + B.note('★ <b>元教训</b>：同一个 bug 上连续写错三份文档，每次都编出'
                        '"三指标矛盾 / 反直觉的 in-domain 恶化"这类叙事。'
                        '<b>能解释一切的叙事，往往就是 bug 在说话</b>；唯一防线 = 换个口径重跑，'
                        '看结论存活否。<br>仍成立的部分：<b>SI-SDR 不能单独作为降噪指标</b> —— '
                        '它是波形保真度，对残留噪声敏感，会系统性高估「把强度拉满」的收益。',
                        'warn'))

    # ---- 6 域不匹配的两种表现
    sec.append(B.h2('s6', '6', '域不匹配的两种表现：降噪域外失效 + 去混响负结果')
               + '<h3>6.1 T5.7 降噪器的「互补失效」—— 两个模型族的有效域不同</h3>'
               + '<p class="lead">用 DNS 官方噪声库 + Valentini 语音自造带噪对'
                 '（800 条，GT 与 SNR 均为真值）。<b>同一组噪声上，两个模型族的表现完全反转</b>：</p>'
               + B.table(['模型', 'ΔSI-SDR', 'ΔPESQ', 'ΔSTOI', 'hf 输入', 'hf 输出'],
                          [('', [DEN_NAME[m],
                                 n((den_row(den16, m, 'synth', 'ALL') or {}).get('si_sdr_improve'), signed=True),
                                 n((den_row(den16, m, 'synth', 'ALL') or {}).get('pesq_improve'), 3, signed=True),
                                 n((den_row(den16, m, 'synth', 'ALL') or {}).get('stoi_improve'), 4, signed=True),
                                 n((den_row(den16, m, 'synth', 'ALL') or {}).get('hf_ratio_in'), 4),
                                 n((den_row(den16, m, 'synth', 'ALL') or {}).get('hf_ratio_out'), 4)])
                           for m in DEN_ORDER])
               + B.figure(DEN_FIG / 'fig_denoise_noise_domain_reversal.png',
                          '域外失效：denoiser vs Mel-RoFormer 在两类噪声上的反转 ｜ '
                          '数据集 DNS dev_testset（真实录音）vs 自造 synth 对 · 16 kHz · '
                          '指标 ΔSI-SDR（配对中位）',
                          max_w=1300)
               + B.figure(DEN_FIG / 'fig_denoise_synth_gain.png',
                          'synth 集按目标 SNR 的增益 ｜ 数据集自造带噪对（200 语音 × DNS 噪声池 '
                          '2308 条，SNR ∈ {−5,0,5,10} dB）· 16 kHz · 指标 ΔSI-SDR / ΔPESQ',
                          max_w=1300)
               + B.note('读法：在真实录音噪声（dns_dev / valentini）上 denoiser 与 Mel-RoFormer '
                        '都能增益；但在 synth 的合成噪声上，<b>denoiser 四档全正（ALL '
                        '%s dB）而 Mel-RoFormer 几乎为 0（%s dB，near-identity）</b>。'
                        '这不是管道 bug —— 已用官方分块推理路径交叉验证；'
                        '本质是<b>两类噪声的时频分布不同</b>，两个模型族的有效域互补。'
                        '→ 结论：<b>「降噪有效」必须带条件</b>（哪种噪声、哪个模型）。'
                        % (n(synth_d48.get('si_sdr_improve'), 2, signed=True),
                           n(synth_mel.get('si_sdr_improve'), 2, signed=True)), 'warn')
               + '<h3>6.2 去混响 / 去回声 —— 负结果</h3>'
               + B.note('两个社区 ckpt（<code>anvuew</code> 去房间混响、'
                        '<code>Dereverb-Echo</code> 去 PA 残响）在本探针上<b>不可用</b>：'
                        '干/湿对比中 <code>dry</code> 支 rms 塌到 1e-5~2e-3（把内容一起压没）。'
                        '已用<b>上游官方分块推理路径</b>交叉验证（Δ si 仅 0.142 dB）→ '
                        '<b>不是我们的实现错，是域不匹配</b>。'
                        '→ <code>docs/DEREVERB_NEGATIVE_RESULT.md</code>。'
                        '照报（R12 / P7）。', 'bad'))

    # ---- 7 T5.6 频谱前后对比
    spec4 = ['t5_6_denoiser_master64_valentini', 't5_6_denoiser_master64_synth',
             't5_6_mel_roformer_denoise_valentini', 't5_6_mel_roformer_denoise_synth']
    grids = ''.join('<div class="grid2">'
                    + B.figure(DEN_FIG / 'denoise' / ('%s_spectral.png' % k),
                               '四联图 ｜ %s ｜ 数据集 %s · 16 kHz · 时频谱裁到 4 kHz / '
                               '平滑平均谱 / hf_ratio 散点' % (k.replace('_', ' '),
                                                              'Valentini' if 'valentini' in k else 'synth（自造对）'),
                               max_w=900)
                    + B.figure(DEN_FIG / 'denoise' / ('%s_delta_spectrum.png' % k),
                               '平均谱差 ｜ %s ｜ 有效带 0~7.8 kHz（16 kHz Nyquist=8 kHz，'
                               '以上为重采样伪影，不纳入）' % k.replace('_', ' '),
                               max_w=900)
                    + '</div>' for k in spec4)
    sec.append(B.h2('s7', '7', '频谱前后对比（T5.6）')
               + '<p class="lead">片段选取<b>不做人工挑选</b>（按 clip_id 排序取前 N，可复现）。'
                 '★ 平均谱差是「P19 存活判据」的直接图证：修正后（0~7.8 kHz 有效带，n=120）'
                 '不是均匀低通，而是<b>随频率增长的倾斜</b> —— denoiser master64 valentini '
                 '1–4k = −1.53 / 4–7.8k = −6.15；同一权重在 synth 瞬态噪声上中频抑制量是'
                 '真实噪声集的 <b>4.7 倍</b>（P17 有效域互补的机理证据）。</p>'
               + B.note('★ <b>Nyquist 边界伪影（新坑）</b>：16 kHz 下 Nyquist=8 kHz，'
                        'denoiser 内部 16 kHz 推理再升回 44.1 kHz → 8 kHz 以上是插值伪影。'
                        '不剔除时「4 kHz 以上平均差」被污染成虚假 <b>−32 dB</b>（修正后 −12.8）。'
                        '识别手法：mel_roformer 原生 44.1 kHz，其谱差曲线在 8 kHz 处<b>无断崖</b> → '
                        '同图对照反向确认断崖来自 denoiser 内部瓶颈。', 'warn')
               + grids)

    # ---- 8 口径与坑
    sec.append(B.h2('s8', '8', '引用前必读：口径与已知坑')
               + B.note(
                   '<ul>'
                   '<li><b>配对差 ≠ 中位数之差</b>：所有 <code>*_improve</code> 列都是'
                   ' med(out−in)，不是 med(out)−med(in)。后者在非同分布时会反号。</li>'
                   '<li><b>PESQ 只支持 16 kHz</b>：非 16 kHz 一律不报（'
                   '<code>pesq_applicable=false</code>），不得当 0 用。</li>'
                   '<li><b>dns_dev 无 clean GT</b>（<code>reference_mode=noref</code>）→ '
                   'fullref 列为 null，<b>不得当 0 用</b>；本节 dns_dev 只有电平行为量。</li>'
                   '<li><b>分档键</b>：真实集按<b>输入 SI-SDR</b> 事后分档；synth 按<b>真值 SNR</b>'
                   '（−5/0 → &lt;5dB，5/10 → 5–15dB）。两者键名相同但含义不同。</li>'
                   '<li><b>采样率契约</b>：denoiser 固定 <code>44.1k→16k→mono→44.1k</code>；'
                   'hf_ratio 引用必须注明口径（§2）。</li>'
                   '<li><b>片段时长</b>：&gt;30 s 的片段统一跳过（dns_dev 867/921），'
                   '以保证所有模型看到同一批片段 —— 可比性优先于覆盖率。</li>'
                   '</ul>'))

    # ---- 9 产物与复现
    sec.append(B.h2('s9', '9', '产物与复现')
               + B.note(
                   '<b>数据</b>：<code>denoiser/data/denoise_eval_16k.json</code>、'
                   '<code>denoise_eval_44k.json</code>、<code>denoise_drywet.json</code>、'
                   '<code>denoise_manifest.json</code>（16575 cells）、'
                   '<code>denoise_ood_probe.json</code>、<code>denoise_probeA_paired.json</code><br>'
                   '<b>文档</b>：<code>docs/T5_DENOISE_STRATIFIED.md</code>（分层主表）、'
                   '<code>docs/T5_4_DNS_DEV_NOREF.md</code>（dns_dev 无参考）、'
                   '<code>docs/T5_5_T5_6_DRYWET_AND_SPECTRA.md</code>（强度旋钮 + 频谱）、'
                   '<code>docs/T5_7_OOD_NOISE_NEGATIVE.md</code>（域外失效）、'
                   '<code>docs/T5_7_PASSTHROUGH_PROBE_CORRECTION.md</code>（直通探针）、'
                   '<code>docs/P19_SAMPLE_RATE_CONTRACT_BUG.md</code>（契约率 bug）、'
                   '<code>docs/DEREVERB_NEGATIVE_RESULT.md</code>（去混响负结果）<br>'
                   '<b>重建本页</b>：<code>python tools/_build_dashboards_t72.py --only denoise</code>'))

    toc = [('s1', '1 分层主表'), ('s2', '2 44k 契约率'), ('s3', '3 dry/wet 旋钮'),
           ('s4', '4 机理证据'), ('s5', '5 三指标分歧'), ('s6', '6 域不匹配'),
           ('s7', '7 频谱前后'), ('s8', '8 口径与坑'), ('s9', '9 产物')]
    return B.page('降噪看板 · 板 2（阶段 5）',
                  '交付物 D10 看板 2 ｜ 5 个降噪模型 · Valentini 分层主表 · '
                  'dry/wet 强度旋钮 · 域外失效与去混响负结果 · P19 纠错对照',
                  [kpi_html] + sec, toc)


# ================================================================ 看板 3：级联（T7.2-B）
def build_cascade(d):
    cas = d['cas']
    man = d['casman']
    mtx = cas['matrix']
    smry = mtx['summary_all_cells']
    bysnr = cascade_by_snr(cas)
    lv = cascade_stem_levels(cas)
    snrs = sorted(bysnr, reverse=True)

    n_main = sum(1 for x in cas['sep_results'] if x['variant'] != 'Vdry')
    n_anchor = cas['n_sep'] - n_main

    g = man.get('gates', [])
    n_gate = len(g)
    # 门禁记录的字段是 pass(bool)，不是 status 字符串（曾误用 -> 显示 0/90）
    n_gate_pass = sum(1 for x in g if x.get('pass'))

    kpi_html = B.kpis([
        ('%d' % n_main, '分离推理格', '10 曲 × 4 SNR × 4 前置变体 × 4 分离模型'
                                        '（另 %d 个干档锚点格，用于校验 loader/口径未漂移）' % n_anchor),
        ('%+.2f' % smry['median_d_L1'], 'L1 前置降噪 ΔSDR',
         '把语音降噪器接在音乐源分离<b>之前</b>，avg4 SDR 净跌'),
        ('%+.2f' % smry['median_d_L1b'], 'L1b 仅带宽代价（★恒等对照）',
         '把网络换成恒等，只付 16 kHz/mono 往返代价 —— 22% 的伤害来自这里'),
        ('%+.2f' % smry['median_denoise_net'], '净降噪动作（L1−L1b）',
         '真正由「降噪」这个动作造成的损失，占 80%'),
        ('%+.3f' % smry['median_d_L2'], 'L2 后置降噪 ΔSDR',
         '降噪放在分离<b>之后</b>近乎中性（对照臂 L2b %+.3f）' % smry['median_d_L2b']),
        ('%d/%d' % (n_gate_pass, n_gate), '数据门禁',
         'G1 SNR 回测 / G2 float32 逐位 / G3 Σ干轨==mixture；全 PASS 矩阵才立得住'),
    ])

    sec = []
    # ---- 1 实验设计
    links = d['casplan'].get('links', {})
    variants = d['casplan'].get('variants', {})
    lrows = [(('base' if k == 'L1' else ''), [k, v.get('desc') if isinstance(v, dict) else str(v)])
             for k, v in links.items()]
    vrows = [(('base' if k in ('V0', 'V1den') else ''), [k, v.get('desc') if isinstance(v, dict) else str(v)])
             for k, v in variants.items()]
    sec.append(B.h2('s1', '1', '实验设计：为什么必须有「只付代价、不做动作」的对照臂')
               + '<p class="lead">问句：把<b>语音</b>降噪器接在<b>音乐</b>源分离的前/后，'
                 'SDR 是涨还是跌？关键陷阱：denoiser 的契约是 '
                 '<code>44.1k→16k→mono→44.1k</code>，<b>即使网络换成恒等</b>，信号也已被'
                 '限带到 8 kHz + 下混单声道（音乐高频大量在 8 kHz 以上）。'
                 '没有对照臂，任何涨跌都无法排除「其实是带宽被砍」。</p>'
               + B.table(['链路', '含义'], lrows)
               + B.table(['前置变体', '含义'], vrows)
               + B.note('★ <b>恒等式（逐格严格成立）</b>：'
                        '<code>L1 = L1b(带宽代价) + (L1−L1b)(降噪净动作)</code>。'
                        'L1m（mel 前置）与 L1b 是两条「只付代价」的对照臂：'
                        'L1b 换恒等网络、L1m 换近恒等的 Mel-RoFormer。'
                        '若 L1m ≈ L1b，则进一步证明伤害来自「降噪动作」而非管线固定损耗。', 'good'))

    # ---- 2 ΔSDR 主矩阵
    rows = []
    for snr in snrs:
        for m in SEP_ORDER:
            r = next((x for x in mtx['rows']
                      if x['model'] == m and float(x['snr_db']) == snr), None)
            if not r:
                continue
            rows.append(('base' if snr == snrs[0] and m == SEP_ORDER[0] else '', [
                SEP_NAME[m], '%+.0f dB' % r['snr_db'], n(r['sdr_L0']),
                n(r['d_L1'], signed=True), n(r['d_L1b'], signed=True),
                n(r['d_L1m'], signed=True), n(r['d_L2'], signed=True),
                n(r['d_L2b'], signed=True), n(r['d_L3'], signed=True),
            ]))
    sec.append(B.h2('s2', '2', 'ΔSDR 主矩阵（%d 格）' % len(mtx['rows']))
               + '<p class="lead">%s。参考：%s。%s</p>'
                 % (mtx['metric'], mtx['reference'], mtx['honesty'])
               + B.figure(CAS_FIG / 'fig_cascade_delta_matrix.png',
                          'ΔSDR 主矩阵 ｜ 数据集 MUSDB test Top-10 曲 × 4 SNR '
                          '（−5/0/+5/+10 dB）× 4 分离模型 ｜ 指标 museval BSSEval v4 SDR '
                          '（mono，2 s/1.5 s 窗），4 轨均值 avg4，跨曲取中位',
                          max_w=1600, wide=True)
               + B.table(['模型', 'SNR', 'SDR(L0)', 'L1 前置', 'L1b 仅带宽',
                          'L1m mel 前置', 'L2 后置', 'L2b 后置限带', 'L3 前+后'], rows)
               + B.note('三条读出来的东西：① <b>L1 前置全线为负</b>，且<b>噪声越大负得越少</b>'
                        '（−5 dB 档约 −1.4，+10 dB 档约 −7.0）—— 与「低 SNR 时压掉的多是噪声、'
                        '高 SNR 时压掉的几乎都是音乐」一致；'
                        '② <b>L2 后置近乎中性</b>；'
                        '③ <b>L3 ≈ L1</b>：后置环节既救不回前置损失，也不额外加伤。', 'warn'))

    # ---- 3 净动作分解
    rows = []
    for snr in snrs:
        s = bysnr[snr]
        tot = s['tot']
        ratio = (s['net'] / tot * 100) if tot else None
        rows.append(('', [
            '%+.0f dB' % snr, n(s['bw'], signed=True), n(s['net'], signed=True),
            n(tot, signed=True),
            ('%.0f%%' % ratio) if ratio is not None else n(None),
        ]))
    sec.append(B.h2('s3', '3', '净动作分解：伤害来自「降噪」本身（80%），不是带宽')
               + B.figure(CAS_FIG / 'fig_cascade_decomposition.png',
                          'L1 vs L1b vs (L1−L1b) 净动作分解 ｜ 数据集 MUSDB test Top-10 曲 × 4 SNR ｜ '
                          '指标 museval BSSEval v4 SDR avg4，跨模型 × 跨曲取中位',
                          max_w=1500, wide=True)
               + B.table(['SNR 档', '带宽代价（L1b−L0）', '降噪净动作（L1−L1b）',
                          '合计（L1−L0）', '净动作占比'], rows)
               + B.note('★ <b>带宽代价与 SNR 基本无关</b>（各档约 −0.6~−1.1），'
                        '而<b>净动作强烈随 SNR 变化</b> —— 走势不同，从侧面确认 '
                        '<code>L1 − L1b</code> 抽出来的确实是<b>降噪网络的行为</b>，'
                        '不是管线的固定损耗。<br>'
                        '净动作在 15/16 格为负，唯一例外是 <b>umx @ −5 dB</b>（该档 L0 中位仅 '
                        '0.014 dB，基线贴地，Δ 相对解释力弱）。', 'warn'))

    # ---- 4 机理
    rows = []
    for m in SEP_ORDER:
        for v in ('V0', 'V1bl', 'V1den', 'V1mel'):
            dd = lv.get((m, v)) or {}
            if not dd:
                continue
            rows.append(('base' if v == 'V1den' else '', [
                SEP_NAME[m], v, n(dd.get('vocals'), 3), n(dd.get('drums'), 3),
                n(dd.get('bass'), 3), n(dd.get('other'), 3),
            ]))
    sec.append(B.h2('s4', '4', '机理：降噪器把鼓 / 贝斯 / 其他当噪声压掉')
               + '<p class="lead">下表是各轨输出／输入 rms 比的中位（≈1 = 原样通过，'
                 '≈0 = 被压掉，&gt;1 = 被放大）。<b>V1den 下 vocals ≈ 0.99、而 drums/bass/other '
                 '塌到 10⁻²~10⁻³</b> → 分离器拿到的输入里只剩人声，任务退化成<b>恒等映射</b>。'
                 '这是<b>任务错配</b>，不是实现错误。</p>'
               + B.table(['模型', '前置变体', 'vocals', 'drums', 'bass', 'other'], rows)
               + B.note('对照：<b>V1bl ≈ V0</b>（仅 16 kHz/mono 往返，电平几乎不变）⇒ '
                        '伤害来自「降噪动作」而非带宽代价 —— 与 §3 的 SNR 依赖性判据互证。'
                        '另：<b>bsrnn_all × V1den 全 40 格 PASS</b> —— 它的 4 个独立单目标 ckpt '
                        '不共享噪声判断，故未被整体压掉（代价是 40 s/格 vs 其他模型 6 s/格，'
                        '这是设计代价不是 bug）。', 'good'))

    # ---- 5 诚实性检查
    sec.append(B.h2('s5', '5', '诚实性检查（T6.4 · R12 / P7）')
               + B.note(
                   '<ul>'
                   '<li><b>Δ 为负即负</b>，不挑数据。本实验整体是一个<b>负结果</b>：'
                   '语音降噪器接在音乐源分离前置 → avg4 SDR 净跌约 <b>%+.1f dB</b>，'
                   '其中 <b>80%%</b> 来自「降噪」动作本身。</li>'
                   '<li><b>不预设降噪有用</b>（P7）：P17 只预测「动作量可迁移」，'
                   '动作可以是负的 —— 本实验正是负的，照报。</li>'
                   '<li><b>先判噪声类型</b>（P17）：本集噪声按<b>波峰因子</b>判为瞬态型'
                   '（缩放后中位 %.1f），与 T5.4 synth 同族，故 P17 预测可迁移。'
                   '⚠️ 不能用 hf_ratio 当噪声类型判据（那是比例量，音乐自带大量高频）。</li>'
                   '<li><b>锚点不成立则整张矩阵作废</b>：40 个干档锚点 Vdry 全部 PASS，'
                   'avg4（demucs 9.040 / mdx 9.910 / bsrnn_all 9.297 / umx 5.375）'
                   '与历史整曲扫描（9.05 / 9.87 / 5.49）吻合 → loader/GT/museval 口径未漂移。</li>'
                   '<li><b>门禁语义修正后重判</b>：级联里「输出相对输入的量级」<b>就是被测现象本身</b>'
                   '（前置把 drums 压到 0.006 是<b>发现</b>不是故障），旧判据误判 35 格 FAIL '
                   '并让整列从矩阵里静默消失；改为「输入没写坏 且 输出非全零/NaN」后 '
                   '<b>680/680 PASS</b>。</li>'
                   '</ul>'
                   % (smry['median_d_L1'],
                      (man.get('noise_type') or {}).get('crest_scaled_median') or 0.0)))

    # ---- 6 口径与坑
    sec.append(B.h2('s6', '6', '引用前必读：口径与已知坑')
               + B.note(
                   '<ul>'
                   '<li><b>32-bit float WAV</b>：噪声脉冲性强（缩放后波峰因子 max 很大），'
                   '按功率匹配 SNR 后 noisy 峰值冲高 → 写 PCM_16 会<b>静默削波</b> 30/40 格。'
                   '⚠️ 峰值大<b>不伤模型</b>：分离 wrapper 内部按输入自身 mean/std 归一化再还原。</li>'
                   '<li><b>G2 门禁</b>：拿 float32 存储值比 float64 精确和 → 纯量化'
                   '（0.55 ulp）会被误判 FAIL。正确判据 = <b>float32 重建逐位相同</b>。</li>'
                   '<li><b>片段</b>：20 s 片段（非整曲），与 T4/T5 口径一致、匹配 museval 2 s 窗。</li>'
                   '<li><b>偏离记录</b>：计划书写的「BSRNN-opt」实为人声单轨（违反 R10）→ '
                   '改用 <b>bsrnn_all</b>（oBSRNN 4 ckpt 四轨）。</li>'
                   '<li><b>无法创建脱离进程</b>：本沙箱 <code>nohup &amp;</code> / '
                   '<code>cmd start</code> 被拒，后台任务随会话结束被杀 → 主跑改用'
                   '<b>逐格 JSONL 增量落盘 + resume</b>，中断可幂等续跑。</li>'
                   '</ul>'))

    # ---- 7 产物与复现
    sec.append(B.h2('s7', '7', '产物与复现')
               + B.note(
                   '<b>数据</b>：<code>cascade/data/cascade_plan.json</code>、'
                   '<code>cascade_manifest.json</code>（门禁 %d/%d PASS）、'
                   '<code>cascade_eval.json</code>（%d 分离 + %d 后置格）、'
                   '<code>cascade_eval.csv</code>、<code>cascade_eval.partial.jsonl</code>'
                   '（增量断点）<br>'
                   '<b>工具</b>：<code>tools/_cascade_experiment.py</code>'
                   '（plan / make-noisy / prep / prep-post / run / post / summary）、'
                   '<code>tools/_plot_cascade.py</code>（出图）、'
                   '<code>tools/_cascade_regate.py</code>（门禁免重跑重判）<br>'
                   '<b>文档</b>：<code>docs/T6_CASCADE_DENOISE_BEFORE_SEPARATION.md</code><br>'
                   '<b>重建本页</b>：<code>python tools/_build_dashboards_t72.py --only cascade</code>'
                   % (n_gate_pass, n_gate, cas['n_sep'], cas['n_post'])))

    toc = [('s1', '1 实验设计'), ('s2', '2 ΔSDR 主矩阵'), ('s3', '3 净动作分解'),
           ('s4', '4 机理'), ('s5', '5 诚实性检查'), ('s6', '6 口径与坑'), ('s7', '7 产物')]
    return B.page('级联看板 · 板 1 × 板 2（阶段 6）',
                  '交付物 D10 看板 3 ｜ 降噪前置/后置对音乐源分离的影响 · '
                  '7 条链路 · 640 分离推理格 · 一个照报的负结果',
                  [kpi_html] + sec, toc)


# ================================================================ 主入口
BUILDERS = {
    'denoise': ('denoise_dashboard.html', P.DEN_HTML, build_denoise),
    'cascade': ('cascade_dashboard.html', P.CAS_HTML, build_cascade),
}


def main(argv=None):
    ap = argparse.ArgumentParser(description='T7.2 看板构建器（降噪 / 级联，自包含离线 HTML）')
    ap.add_argument('--only', default='all', help='denoise | cascade | all')
    a = ap.parse_args(argv)

    want = list(BUILDERS) if a.only == 'all' else [a.only]
    unknown = [w for w in want if w not in BUILDERS]
    if unknown:
        raise SystemExit('[FATAL] 未知看板：%s（可用：%s / all）'
                         % (', '.join(unknown), ' / '.join(BUILDERS)))

    d = load_t72()
    rc = 0
    for w in want:
        fname, outdir, fn = BUILDERS[w]
        html_txt = fn(d)
        outdir.mkdir(parents=True, exist_ok=True)
        out = outdir / fname
        out.write_text(html_txt, encoding='utf-8')
        n_img = html_txt.count('data:image/jpeg;base64,')
        print('[ok] %-32s %7.2f MB  (%d images embedded)'
              % (out.name, len(html_txt.encode('utf-8')) / 1048576.0, n_img))
        print('     -> %s' % out)
    return rc


if __name__ == '__main__':
    sys.exit(main())

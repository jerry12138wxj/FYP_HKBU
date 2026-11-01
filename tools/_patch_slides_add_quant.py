# -*- coding: utf-8 -*-
"""一次性 patch：把 mdx_q / mdx_extra_q 加入防御 slides 的分离精度表（幂等）。"""
import io, sys

p = r"E:\FYP_HKBU\tools\_build_defense_v2.py"
s = io.open(p, encoding="utf-8").read()

OLD = '''    order = [("bsrnn_simo", "oBSRNN-SIMO"), ("bsrnn_all", "oBSRNN (4 ckpt)"), ("mdx", "MDX-Net"),
             ("bsrnn_large_all", "BSRNN-large (4ckpt)"), ("oracle", "IRM/IBM Oracle"), ("demucs", "Demucs (htdemucs)"),'''

NEW = '''    order = [("bsrnn_simo", "oBSRNN-SIMO"), ("bsrnn_all", "oBSRNN (4 ckpt)"),
             ("mdx", "MDX-Net (mdx_extra)"), ("mdx_extra_q", "MDX-Net (mdx_extra_q 量化)"),
             ("mdx_q", "MDX-Net (mdx_q 量化)"),
             ("bsrnn_large_all", "BSRNN-large (4ckpt)"), ("oracle", "IRM/IBM Oracle"), ("demucs", "Demucs (htdemucs)"),'''

if 'mdx_extra_q 量化' in s:
    print("SKIP 已 patch 过")
elif OLD in s:
    s = s.replace(OLD, NEW, 1)
    print("OK order 已替换")
else:
    print("!! 未找到 order 锚点，需人工核对")
    sys.exit(1)

# 在精度表结论后追加量化对照 note（幂等）
ANCHOR = '''    '<div class="note"><b>DPRNN −1.72 dB</b> 系自训 5 h 欠训练对照，非官方权重，不进结论。</div>','''
ADD = ANCHOR + '''
    '<div class="note warn"><b>量化对照（2026-10-21 实测，3 段 × 10 s 同口径）</b>：mdx_extra 8.96 → '
    '<b>mdx_extra_q 8.37 dB（−0.59）</b>，量化确有掉点，此前「<0.1 dB」的估计偏乐观；'
    'mdx_q 8.80 dB 属 demucs <code>mdx</code> 另一权重族，<b>不与 mdx_extra 同源</b>，仅列参考。</div>','''
if '量化对照（2026-10-21' in s:
    print("SKIP note 已存在")
elif ANCHOR in s:
    s = s.replace(ANCHOR, ADD, 1)
    print("OK note 已追加")
else:
    print("!! 未找到 note 锚点")
    sys.exit(1)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("WROTE", p)

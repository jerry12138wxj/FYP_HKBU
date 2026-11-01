# -*- coding: utf-8 -*-
"""修复 patch 引入的参数错误：把 DPRNN note 结尾的 `,` 改为 ` +`，使量化 note 成为同一个字符串表达式。"""
import io, sys

p = r"E:\FYP_HKBU\tools\_build_defense_v2.py"
s = io.open(p, encoding="utf-8").read()

BAD = """不进结论。</div>',
    '<div class="note warn"><b>量化对照"""
GOOD = """不进结论。</div>' +
    '<div class="note warn"><b>量化对照"""

if GOOD in s:
    print("SKIP 已修复")
elif BAD in s:
    s = s.replace(BAD, GOOD, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("OK 已修复 + 连接符")
else:
    print("!! 未找到锚点")
    sys.exit(1)

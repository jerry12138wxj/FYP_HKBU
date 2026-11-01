# -*- coding: utf-8 -*-
"""把 MODEL_REGISTRY 里「量化掉点 <0.1 dB，未单测」的猜测替换为实测值（幂等）。"""
import io, sys

p = r"E:\FYP_HKBU\01_models\MODEL_REGISTRY.md"
s = io.open(p, encoding="utf-8").read()

OLD = "≈ 同 mdx/mdx_extra（量化掉点 <0.1 dB，未单测）"
NEW = "实测 3 段 × 10 s：mdx_extra **8.96 → mdx_extra_q 8.37 dB（−0.59）**；mdx_q 8.80（属 demucs `mdx` 另一权重族，仅参考）"

if "8.96 → mdx_extra_q 8.37" in s:
    print("SKIP 已更新")
elif OLD in s:
    s = s.replace(OLD, NEW, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("OK 已更新")
else:
    print("!! 未找到锚点，人工核对")
    sys.exit(1)

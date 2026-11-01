# -*- coding: utf-8 -*-
"""把 Wiener filter 接入 _denoise_registry.py（幂等）。"""
import io, sys

p = r"E:\FYP_HKBU\tools\_denoise_registry.py"
s = io.open(p, encoding="utf-8").read()

# 1) 常量区加 WF 路径（在 DEN 定义后）
OLD_CONST = 'DEN = os.path.join(ROOT, "01_models", "_third_party", "denoiser")'
NEW_CONST = OLD_CONST + '\nWF = os.path.join(ROOT, "01_models", "_third_party", "wiener_filter")'
if "WF = os.path.join" in s:
    print("SKIP const 已存在")
elif OLD_CONST in s:
    s = s.replace(OLD_CONST, NEW_CONST, 1)
    print("OK const 已加")
else:
    print("!! 未找到 const 锚点"); sys.exit(1)

# 2) loader 函数（加在 registry 注释块之前）
OLD_FUNC = '# ------------------------------------------------------------------ registry'
NEW_FUNC = '''def _make_wiener_loader():
    """Classical Wiener filter (NumPy-only, parameter-free baseline)."""

    def load():
        if WF not in sys.path:
            sys.path.insert(0, WF)
        from wiener_filter import WienerParams, wiener_stereo

        t0 = time.time()
        params = WienerParams(n_fft=2048, hop=512, noise_frames=8)
        dt = time.time() - t0

        def run(mix):
            out = wiener_stereo(np.asarray(mix, dtype=np.float32), SR, params)
            return {"enhanced": out}

        run.contract_sr = SR

        return run, dt, {
            "kind": "classical", "repo": "self-contained (NumPy)",
            "arch": "Wiener filter (decision-directed)",
            "params": 0, "targets": ["enhanced"], "n_stems": 1,
            "sample_rate": SR, "channels": 2,
            "ckpt": None, "device": "cpu",
            "license": "public-domain algorithm",
        }

    return load


# ------------------------------------------------------------------ registry'''
if "def _make_wiener_loader" in s:
    print("SKIP loader 已存在")
elif OLD_FUNC in s:
    s = s.replace(OLD_FUNC, NEW_FUNC, 1)
    print("OK loader 已加")
else:
    print("!! 未找到 registry 注释锚点"); sys.exit(1)

# 3) REGISTRY 末尾加条目
OLD_REG = '''    "denoiser_master64": dict(
        loader=_make_denoiser_loader("master64-8a5dfb4bb92753dd.th", 64),
        needs_gt=False, label="denoiser master64 (16 kHz)"),
}'''
NEW_REG = '''    "denoiser_master64": dict(
        loader=_make_denoiser_loader("master64-8a5dfb4bb92753dd.th", 64),
        needs_gt=False, label="denoiser master64 (16 kHz)"),

    "wiener_filter": dict(
        loader=_make_wiener_loader(),
        needs_gt=False, label="Wiener filter (classical baseline)"),
}'''
if '"wiener_filter": dict' in s:
    print("SKIP registry 条目已存在")
elif OLD_REG in s:
    s = s.replace(OLD_REG, NEW_REG, 1)
    print("OK registry 条目已加")
else:
    print("!! 未找到 registry 末尾锚点"); sys.exit(1)

# 4) GROUP 加映射
OLD_GRP = '''    "mel_roformer_dereverb_echo": "dereverb",
}'''
NEW_GRP = '''    "mel_roformer_dereverb_echo": "dereverb",
    "wiener_filter": "denoise",
}'''
if '"wiener_filter": "denoise"' in s:
    print("SKIP group 已存在")
elif OLD_GRP in s:
    s = s.replace(OLD_GRP, NEW_GRP, 1)
    print("OK group 已加")
else:
    print("!! 未找到 group 锚点"); sys.exit(1)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("WROTE", p)

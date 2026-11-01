# -*- coding: utf-8 -*-
"""把 demucs 量化模型 mdx_q / mdx_extra_q 的权重归档到项目模型库。

依赖：权重需先从 demucs 远程下载到 torch hub 缓存
      (~/.cache/torch/hub/checkpoints/)，由 get_model() 触发。

归档结果：
  01_models/_weights/MDX-Net/mdx_q/      4 个 .th + mdx_q.yaml
  01_models/_weights/MDX-Net/mdx_extra_q/ 4 个 .th + mdx_extra_q.yaml

加载方式（与 mdx 一致）：
  from demucs.pretrained import get_model
  model = get_model('mdx_q', repo=Path('01_models/_weights/MDX-Net/mdx_q'))
"""
import shutil
from pathlib import Path

ROOT = Path(r"E:\FYP_HKBU")
CACHE = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
DEST = ROOT / "01_models" / "_weights" / "MDX-Net"

# sig -> (checksum, 归档子目录, yaml 内容)
MODELS = {
    "mdx_q": {
        "files": {
            "6b9c2ca1": "3fd82607",
            "b72baf4e": "8778635e",
            "42e558d4": "196e0e1b",
            "305bc58f": "18378783",
        },
        "yaml": (
            "models: ['6b9c2ca1', 'b72baf4e', '42e558d4', '305bc58f']\n"
            "weights: [\n"
            "  [1., 1., 0., 0.],\n"
            "  [0., 1., 0., 0.],\n"
            "  [1., 0., 1., 1.],\n"
            "  [1., 0., 1., 1.],\n"
            "]\n"
            "segment: 44\n"
        ),
    },
    "mdx_extra_q": {
        "files": {
            "83fc094f": "4a16d450",
            "464b36d7": "e5a9386e",
            "14fc6a69": "a89dd0ee",
            "7fd6ef75": "a905dd85",
        },
        "yaml": (
            "models: ['83fc094f', '464b36d7', '14fc6a69', '7fd6ef75']\n"
            "segment: 44\n"
        ),
    },
}


def archive_one(name: str, cfg: dict) -> bool:
    d = DEST / name
    d.mkdir(parents=True, exist_ok=True)
    missing = []
    for sig, cksum in cfg["files"].items():
        src = CACHE / f"{sig}-{cksum}.th"
        dst = d / f"{sig}-{cksum}.th"
        if not src.exists():
            missing.append(src.name)
            continue
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            continue
        shutil.copy2(src, dst)
    # 写 yaml（若内容不同则覆盖）
    yaml_path = d / f"{name}.yaml"
    if yaml_path.exists():
        old = yaml_path.read_text(encoding="utf-8")
    else:
        old = None
    if old != cfg["yaml"]:
        yaml_path.write_text(cfg["yaml"], encoding="utf-8")
    ok = not missing
    print(f"[{name}] 归档 {'OK' if ok else 'MISSING ' + ','.join(missing)}")
    for f in sorted(d.iterdir()):
        if f.name != "__pycache__":
            print(f"    {f.name}  ({f.stat().st_size/1e6:.1f} MB)")
    return ok


def main():
    all_ok = True
    for name, cfg in MODELS.items():
        all_ok &= archive_one(name, cfg)
    print("ALL_ARCHIVED" if all_ok else "SOME_MISSING")


if __name__ == "__main__":
    main()

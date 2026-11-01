# -*- coding: utf-8 -*-
"""Scan official config files for init params (STFT / segment / normalize)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import yaml  # noqa: E402


class _Loader(yaml.SafeLoader):
    """SafeLoader + python/tuple tag (BS-RoFormer / Mel-Band configs use it)."""


_Loader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    lambda loader, node: tuple(loader.construct_sequence(node, deep=True)),
)

KEYS = (
    "sample_rate", "samplerate", "sr", "n_fft", "hop_length", "n_hop", "hop",
    "win_length", "window", "segment", "chunk_size", "channels", "nb_channels",
    "normalize", "normalise", "sources", "instruments", "target_instrument",
    "dim", "depth", "num_channels", "stft",
)

ROOTS = [
    _paths.WEIGHTS,
    _paths.MODELS / "_third_party" / "bsrnn" / "conf",
    _paths.MODELS / "_third_party" / "demucs" / "conf",
    _paths.MODELS / "_third_party" / "denoiser" / "conf",
    _paths.MODELS / "_third_party" / "mdx-net" / "configs",
]


def walk(node, prefix=""):
    out = {}
    if isinstance(node, dict):
        for k, v in node.items():
            key = str(k)
            p = f"{prefix}.{key}" if prefix else key
            if key.lower() in KEYS and not isinstance(v, (dict, list)):
                out[p] = v
            elif key.lower() in KEYS and isinstance(v, list):
                out[p] = v[:8]
            else:
                out.update(walk(v, p))
    return out


def main():
    rows = []
    for root in ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.yaml")):
            try:
                doc = yaml.load(p.read_text(encoding="utf-8", errors="replace"), Loader=_Loader)
            except Exception as exc:
                rows.append({"path": str(p), "error": f"{type(exc).__name__}: {exc}"})
                continue
            if not isinstance(doc, dict):
                continue
            rows.append({"path": str(p), "keys": walk(doc)})
    out = _paths.PROJECT_ROOT / "configs" / "_init_params_raw.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out, "entries", len(rows))
    for r in rows:
        if "keys" not in r:
            print("ERR", r["path"], r["error"])
            continue
        print("---", r["path"].replace(str(_paths.PROJECT_ROOT) + "\\", ""))
        for k, v in r["keys"].items():
            print("   ", k, "=", v)


if __name__ == "__main__":
    main()

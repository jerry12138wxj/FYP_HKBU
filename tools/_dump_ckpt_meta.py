# -*- coding: utf-8 -*-
"""Dump init-relevant metadata from local checkpoints (args / hyper_parameters / config)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

_paths.setup_env()

import torch  # noqa: E402

PATTERNS = ("*.th", "*.ckpt", "*.pt", "*.pth")
KEY_HINTS = ("n_fft", "nfft", "hop", "segment", "samplerate", "sample_rate", "sources",
             "targets", "channels", "normalize", "dim", "depth", "chunk_size",
             "kernel_size", "stride", "n_hop", "win_length", "sources_names")


def flat(obj, prefix="", depth=0):
    out = {}
    if depth > 3:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flat(v, f"{prefix}.{k}" if prefix else str(k), depth + 1))
    elif hasattr(obj, "__dict__") and not isinstance(obj, (str, bytes, int, float, bool)):
        for k, v in vars(obj).items():
            out.update(flat(v, f"{prefix}.{k}" if prefix else str(k), depth + 1))
    else:
        if isinstance(obj, (int, float, str, bool, list, tuple)) or obj is None:
            out[prefix] = obj if not isinstance(obj, (list, tuple)) else list(obj)[:6]
    return out


def main():
    rows = []
    files = []
    for pat in PATTERNS:
        files.extend(_paths.WEIGHTS.rglob(pat))
    for p in sorted(files):
        rec = {"path": str(p.relative_to(_paths.PROJECT_ROOT)), "mb": round(p.stat().st_size / 2**20, 1)}
        try:
            obj = torch.load(str(p), map_location="cpu", weights_only=False)
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(rec)
            continue
        rec["top_keys"] = list(obj.keys())[:12] if isinstance(obj, dict) else type(obj).__name__
        blob = {}
        if isinstance(obj, dict):
            for key in ("args", "kwargs", "hyper_parameters", "hparams", "cfg", "config"):
                if key in obj:
                    blob[key] = flat(obj[key], key)
        if "config" in obj and isinstance(obj["config"], str):
            rec["config_yaml_head"] = obj["config"][:600]
        keep = {}
        for k, v in blob.items():
            for kk, vv in v.items():
                if any(h in kk.lower() for h in KEY_HINTS):
                    keep[f"{k}.{kk}"] = vv
        rec["params"] = keep
        rows.append(rec)
        print("---", rec["path"], rec.get("mb"), "MB")
        for k, v in list(keep.items())[:14]:
            print("   ", k, "=", v)
        if "error" in rec:
            print("   ERR", rec["error"])

    out = _paths.PROJECT_ROOT / "configs" / "_weights_meta.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("wrote", out, len(rows))


if __name__ == "__main__":
    main()

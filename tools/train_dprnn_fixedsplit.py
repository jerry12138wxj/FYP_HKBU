# -*- coding: utf-8 -*-
"""DPRNN retrain with a leak-free by-song split (zero-touch wrapper).

Why: tools/train_dprnn_musdb.py L78-82 puts all 3 validation clips in subset="train",
     i.e. the validation set is a subset of the 100 training songs -> best.pt selection
     is contaminated (val +2.745 dB vs test -1.72 dB).

What this wrapper changes (module-level attributes only, the original file is untouched):
   1. build_index("train") drops HELD_OUT songs  -> train = 90 songs
   2. VAL_CLIPS = HELD_OUT songs (whole-song holdout, still read from subset "train")
   3. checkpoints / history / log go to D:\\FYP_HKBU_runs\\dprnn_v2\\ (originals preserved)

Usage:
    python tools/train_dprnn_fixedsplit.py --minutes 300 --batch 4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import train_dprnn_musdb as T  # noqa: E402

RUN = Path(r"D:\FYP_HKBU_runs\dprnn_v2")

_ORIG_BUILD = T.build_index
_orig_index = _ORIG_BUILD("train")
_all_songs = [s for s, _ in _orig_index]
HELD_OUT = tuple(sorted(_all_songs)[:10])          # deterministic: first 10 by name
TRAIN_SONGS = tuple(s for s in _all_songs if s not in HELD_OUT)

assert len(TRAIN_SONGS) == len(_all_songs) - 10, "held-out size mismatch"
assert not (set(TRAIN_SONGS) & set(HELD_OUT)), "LEAK: train and valid overlap"

# offsets inside a held-out song: middle of the track (avoid intro silence)
_offsets = {}
for s, frames in _orig_index:
    if s in HELD_OUT:
        _offsets[s] = round(frames / 44100.0 * 0.5, 1)


def _patched_build(subset: str = "train"):
    idx = _ORIG_BUILD(subset)
    if subset == "train":
        return [(s, n) for s, n in idx if s in TRAIN_SONGS]
    return idx


T.build_index = _patched_build
T.VAL_CLIPS = tuple((s, "train", _offsets[s]) for s in HELD_OUT[:3])
T.CKPT_DIR = RUN / "checkpoints"
T.HIST_JSON = RUN / "training.json"
T.LOG_TXT = RUN / "train_dprnn_v2.log"
T.CURVE_PNG = RUN / "training_curve.png"


def write_manifest():
    RUN.mkdir(parents=True, exist_ok=True)
    print("train_songs=%d held_out=%d (valid clips=%d)" % (len(TRAIN_SONGS), len(HELD_OUT), len(T.VAL_CLIPS)))
    for s, sub, off in T.VAL_CLIPS:
        print("  valid: %-40s subset=%s offset=%.1fs" % (s, sub, off))
    (RUN / "split_manifest.txt").write_text(
        "train_songs=%d\nheld_out=%d\n\n[train]\n%s\n\n[valid]\n%s\n" % (
            len(TRAIN_SONGS), len(HELD_OUT),
            "\n".join(TRAIN_SONGS), "\n".join(HELD_OUT)),
        encoding="utf-8")


def main():
    write_manifest()
    # hand over to the original CLI (it parses sys.argv itself)
    T.main()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--dry-run", action="store_true")
    known, rest = ap.parse_known_args()
    if known.dry_run:
        write_manifest()
        print("dry-run ok; no training started")
        print("ckpt_dir=%s" % T.CKPT_DIR)
    else:
        main()

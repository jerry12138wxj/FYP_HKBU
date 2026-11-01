"""Live listening playground for both boards, on one port.

    * `/`     denoise: upload a noisy signal, run the 5 board-2 models on the
              spot, listen to the enhanced output.
    * `/sep`  separation: the MUSDB18-HQ three-song per-model comparison, plus a
              box that runs the 13 board-1 models on a built-in mixture or an
              uploaded file (a model over the per-model budget is skipped).

Why this exists
---------------
The offline comparison page referenced its audio with paths relative to the
*project root* (`../../../03_outputs/...`).  That only resolves when the page is
served by a static server rooted at the project.  Opened any other way (a bare
file:// open, or a preview pane that serves only the single HTML file) every
audio request 404s -- which is exactly the "all audio failed to load" symptom.

This server removes the ambiguity: the pages and the audio come from the *same*
origin, and every audio URL is root-absolute on that origin.

Deliverables / routes
---------------------
    GET  /                     live upload page  (this app)
    GET  /ab                   offline A/B page (10 Valentini + 6 transient)
    GET  /sep                  MUSDB18-HQ 3-song comparison + run-any-model box
    GET  /media/<clip>/<f>     audio for the A/B page (03_outputs/_denoise_ab)
    GET  /live/<sid>/<f>       audio produced by this session
    GET  /api/health           device / loaded models / config
    GET  /api/models           model catalogue for the UI
    GET  /api/sample?id=...    start a session from a built-in clip (no upload)
    POST /api/session          body = {name, noisy_b64, clean_b64?} -> {sid, ...}
    POST /api/run              body = {sid, model} -> one model's result
    GET  /<anything else>      static file under the project root (Range-aware)

Contract (the part that must not be fudged)
-------------------------------------------
Every model is addressed exactly as in `_denoise_eval.py`:

    noisy --> mono @16 kHz (metric rate)
          --> resample @ run_fn.contract_sr   (44100; NOT the metric rate!)
          --> np.stack([x, x], -1)            (always (N, 2))
          --> run_fn(...)["enhanced"]         (N, 2) @ contract_sr
          --> saved as the playable wav, then downmixed + resampled to 16 kHz
              for SI-SDR / PESQ / STOI

Feeding the 16 kHz array straight to a model would make the denoiser wrapper
resample a *second* time (audio sped up 2.76x) -- the P19 bug.  Hence the
explicit `contract_sr` hop, and the `min(len)` alignment (denoiser returns 2
fewer samples).

Run
---
    python tools/_denoise_live_server.py            # http://127.0.0.1:8123/
    python tools/_denoise_live_server.py --port 8123 --preload
"""
from __future__ import annotations

import argparse
import base64
import collections
import csv
import gc
import io
import json
import mimetypes
import os
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

import _denoise_registry as REG  # noqa: E402
from _denoise_eval import (  # noqa: E402
    list_synth, list_valentini, load_mono, mix_at_snr, pesq_wb,
    resample_mono, si_sdr, stoi_score,
)

ROOT = _paths.PROJECT_ROOT
TOOLS = ROOT / "tools"
AB_AUDIO = ROOT / "03_outputs" / "_denoise_ab"
LIVE_AUDIO = ROOT / "03_outputs" / "_denoise_live"
SEP_AUDIO = ROOT / "03_outputs" / "_sep_live"
AB_HTML = ROOT / "04_reports" / "02_denoising" / "html" / "denoise_ab_listen.html"
SEP_HTML = ROOT / "04_reports" / "01_separation" / "html" / "listen_compare.html"
MUSDB_TEST = ROOT / "02_databases" / "MUSDB18-HQ" / "test"

METRIC_SR = 16000
MAX_SEC = 60.0            # keep the interaction snappy; longer input is truncated
MAX_BYTES = 64 * 1024 * 1024

# Order matters for the UI: cheapest/fastest first.
MODEL_KEYS = [
    "denoiser_dns48", "denoiser_dns64", "denoiser_master64",
    "mel_roformer_denoise", "mel_roformer_denoise_aggr",
]

# Sample clips offered without an upload (same ids as the A/B page).
SAMPLE_IDS = ["p232_340", "p232_361", "p232_309", "p232_412_s-05", "p232_066_s+05"]


def _quiet(fn, *args):
    """Best-effort filesystem cleanup: never let a delete abort a user request.

    Some hosts intercept deletes -- AV real-time scanners, MDM, Smart App Control,
    a hardened sandbox -- and raise an exception that is *not* OSError.  Cleanup is
    housekeeping: if it fails the only cost is disk space.  Swallowing the whole
    exception hierarchy here is deliberate, because an exception escaping a
    cleanup call used to bubble out of the HTTP handler and close the connection
    with an empty reply (curl reports status 000).
    """
    try:
        fn(*args)
        return True
    except BaseException:                                          # noqa: BLE001
        return False

# --------------------------------------------------------------- model cache --
_LOCK = threading.RLock()          # guards loading AND inference (CUDA + 8 GiB)
_CACHE: dict = {}


def get_model(key: str):
    """Lazy-load a model once.  Serialised under _LOCK (multi-model + 8 GiB)."""
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        if key not in REG.REGISTRY:
            raise KeyError("unknown model: %s" % key)
        run_fn, load_s, info = REG.REGISTRY[key]["loader"]()
        _CACHE[key] = (run_fn, load_s, info)
        return _CACHE[key]


def catalogue():
    out = []
    for k in MODEL_KEYS:
        info = REG.REGISTRY[k]
        out.append({
            "key": k,
            "label": info.get("label", k),
            "needs_gt": bool(info.get("needs_gt")),
            "loaded": k in _CACHE,
        })
    return out


# ------------------------------------------------------------------- audio ----
def write_wav(path, audio, sr):
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 1:
        a = np.stack([a, a], axis=-1)
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    sf.write(str(path), a, int(sr), subtype="PCM_16")
    return os.path.getsize(str(path))


def rms(x):
    x = np.asarray(x, dtype=np.float32)
    return float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0


def enhance(noisy16, model_key, max_sec=MAX_SEC):
    """Run one model on a mono 16 kHz array; return (est16, out44, info, infer_s).

    `out44` is the (N, 2) @ contract_sr array actually written for playback.
    """
    run_fn, _load_s, info = get_model(model_key)
    csr = int(getattr(run_fn, "contract_sr", 44100))

    x = noisy16 if csr == METRIC_SR else resample_mono(noisy16, METRIC_SR, csr)
    stack = np.stack([x, x], axis=-1).astype(np.float32)

    t0 = time.time()
    with _LOCK:                                    # one GPU job at a time
        est = np.asarray(run_fn(stack)["enhanced"], dtype=np.float32)
    infer_s = time.time() - t0

    est16 = est.mean(axis=1) if est.ndim == 2 else np.asarray(est, dtype=np.float32)
    if csr != METRIC_SR:
        est16 = resample_mono(est16, csr, METRIC_SR)
    return est16, est, info, infer_s, csr


def score(noisy16, est16, clean16=None):
    """Metrics on the 16 kHz arrays.  Δ* need a clean reference; without one we
    still report loudly-meaningful level / energy numbers (never a fake 0)."""
    n = min(len(noisy16), len(est16))
    nz, es = noisy16[:n], est16[:n]
    m = {
        "rms_in": round(rms(nz), 6),
        "rms_out": round(rms(es), 6),
        "level_ratio_vs_in": round(rms(es) / (rms(nz) + 1e-12), 4),
        "has_clean": clean16 is not None,
        "si_sdr_in": None, "si_sdr_out": None, "si_sdr_improve": None,
        "pesq_in": None, "pesq_out": None, "pesq_improve": None,
        "stoi_in": None, "stoi_out": None, "stoi_improve": None,
        "level_ratio": None,
    }
    if clean16 is None:
        return m
    k = min(len(clean16), n)
    cl = clean16[:k]
    m["si_sdr_in"] = round(si_sdr(cl, nz[:k]), 4)
    m["si_sdr_out"] = round(si_sdr(cl, es[:k]), 4)
    m["si_sdr_improve"] = round(m["si_sdr_out"] - m["si_sdr_in"], 4)
    m["pesq_in"] = pesq_wb(cl, nz[:k], METRIC_SR)
    m["pesq_out"] = pesq_wb(cl, es[:k], METRIC_SR)
    if m["pesq_in"] is not None and m["pesq_out"] is not None:
        m["pesq_improve"] = round(m["pesq_out"] - m["pesq_in"], 4)
    m["stoi_in"] = stoi_score(cl, nz[:k], METRIC_SR)
    m["stoi_out"] = stoi_score(cl, es[:k], METRIC_SR)
    if m["stoi_in"] is not None and m["stoi_out"] is not None:
        m["stoi_improve"] = round(m["stoi_out"] - m["stoi_in"], 4)
    m["level_ratio"] = round(rms(es[:k]) / (rms(cl) + 1e-12), 4)
    return m


# ----------------------------------------------------------------- sessions ---
_SESSIONS: dict = {}


def _finalise(name, sid, d, noisy16, clean16):
    """Persist the playable wavs and register the session.

    noisy.wav is written at the *contract* rate (44.1 kHz) -- the array the
    models actually receive -- so what you hear is what was scored.
    """
    write_wav(d / "noisy.wav", resample_mono(noisy16, METRIC_SR, 44100), 44100)
    if clean16 is not None:
        write_wav(d / "clean.wav", resample_mono(clean16, METRIC_SR, 44100), 44100)
    s = {
        "sid": sid, "name": name, "dir": d,
        "noisy16": noisy16, "clean16": clean16,
        "dur_s": round(len(noisy16) / METRIC_SR, 3),
        "truncated": False, "results": {},
    }
    _SESSIONS[sid] = s
    return s


def new_session(name, noisy_bytes, clean_bytes=None):
    sid = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
    d = LIVE_AUDIO / sid
    d.mkdir(parents=True, exist_ok=True)

    tmp_noisy = d / ("_upload_noisy" + (os.path.splitext(name or ".wav")[1].lower() or ".wav"))
    tmp_noisy.write_bytes(noisy_bytes)
    noisy16 = load_mono(tmp_noisy, METRIC_SR, max_seconds=MAX_SEC)

    clean16 = None
    if clean_bytes:
        tmp_clean = d / "_upload_clean.wav"
        tmp_clean.write_bytes(clean_bytes)
        clean16 = load_mono(tmp_clean, METRIC_SR, max_seconds=MAX_SEC)

    for f in d.glob("_upload_*"):
        _quiet(f.unlink)
    return _finalise(name or "upload.wav", sid, d, noisy16, clean16)


def new_session_from_arrays(name, noisy16, clean16):
    sid = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
    d = LIVE_AUDIO / sid
    d.mkdir(parents=True, exist_ok=True)
    return _finalise(name, sid, d, noisy16, clean16)


def sample_inputs(cid):
    """Resolve a built-in sample to 16 kHz arrays.

    🔴 Read the ORIGINAL dataset file, never the stored 44.1 kHz wav under
    `_denoise_ab/`: re-decoding that wav adds a 16k round-trip and perturbs the
    model input (measured: dns64 +0.19 dB, master64 +2.15 dB off).  Going
    straight from the dataset is the route the offline numbers were produced on.
    """
    for r in list_valentini():
        if r["clip_id"] == cid:
            return (cid + ".wav",
                    load_mono(r["noisy_path"], METRIC_SR, max_seconds=MAX_SEC),
                    load_mono(r["clean_path"], METRIC_SR, max_seconds=MAX_SEC))
    for r in list_synth():
        if r["clip_id"] == cid:
            clean16 = load_mono(r["clean_path"], METRIC_SR, max_seconds=MAX_SEC)
            noise16 = load_mono(r["noise_path"], METRIC_SR, max_seconds=MAX_SEC)
            # same deterministic seed as tools/_export_denoise_ab.py, so the
            # page and this endpoint describe the same mixture
            seed = zlib.crc32(cid.encode("utf-8")) & 0xFFFF
            return (cid + ".wav",
                    mix_at_snr(clean16, noise16, r["snr_db"], seed=seed), clean16)
    return None


def run_one(sid, model_key):
    s = _SESSIONS.get(sid)
    if s is None:
        raise KeyError("unknown session: %s" % sid)
    if model_key in s["results"]:
        return s["results"][model_key]

    est16, out44, info, infer_s, csr = enhance(s["noisy16"], model_key)
    fname = model_key.replace("_", "-") + ".wav"
    mb = write_wav(s["dir"] / fname, out44, csr)
    rec = {
        "key": model_key,
        "label": REG.REGISTRY[model_key].get("label", model_key),
        "src": "/live/%s/%s" % (sid, quote(fname)),
        "out_sr": csr,
        "native_sr": info.get("sample_rate"),
        "params": info.get("params"),
        "n_stems": info.get("n_stems"),
        "infer_s": round(infer_s, 3),
        "mb": round(mb / 1e6, 3),
        "metrics": score(s["noisy16"], est16, s["clean16"]),
    }
    s["results"][model_key] = rec
    return rec


# ================================================== board 1: separation (stage 4)
# The 13 deep separation models.  Excluded on purpose:
#   oracle -- needs the ground truth, which an arbitrary upload does not have;
#   rpca   -- analytic, RTF 8.25 (82.5 s for a 10 s clip) so the 8 s budget would
#             always kill it, and its sparse component has no natural stem mapping.
SEP_KEYS = [
    "demucs", "umx", "mmdenselstm", "mdx", "convtasnet", "dprnn",
    "bsrnn", "bsrnn_all", "bsrnn_large", "bsrnn_large_all", "bsrnn_simo",
    "bsroformer_l6", "bsroformer_l12",
]
SEP_STEMS = ("vocals", "drums", "bass", "other")

SEP_BUDGET_S = 8.0            # 用户规则：单模型推理超过 8 秒 -> 跳过
SEP_MAX_SEC = 30.0            # 上传/内置样本的时长上限（与 8 s 预算配合）
SEP_CHUNK_S = 10.0            # 分块把显存峰值钉在 10 s 档（profile 最坏 3394 MB）
SEP_OVERLAP_S = 1.0
SEP_LOAD_TIMEOUT_S = 600.0    # 只约束"加载"，不计入 8 s 预算
SEP_KEEP_SESSIONS = 3

PROFILE_CSV = ROOT / "04_reports" / "00_shared" / "data" / "model_analysis" / "model_profile.csv"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _load_sep_profile():
    """Read the machine-generated profile so the UI never hardcodes a number."""
    out = {}
    if not PROFILE_CSV.is_file():
        return out
    with open(PROFILE_CSV, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            out[r["model_key"]] = r
    return out


_SEP_PROFILE = _load_sep_profile()
_SEP_GT_CACHE: dict = {}
_SEP_SESSIONS: dict = {}
_SEP_LOCK = threading.RLock()
_SEP_WORKER = None            # single live worker -- see SepWorker docstring


def sep_catalogue():
    w = _SEP_WORKER
    live = bool(w and w.alive())
    out = []
    for k in SEP_KEYS:
        row = _SEP_PROFILE.get(k, {})
        out.append({
            "key": k,
            "label": row.get("label") or k,
            "group": row.get("group") or "",
            "params_M": _f(row.get("params_M")),
            "latency_s": _f(row.get("latency_s")),
            "rtf": _f(row.get("rtf")),
            "flops_G": _f(row.get("flops_G")),
            "peak_vram_mb": _f(row.get("peak_vram_infer_mb")),
            "loaded": bool(live and w.key == k),
            "load_s": (w.info.get("load_s") if live and w.key == k else None),
            "targets": (w.info.get("targets") if live and w.key == k else []),
        })
    return out


# ------------------------------------------------------------ worker plumbing --
class _Lines(threading.Thread):
    """Drain a text stream into a queue so a read can be given a deadline."""

    def __init__(self, stream, tag):
        super().__init__(daemon=True, name=tag)
        self.stream = stream
        self.q: "queue.Queue" = queue.Queue()
        self.tail = collections.deque(maxlen=60)
        self.start()

    def run(self):
        try:
            for line in self.stream:
                self.tail.append(line.rstrip())
                self.q.put(line)
        except Exception:                                      # noqa: BLE001
            pass
        finally:
            self.q.put(None)


def _next_json(reader, timeout):
    """Read lines until one parses as a JSON object.

    Loader chatter must never break the protocol.  `_sep_worker.py` already
    redirects loader prints to stderr, but this stays defensive: a single stray
    line used to be fatal (`JSONDecodeError: Expecting value: line 1 column 6`).
    """
    deadline = time.time() + timeout
    while True:
        left = deadline - time.time()
        if left <= 0:
            raise TimeoutError("no protocol line within %.1fs" % timeout)
        try:
            line = reader.q.get(timeout=left)
        except queue.Empty:
            raise TimeoutError("no protocol line within %.1fs" % timeout)
        if line is None:
            raise RuntimeError("worker closed stdout")
        s = line.strip()
        if not s or not s.startswith("{"):
            continue
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            continue


class SepWorker:
    """One separation model, one process.

    Why a process and not a thread: the 8 s budget has to be *enforceable*.
    A torch forward pass has no cancellation point, so a thread cannot be
    stopped -- but a process can be killed, and its CUDA context dies with it,
    returning the VRAM immediately so the next model is not left blocked.
    """

    def __init__(self, key):
        self.key = key
        self.proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", str(TOOLS / "_sep_worker.py"), "--model", key],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1, cwd=str(ROOT),
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        )
        self.out = _Lines(self.proc.stdout, "sep-%s-out" % key)
        self.err = _Lines(self.proc.stderr, "sep-%s-err" % key)
        try:
            msg = _next_json(self.out, SEP_LOAD_TIMEOUT_S)
        except Exception as e:                                 # noqa: BLE001
            detail = " | ".join(list(self.err.tail)[-6:])
            self.kill()
            raise RuntimeError("load failed for %s: %s :: %s" % (key, e, detail[-600:]))
        if msg.get("event") != "ready":
            detail = " | ".join(list(self.err.tail)[-6:])
            self.kill()
            raise RuntimeError("load failed for %s: %s :: %s"
                               % (key, msg.get("error"), detail[-600:]))
        self.info = msg

    def alive(self):
        return self.proc.poll() is None

    def run(self, job, budget_s):
        if not self.alive():
            raise RuntimeError("worker for %s exited (rc=%s)" % (self.key, self.proc.returncode))
        try:
            self.proc.stdin.write(json.dumps(job) + "\n")
            self.proc.stdin.flush()
        except OSError as e:
            raise RuntimeError("worker stdin closed: %s" % e)
        msg = _next_json(self.out, budget_s)                   # <-- the 8 s budget
        if msg.get("event") != "result":
            raise RuntimeError(msg.get("error") or "unexpected worker reply: %s" % msg.get("event"))
        return msg

    def kill(self):
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:                                      # noqa: BLE001
            pass
        if self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.wait(timeout=10)
            except Exception:                                  # noqa: BLE001
                pass

    def note(self, n=8):
        return " | ".join(list(self.err.tail)[-n:])


def _unload_denoise(reason):
    """Free the denoise models so a big separation model has room.

    Device-wide free memory is the only meaningful number here: the separation
    model lives in a *separate process*, so this process's allocator cache tells
    us nothing about what the worker will find.
    """
    with _LOCK:
        if not _CACHE:
            return 0
        n = len(_CACHE)
        _CACHE.clear()
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:                                          # noqa: BLE001
        pass
    sys.stderr.write("  [gpu] unloaded %d denoise model(s): %s\n" % (n, reason))
    return n


def _ensure_vram(key):
    need = None
    row = _SEP_PROFILE.get(key) or {}
    need = _f(row.get("peak_vram_infer_mb")) or _f(row.get("peak_vram_mb"))
    if not need:
        return None
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        free_b, _total = torch.cuda.mem_get_info()
    except Exception:                                          # noqa: BLE001
        return None
    free_mb = free_b / 1e6
    if free_mb < need * 1.15 + 400:
        return _unload_denoise("%s needs ~%.0f MB, only %.0f MB free" % (key, need, free_mb))
    return None


def sep_reset():
    """Kill the live worker (used on overrun and on shutdown)."""
    global _SEP_WORKER
    with _SEP_LOCK:
        if _SEP_WORKER is not None:
            _SEP_WORKER.kill()
            _SEP_WORKER = None


def sep_worker(key):
    """Return a live worker for `key`, killing whatever else was resident.

    Deliberately LRU=1: 13 separation models sum to ~1.18 G parameters (4.7 GB of
    weights alone), so two of them plus activations do not fit in 8 GiB.
    """
    global _SEP_WORKER
    if key not in SEP_KEYS:
        raise KeyError("unsupported separation model: %s" % key)
    if _SEP_WORKER is not None and _SEP_WORKER.key == key and _SEP_WORKER.alive():
        return _SEP_WORKER
    if _SEP_WORKER is not None:
        _SEP_WORKER.kill()
        _SEP_WORKER = None
    _ensure_vram(key)
    _SEP_WORKER = SepWorker(key)
    return _SEP_WORKER


# ------------------------------------------------------- separation sessions --
# Housekeeping is deliberately off the request path.  A bulk delete can be
# intercepted on a locked-down host (AV, MDM, a batch-delete guard) and take tens
# of seconds; measured on this machine, pruning ten stale session directories
# stalled /api/sep/sample for 48 s.  No user request should ever pay that.
_PRUNE_BUSY = threading.Event()
_PRUNE_BACKOFF_UNTIL = [0.0]
_PRUNE_MAX_PER_PASS = 24
_PRUNE_BACKOFF_S = 60.0


def _sep_prune(max_delete=_PRUNE_MAX_PER_PASS):
    """Drop the oldest session directories.  Returns ``(attempted, deleted)``.

    Each session dir can hold four stem wavs, so they are worth reclaiming -- but
    not at the cost of request latency.  ``max_delete`` bounds a single pass so
    one request can never fan out into an enormous burst of deletions.
    """
    try:
        dirs = sorted((d for d in SEP_AUDIO.iterdir() if d.is_dir()),
                      key=lambda d: d.stat().st_mtime, reverse=True)
    except OSError:
        return 0, 0
    keep = {sid for sid in _SEP_SESSIONS}
    attempted = deleted = 0
    for i, d in enumerate(dirs):
        if i < SEP_KEEP_SESSIONS or d.name in keep:
            continue
        if attempted >= max_delete:
            break
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            attempted += 1
            if _quiet(f.unlink):
                deleted += 1
        if _quiet(d.rmdir):
            deleted += 1
    return attempted, deleted


def _sep_prune_async():
    """Fire-and-forget prune, throttled so it can never pile up or spam retries."""
    if _PRUNE_BUSY.is_set() or time.time() < _PRUNE_BACKOFF_UNTIL[0]:
        return

    def work():
        try:
            attempted, deleted = _sep_prune()
            if attempted and not deleted:
                # Every single delete was refused -- stop retrying on each request.
                _PRUNE_BACKOFF_UNTIL[0] = time.time() + _PRUNE_BACKOFF_S
        except BaseException:                                      # noqa: BLE001
            _PRUNE_BACKOFF_UNTIL[0] = time.time() + _PRUNE_BACKOFF_S
        finally:
            _PRUNE_BUSY.clear()

    _PRUNE_BUSY.set()
    threading.Thread(target=work, daemon=True, name="sep-prune").start()


def _sep_gt(song):
    """Mono ground-truth stems for the first SEP_MAX_SEC seconds (cached).

    Decodes only the head of each stem: ``frames=`` stops the read at the clip
    length, instead of pulling in the whole 13 MB track just to discard the tail.
    """
    if song in _SEP_GT_CACHE:
        return _SEP_GT_CACHE[song]
    out = {}
    d = MUSDB_TEST / song
    for t in SEP_STEMS:
        p = d / (t + ".wav")
        if not p.is_file():
            continue
        try:
            sr = sf.info(str(p)).samplerate
        except Exception:                                          # noqa: BLE001
            continue
        x, sr = sf.read(str(p), frames=int(SEP_MAX_SEC * sr),
                        dtype="float32", always_2d=True)
        out[t] = x[: int(SEP_MAX_SEC * sr)].mean(axis=1).astype(np.float32)
    _SEP_GT_CACHE[song] = out or None
    return _SEP_GT_CACHE[song]


def _sep_write_input(raw_bytes, out_path):
    """Write an upload as (N,2) @ 44.1 kHz, truncated to SEP_MAX_SEC.

    Decoded straight from memory via ``io.BytesIO``.  The previous version wrote a
    temp file and unlinked it afterwards; that added one delete per request, and
    on a locked-down host a blocked delete can raise something *other* than
    OSError -- which escaped the old ``except OSError`` and killed the whole HTTP
    request with an empty reply (curl: status 000).  No temp file, no delete.
    """
    x, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32", always_2d=True)
    x = x[: int(SEP_MAX_SEC * sr)]
    if sr != 44100:
        import torch
        import torchaudio.functional as AF
        t = torch.as_tensor(np.ascontiguousarray(x.T))
        x = AF.resample(t, sr, 44100).numpy().T
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    elif x.shape[1] > 2:
        x = x[:, :2]
    d = len(x) / 44100
    sf.write(str(out_path), np.ascontiguousarray(x, dtype=np.float32), 44100, subtype="PCM_16")
    return out_path, d


def sep_new_session(name, input_path, dur_s, gt):
    sid = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
    d = SEP_AUDIO / sid
    d.mkdir(parents=True, exist_ok=True)
    s = {"sid": sid, "dir": d, "name": name, "input": input_path,
         "dur_s": round(dur_s, 3), "gt": gt}
    _SEP_SESSIONS[sid] = s
    _sep_prune_async()
    return s


def _sep_score(s, key, res):
    """Per-stem SI-SDR against ground truth when we have it.

    For an arbitrary upload there is no reference -- then we report levels only
    and say so, rather than inventing a "0 dB improvement".
    """
    gt = s.get("gt")
    per, levels = {}, {}
    for st in res["stems"]:
        t = st["target"]
        levels[t] = {"rms": st["rms"], "peak": st["peak"], "dur_s": st["dur_s"]}
        if not gt:
            continue
        ref = gt.get(t)
        if ref is None and t == "vocals+other" and "vocals" in gt and "other" in gt:
            ref = gt["vocals"] + gt["other"]
        if ref is None:
            continue
        try:
            y, _sr = sf.read(str(s["dir"] / key / st["file"]), dtype="float32", always_2d=True)
        except OSError:
            continue
        y = y.mean(axis=1)
        n = min(len(ref), len(y))
        per[t] = round(si_sdr(ref[:n], y[:n]), 3)
    four = [per[k] for k in SEP_STEMS if k in per]
    return {
        "has_gt": bool(gt),
        "per_target": per,
        "mean4": round(sum(four) / len(four), 3) if len(four) == 4 else None,
        "levels": levels,
        "gt_note": ("SI-SDR vs MUSDB18-HQ ground truth（前 %g 秒）" % SEP_MAX_SEC) if gt else None,
    }


def sep_run(sid, key, budget_s=SEP_BUDGET_S):
    """Run one separation model on a session, under a hard inference budget."""
    s = _SEP_SESSIONS.get(sid)
    if s is None:
        raise KeyError("unknown session: %s" % sid)
    if key not in SEP_KEYS:
        raise KeyError("unsupported separation model: %s" % key)

    with _LOCK:                                    # one GPU job at a time, global
        t0 = time.time()
        try:
            w = sep_worker(key)
        except Exception as e:                                 # noqa: BLE001
            return {"model": key, "skipped": False, "failed": True,
                    "error": str(e)[:800], "elapsed_s": round(time.time() - t0, 3)}
        load_s = w.info.get("load_s")
        job = {"job_id": "%s-%s" % (sid, key), "input": str(s["input"]),
               "out_dir": str(s["dir"] / key), "max_seconds": SEP_MAX_SEC,
               "chunk_s": SEP_CHUNK_S, "overlap_s": SEP_OVERLAP_S}
        try:
            res = w.run(job, budget_s)
        except TimeoutError:
            sep_reset()                     # the kill IS the budget -- see SepWorker
            return {"model": key, "skipped": True, "failed": False,
                    "budget_s": budget_s, "load_s": load_s,
                    "reason": "运行时间过长，已跳过（推理超过 %g 秒）" % budget_s,
                    "elapsed_s": round(time.time() - t0, 3)}
        except Exception as e:                                 # noqa: BLE001
            note = w.note()
            sep_reset()
            return {"model": key, "skipped": False, "failed": True,
                    "error": "%s :: %s" % (str(e)[:400], note[-400:]),
                    "elapsed_s": round(time.time() - t0, 3)}

    stems = []
    for st in res["stems"]:
        stems.append(dict(st, src="/seplive/%s/%s/%s" % (sid, quote(key, safe=""),
                                                         quote(st["file"], safe=""))))
    return {
        "model": key,
        "label": (_SEP_PROFILE.get(key) or {}).get("label") or key,
        "skipped": False, "failed": False,
        "load_s": load_s,
        "infer_s": res["infer_s"],
        "elapsed_s": round(time.time() - t0, 3),
        "in_s": res["in_s"], "out_sr": res["out_sr"],
        "chunked": res["chunked"], "n_chunks": res["n_chunks"],
        "params": w.info.get("params"),
        "stems": stems,
        "score": _sep_score(s, key, res),
    }


# --------------------------------------------------------------- http infra ---
def _range(total, header):
    """Parse a single-range header -> (start, end_inclusive) or None."""
    if not header or not header.startswith("bytes="):
        return None
    spec = header[6:].split(",")[0].strip()
    m = re.match(r"^(\d*)-(\d*)$", spec)
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    if a == "" and b == "":
        return None
    if a == "":
        n = int(b)
        start = max(0, total - n)
        return start, total - 1
    start = int(a)
    end = int(b) if b else total - 1
    end = min(end, total - 1)
    if start > end:
        return None
    return start, end


class Handler(BaseHTTPRequestHandler):
    server_version = "FYP-DenoiseLive/1.0"
    protocol_version = "HTTP/1.1"

    # -------------------------------------------------------------- helpers --
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text, code=200):
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, msg):
        self._json({"error": msg}, code)

    def _file(self, path):
        p = os.path.abspath(str(path))
        if not os.path.isfile(p):
            return self._error(404, "not found: %s" % os.path.basename(p))
        total = os.path.getsize(p)
        ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
        rng = _range(total, self.headers.get("Range"))
        try:
            fh = open(p, "rb")
        except OSError as e:
            return self._error(500, str(e))
        with fh:
            if rng is None:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(total))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                while True:
                    chunk = fh.read(1 << 16)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            else:
                start, end = rng
                length = end - start + 1
                fh.seek(start)
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, total))
                self.end_headers()
                left = length
                while left > 0:
                    chunk = fh.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return b""
        if n > MAX_BYTES * 2:
            raise ValueError("body too large: %d bytes" % n)
        buf = bytearray()
        while len(buf) < n:
            chunk = self.rfile.read(min(1 << 16, n - len(buf)))
            if not chunk:
                break
            buf += chunk
        return bytes(buf)

    # ------------------------------------------------------------------ GET --
    def do_GET(self):                                            # noqa: N802
        u = urlparse(self.path)
        p = unquote(u.path)

        if p in ("/", "/index.html"):
            return self._html(LIVE_HTML)

        if p == "/ab":
            if not os.path.isfile(str(AB_HTML)):
                return self._error(404, "A/B page not built: run tools/_build_denoise_ab_page.py")
            return self._file(AB_HTML)

        if p == "/sep":
            if not os.path.isfile(str(SEP_HTML)):
                return self._error(404, "separation page not built: run tools/_build_listen_page.py")
            return self._file(SEP_HTML)

        if p == "/api/health":
            import torch
            return self._json({
                "ok": True,
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "loaded": sorted(_CACHE.keys()),
                "metric_sr": METRIC_SR, "contract_sr": 44100,
                "max_sec": MAX_SEC, "max_mb": MAX_BYTES // (1024 * 1024),
                "sessions": len(_SESSIONS),
                "sep_worker": (_SEP_WORKER.key if _SEP_WORKER and _SEP_WORKER.alive() else None),
                "sep_budget_s": SEP_BUDGET_S, "sep_max_sec": SEP_MAX_SEC,
            })

        if p == "/api/sep/models":
            return self._json({
                "models": sep_catalogue(),
                "order": SEP_KEYS,
                "budget_s": SEP_BUDGET_S,
                "max_sec": SEP_MAX_SEC,
                "chunk_s": SEP_CHUNK_S,
            })

        if p == "/api/sep/sample":
            qs = parse_qs(u.query)
            song = (qs.get("id") or [""])[0]
            d = MUSDB_TEST / song
            mix = d / "mixture.wav"
            if not song or not mix.is_file():
                return self._error(404, "song not found: %s" % song)
            sid = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
            sdir = SEP_AUDIO / sid
            sdir.mkdir(parents=True, exist_ok=True)
            try:
                inp, dur = _sep_write_input(mix.read_bytes(), sdir / "input.wav")
                s = sep_new_session(song, inp, dur, _sep_gt(song))
            except Exception as e:                             # noqa: BLE001
                traceback.print_exc()
                return self._error(500, "could not prepare sample: %s" % e)
            return self._json({"sid": s["sid"], "name": s["name"], "dur_s": s["dur_s"],
                               "has_gt": bool(s["gt"]),
                               "input_src": "/seplive/%s/input.wav" % s["sid"]})

        if p == "/api/models":
            return self._json({"models": catalogue(), "order": MODEL_KEYS,
                               "samples": SAMPLE_IDS})

        if p == "/api/sample":
            qs = parse_qs(u.query)
            cid = (qs.get("id") or [SAMPLE_IDS[0]])[0]
            got = sample_inputs(cid)
            if got is None:
                return self._error(404, "sample not found: %s" % cid)
            name, noisy16, clean16 = got
            s = new_session_from_arrays(name, noisy16, clean16)
            return self._json({"sid": s["sid"], "name": s["name"],
                               "dur_s": s["dur_s"],
                               "noisy_src": "/live/%s/noisy.wav" % s["sid"],
                               "clean_src": ("/live/%s/clean.wav" % s["sid"])
                               if s["clean16"] is not None else None})

        m = re.match(r"^/media/([^/]+)/([^/]+)$", p)
        if m:
            return self._file(AB_AUDIO / unquote(m.group(1)) / unquote(m.group(2)))

        m = re.match(r"^/seplive/([^/]+)/([^/]+)/([^/]+)$", p)
        if m:
            sid, model, fn = (unquote(g) for g in m.groups())
            for part in (sid, model, fn):
                if not re.match(r"^[\w.\-+]+$", part):
                    return self._error(400, "bad path")
            return self._file(SEP_AUDIO / sid / model / fn)

        m = re.match(r"^/seplive/([^/]+)/([^/]+)$", p)
        if m:
            sid, fn = unquote(m.group(1)), unquote(m.group(2))
            for part in (sid, fn):
                if not re.match(r"^[\w.\-+]+$", part):
                    return self._error(400, "bad path")
            return self._file(SEP_AUDIO / sid / fn)

        m = re.match(r"^/live/([^/]+)/([^/]+)$", p)
        if m:
            sid, fn = unquote(m.group(1)), unquote(m.group(2))
            if not re.match(r"^[\w.\-+]+$", sid) or not re.match(r"^[\w.\-+]+$", fn):
                return self._error(400, "bad path")
            return self._file(LIVE_AUDIO / sid / fn)

        # static fallback: anything under the project root (separation page etc.)
        rel = p.lstrip("/")
        cand = os.path.normpath(os.path.join(str(ROOT), rel.replace("/", os.sep)))
        if cand.startswith(os.path.abspath(str(ROOT)) + os.sep) and os.path.isfile(cand):
            return self._file(cand)
        return self._error(404, "not found: %s" % p)

    # ----------------------------------------------------------------- POST --
    def do_POST(self):                                           # noqa: N802
        u = urlparse(self.path)
        try:
            raw = self._body()
            req = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as e:                                   # noqa: BLE001
            return self._error(400, "bad request body: %s" % e)

        if u.path == "/api/session":
            try:
                nz = base64.b64decode(req.get("noisy_b64") or "", validate=False)
                cl = base64.b64decode(req["clean_b64"]) if req.get("clean_b64") else None
                if not nz:
                    return self._error(400, "noisy_b64 is empty")
                s = new_session(req.get("name") or "upload.wav", nz, cl)
                return self._json({
                    "sid": s["sid"], "name": s["name"], "dur_s": s["dur_s"],
                    "noisy_src": "/live/%s/noisy.wav" % s["sid"],
                    "clean_src": ("/live/%s/clean.wav" % s["sid"])
                    if s["clean16"] is not None else None,
                })
            except Exception as e:                               # noqa: BLE001
                traceback.print_exc()
                return self._error(500, "session failed: %s" % e)

        if u.path == "/api/run":
            sid = req.get("sid") or ""
            key = req.get("model") or ""
            if key not in REG.REGISTRY:
                return self._error(400, "unknown model: %s" % key)
            try:
                t0 = time.time()
                rec = run_one(sid, key)
                rec["elapsed_s"] = round(time.time() - t0, 3)
                return self._json(rec)
            except KeyError as e:
                return self._error(404, str(e))
            except Exception as e:                               # noqa: BLE001
                traceback.print_exc()
                return self._error(500, "run failed: %s" % e)

        if u.path == "/api/sep/session":
            try:
                raw_nz = base64.b64decode(req.get("noisy_b64") or "", validate=False)
                if not raw_nz:
                    return self._error(400, "noisy_b64 is empty")
                sid = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
                sdir = SEP_AUDIO / sid
                sdir.mkdir(parents=True, exist_ok=True)
                name = req.get("name") or "upload.wav"
                inp, dur = _sep_write_input(raw_nz, sdir / "input.wav")
                s = sep_new_session(name, inp, dur, None)      # upload -> no reference
                return self._json({"sid": s["sid"], "name": s["name"], "dur_s": s["dur_s"],
                                   "has_gt": False,
                                   "input_src": "/seplive/%s/input.wav" % s["sid"]})
            except Exception as e:                               # noqa: BLE001
                traceback.print_exc()
                return self._error(500, "separation session failed: %s" % e)

        if u.path == "/api/sep/run":
            sid = req.get("sid") or ""
            key = req.get("model") or ""
            try:
                budget = float(req.get("budget_s") or SEP_BUDGET_S)
            except (TypeError, ValueError):
                budget = SEP_BUDGET_S
            if key not in SEP_KEYS:
                return self._error(400, "unsupported separation model: %s" % key)
            try:
                return self._json(sep_run(sid, key, budget))
            except KeyError as e:
                return self._error(404, str(e))
            except Exception as e:                               # noqa: BLE001
                traceback.print_exc()
                return self._error(500, "separation run failed: %s" % e)

        return self._error(404, "unknown endpoint: %s" % u.path)

    def log_message(self, fmt, *args):                            # noqa: A003
        msg = fmt % args
        if "/api/" in msg or " 4" in msg or " 5" in msg:
            sys.stderr.write("  %s\n" % msg)


# --------------------------------------------------------------------- UI -----
LIVE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>降噪实时试听 · 上传 → 运行 → 试听</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1f2328;--dim:#6b7280;--line:#e5e7eb;
 --acc:#2563eb;--warn:#b45309;--bad:#b91c1c;--grn:#15803d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:20px 18px 80px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--dim);font-size:12.5px;margin-bottom:16px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}
.panel h2{font-size:13px;margin:0 0 12px;color:var(--dim);font-weight:600;
 letter-spacing:.03em;text-transform:uppercase}
.drop{border:2px dashed #cbd5e1;border-radius:10px;padding:22px;text-align:center;
 background:#fbfcfe;cursor:pointer;transition:.15s}
.drop:hover,.drop.over{border-color:var(--acc);background:#eff6ff}
.drop b{display:block;font-size:14px;margin-bottom:4px}
.drop span{color:var(--dim);font-size:12.5px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px}
label.f{font-size:12.5px;color:var(--dim)}
input[type=file]{display:none}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);
 background:#fff;border-radius:999px;padding:5px 11px;font-size:12.5px;cursor:pointer}
.pill input{margin:0}
.pill.on{border-color:var(--acc);background:#eff6ff;color:#1d4ed8;font-weight:600}
button{font:inherit;border-radius:8px;cursor:pointer}
.btn{border:1px solid var(--line);background:#fff;padding:8px 14px}
.btn.pri{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.btn:disabled{opacity:.5;cursor:not-allowed}
.msg{margin-top:10px;font-size:12.5px;color:var(--dim)}
.msg.err{color:var(--bad)}
.msg.ok{color:var(--grn)}
progress{width:100%;height:8px;border-radius:999px;overflow:hidden;margin-top:10px}
.bar{height:6px;background:#e5e7eb;border-radius:999px;overflow:hidden;margin-top:14px}
.bar i{display:block;height:100%;width:0;background:var(--acc);transition:width .25s}
.audio{display:grid;grid-template-columns:210px 1fr 168px;gap:10px;align-items:center;
 border:1px solid var(--line);border-radius:9px;padding:8px 12px;margin-bottom:6px;background:#fff}
.audio.ref{background:#fafafa}
.audio .nm{font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.audio .nm i{display:block;font-weight:400;font-style:normal;color:var(--dim);font-size:11.5px}
.audio audio{width:100%;height:34px}
.mt{display:flex;gap:4px;justify-content:flex-end;flex-wrap:wrap}
.k{font-variant-numeric:tabular-nums;font-size:11px;padding:2px 7px;border-radius:5px;background:#f3f4f6;color:#374151;white-space:nowrap}
.k.p{background:#dcfce7;color:#166534}.k.n{background:#fee2e2;color:#991b1b}.k.z{background:#f3f4f6;color:#6b7280}
.k.s{background:#e0e7ff;color:#3730a3}.k.run{background:#fef3c7;color:#92400e}
.hint{background:#fffbeb;border-left:3px solid #f59e0b;padding:9px 11px;border-radius:0 6px 6px 0;font-size:12.5px;margin-top:10px}
code{background:#f3f4f6;padding:1px 5px;border-radius:4px;font-size:12px}
.hidden{display:none}
</style>
</head>
<body>
<div class="wrap">
  <h1>降噪实时试听</h1>
  <div class="sub">上传你自己的含噪信号 → 当场运行 5 个降噪模型 → 立即试听。
    指标口径 16 kHz，播放 44.1 kHz（与离线评测完全同一契约）。
    <br>分离模型聆听 + 实时试听：<a href="/sep">MUSDB18-HQ test · 逐模型聆听对比</a>
    · 离线降噪 A/B 对比：<a href="/ab">10 条 Valentini + 6 条瞬态噪声</a></div>

  <div class="panel" id="p1">
    <h2>1 · 选择输入</h2>
    <div class="drop" id="drop">
      <b>拖入音频文件，或点这里选择</b>
      <span>支持 wav / flac / mp3 等（≤ 64 MB，超过 60 s 会被截断）</span>
      <input type="file" id="fNoisy" accept="audio/*">
    </div>
    <div class="row">
      <label class="f">可选：干净参考 clean（给了才能算 ΔSI-SDR / ΔPESQ / ΔSTOI）</label>
      <button class="btn" id="bClean">选择 clean 文件</button>
      <span class="f" id="cleanName">未选择</span>
      <input type="file" id="fClean" accept="audio/*">
    </div>
    <div class="row">
      <label class="f">或直接用内置样本：</label>
      <span id="samples"></span>
    </div>
    <div class="msg" id="msg1"></div>
  </div>

  <div class="panel">
    <h2>2 · 选择模型</h2>
    <div class="row" id="models"></div>
    <div class="bar"><i id="prog"></i></div>
    <div class="msg" id="msg2"></div>
  </div>

  <div class="panel hidden" id="p3">
    <h2>3 · 试听与指标</h2>
    <div id="out"></div>
  </div>

  <div class="hint">
    <b>denoiser 是 16 kHz 原生模型</b>：8 kHz 以上没有内容，听感偏「闷」是带宽上限，不是降噪把高频削坏了。
    <br>没有勾选 clean 时不会伪造 Δ 指标 —— 只给电平与能量，避免「看起来有改善」的假象。
  </div>
</div>

<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let SID=null, CLEAN=null, NOISY=null, RUNNING=false;

function toast(el,msg,cls){ el.textContent=msg||""; el.className="msg"+(cls?" "+cls:""); }
function b64(file){ return new Promise((res,rej)=>{ const r=new FileReader();
  r.onload=()=>res(String(r.result).split(",")[1]||""); r.onerror=rej; r.readAsDataURL(file); }); }
function fmtK(v,u){ if(v===null||v===undefined) return '<span class="k z">n/a</span>';
  const cls=v>0?"k p":(v<0?"k n":"k z");
  return '<span class="'+cls+'">'+(v>=0?"+":"")+(Math.abs(v)>=1?v.toFixed(2):v.toFixed(3))+" "+u+'</span>'; }

async function boot(){
  const r = await fetch("/api/health"); const h = await r.json();
  const m = await (await fetch("/api/models")).json();
  $("#models").innerHTML = m.order.map((k,i)=>{
    const x=m.models.find(y=>y.key===k);
    return '<label class="pill on"><input type="checkbox" value="'+k+'" checked>'+x.label+'</label>';
  }).join("");
  $$("#models input").forEach(cb=>cb.addEventListener("change",()=>{
    cb.closest(".pill").classList.toggle("on", cb.checked); }));
  $("#samples").innerHTML = m.samples.map(id=>
    '<button class="btn" data-sample="'+id+'" style="margin-right:6px">'+id+'</button>').join("");
  toast($("#msg1"), "服务就绪 · 设备 "+(h.device||"?").toUpperCase()+
    (h.gpu? " ("+h.gpu+")":"") + " · 已载模型 "+(h.loaded.length||0)+"/5", "ok");
}
boot();

$("#drop").onclick = ()=> $("#fNoisy").click();
$("#fNoisy").onchange = e => { if(e.target.files[0]) loadFile(e.target.files[0]); };
$("#bClean").onclick = ()=> $("#fClean").click();
$("#fClean").onchange = e => { if(e.target.files[0]){ CLEAN=e.target.files[0];
  $("#cleanName").textContent = CLEAN.name; toast($("#msg1"),"已选 clean："+CLEAN.name,"ok"); } };
["dragenter","dragover"].forEach(ev=>$("#drop").addEventListener(ev,e=>{
  e.preventDefault(); $("#drop").classList.add("over"); }));
["dragleave","drop"].forEach(ev=>$("#drop").addEventListener(ev,e=>{
  e.preventDefault(); $("#drop").classList.remove("over"); }));
$("#drop").addEventListener("drop", e=>{ const f=e.dataTransfer.files[0]; if(f) loadFile(f); });

document.addEventListener("click", async e=>{
  const b = e.target.closest("[data-sample]");
  if(!b) return;
  toast($("#msg1"), "载入内置样本 "+b.dataset.sample+" …");
  const r = await fetch("/api/sample?id="+encodeURIComponent(b.dataset.sample));
  const j = await r.json();
  if(j.error) return toast($("#msg1"), j.error, "err");
  SID=j.sid; NOISY=j.noisy_src; CLEAN=null;
  $("#cleanName").textContent = j.clean_src? "（样本自带 clean）":"未选择";
  $("#p3").classList.remove("hidden");
  renderRefs(j);
  toast($("#msg1"), "已载入 "+j.name+"，时长 "+j.dur_s+" s", "ok");
});

async function loadFile(f){
  NOISY=null; SID=null;
  toast($("#msg1"), "正在上传并解码 "+f.name+" …");
  try{
    const nz = await b64(f);
    const body = {name:f.name, noisy_b64:nz};
    if(CLEAN) body.clean_b64 = await b64(CLEAN);
    const r = await fetch("/api/session",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(body)});
    const j = await r.json();
    if(j.error) throw new Error(j.error);
    SID=j.sid; NOISY=j.noisy_src;
    $("#p3").classList.remove("hidden");
    renderRefs(j);
    toast($("#msg1"), "已就绪："+j.name+" · "+j.dur_s+" s"
      + (j.clean_src? " · 含 clean 参考":" · 无 clean（不算 Δ 指标）"), "ok");
    document.getElementById("out").scrollIntoView({behavior:"smooth"});
  }catch(err){ toast($("#msg1"), "失败："+err.message, "err"); }
}

let RUNNING_SEQ = 0;
function renderRefs(j){
  RUNNING_SEQ++;
  const c = j.clean_src ? '<div class="audio ref"><div class="nm">参考 clean（真值）<i>仅用于算指标</i></div>'
      +'<audio controls preload="metadata" src="'+j.clean_src+'"></audio><div class="mt"></div></div>' : "";
  $("#out").innerHTML =
    '<div class="audio ref"><div class="nm">输入 noisy<i>模型看到的就是它</i></div>'
   +'<audio controls preload="metadata" src="'+j.noisy_src+'"></audio><div class="mt"></div></div>'
   + c
   +'<div class="row"><button class="btn pri" id="run">▶ 运行选中模型</button>'
   +'<span class="msg" id="msgRun"></span></div><div id="res"></div>';
  $("#run").onclick = run;
}

async function run(){
  if(!SID) return toast($("#msg1"),"请先上传文件或载入样本","err");
  if(RUNNING) return;
  const keys = $$("#models input:checked").map(c=>c.value);
  if(!keys.length) return toast($("#msg2"),"至少选一个模型","err");
  RUNNING=true; const seq=RUNNING_SEQ;
  $("#run").disabled=true;
  $("#res").innerHTML="";
  let done=0;
  for(const k of keys){
    if(seq!==RUNNING_SEQ) return;
    const label = $$("#models input").find(c=>c.value===k).closest("label").textContent.trim();
    $("#res").insertAdjacentHTML("beforeend",
      '<div class="audio" data-k="'+k+'"><div class="nm">'+label+'<i>运行中…</i></div>'
      +'<div class="k run">推理中…</div><div class="mt"></div></div>');
    const t0=performance.now();
    try{
      const r = await fetch("/api/run",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({sid:SID, model:k})});
      const j = await r.json();
      if(seq!==RUNNING_SEQ) return;
      if(j.error) throw new Error(j.error);
      const mt=j.metrics;
      let chips = "";
      if(mt.has_clean){
        chips = fmtK(mt.si_sdr_improve,"dB") + fmtK(mt.pesq_improve,"PESQ") + fmtK(mt.stoi_improve,"STOI");
      } else {
        chips = '<span class="k s" title="输出/输入 RMS 比">L '+mt.level_ratio_vs_in.toFixed(3)+'</span>';
      }
      chips += '<span class="k z" title="推理耗时">'+j.infer_s.toFixed(2)+' s</span>';
      if(j.params) chips += '<span class="k z">'+(j.params/1e6).toFixed(1)+' M</span>';
      const el = $('#res [data-k="'+k+'"]');
      el.className="audio";
      el.innerHTML = '<div class="nm">'+j.label+'<i>'+(j.out_sr/1000)+' kHz · 原生 '
        +(j.native_sr/1000)+' kHz · '+(j.n_stems||1)+' stem</i></div>'
        + '<audio controls preload="metadata" src="'+j.src+'"></audio>'
        + '<div class="mt">'+chips+'</div>';
    }catch(err){
      const el = $('#res [data-k="'+k+'"]');
      if(el) el.innerHTML = '<div class="nm">'+label+'</div><div class="msg err">失败：'+err.message+'</div><div></div>';
    }
    done++; $("#prog").style.width = Math.round(done/keys.length*100)+"%";
    toast($("#msgRun"), "已完成 "+done+"/"+keys.length, done===keys.length?"ok":"");
  }
  $("#run").disabled=false; RUNNING=false;
  toast($("#msgRun"), "全部完成（"+keys.length+" 个模型）", "ok");
}
</script>
</body>
</html>
"""


# --------------------------------------------------------------------- main ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--preload", action="store_true", help="载入全部模型后再开始服务")
    a = ap.parse_args()

    LIVE_AUDIO.mkdir(parents=True, exist_ok=True)
    SEP_AUDIO.mkdir(parents=True, exist_ok=True)

    if a.preload:
        for k in MODEL_KEYS:
            t0 = time.time()
            _run, ls, info = get_model(k)
            print("  preloaded %-28s %.2f M  (%.1fs)"
                  % (k, info.get("params", 0) / 1e6, time.time() - t0))

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    base = "http://%s:%d" % (a.host, a.port)
    print("=" * 68)
    print("  Live denoise + separation playground")
    print("    denoise (upload + run) : %s/" % base)
    print("    separation listening   : %s/sep" % base)
    print("    offline denoise A/B    : %s/ab" % base)
    print("    health                 : %s/api/health" % base)
    print("  separation budget: %.1f s per model (overruns are killed and skipped)"
          % SEP_BUDGET_S)
    print("  Ctrl+C to stop.")
    print("=" * 68)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        sep_reset()
    return 0


if __name__ == "__main__":
    sys.exit(main())

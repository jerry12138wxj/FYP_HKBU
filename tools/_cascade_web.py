# -*- coding: utf-8 -*-
"""FYP 级联实时演示 Web 服务（分离 → 人声降噪）。

设计目标（用户原话）：**不要求速度，只要求稳定** ——
  1. 稳定运行模型：单模型单子进程，跑完即退，8 GiB 上永不 OOM；
  2. 稳定输出：worker 崩溃 → 服务不崩，job 置 error，可重跑；
  3. 稳定打开：刷新/并发上传/运行中再上传，全部由会话 + 全局串行锁兜住。

流水线：noisy → [分离模型] → vocals → [降噪/去混响模型] → 干净人声。

路由
----
  GET  /                    单页应用
  GET  /api/health          device / 运行中 job / 会话数
  GET  /api/models          模型目录（sep + den 两块）
  POST /api/upload          {name, b64} -> {sid}
  POST /api/run             {sid, sep, den} -> {sid}（后台跑）
  GET  /api/job/<sid>       轮询 job 状态与结果
  GET  /media/<sid>/<f>     音频（支持 Range 拖拽 seek）

用法
----
  python tools/_cascade_web.py --port 8123
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import os
import posixpath
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

ROOT = _paths.PROJECT_ROOT
LIVE_ROOT = _paths.OUTPUTS / "_cascade_live"
WORKER = _paths.TOOLS / "_cascade_worker.py"
PY = sys.executable

SR = 44100

# ------------------------------------------------------------------ 模型目录
CATALOGUE = {
    "sep": [
        {"key": "demucs", "label": "Demucs (htdemucs)", "note": "最快 · 4-stem · GPU RTF 0.03", "default": True},
        {"key": "bsrnn_simo", "label": "BSRNN-SIMO", "note": "精度第一 · 四轨 9.27 dB"},
        {"key": "bsrnn_all", "label": "BSRNN (oBSRNN 4-stem)", "note": "四轨 9.16 dB"},
        {"key": "mdx", "label": "MDX-Net (mdx_extra)", "note": "四轨 8.96 dB"},
        {"key": "mdx_q", "label": "MDX-Net (mdx_q 量化)", "note": "量化版 · 精度≈mdx"},
        {"key": "mdx_extra_q", "label": "MDX-Net (mdx_extra_q 量化)", "note": "量化版 · 精度≈mdx_extra"},
        {"key": "bsrnn_large_all", "label": "BSRNN-large (4-stem)", "note": "四轨 8.42 dB"},
        {"key": "bsroformer_l12", "label": "BS-RoFormer-L12 (vocals)", "note": "人声 9.69 dB · 单目标"},
        {"key": "umx", "label": "Open-Unmix", "note": "基线 6.65 dB"},
        {"key": "convtasnet", "label": "Conv-TasNet", "note": "四轨 5.93 dB"},
        {"key": "mmdenselstm", "label": "MMDenseLSTM", "note": "四轨 6.27 dB"},
    ],
    "den": [
        {"key": "denoiser_master64", "label": "denoiser master64", "note": "16 kHz · ΔPESQ +0.963", "default": True},
        {"key": "denoiser_dns64", "label": "denoiser dns64", "note": "16 kHz · ΔPESQ +0.601"},
        {"key": "denoiser_dns48", "label": "denoiser dns48", "note": "最小 18.9 M · 门禁改善最高"},
        {"key": "mel_roformer_denoise", "label": "Mel-RoFormer-Denoise", "note": "44.1 kHz 立体声"},
        {"key": "mel_roformer_denoise_aggr", "label": "Mel-RoFormer-Denoise (aggr)", "note": "44.1 kHz 立体声 · 激进降噪"},
        {"key": "mel_roformer_dereverb", "label": "Mel-RoFormer-Dereverb", "note": "去混响"},
        {"key": "mel_roformer_dereverb_echo", "label": "Mel-RoFormer-Dereverb-Echo", "note": "去混响 + 去回声"},
    ],
}
_LABEL = {}
for _b in ("sep", "den"):
    for _m in CATALOGUE[_b]:
        _LABEL[_m["key"]] = _m["label"]

# ------------------------------------------------------------------ 会话与任务
SESSIONS = {}          # sid -> {"dir", "input", "name", "meta"}
JOBS = {}              # sid -> {"status","phase","sep","den","error","result","t"}
_LOCKS = {}            # sid -> threading.Lock()（读改写状态用）
_RUN_SEM = threading.Semaphore(1)   # 全局串行：同一时刻只跑一个级联

_STATUSES = ("queued", "running", "done", "error")


def _lock_of(sid):
    if sid not in _LOCKS:
        _LOCKS[sid] = threading.Lock()
    return _LOCKS[sid]


def _set_job(sid, **kw):
    with _lock_of(sid):
        j = JOBS.setdefault(sid, {"status": "queued", "phase": "", "result": {}, "t": time.time()})
        j.update(kw)
        j["t"] = time.time()


# ------------------------------------------------------------------ worker 驱动
def _run_worker(board, model, input_path, out_dir, keep, max_seconds=600.0):
    """跑一个单发 worker，返回其 result 字典；异常向上抛（由 job 层接住）。"""
    cmd = [PY, "-X", "utf8", "-u", str(WORKER),
           "--board", board, "--model", model,
           "--input", str(input_path), "--out-dir", str(out_dir),
           "--max-seconds", str(max_seconds)]
    if keep:
        cmd += ["--keep"] + list(keep)

    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=max_seconds + 600)
    out = (proc.stdout or "").strip()
    last = None
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    if last is None:
        raise RuntimeError("worker 无协议输出 (rc=%s) stderr=%s" % (
            proc.returncode, (proc.stderr or "")[-500:]))
    if last.get("event") == "fatal" or last.get("event") == "error":
        raise RuntimeError("[%s] %s" % (last.get("model"), last.get("error")))
    if last.get("event") != "result":
        raise RuntimeError("worker 意外事件: %s" % last.get("event"))
    return last


def _analyze(sid):
    """级联完成后：原数据 / 分离数据 / 降噪数据三者的 spectrogram + SDR。

    SDR 口径（无 clean 参考，用户已确认）：**以原数据为参考**——
      SDR(sep|orig)  = 10·log10( Σorig² / Σ(sep−orig)² )
      SDR(den|orig)  = 10·log10( Σorig² / Σ(den−orig)² )
      SDR(den|sep)   = 10·log10( Σsep²  / Σ(den−sep)² )
    即「分离/降噪相对输入改变了多少」的相对量，非绝对质量分。

    产物：<session>/analysis.png（三行 spectrogram，共用原数据峰值做 0 dB 参考）。
    返回 {metrics, spectrogram} 或 {error}。失败不拖垮 job（由调用方兜底）。
    """
    sess = SESSIONS[sid]
    d = sess["dir"]
    inp = sess["input"]

    # 定位分离人声轨与降噪最终轨
    vocals = None
    for f in sorted((d / "sep").glob("*.wav")):
        if f.stem.lower() == "vocals":
            vocals = f
            break
    if vocals is None:
        sf_ = sorted((d / "sep").glob("*.wav"))
        vocals = sf_[0] if sf_ else None

    final = None
    for f in sorted((d / "den").glob("*.wav")):
        if f.stem.lower() in ("enhanced", "dry"):
            final = f
            break
    if final is None:
        df_ = sorted((d / "den").glob("*.wav"))
        final = df_[0] if df_ else None

    if vocals is None or final is None:
        return {"error": "缺分离/降噪产物，跳过分析"}

    import numpy as np
    import soundfile as sf

    def load_mono(p):
        x, sr = sf.read(str(p), dtype="float32", always_2d=True)
        if sr != SR:
            import torch
            import torchaudio.functional as AF
            t = torch.as_tensor(np.ascontiguousarray(x.T))
            x = AF.resample(t, sr, SR).numpy().T
        return x.mean(axis=1)

    a = load_mono(inp)
    b = load_mono(vocals)
    c = load_mono(final)
    m = min(len(a), len(b), len(c))
    if m == 0:
        return {"error": "空音频，跳过分析"}
    a, b, c = (a[:m].astype(np.float64), b[:m].astype(np.float64), c[:m].astype(np.float64))

    def sdr(ref, est):
        num = float(np.sum(ref ** 2))
        den = float(np.sum((est - ref) ** 2))
        return round(10.0 * np.log10(num / (den + 1e-12)), 3)

    metrics = {
        "sdr_sep_vs_orig": sdr(a, b),
        "sdr_den_vs_orig": sdr(a, c),
        "sdr_den_vs_sep": sdr(b, c),
    }

    import librosa
    import librosa.display
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    N_FFT, HOP = 1024, 256
    def spec(x):
        return np.abs(librosa.stft(x, n_fft=N_FFT, hop_length=HOP))
    Sa, Sb, Sc = spec(a), spec(b), spec(c)
    ref = float(Sa.max())
    def to_db(S):
        return librosa.amplitude_to_db(S, ref=ref)

    fig, axes = plt.subplots(3, 1, figsize=(9, 6), sharex=True)
    rows = (("orig", to_db(Sa)), ("sep (vocals)", to_db(Sb)), ("den (final)", to_db(Sc)))
    for ax, (label, S) in zip(axes, rows):
        librosa.display.specshow(S, sr=SR, hop_length=HOP, x_axis="time", y_axis="hz",
                                 ax=ax, vmin=-80, vmax=0, cmap="magma")
        ax.set_ylabel(label, fontsize=9)
    axes[2].set_xlabel("time (s)")
    fig.suptitle("SDR(sep|orig)=%s dB   SDR(den|orig)=%s dB   SDR(den|sep)=%s dB"
                 % (metrics["sdr_sep_vs_orig"], metrics["sdr_den_vs_orig"],
                    metrics["sdr_den_vs_sep"]), fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    png = d / "analysis.png"
    fig.savefig(png, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return {"metrics": metrics, "spectrogram": png.name}


def _cascade(sid, sep_key, den_key):
    """后台线程入口：分离 → vocals → 降噪。"""
    sess = SESSIONS[sid]
    d = sess["dir"]
    sep_dir = d / "sep"
    den_dir = d / "den"
    try:
        _set_job(sid, status="running", phase="sep-load", sep=sep_key, den=den_key)
        sep_res = _run_worker("sep", sep_key, sess["input"], sep_dir, keep=["vocals"])

        # 找到分离出的「人声」轨（4-stem 出 vocals；单目标模型也出 vocals）
        vocals = None
        for st in sep_res.get("stems", []):
            if st["target"] in ("vocals", "vocals.wav"):
                vocals = sep_dir / st["file"]
        if vocals is None:
            stems = sep_res.get("stems", [])
            if stems:
                vocals = sep_dir / stems[0]["file"]
        if vocals is None or not vocals.exists():
            raise RuntimeError("分离未产出 vocals 轨")

        _set_job(sid, status="running", phase="den-load", sep=sep_res.get("label"))
        den_res = _run_worker("den", den_key, vocals, den_dir, keep=None)

        # 最终产物：enhanced 或 dry
        final = None
        for st in den_res.get("stems", []):
            if st["target"] in ("enhanced", "dry"):
                final = den_dir / st["file"]
                break
        if final is None:
            stems = den_res.get("stems", [])
            if stems:
                final = den_dir / stems[0]["file"]
        if final is None or not final.exists():
            raise RuntimeError("降噪未产出最终轨")

        _set_job(sid, status="running", phase="analyze")
        try:
            analysis = _analyze(sid)
        except Exception as e:  # noqa: BLE001
            analysis = {"error": "%s: %s" % (type(e).__name__, e)}

        _set_job(sid, status="done", phase="done",
                 result={
                     "sep": {"model": sep_key, "label": sep_res.get("label"),
                             "load_s": sep_res.get("load_s"), "infer_s": sep_res.get("infer_s"),
                             "stems": sep_res.get("stems")},
                     "den": {"model": den_key, "label": den_res.get("label"),
                             "load_s": den_res.get("load_s"), "infer_s": den_res.get("infer_s"),
                             "stems": den_res.get("stems")},
                     "final": final.name,
                     "analysis": analysis,
                 })
    except Exception as e:  # noqa: BLE001
        _set_job(sid, status="error", phase="", error="%s: %s" % (type(e).__name__, e),
                 detail=traceback.format_exc()[-1500:])


def _start_cascade(sid, sep_key, den_key):
    t = threading.Thread(target=_cascade, args=(sid, sep_key, den_key), daemon=True)
    t.start()
    return t


# ------------------------------------------------------------------ HTTP
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")
EXTRA_TYPES = {".flac": "audio/flac", ".wav": "audio/wav", ".m4a": "audio/mp4",
               ".opus": "audio/ogg", ".ogg": "audio/ogg", ".mp3": "audio/mpeg"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "FYPcascade/1.0"

    def log_message(self, fmt, *args):
        code = args[1] if len(args) > 1 else ""
        if str(code).startswith(("2", "3")) and str(code) != "206":
            return
        sys.stderr.write("[srv] %s %s\n" % (self.address_string(), fmt % args))

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    # ---- JSON helpers ----
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self, limit=256 * 1024 * 1024):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("body too large (%d bytes)" % n)
        return self.rfile.read(n) if n else b""

    # ---- media serve (with Range) ----
    def _serve_file(self, path: Path):
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
            return
        size = path.stat().st_size
        ctype = EXTRA_TYPES.get(path.suffix.lower()) or \
            mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        if not rng:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(size))
            self.end_headers()
            shutil.copyfileobj(f, self.wfile)
            f.close()
            return
        m = RANGE_RE.match(rng.strip())
        if not m:
            f.close()
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            return
        start_s, end_s = m.group(1), m.group(2)
        if start_s == "":
            length = min(int(end_s or 0), size)
            start, end = size - length, size - 1
        else:
            start = int(start_s)
            end = min(int(end_s), size - 1) if end_s else size - 1
        if start >= size or start > end:
            f.close()
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", "bytes */%d" % size)
            self.end_headers()
            return
        f.seek(start)
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        left = end - start + 1
        while left > 0:
            chunk = f.read(min(262144, left))
            if not chunk:
                break
            self.wfile.write(chunk)
            left -= len(chunk)
        f.close()

    # ---- routes ----
    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        p = u.path
        try:
            if p in ("/", "/index.html"):
                return self._serve_index()
            if p == "/api/health":
                return self._json({
                    "ok": True,
                    "device": "cuda" if _cuda_available() else "cpu",
                    "jobs": {k: {"status": v["status"], "phase": v["phase"]}
                             for k, v in JOBS.items()},
                    "sessions": len(SESSIONS),
                    "models": {"sep": len(CATALOGUE["sep"]), "den": len(CATALOGUE["den"])},
                })
            if p == "/api/models":
                return self._json(CATALOGUE)
            m = re.match(r"^/api/job/([0-9a-f-]+)$", p)
            if m:
                sid = m.group(1)
                with _lock_of(sid):
                    j = JOBS.get(sid)
                if j is None:
                    return self._json({"status": "unknown", "sid": sid}, 404)
                return self._json(j)
            m = re.match(r"^/media/([0-9a-f-]+)/([^/]+)/([^/]+)$", p)
            if m:
                sid, sub, fname = m.group(1), m.group(2), m.group(3)
                if sub not in ("sep", "den") or ".." in fname or "/" in fname:
                    return self.send_error(HTTPStatus.NOT_FOUND, "bad path")
                d = _session_dir(sid)
                if d is None:
                    return self.send_error(HTTPStatus.NOT_FOUND, "session not found")
                return self._serve_file(d / sub / fname)
            m = re.match(r"^/media/([0-9a-f-]+)/([^/]+)$", p)
            if m:
                sid, fname = m.group(1), m.group(2)
                if ".." in fname or "/" in fname:
                    return self.send_error(HTTPStatus.NOT_FOUND, "bad path")
                d = _session_dir(sid)
                if d is None:
                    return self.send_error(HTTPStatus.NOT_FOUND, "session not found")
                return self._serve_file(d / fname)
            return self.send_error(HTTPStatus.NOT_FOUND, "route not found")
        except Exception as e:  # noqa: BLE001
            return self._json({"error": "%s: %s" % (type(e).__name__, e)}, 500)

    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        try:
            if u.path == "/api/upload":
                raw = self._read_body()
                try:
                    obj = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return self._json({"error": "bad json body"}, 400)
                return self._handle_upload(obj)
            if u.path == "/api/run":
                raw = self._read_body()
                try:
                    obj = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return self._json({"error": "bad json body"}, 400)
                return self._handle_run(obj)
            return self.send_error(HTTPStatus.NOT_FOUND, "route not found")
        except Exception as e:  # noqa: BLE001
            return self._json({"error": "%s: %s" % (type(e).__name__, e)}, 500)

    # ---- handlers ----
    def _handle_upload(self, obj):
        b64 = obj.get("b64") or ""
        name = str(obj.get("name") or "upload.wav")
        name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        if not name.lower().endswith((".wav", ".flac", ".mp3", ".m4a", ".ogg")):
            name += ".wav"
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            return self._json({"error": "bad base64"}, 400)
        if not raw:
            return self._json({"error": "empty audio"}, 400)

        sid = uuid.uuid4().hex
        d = LIVE_ROOT / sid
        (d / "sep").mkdir(parents=True, exist_ok=True)
        (d / "den").mkdir(parents=True, exist_ok=True)
        inp = d / ("input_" + name)
        inp.write_bytes(raw)

        SESSIONS[sid] = {"dir": d, "input": inp, "name": name,
                         "bytes": len(raw), "t": time.time()}
        return self._json({"sid": sid, "name": name, "bytes": len(raw)})

    def _handle_run(self, obj):
        sid = obj.get("sid")
        sep_key = obj.get("sep")
        den_key = obj.get("den")
        if sid not in SESSIONS:
            return self._json({"error": "unknown sid"}, 404)
        if sep_key not in _LABEL or _board_of(sep_key) != "sep":
            return self._json({"error": "unknown sep model: %s" % sep_key}, 400)
        if den_key not in _LABEL or _board_of(den_key) != "den":
            return self._json({"error": "unknown den model: %s" % den_key}, 400)

        with _lock_of(sid):
            cur = JOBS.get(sid, {}).get("status")
        if cur == "running":
            return self._json({"error": "job already running", "sid": sid}, 409)
        if cur == "queued":
            return self._json({"sid": sid, "status": "queued"})

        # 拿到全局串行许可再启动（后台线程内部再 acquire，避免阻塞 HTTP 线程）
        _set_job(sid, status="queued", phase="", sep=sep_key, den=den_key)
        _start_cascade(sid, sep_key, den_key)
        return self._json({"sid": sid, "status": "queued"})

    # ---- index ----
    def _serve_index(self):
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _board_of(key):
    for b in ("sep", "den"):
        for m in CATALOGUE[b]:
            if m["key"] == key:
                return b
    return None


def _session_dir(sid):
    s = SESSIONS.get(sid)
    return s["dir"] if s else None


def _cuda_available():
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------ 前端
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FYP 级联演示 · 分离 → 人声降噪</title>
<style>
:root{--ink:#111827;--mut:#6b7280;--line:#e5e7eb;--bg:#f7f8fa;--card:#fff;
--blue:#1d4ed8;--grn:#15803d;--red:#dc2626;--amb:#b45309}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Microsoft YaHei","Segoe UI",system-ui,sans-serif;line-height:1.6}
.wrap{max-width:980px;margin:0 auto;padding:24px 20px 80px}
h1{font-size:24px;margin:0 0 4px}
h2{font-size:16px;margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.sub{color:var(--mut);font-size:13px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px;margin-bottom:16px;box-shadow:0 1px 2px rgba(17,24,39,.04)}
.row{display:flex;gap:14px;flex-wrap:wrap}
.row>div{flex:1;min-width:260px}
label{display:block;font-size:13px;font-weight:600;color:var(--mut);margin-bottom:6px}
select{width:100%;padding:9px 10px;border:1px solid var(--line);border-radius:8px;
font-size:14px;background:#fff}
.note{font-size:12px;color:var(--mut);margin-top:4px}
#drop{border:2px dashed var(--line);border-radius:12px;padding:30px;text-align:center;
color:var(--mut);cursor:pointer;transition:.15s}
#drop.over{border-color:var(--blue);background:#eff6ff}
#drop.done{border-style:solid;border-color:var(--grn)}
#fname{font-size:14px;color:var(--ink);margin-top:8px;font-weight:600}
.btn{display:inline-block;padding:11px 22px;border:none;border-radius:8px;font-size:15px;
font-weight:600;cursor:pointer;background:var(--blue);color:#fff}
.btn:disabled{background:#cbd5e1;cursor:not-allowed}
.btn.sec{background:#fff;color:var(--blue);border:1px solid var(--blue)}
#status{margin-top:14px;font-size:14px}
#status .badge{display:inline-block;padding:3px 12px;border-radius:999px;font-size:12px;
font-weight:700;color:#fff}
.badge.queued{background:#6b7280}.badge.running{background:var(--amb)}
.badge.done{background:var(--grn)}.badge.error{background:var(--red)}
.spin{display:inline-block;width:14px;height:14px;border:2px solid #d1d5db;
border-top-color:var(--blue);border-radius:50%;animation:sp .7s linear infinite;
vertical-align:-2px;margin-right:8px}
@keyframes sp{to{transform:rotate(360deg)}}
.audio{width:100%;margin-top:6px}
.stem{display:flex;align-items:center;gap:12px;padding:8px 0;border-top:1px solid var(--line)}
.stem .name{font-weight:600;min-width:120px}
.stem a{color:var(--blue);text-decoration:none;font-size:13px}
.stem .meta{color:var(--mut);font-size:12px;margin-left:auto}
.hidden{display:none}
.err{color:var(--red);font-size:13px;white-space:pre-wrap}
code{background:#f1f5f9;padding:2px 6px;border-radius:5px;font-size:12px}
</style>
</head>
<body>
<div class="wrap">
  <h1>音乐人声分离 → 降噪（级联演示）</h1>
  <div class="sub">上传带噪音频 → 先分离人声 → 再去噪声/去混响 → 在线试听与下载。</div>

  <div class="card">
    <h2>① 选择模型</h2>
    <div class="row">
      <div>
        <label>分离模型（Separation）</label>
        <select id="sep"></select>
        <div class="note" id="sepNote"></div>
      </div>
      <div>
        <label>降噪模型（Denoise / Dereverb）</label>
        <select id="den"></select>
        <div class="note" id="denNote"></div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>② 上传带噪音频</h2>
    <div id="drop">点击或拖拽到这里上传（WAV / FLAC / MP3）</div>
    <input type="file" id="file" accept="audio/*" class="hidden">
    <div id="fname" class="hidden"></div>
  </div>

  <div class="card">
    <h2>③ 运行</h2>
    <button class="btn" id="run" disabled>开始处理</button>
    <button class="btn sec hidden" id="dlfinal">下载最终结果</button>
    <div id="status"></div>
  </div>

  <div class="card hidden" id="results">
    <h2>④ 结果</h2>
    <div id="finalBox"></div>
    <div id="stems"></div>
  </div>
</div>

<script>
const $=s=>document.querySelector(s);
let MODELS={sep:[],den:[]}, current={sid:null,name:null,file:null,sep:null,den:null};
let pollTimer=null;

function b64(file){
  return new Promise((res,rej)=>{
    const r=new FileReader();
    r.onload=()=>res(r.result.split(',')[1]);
    r.onerror=rej;r.readAsDataURL(file);
  });
}
function fmt(s){
  if(s==null)return '—';
  if(s>=60)return (s/60).toFixed(1)+' min';
  return s.toFixed(2)+' s';
}
function badge(st){
  const t={queued:'排队中',running:'运行中',done:'完成',error:'失败',unknown:'未知'}[st]||st;
  return '<span class="badge '+st+'">'+t+'</span>';
}

async function loadModels(){
  const r=await fetch('/api/models');const m=await r.json();
  MODELS=m;
  const fill=(sel,list,defKey)=>{
    const e=$(sel);e.innerHTML='';
    list.forEach(x=>{const o=document.createElement('option');o.value=x.key;
      o.textContent=x.label;if(x.default)o.selected=true;e.appendChild(o);});
    e.onchange=()=>{const x=list.find(v=>v.key===e.value);
      $(sel==='#sep'?'#sepNote':'#denNote').textContent=x?x.note:'';};
    e.dispatchEvent(new Event('change'));
  };
  fill('#sep',m.sep,'demucs');fill('#den',m.den,'denoiser_master64');
}

async function health(){
  try{const r=await fetch('/api/health');const h=await r.json();
    const tag=$('#run');
    if(h.device==='cuda'){} // no-op
  }catch(e){}
}

// ---- upload ----
const drop=$('#drop'),fileInput=$('#file');
drop.onclick=()=>fileInput.click();
drop.ondragover=e=>{e.preventDefault();drop.classList.add('over');};
drop.ondragleave=()=>drop.classList.remove('over');
drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');
  if(e.dataTransfer.files.length)pick(e.dataTransfer.files[0]);};
fileInput.onchange=()=>{if(fileInput.files.length)pick(fileInput.files[0]);};

async function pick(f){
  current.file=f;current.name=f.name;
  drop.classList.add('done');drop.textContent='已选择：'+f.name+' ('+(f.size/1048576).toFixed(2)+' MB)';
  $('#fname').classList.remove('hidden');
  $('#fname').textContent='待上传 · 点击「开始处理」上传并运行';
  $('#run').disabled=false;
}

// ---- run ----
$('#run').onclick=async()=>{
  if(!current.file)return;
  const btn=$('#run');btn.disabled=true;btn.textContent='上传中…';
  setStatus('queued','上传音频…');
  try{
    const data=await b64(current.file);
    const up=await fetch('/api/upload',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:current.name,b64:data})});
    const us=await up.json();
    if(us.error){throw new Error(us.error);}
    current.sid=us.sid;sessionStorage.setItem('fyp_cascade_sid',us.sid);
    setStatus('queued','排队中（上传完成）…');
    const run=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({sid:us.sid,sep:$('#sep').value,den:$('#den').value})});
    const rs=await run.json();
    if(rs.error){throw new Error(rs.error);}
    poll(us.sid);
  }catch(e){
    setStatus('error','上传/提交失败：'+e.message);
    btn.disabled=false;btn.textContent='开始处理';
  }
};

function setStatus(st,txt){
  $('#status').innerHTML=badge(st)+' '+(txt||'');
}

function poll(sid){
  clearInterval(pollTimer);
  pollTimer=setInterval(async()=>{
    try{
      const r=await fetch('/api/job/'+sid);const j=await r.json();
      if(j.status==='running'){
        setStatus('running',(j.phase==='sep-load'?'分离模型加载/推理中…':
          j.phase==='den-load'?'降噪模型加载/推理中…':'运行中…'));
        $('#run').disabled=true;
      }else if(j.status==='done'){
        clearInterval(pollTimer);
        setStatus('done','完成！总耗时见下方。');
        $('#run').disabled=false;$('#run').textContent='再处理一次';
        render(j.result);
      }else if(j.status==='error'){
        clearInterval(pollTimer);
        setStatus('error','处理失败：'+j.error);
        $('#status').insertAdjacentHTML('beforeend','<div class="err">'+(j.detail||'')+'</div>');
        $('#run').disabled=false;$('#run').textContent='重试';
      }
    }catch(e){/* 服务暂不可达，继续轮询 */}
  },1200);
}

function stemBlock(sid,dir,st,title){
  const url='/media/'+sid+'/'+dir+'/'+st.file;
  return '<div class="stem"><span class="name">'+title+'</span>'+
    '<audio class="audio" controls preload="none" src="'+url+'"></audio>'+
    '<a href="'+url+'" download>下载</a>'+
    '<span class="meta">'+st.dur_s+' s · '+st.mb+' MB</span></div>';
}

function render(res){
  $('#results').classList.remove('hidden');
  const sid=current.sid;
  const fin=res.final;
  $('#finalBox').innerHTML='<h2>最终结果（'+fin+'）</h2>'+
    '<div class="stem"><span class="name">最终人声</span>'+
    '<audio class="audio" controls preload="metadata" src="/media/'+sid+'/den/'+fin+'"></audio>'+
    '<a href="/media/'+sid+'/den/'+fin+'" download>下载</a></div>';
  const dl=$('#dlfinal');dl.classList.remove('hidden');
  dl.onclick=()=>{window.location.href='/media/'+sid+'/den/'+fin;};

  let html='<h2>中间产物</h2>';
  (res.sep.stems||[]).forEach(st=>{html+=stemBlock(sid,'sep',st,'分离·'+st.target);});
  (res.den.stems||[]).forEach(st=>{html+=stemBlock(sid,'den',st,'降噪·'+st.target);});
  if(res.analysis && res.analysis.spectrogram){
    const m=res.analysis.metrics||{};
    html+='<h2 style="margin-top:16px">分析：spectrogram + SDR（以原数据为参考）</h2>';
    html+='<img class="spec" src="/media/'+sid+'/analysis.png" alt="spectrogram" '+
      'style="width:100%;border-radius:8px;margin:6px 0;background:#111">';
    html+='<div class="sub">SDR(分离|原)='+m.sdr_sep_vs_orig+' dB · SDR(降噪|原)='+
      m.sdr_den_vs_orig+' dB · SDR(降噪|分离)='+m.sdr_den_vs_sep+' dB</div>';
  } else if(res.analysis && res.analysis.error){
    html+='<div class="sub" style="margin-top:12px">分析跳过：'+res.analysis.error+'</div>';
  }
  html+='<div class="sub" style="margin-top:12px">分离 '+res.sep.label+'（加载 '+
    fmt(res.sep.load_s)+'，推理 '+fmt(res.sep.infer_s)+'）→ 降噪 '+res.den.label+
    '（加载 '+fmt(res.den.load_s)+'，推理 '+fmt(res.den.infer_s)+'）</div>';
  $('#stems').innerHTML=html;
}

// 恢复：刷新后若有 sid，重新拉取状态
(function restore(){
  const sid=sessionStorage.getItem('fyp_cascade_sid');
  if(sid){current.sid=sid;poll(sid);
    $('#run').disabled=false;$('#run').textContent='恢复中…';
    fetch('/api/job/'+sid).then(r=>r.json()).then(j=>{
      if(j.status==='done'){render(j.result);$('#run').textContent='再处理一次';}
      else if(j.status==='error'){setStatus('error',j.error);$('#run').textContent='重试';}
      else{setStatus(j.status);}
    }).catch(()=>{sessionStorage.removeItem('fyp_cascade_sid');});
  }
})();

loadModels();health();
</script>
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)

    LIVE_ROOT.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    base = "http://%s:%d" % (a.host, a.port)
    print("FYP cascade demo")
    print("  page   : %s/" % base)
    print("  models : sep=%d  den=%d" % (len(CATALOGUE["sep"]), len(CATALOGUE["den"])))
    print("  python : %s" % PY)
    print("  out    : %s" % LIVE_ROOT)
    print("  stop   : Ctrl-C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()

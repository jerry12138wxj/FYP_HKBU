# -*- coding: utf-8 -*-
"""Drive tools/_sep_worker.py for one or more models -- protocol-level test.

    python tools/_test_sep_worker.py demucs bsrnn mdx
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as _paths  # noqa: E402

_paths.setup_env()

ROOT = _paths.PROJECT_ROOT
PY = sys.executable
INP = ROOT / "03_outputs" / "_sep_live" / "_selftest" / "input.wav"
OUT = ROOT / "03_outputs" / "_sep_live" / "_selftest" / "out"


class Lines(threading.Thread):
    def __init__(self, stream):
        super().__init__(daemon=True)
        self.stream, self.q = stream, queue.Queue()
        self.start()

    def run(self):
        try:
            for line in self.stream:
                self.q.put(line)
        except Exception:
            pass
        finally:
            self.q.put(None)

    def get(self, timeout):
        return self.q.get(timeout=timeout)


def get_json(reader, timeout):
    """Read lines until one parses as JSON (loader chatter must never break this)."""
    deadline = time.time() + timeout
    while True:
        left = deadline - time.time()
        if left <= 0:
            raise queue.Empty
        line = reader.get(timeout=left)
        if line is None:
            return None
        line = line.strip()
        if not line or not line.startswith("{"):
            print("    (ignored non-protocol line: %s)" % line[:100])
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            print("    (ignored non-JSON line: %s)" % line[:100])


def main(argv):
    keys = argv or ["demucs"]
    OUT.mkdir(parents=True, exist_ok=True)
    for key in keys:
        print("\n[%s]" % key)
        t0 = time.time()
        p = subprocess.Popen(
            [PY, "-X", "utf8", str(ROOT / "tools" / "_sep_worker.py"), "--model", key],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, cwd=str(ROOT),
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
        out, err = Lines(p.stdout), Lines(p.stderr)
        try:
            ready = get_json(out, 600)
        except queue.Empty:
            ready = None
        if ready is None:
            print("  worker died during load; stderr tail:")
            try:
                print("   ", err.q.get_nowait()[:600])
            except Exception:
                pass
            p.kill()
            continue
        print("  ready %s  load %.2fs  params %s  targets %s  native %s"
              % (ready["event"], ready["load_s"],
                 (ready.get("params") or 0) / 1e6, ready.get("targets"), ready.get("native_sr")))
        if ready["event"] != "ready":
            print("  LOAD FAILED:", ready)
            p.kill()
            continue

        d = OUT / key
        p.stdin.write(json.dumps({"job_id": "j1", "input": str(INP),
                                  "out_dir": str(d), "max_seconds": 30,
                                  "chunk_s": 10, "overlap_s": 1}) + "\n")
        p.stdin.flush()
        t1 = time.time()
        try:
            res = get_json(out, 120)
        except queue.Empty:
            print("  TIMEOUT waiting for result")
            p.kill()
            continue
        dt = time.time() - t1
        if res is None or res.get("event") != "result":
            print("  ERROR:", json.dumps(res, ensure_ascii=False)[:600])
        else:
            print("  result  wall %.2fs  infer %.2fs  chunked=%s n=%s  in %.2fs"
                  % (dt, res["infer_s"], res["chunked"], res["n_chunks"], res["in_s"]))
            for s in res["stems"]:
                print("      %-12s %-18s %8.3f MB  %.2fs  rms %.4f"
                      % (s["target"], s["file"], s["mb"], s["dur_s"], s["rms"]))
        p.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
        p.stdin.flush()
        try:
            p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            p.kill()
        print("  total %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

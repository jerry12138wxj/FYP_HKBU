#!/usr/bin/env python
"""Bring up the local listening app: reuse or start the server, then open the two
pages -- and never vanish silently.

Why this is Python and not batch
--------------------------------
The previous start_listen.bat had a wait loop shaped like this::

    if errorlevel 1 (
        ...
        set /a TRIES=0
        :wait
        timeout /t 2 /nobreak >nul
        netstat ... >nul 2>&1
        if errorlevel 1 (
            set /a TRIES+=1
            if %TRIES% LSS 30 goto wait      <-- the bug
        )
    ) else ( ... )

cmd performs variable expansion for a whole parenthesised block while *parsing*
it -- before the `set /a TRIES=0` on the line above has executed.  %TRIES% is
therefore still undefined, the line collapses to `if  LSS 30 goto wait`, cmd hits
a syntax error, and it abandons the entire batch file: nothing is printed, no
page is opened, and the console window closes instantly.  That is the reported
"double-click and it flashes away".  Reproduced verbatim:

    returncode = 255, stdout = 0 bytes, stderr = "此时不应有 30。"

Batch control flow is also untestable in this environment (cmd.exe is blocked),
so the launcher logic lives here where it can actually be exercised.

Design notes
------------
* Readiness is decided by polling ``/api/health`` over HTTP, not by ``netstat``.
  "The port is listening" does not mean "the app answers"; opening a browser
  against a half-started server is what produces blank pages.
* Pages are opened only after the server answers, so the browser never races it.
* By default the server runs **in this same console** and this process stays
  alive supervising it, so the window cannot close out from under a live server
  and there is no detached process to lose track of.  ``--server-console new``
  restores the older "separate window" behaviour if that is ever wanted, and
  ``none`` is for headless tests.
* Every failure prints an actionable next step and returns 1; the .bat keeps the
  window open, so the error is readable.

Exit codes: 0 = ready (pages opened), 1 = failed.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# The two pages this app is allowed to open, in display order.
PAGES = (
    ("/", "denoise live (upload + run)"),
    ("/sep", "separation listening"),
)

CREATE_NEW_CONSOLE = 0x00000010
CREATE_NO_WINDOW = 0x08000000

# Keep handles of redirected server logs alive for the process lifetime.
_KEEP = []


def _say(msg):
    """Console-safe print: never raise on an unencodable character."""
    try:
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()
    except Exception:                                              # noqa: BLE001
        pass


def port_open(port, timeout=0.6):
    """True if something accepts a TCP connection on 127.0.0.1:port."""
    try:
        with socket.socket() as s:
            s.settimeout(timeout)
            return s.connect_ex(("127.0.0.1", int(port))) == 0
    except Exception:                                              # noqa: BLE001
        return False


# A proxy must never sit between us and 127.0.0.1: a stale HTTP_PROXY in the
# environment turns "the server is down" into a 502 from the proxy, and worse,
# could make a readiness check report on the wrong thing entirely.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_status(url, timeout=3.0):
    """HTTP status code, or None if the request could not complete.

    No Range header: the server answers Range requests with 206, which would
    make a perfectly healthy page look like a failure.  The body is never read,
    so this stays cheap even for the large self-contained pages.
    """
    try:
        with _OPENER.open(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:                                              # noqa: BLE001
        return None


def healthy(port, timeout=3.0):
    return http_status("http://127.0.0.1:%d/api/health" % port, timeout) == 200


def spawn_server(python_exe, server_py, root, port, mode, log_path):
    """Start the server.

    mode="attach" -> runs in THIS console; we stay alive supervising it.  This
                     is the default because it removes a whole failure mode:
                     there is no detached process to be reaped, no second window
                     to lose track of, and the console cannot close while the
                     server still matters.
    mode="new"    -> its own console window, independent of us.
    mode="none"   -> hidden, stdout+stderr appended to log_path (headless tests).
    """
    argv = [str(python_exe), str(server_py), "--port", str(port), "--preload"]
    kwargs = {"cwd": str(root)}
    if mode == "none":
        fh = open(str(log_path), "wb")
        _KEEP.append(fh)
        kwargs["stdout"] = fh
        kwargs["stderr"] = subprocess.STDOUT
        kwargs["creationflags"] = CREATE_NO_WINDOW
    elif mode == "new":
        kwargs["creationflags"] = CREATE_NEW_CONSOLE
    # "attach": no creation flags -- the child inherits our console.
    return subprocess.Popen(argv, **kwargs)


def _manual_hint(python_exe, server_py, port):
    _say("")
    _say("  自己跑一遍看报错：")
    _say('    "%s" "%s" --port %d --preload' % (python_exe, server_py, port))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Launch the local listening app.")
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--root", default=None,
                    help="project root (default: the parent of tools/)")
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter used to start the server")
    ap.add_argument("--server-console", choices=("attach", "new", "none"),
                    default="attach",
                    help="attach = run the server in this window and supervise "
                         "it (default); new = give it its own window; "
                         "none = hidden, for headless tests")
    ap.add_argument("--wait", type=float, default=120.0,
                    help="seconds to wait for the server to become healthy")
    ap.add_argument("--no-open", action="store_true",
                    help="do not open a browser (for testing)")
    ap.add_argument("--probe", action="store_true",
                    help="report status only; never start anything")
    a = ap.parse_args(argv)

    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent.parent
    server_py = root / "tools" / "_denoise_live_server.py"
    python_exe = Path(a.python)
    base = "http://127.0.0.1:%d" % a.port
    spawned = None

    _say("")
    _say("FYP listening app  --  port %d" % a.port)
    _say("=" * 62)

    if not server_py.is_file():
        _say("[ERROR] server script not found: %s" % server_py)
        return 1
    if not python_exe.is_file():
        _say("[ERROR] python interpreter not found: %s" % python_exe)
        _say("        edit start_listen.bat and point PY at a python.exe that")
        _say("        has the project dependencies installed.")
        return 1

    # ---------------------------------------------------------------- decide
    if healthy(a.port):
        _say("  [1/3] server already healthy on port %d -- reusing it" % a.port)
        reused = True
    elif port_open(a.port):
        _say("  [1/3] port %d is occupied but /api/health does not answer." % a.port)
        _say("        another program is probably on this port; stopping here")
        _say("        rather than opening pages that cannot work.")
        _manual_hint(python_exe, server_py, a.port)
        return 1
    else:
        reused = False
        _say("  [1/3] starting the server (first start loads 5 models, ~10-30 s)")
        try:
            spawned = spawn_server(python_exe, server_py, root, a.port,
                                   a.server_console,
                                   root / "tools" / "_scratch" / "server_launch.log")
        except Exception as e:                                     # noqa: BLE001
            _say("[ERROR] could not start the server: %s" % e)
            _manual_hint(python_exe, server_py, a.port)
            return 1

    if a.probe:
        _say("  [probe] healthy=%s  port_open=%s"
             % (healthy(a.port), port_open(a.port)))
        return 0 if healthy(a.port) else 1

    # ------------------------------------------------------------------ wait
    if not reused:
        t0 = time.time()
        ready = False
        ticks = 0
        while time.time() - t0 < a.wait:
            if healthy(a.port):
                ready = True
                break
            if spawned is not None and spawned.poll() is not None:
                _say("")
                _say("[ERROR] the server exited immediately (code %s)."
                     % spawned.returncode)
                _manual_hint(python_exe, server_py, a.port)
                return 1
            time.sleep(0.5)
            ticks += 1
            if ticks % 8 == 0:                                     # ~every 4 s
                sys.stdout.write(".")
                sys.stdout.flush()
        if not ready:
            _say("")
            _say("[ERROR] timed out after %g s waiting for %s/api/health"
                 % (a.wait, base))
            _manual_hint(python_exe, server_py, a.port)
            return 1
        _say("        ready in %.1f s" % (time.time() - t0))

    # --------------------------------------------------------------- verify
    _say("  [2/3] checking the two pages")
    bad = []
    for path, label in PAGES:
        code = http_status(base + path)
        ok = code in (200, 206)          # 200 normal, 206 if a Range is served
        if not ok:
            bad.append((label, code))
        _say("        %-30s %s" % (label, "200 OK" if ok else "!! %s" % code))

    # ------------------------------------------------------------------ open
    if a.no_open:
        _say("  [3/3] --no-open: not opening a browser")
    else:
        _say("  [3/3] opening the two pages")
        for path, _label in PAGES:
            try:
                webbrowser.open(base + path)
            except Exception as e:                                 # noqa: BLE001
                _say("        could not open %s%s: %s" % (base, path, e))

    _say("-" * 62)
    _say("  denoise live (upload + run) : %s/" % base)
    _say("  separation listening        : %s/sep" % base)
    _say("")
    _say("  Separation rule: a model whose inference exceeds 8 s is killed and")
    _say("  reported as \"run took too long - skipped\".")
    _say("")
    if reused:
        _say("  A server was already running on this port and is being reused.")
    elif a.server_console == "attach":
        _say("  The server is running in THIS window -- close this window (or")
        _say("  press Ctrl+C) to stop it.")
    else:
        _say('  Server window: "FYP listening server" -- close THAT window to')
        _say("  stop the server. Closing this launcher window does not.")
    if bad:
        _say("")
        _say("[WARN] %d page(s) did not answer 200: %s"
             % (len(bad), ", ".join("%s(%s)" % (l, c) for l, c in bad)))

    # In attach mode we own the server's lifetime: stay here so the console --
    # and therefore the server -- lives until the user stops it.  Any exit path
    # below still returns through the caller, which keeps the window open.
    if spawned is not None and a.server_console == "attach":
        _say("=" * 62)
        _say("  server is up; leaving this window open while it runs ...")
        try:
            rc = spawned.wait()
        except KeyboardInterrupt:
            _say("")
            _say("  stopping the server ...")
            spawned.terminate()
            try:
                spawned.wait(timeout=10)
            except Exception:                                      # noqa: BLE001
                spawned.kill()
            return 0
        _say("")
        _say("  server exited with code %s" % rc)
        return 0 if rc == 0 else 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:                                              # noqa: BLE001
        pass
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:                                              # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(1)

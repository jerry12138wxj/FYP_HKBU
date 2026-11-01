@echo off
REM ===================================================================
REM fig3_spectrogram_{est,ref} -- n_fft=2048 ADDITIONAL version
REM >>> INDEPENDENT MODE (does NOT wait for the main figure job) <<<
REM
REM Difference vs _fig3_2048_full.bat:
REM   _fig3_2048_full  : only processes units whose main .done exists
REM                      -> capped by the main job, can never finish first.
REM   _fig3_2048_indep : enumerates ALL units straight from 03_outputs
REM                      -> finishes on its own, in parallel with the main job.
REM
REM Safety (verified against source):
REM   * the main job never deletes anything (no rmtree/unlink in --all path)
REM   * this job writes only fig3_*_nfft2048.png  (no filename overlap)
REM   * this job NEVER writes caption.json; it writes caption_nfft2048.json
REM     instead (sidecar). Merge later with:
REM        python tools\_make_fig3_nfft2048_indep.py --merge-caption
REM
REM Covers three unit sets:
REM   sep  _model_figs/<Model>/<Song>/<stem>/
REM   den  _model_figs/<slug>/p232_001/
REM   val  _model_figs/<slug>/valentini/<clip>/
REM
REM Resumable / idempotent: each unit writes .done_nfft2048; run it as often
REM as you like -- it only fills in what is missing.
REM
REM Why this must run OUTSIDE the agent session (double-click, or Task
REM Scheduler): a background process started by an agent session turn is
REM HARD-KILLED when that turn ends (no traceback, half-written unit) --
REM measured 2026-09-21, re-confirmed 2026-09-23 and twice on 2026-10-13.
REM
REM Output: redirect straight to a file. Do NOT use tee.
REM Keep this file ASCII-only (cmd.exe mis-decodes Chinese as GBK).
REM ===================================================================
cd /d E:\FYP_HKBU

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
set OUT=E:\FYP_HKBU\tools\_logs\_fig3_2048_indep.out
set PYTHONPATH=E:\FYP_HKBU\tools

if not exist "E:\FYP_HKBU\tools\_logs" mkdir "E:\FYP_HKBU\tools\_logs"

echo ===== launch %DATE% %TIME% ===== >> "%OUT%"

"%PY%" -X utf8 -u tools\_run_fig3_2048_indep_until_done.py >> "%OUT%" 2>&1

echo ===== ALL EXIT %ERRORLEVEL% %DATE% %TIME% ===== >> "%OUT%"
echo.
echo Done. Log: %OUT%
pause

@echo off
REM ===================================================================
REM fig3_spectrogram_{est,ref} -- n_fft=2048 ADDITIONAL version (all figure sets)
REM
REM Adds:  fig3_spectrogram_est_nfft2048.png / fig3_spectrogram_ref_nfft2048.png
REM into every figure-set unit dir (separation board + denoising board).
REM Originals (fig3_*, n_fft=1024) are NEVER touched.
REM
REM Covers three unit sets:
REM   sep  _model_figs/<Model>/<Song>/<stem>/
REM   den  _model_figs/<slug>/p232_001/
REM   val  _model_figs/<slug>/valentini/<clip>/
REM
REM Resumable / idempotent: each unit writes .done_nfft2048; run it as often
REM as you like -- it only fills in what is missing.
REM
REM NOTE: it only touches units whose main .done already exists, so it never
REM races the running _figures_full.bat job. Run it now for the finished
REM units, and run it AGAIN after the separation job finishes to catch the rest.
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
set OUT=E:\FYP_HKBU\tools\_logs\_fig3_2048_full.out
set PYTHONPATH=E:\FYP_HKBU\tools

if not exist "E:\FYP_HKBU\tools\_logs" mkdir "E:\FYP_HKBU\tools\_logs"

echo ===== launch %DATE% %TIME% ===== >> "%OUT%"

"%PY%" -X utf8 -u tools\_run_fig3_2048_until_done.py >> "%OUT%" 2>&1

echo ===== ALL EXIT %ERRORLEVEL% %DATE% %TIME% ===== >> "%OUT%"
echo.
echo Done. Log: %OUT%
pause

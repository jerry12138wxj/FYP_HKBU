@echo off
REM ===================================================================
REM Separation figure sets -- FULL run (11 models x MUSDB18 test, 1607 units)
REM Resumable: each unit writes a .done marker; finished units are skipped.
REM
REM Why this must run OUTSIDE the agent session (double-click this file,
REM or launch via Windows Task Scheduler):
REM   2026-09-21 measured, 2026-09-23 re-confirmed (see _denoise_full.bat):
REM   a background process started by an agent session turn is HARD-KILLED
REM   when that turn ends -- no traceback, and the in-flight unit is left
REM   half-written (some figures missing, no .done).
REM   Re-confirmed twice on THIS job on 2026-10-13 (died at 01:10 and 02:13).
REM   A process owned by your own console / by the Task Scheduler service is
REM   fully decoupled from the session and survives.
REM
REM The python driver adds an outer "restart until done" loop, so even an
REM unexpected interruption (sleep, resource reclaim) only costs one unit.
REM
REM Output: redirect straight to a file. Do NOT use tee.
REM Keep this file ASCII-only (cmd.exe mis-decodes Chinese as GBK).
REM ===================================================================
cd /d E:\FYP_HKBU

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
set OUT=E:\FYP_HKBU\tools\_logs\_figures_full.out
set PYTHONPATH=E:\FYP_HKBU\tools

if not exist "E:\FYP_HKBU\tools\_logs" mkdir "E:\FYP_HKBU\tools\_logs"

echo ===== launch %DATE% %TIME% ===== >> "%OUT%"

"%PY%" -X utf8 -u tools\_run_figures_until_done.py >> "%OUT%" 2>&1

echo ===== ALL EXIT %ERRORLEVEL% %DATE% %TIME% ===== >> "%OUT%"
echo.
echo Done. Log: %OUT%
pause

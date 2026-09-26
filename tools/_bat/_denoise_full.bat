@echo off
REM ===================================================================
REM Denoise evaluation -- full evaluator sweep (Valentini + synth pairs)
REM Launched by Windows Task Scheduler (see _denoise_eval_launch.bat usage).
REM
REM Why not nohup / run_in_background:
REM   2026-09-21 measured: a background process started by the agent session
REM   is HARD-KILLED when that session turn ends. Re-confirmed 2026-09-23.
REM   Under Task Scheduler the process is owned by the service, fully decoupled.
REM
REM Output: redirect straight to a file. Do NOT use tee.
REM Keep this file ASCII-only (cmd.exe mis-decodes Chinese as GBK and can
REM   eat the following line).
REM ===================================================================
cd /d E:\FYP_HKBU

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
set OUT=E:\FYP_HKBU\tools\_logs\_denoise_full.out
set PYTHONPATH=E:\FYP_HKBU\tools

echo ===== launch %DATE% %TIME% ===== >> "%OUT%"

REM --- 1. main 16 kHz pass (PESQ applicable) ---
"%PY%" -X utf8 tools\_denoise_eval.py run --models A,B --dataset valentini --sr 16000 --resume >> "%OUT%" 2>&1
echo ===== valentini 16k exit %ERRORLEVEL% %DATE% %TIME% ===== >> "%OUT%"

"%PY%" -X utf8 tools\_denoise_eval.py run --models A,B --dataset synth --sr 16000 --resume >> "%OUT%" 2>&1
echo ===== synth 16k exit %ERRORLEVEL% %DATE% %TIME% ===== >> "%OUT%"

REM --- 2. dns_dev blind set (no reference) ---
"%PY%" -X utf8 tools\_denoise_eval.py run --models A,B --dataset dns_dev --sr 16000 --allow-noref --resume >> "%OUT%" 2>&1
echo ===== dns_dev 16k exit %ERRORLEVEL% %DATE% %TIME% ===== >> "%OUT%"

REM --- 3. native-rate pass (no PESQ) ---
"%PY%" -X utf8 tools\_denoise_eval.py run --models A,B --dataset valentini --sr 44100 --resume >> "%OUT%" 2>&1
echo ===== valentini 44k exit %ERRORLEVEL% %DATE% %TIME% ===== >> "%OUT%"

"%PY%" -X utf8 tools\_denoise_eval.py run --models A,B --dataset synth --sr 44100 --resume >> "%OUT%" 2>&1
echo ===== synth 44k exit %ERRORLEVEL% %DATE% %TIME% ===== >> "%OUT%"

echo ===== ALL DONE %DATE% %TIME% ===== >> "%OUT%"

@echo off
REM ===================================================================
REM Export real OUTPUT audio + source audio for the representative
REM samples shown in Final_Eval_Report.xlsx.
REM
REM Output root: E:\FYP_HKBU\03_outputs\TableSample_Audio
REM   <model>/<database>/raw_data/<sample>__input.wav
REM                        <sample>__reference.wav  (no clean -> skipped)
REM                        <sample>__noise.wav      (dns only)
REM   <model>/<database>/output/<sample>__output.wav
REM
REM Samples = same 9-per-group picks as the Excel (mean / best / worst
REM after extreme-value filtering).  324 samples total, ~45-50 min on GPU.
REM
REM WHY double-click: a background process started by the agent session
REM is killed when the turn ends. Run this file yourself so the export
REM survives. Re-runnable: it overwrites the same files idempotently.
REM
REM ASCII-ONLY on purpose (cmd decodes this file as GBK; any non-ASCII
REM byte shifts parsing and spawns fake "not recognized" errors).
REM ===================================================================
cd /d E:\FYP_HKBU

set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
set LOG=E:\FYP_HKBU\tools\_logs\_export_audio.out

if not exist "E:\FYP_HKBU\tools\_logs" mkdir "E:\FYP_HKBU\tools\_logs"

echo ===== export audio launch %DATE% %TIME% ===== >> "%LOG%"

"%PY%" -X utf8 -u tools\_export_table_audio.py >> "%LOG%" 2>&1

echo ===== ALL EXIT %ERRORLEVEL% %DATE% %TIME% ===== >> "%LOG%"
echo.
echo Done. Check: E:\FYP_HKBU\03_outputs\TableSample_Audio
echo Manifest: E:\FYP_HKBU\03_outputs\TableSample_Audio\_manifest.json
echo Log: %LOG%
pause

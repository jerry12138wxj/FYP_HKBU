@echo off
REM bench500 finalizer: wait for rpca + dprnn retrain, re-bench DPRNN v2, build tables.
REM Double-click to run. Safe to re-run (idempotent, finished stages are skipped).
REM Closing this window kills the wait loop, NOT the underlying bench (one python child).
chcp 65001 >nul
cd /d E:\FYP_HKBU
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
set PYTHONIOENCODING=utf-8

if not exist "D:\FYP_HKBU_runs\bench500_table" mkdir "D:\FYP_HKBU_runs\bench500_table"

echo ============================================================
echo  bench500 finalizer
echo  1) wait until rpca reaches 500/500 and dprnn retrain exits
echo  2) re-bench DPRNN with the NEW checkpoint as dprnn_v2
echo  3) build BENCH500_COMPARE.md  (4-stem / vocals-only / other)
echo  output -^> D:\FYP_HKBU_runs\bench500_table
echo ============================================================

"C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe" -X utf8 -u tools\_bench500_finalize.py --wait-minutes 300 > "D:\FYP_HKBU_runs\bench500_table\finalize.out" 2>&1

echo.
echo exit code = %ERRORLEVEL%
echo see D:\FYP_HKBU_runs\bench500_table\finalize.out
pause

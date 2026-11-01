@echo off
REM DPRNN retrain with leak-free by-song split (train 90 / holdout 10).
REM Double-click to run. Outputs go to D:\FYP_HKBU_runs\dprnn_v2
REM Do NOT close this window while training; closing kills training.
chcp 65001 >nul
cd /d E:\FYP_HKBU
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
set PYTHONIOENCODING=utf-8

echo ============================================================
echo  DPRNN v2 : train 90 songs / valid 10 held-out songs
echo  checkpoints -^> D:\FYP_HKBU_runs\dprnn_v2\checkpoints
echo  log         -^> D:\FYP_HKBU_runs\dprnn_v2\run.out
echo ============================================================

"C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe" -X utf8 -u tools\train_dprnn_fixedsplit.py --minutes 300 --batch 4 > D:\FYP_HKBU_runs\dprnn_v2\run.out 2>&1

echo.
echo exit code = %ERRORLEVEL%
echo see D:\FYP_HKBU_runs\dprnn_v2\run.out
pause

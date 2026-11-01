@echo off
setlocal
REM ============================================================
REM  D1-b stage: DNS dev_testset pseudo-clean
REM    A) two Mel-RoFormer DENOISE models  (~85 min each, RTF ~0.2)
REM    B) metrics -> a complete 6-model denoise table
REM    C) two Mel-RoFormer DEREVERB models (~85 min each)
REM    D) metrics -> refresh with all 8 board-2 models
REM  Stop after (B) if you only need denoisers: you still get a full table.
REM  Resumable: existing .flac files are skipped, safe to re-run.
REM  Output : baseline\dns_pseudo\<model>\<clip>.flac
REM           baseline\dns_pseudo\_index.csv
REM           baseline\dns_pseudo\b_prime.csv
REM  Log    : tools\_logs\_dns_pseudo.out
REM ============================================================
cd /d "%~dp0..\.."
set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
set LOG=tools\_logs\_dns_pseudo.out
if not exist "tools\_logs" mkdir "tools\_logs"

echo ================================================== >> "%LOG%"
echo [%DATE% %TIME%] START DNS pseudo-clean >> "%LOG%"

echo [%DATE% %TIME%] A1 mel_roformer_denoise >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_clean.py --models mel_roformer_denoise >> "%LOG%" 2>&1
echo [%DATE% %TIME%] A1 exit=%ERRORLEVEL% >> "%LOG%"

echo [%DATE% %TIME%] A2 mel_roformer_denoise_aggr >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_clean.py --models mel_roformer_denoise_aggr >> "%LOG%" 2>&1
echo [%DATE% %TIME%] A2 exit=%ERRORLEVEL% >> "%LOG%"

echo [%DATE% %TIME%] B metrics (denoise only) >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_sdr.py --limit 300 --jobs 1 >> "%LOG%" 2>&1
echo [%DATE% %TIME%] B exit=%ERRORLEVEL% >> "%LOG%"

echo [%DATE% %TIME%] C1 mel_roformer_dereverb >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_clean.py --models mel_roformer_dereverb >> "%LOG%" 2>&1
echo [%DATE% %TIME%] C1 exit=%ERRORLEVEL% >> "%LOG%"

echo [%DATE% %TIME%] C2 mel_roformer_dereverb_echo >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_clean.py --models mel_roformer_dereverb_echo >> "%LOG%" 2>&1
echo [%DATE% %TIME%] C2 exit=%ERRORLEVEL% >> "%LOG%"

echo [%DATE% %TIME%] D metrics (all 8) >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_sdr.py --limit 300 --jobs 1 >> "%LOG%" 2>&1
echo [%DATE% %TIME%] D exit=%ERRORLEVEL% >> "%LOG%"

echo [%DATE% %TIME%] ALL DONE >> "%LOG%"
echo.
echo Done. Log: tools\_logs\_dns_pseudo.out
echo Results: baseline\dns_pseudo\_index.csv  and  b_prime.csv
pause

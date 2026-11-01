@echo off
setlocal
REM Headless variant (no pause). Same body/order as _dns_pseudo_mel.bat:
REM A) 2 denoise models  B) metrics  C) 2 dereverb models  D) metrics
REM (Task Scheduler is unavailable on this machine: schtasks is blacklisted.)
cd /d "%~dp0..\.."
set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
set LOG=tools\_logs\_dns_pseudo.out
if not exist "tools\_logs" mkdir "tools\_logs"

echo ================================================== >> "%LOG%"
echo [%DATE% %TIME%] START DNS pseudo-clean (headless) >> "%LOG%"

"%PY%" -X utf8 -u tools\_dns_pseudo_clean.py --models mel_roformer_denoise >> "%LOG%" 2>&1
echo [%DATE% %TIME%] A1 exit=%ERRORLEVEL% >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_clean.py --models mel_roformer_denoise_aggr >> "%LOG%" 2>&1
echo [%DATE% %TIME%] A2 exit=%ERRORLEVEL% >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_sdr.py --limit 300 --jobs 1 >> "%LOG%" 2>&1
echo [%DATE% %TIME%] B metrics exit=%ERRORLEVEL% >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_clean.py --models mel_roformer_dereverb >> "%LOG%" 2>&1
echo [%DATE% %TIME%] C1 exit=%ERRORLEVEL% >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_clean.py --models mel_roformer_dereverb_echo >> "%LOG%" 2>&1
echo [%DATE% %TIME%] C2 exit=%ERRORLEVEL% >> "%LOG%"
"%PY%" -X utf8 -u tools\_dns_pseudo_sdr.py --limit 300 --jobs 1 >> "%LOG%" 2>&1
echo [%DATE% %TIME%] D metrics exit=%ERRORLEVEL% >> "%LOG%"

echo [%DATE% %TIME%] ALL DONE >> "%LOG%"
exit /b 0

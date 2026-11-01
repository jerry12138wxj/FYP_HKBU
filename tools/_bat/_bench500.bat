@echo off
setlocal enabledelayedexpansion
set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
cd /d E:\FYP_HKBU
if not exist tools\_logs mkdir tools\_logs
set LOG=tools\_logs\_bench500.out
echo ==== 500-segment model comparison ==== > %LOG%
echo START %DATE% %TIME% >> %LOG%

"%PY%" -X utf8 -u tools\_bench500.py build >> %LOG% 2>&1
echo BUILD EXIT %ERRORLEVEL% >> %LOG%

for %%M in (demucs umx mdx mdx_q mdx_extra_q convtasnet mmdenselstm bsroformer_l12 bsroformer_l6 bsrnn_all bsrnn_large_all bsrnn_simo bsrnn bsrnn_large dprnn rpca) do (
  echo. >> %LOG%
  echo ---- %%M ---- >> %LOG%
  "%PY%" -X utf8 -u tools\_bench500.py model --model %%M >> %LOG% 2>&1
  echo %%M EXIT !ERRORLEVEL! >> %LOG%
)

"%PY%" -X utf8 -u tools\_bench500.py summary >> %LOG% 2>&1
echo SUMMARY EXIT %ERRORLEVEL% >> %LOG%
echo ALL EXIT %ERRORLEVEL% >> %LOG%
echo.
echo Done. Log: %LOG%
type %LOG% | findstr /C:"ALL EXIT" /C:"SUMMARY EXIT" /C:"BUILD EXIT"
pause

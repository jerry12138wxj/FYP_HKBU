@echo off
setlocal
set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
cd /d E:\FYP_HKBU
if not exist tools\_logs mkdir tools\_logs
echo ==== baseline recompute 2s/1.5s + real re-decode (D2 + D3) ==== > tools\_logs\_baseline_win2s.out
echo START %DATE% %TIME% >> tools\_logs\_baseline_win2s.out
"%PY%" -X utf8 -u tools\_build_baseline.py sdr --root baseline_win2s --dataset all --win-s 2.0 --hop-s 1.5 >> tools\_logs\_baseline_win2s.out 2>&1
echo SDR EXIT %ERRORLEVEL% >> tools\_logs\_baseline_win2s.out
"%PY%" -X utf8 -u tools\_build_baseline.py summary --root baseline_win2s >> tools\_logs\_baseline_win2s.out 2>&1
echo SUMMARY EXIT %ERRORLEVEL% >> tools\_logs\_baseline_win2s.out
echo ALL EXIT %ERRORLEVEL% >> tools\_logs\_baseline_win2s.out
echo.
echo Done. Log: tools\_logs\_baseline_win2s.out
type tools\_logs\_baseline_win2s.out | findstr /C:"ALL EXIT" /C:"SDR EXIT" /C:"SUMMARY EXIT"
pause

@echo off
REM ============================================================
REM  Launch the FYP cascade demo -- ONE page:
REM    * http://127.0.0.1:8123/
REM      upload a noisy audio -> separate vocals -> denoise the
REM      vocals -> listen online + download.
REM
REM  Models load on demand (when you click "start"), one at a
REM  time, so startup here is instant and memory-safe.
REM
REM  STYLE RULES -- do not "simplify" these away:
REM  1. ASCII only.
REM  2. NO parenthesised if/else blocks (cmd expands %VAR% at
REM     parse time for the whole block).
REM  3. ping -n N is the sleep (timeout.exe fails on redirected
REM     stdin under a test harness).
REM  4. ver >nul before every "start ... / if errorlevel 1" pair
REM     (start does NOT reset ERRORLEVEL).
REM ============================================================
setlocal
title FYP cascade demo

set "PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
set "PORT=8123"
set "BASE=http://127.0.0.1:%PORT%"
set "SERVER=%ROOT%tools\_cascade_web.py"

echo.
echo  FYP cascade demo  --  separation then vocal denoise, port %PORT%
echo  ==============================================================

if not exist "%SERVER%" goto noserver

cd /d "%ROOT%"

REM --- step 1: is a server already listening on this port? ---------
netstat -ano | findstr /c:":%PORT% " | findstr /c:"LISTENING" >nul 2>&1
if not errorlevel 1 goto reuse

echo   [1/3] starting the server in its own window ...
ver >nul
start "FYP cascade server" "%PY%" "%SERVER%" --port %PORT%
if errorlevel 1 goto startfail

echo         waiting for port %PORT% to answer ...
set /a TRIES=0

:wait
ping -n 3 127.0.0.1 >nul 2>&1
netstat -ano | findstr /c:":%PORT% " | findstr /c:"LISTENING" >nul 2>&1
if not errorlevel 1 goto ready
set /a TRIES+=1
if %TRIES% GEQ 40 goto slow
goto wait

:reuse
echo   [1/3] a server is already listening on port %PORT% -- reusing it
goto ready

:ready
echo   [2/3] opening the page
start "" "%BASE%/"

echo   [3/3] done
echo.
echo   page : %BASE%/
echo.
echo   The server runs in the window titled "FYP cascade server".
echo   Close THAT window to stop it.  This window closes by itself in 6 s.
ping -n 7 127.0.0.1 >nul 2>&1
endlocal
exit /b 0

:noserver
echo [ERROR] server script not found:
echo         %SERVER%
echo         start_cascade.bat must sit in the project root, next to tools\
goto hold

:startfail
echo [ERROR] the server could not be started.
echo         Run it by hand to see why:
echo           "%PY%" "%SERVER%" --port %PORT%
goto hold

:slow
echo.
echo [WARN] port %PORT% was still not listening after 80 s, so the page was
echo        NOT opened.  Look at the window titled "FYP cascade server".
goto hold

:hold
echo.
pause
endlocal
exit /b 1

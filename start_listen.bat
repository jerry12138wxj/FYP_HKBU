@echo off
REM ============================================================
REM  Launch the local listening app -- THREE pages:
REM    * http://127.0.0.1:8123/      denoise live: upload a noisy
REM                                  signal, run the 5 models, listen
REM    * http://127.0.0.1:8123/sep  separation: MUSDB18-HQ three-song
REM                                  per-model comparison, plus a box
REM                                  that runs the 13 models on the spot
REM    * http://127.0.0.1:8123/ab   offline denoise A/B: 10 Valentini
REM                                  clips plus 6 transient-noise clips
REM
REM  A separation model whose inference exceeds 8 s is killed and
REM  reported as "run took too long - skipped".
REM
REM  STYLE RULES -- do not "simplify" these away.
REM
REM  1. ASCII only.  A .bat is read in the console code page, so
REM     non-ASCII echo text would come out garbled.
REM
REM  2. NO parenthesised if/else blocks.  cmd expands %VAR% for a whole
REM     block while *parsing* the block, before the set on the line above
REM     has executed.  An earlier version of this file kept a retry
REM     counter inside a block; the line collapsed to
REM         if  LSS 30 goto wait
REM     cmd reported "30 was unexpected at this time." and abandoned the
REM     entire script at PARSE time -- nothing printed, no page opened,
REM     window gone instantly.  That was the "double-click and it flashes
REM     away" bug.  Labels and goto are parsed one line at a time and are
REM     safe, so the retry loop below uses :wait / goto and never a block.
REM
REM  3. ping -n N is used as the sleep.  timeout.exe refuses to run when
REM     stdin is redirected, which makes it useless under a test harness.
REM
REM  4. ver >nul before every "start ... / if errorlevel 1" pair.  start does
REM     NOT reset ERRORLEVEL, so the status of whatever ran before it leaks
REM     through and a perfectly good launch looks like a failure.  Measured
REM     here: PRE=1, POST-START=1, POST-VER=0, child process really spawned.
REM
REM  tools\listen_launcher.py does the same job with an HTTP readiness
REM  probe.  It is kept because it can be exercised headlessly; this file
REM  deliberately needs nothing but cmd.
REM ============================================================
setlocal
title FYP listening app

set "PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "ROOT=%~dp0"
set "PORT=8123"
set "BASE=http://127.0.0.1:%PORT%"
set "SERVER=%ROOT%tools\_denoise_live_server.py"

echo.
echo  FYP listening app  --  three pages, port %PORT%
echo  ==============================================================

if not exist "%SERVER%" goto noserver

cd /d "%ROOT%"

REM --- step 1: is a server already listening on this port? ---------------
netstat -ano | findstr /c:":%PORT% " | findstr /c:"LISTENING" >nul 2>&1
if not errorlevel 1 goto reuse

echo   [1/3] starting the server in its own window ...
echo         the first start loads 5 models: allow 15-30 s

REM ver >nul resets ERRORLEVEL to 0.  start does NOT: the 1 left behind by the
REM netstat above would survive a SUCCESSFUL start and make the check below
REM report a failure that never happened.  Measured: PRE=1, POST-START=1,
REM POST-VER=0 -- with the child actually spawned.
ver >nul
start "FYP listening server" "%PY%" "%SERVER%" --port %PORT% --preload
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
echo   [2/3] opening the three pages
start "" "%BASE%/"
start "" "%BASE%/sep"
start "" "%BASE%/ab"

echo   [3/3] done
echo.
echo   [1] denoise live  : %BASE%/
echo   [2] separation    : %BASE%/sep
echo   [3] offline A/B   : %BASE%/ab
echo.
echo   Separation rule: a model whose inference exceeds 8 s is killed
echo   and reported as "run took too long - skipped".
echo.
echo   The server runs in the window titled "FYP listening server".
echo   Close THAT window to stop it.  This window closes by itself in 6 s.
ping -n 7 127.0.0.1 >nul 2>&1
endlocal
exit /b 0

:noserver
echo [ERROR] server script not found:
echo         %SERVER%
echo         start_listen.bat must sit in the project root, next to tools\
goto hold

:startfail
echo [ERROR] the server could not be started.
echo         Run it by hand to see why:
echo           "%PY%" "%SERVER%" --port %PORT% --preload
goto hold

:slow
echo.
echo [WARN] port %PORT% was still not listening after 80 s, so the three
echo        pages were NOT opened: against a half-started server they would
echo        show no audio at all.  Look at the window titled
echo        "FYP listening server" for the model-loading log.
goto hold

:hold
echo.
pause
endlocal
exit /b 1

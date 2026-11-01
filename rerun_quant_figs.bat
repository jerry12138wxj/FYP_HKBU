@echo off
REM ===================================================================
REM Re-run mdx_q / mdx_extra_q (8 tasks) with --force to regenerate
REM figures whose title had CJK "quantization" rendered as tofu boxes.
REM
REM --force ignores .done markers and OVERWRITES results.json, so no
REM files need to be deleted (avoids the bulk-delete guardrail).
REM
REM ASCII-ONLY on purpose: cmd.exe decodes this as GBK; non-ASCII
REM bytes in comments shift parsing and spawn fake "not recognized"
REM errors.
REM
REM Fast tasks first, slow wham tasks last. Resumable: if interrupted,
REM just re-run this file -- but --force always reprocesses, so it
REM starts over. To resume a PARTIAL run, remove --force from the
REM already-finished lines.
REM
REM ETA: ~3-3.5 h total (wham 2 tasks = ~1.4 h each).
REM ===================================================================
cd /d E:\FYP_HKBU

set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
set OUT=E:\FYP_HKBU\03_outputs\_eval
set LOG=E:\FYP_HKBU\tools\_logs\_rerun_quant.out

if not exist "E:\FYP_HKBU\tools\_logs" mkdir "E:\FYP_HKBU\tools\_logs"

echo ===== launch %DATE% %TIME% ===== >> "%LOG%"

REM ---- fast: mdx_q x musdb/valentini/dns ----
echo [R] mdx_q x musdb ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_q --db musdb --force --out-dir "%OUT%\sep__mdx_q__musdb" >> "%LOG%" 2>&1

echo [R] mdx_q x valentini ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_q --db valentini --force --out-dir "%OUT%\sep__mdx_q__valentini" >> "%LOG%" 2>&1

echo [R] mdx_q x dns ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_q --db dns --force --out-dir "%OUT%\sep__mdx_q__dns" >> "%LOG%" 2>&1

REM ---- fast: mdx_extra_q x musdb/valentini/dns ----
echo [R] mdx_extra_q x musdb ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_extra_q --db musdb --force --out-dir "%OUT%\sep__mdx_extra_q__musdb" >> "%LOG%" 2>&1

echo [R] mdx_extra_q x valentini ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_extra_q --db valentini --force --out-dir "%OUT%\sep__mdx_extra_q__valentini" >> "%LOG%" 2>&1

echo [R] mdx_extra_q x dns ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_extra_q --db dns --force --out-dir "%OUT%\sep__mdx_extra_q__dns" >> "%LOG%" 2>&1

REM ---- slow: wham ----
echo [R] mdx_q x wham ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_q --db wham --force --out-dir "%OUT%\sep__mdx_q__wham" >> "%LOG%" 2>&1

echo [R] mdx_extra_q x wham ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_extra_q --db wham --force --out-dir "%OUT%\sep__mdx_extra_q__wham" >> "%LOG%" 2>&1

REM ---- rebuild Excel (ASCII filename) ----
echo [EXCEL] rebuild xlsx ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_build_eval_excel.py --root "%OUT%" --out "E:\FYP_HKBU\03_outputs\Model_Eval_Report.xlsx" >> "%LOG%" 2>&1

echo ===== ALL EXIT %ERRORLEVEL% %DATE% %TIME% ===== >> "%LOG%"
echo.
echo Done. Excel: E:\FYP_HKBU\03_outputs\Model_Eval_Report.xlsx
echo Log: %LOG%
pause

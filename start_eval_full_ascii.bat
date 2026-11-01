@echo off
REM ===================================================================
REM Model evaluation full sweep (Sheet1 sep x4 dbs + Sheet2 cascade x valentini)
REM
REM WHY double-click: a background process started by the agent session
REM is HARD-KILLED when the turn ends.  Run this file yourself so the
REM whole sweep survives.  It is resumable (each sample writes a .done).
REM
REM ASCII-ONLY on purpose: cmd.exe decodes this file as GBK; any
REM non-ASCII byte in comments shifts parsing and spawns fake
REM "not recognized as a command" errors (the bug this file replaces).
REM
REM Default cap: first 500 samples per db (musdb 50 runs all).
REM Override with --limit N on any command below.
REM
REM Rough duration (RTX 4070 Laptop, 8 GiB):
REM   demucs / mdx_q / mdx_extra_q : RTF ~0.03-0.08 (fast)
REM   bsroformer_l12               : RTF ~0.49 (slow ~10x)
REM   musdb 50 full songs (3-4 min each)
REM   valentini 500 clips (3-5 s)  : fast models ~5 min, slow ~25 min
REM   dns 500 clips (3-5 s)        : fast models ~5 min, slow ~25 min
REM   wham 500 clips (150-280 s)   : fast models ~1-2 h, slow ~14 h  <- biggest
REM
REM Every sample writes a .done marker; re-running resumes where it stopped.
REM ===================================================================
cd /d E:\FYP_HKBU

set PY=C:\Users\jerry\.workbuddy\binaries\python\envs\fyp_audio\Scripts\python.exe
set OUT=E:\FYP_HKBU\03_outputs\_eval
set LOG=E:\FYP_HKBU\tools\_logs\_eval_full.out

if not exist "%OUT%" mkdir "%OUT%"
if not exist "E:\FYP_HKBU\tools\_logs" mkdir "E:\FYP_HKBU\tools\_logs"

echo ===== launch %DATE% %TIME% ===== >> "%LOG%"

REM ============================================================
REM Sheet 1  -- separation models x 4 databases
REM ============================================================
echo [S1] bsroformer_l12 x musdb ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:bsroformer_l12 --db musdb --out-dir "%OUT%\sep__bsroformer_l12__musdb" >> "%LOG%" 2>&1

echo [S1] bsroformer_l12 x valentini ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:bsroformer_l12 --db valentini --out-dir "%OUT%\sep__bsroformer_l12__valentini" >> "%LOG%" 2>&1

echo [S1] bsroformer_l12 x dns ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:bsroformer_l12 --db dns --out-dir "%OUT%\sep__bsroformer_l12__dns" >> "%LOG%" 2>&1

echo [S1] bsroformer_l12 x wham ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:bsroformer_l12 --db wham --out-dir "%OUT%\sep__bsroformer_l12__wham" >> "%LOG%" 2>&1

echo [S1] demucs x musdb ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:demucs --db musdb --out-dir "%OUT%\sep__demucs__musdb" >> "%LOG%" 2>&1

echo [S1] demucs x valentini ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:demucs --db valentini --out-dir "%OUT%\sep__demucs__valentini" >> "%LOG%" 2>&1

echo [S1] demucs x dns ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:demucs --db dns --out-dir "%OUT%\sep__demucs__dns" >> "%LOG%" 2>&1

echo [S1] demucs x wham ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:demucs --db wham --out-dir "%OUT%\sep__demucs__wham" >> "%LOG%" 2>&1

echo [S1] mdx_q x musdb ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_q --db musdb --out-dir "%OUT%\sep__mdx_q__musdb" >> "%LOG%" 2>&1

echo [S1] mdx_q x valentini ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_q --db valentini --out-dir "%OUT%\sep__mdx_q__valentini" >> "%LOG%" 2>&1

echo [S1] mdx_q x dns ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_q --db dns --out-dir "%OUT%\sep__mdx_q__dns" >> "%LOG%" 2>&1

echo [S1] mdx_q x wham ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_q --db wham --out-dir "%OUT%\sep__mdx_q__wham" >> "%LOG%" 2>&1

echo [S1] mdx_extra_q x musdb ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_extra_q --db musdb --out-dir "%OUT%\sep__mdx_extra_q__musdb" >> "%LOG%" 2>&1

echo [S1] mdx_extra_q x valentini ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_extra_q --db valentini --out-dir "%OUT%\sep__mdx_extra_q__valentini" >> "%LOG%" 2>&1

echo [S1] mdx_extra_q x dns ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_extra_q --db dns --out-dir "%OUT%\sep__mdx_extra_q__dns" >> "%LOG%" 2>&1

echo [S1] mdx_extra_q x wham ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline sep:mdx_extra_q --db wham --out-dir "%OUT%\sep__mdx_extra_q__wham" >> "%LOG%" 2>&1

REM ============================================================
REM Sheet 2  -- cascade (4 sep x 5 den) x valentini
REM ============================================================
echo [S2] demucs x denoiser_master64 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:demucs:denoiser_master64 --db valentini --out-dir "%OUT%\cascade__demucs__denoiser_master64__valentini" >> "%LOG%" 2>&1

echo [S2] demucs x denoiser_dns64 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:demucs:denoiser_dns64 --db valentini --out-dir "%OUT%\cascade__demucs__denoiser_dns64__valentini" >> "%LOG%" 2>&1

echo [S2] demucs x denoiser_dns48 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:demucs:denoiser_dns48 --db valentini --out-dir "%OUT%\cascade__demucs__denoiser_dns48__valentini" >> "%LOG%" 2>&1

echo [S2] demucs x mel_roformer_denoise_aggr ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:demucs:mel_roformer_denoise_aggr --db valentini --out-dir "%OUT%\cascade__demucs__mel_roformer_denoise_aggr__valentini" >> "%LOG%" 2>&1

echo [S2] demucs x wiener_filter ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:demucs:wiener_filter --db valentini --out-dir "%OUT%\cascade__demucs__wiener_filter__valentini" >> "%LOG%" 2>&1

echo [S2] bsroformer_l12 x denoiser_master64 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:bsroformer_l12:denoiser_master64 --db valentini --out-dir "%OUT%\cascade__bsroformer_l12__denoiser_master64__valentini" >> "%LOG%" 2>&1

echo [S2] bsroformer_l12 x denoiser_dns64 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:bsroformer_l12:denoiser_dns64 --db valentini --out-dir "%OUT%\cascade__bsroformer_l12__denoiser_dns64__valentini" >> "%LOG%" 2>&1

echo [S2] bsroformer_l12 x denoiser_dns48 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:bsroformer_l12:denoiser_dns48 --db valentini --out-dir "%OUT%\cascade__bsroformer_l12__denoiser_dns48__valentini" >> "%LOG%" 2>&1

echo [S2] bsroformer_l12 x mel_roformer_denoise_aggr ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:bsroformer_l12:mel_roformer_denoise_aggr --db valentini --out-dir "%OUT%\cascade__bsroformer_l12__mel_roformer_denoise_aggr__valentini" >> "%LOG%" 2>&1

echo [S2] bsroformer_l12 x wiener_filter ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:bsroformer_l12:wiener_filter --db valentini --out-dir "%OUT%\cascade__bsroformer_l12__wiener_filter__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_q x denoiser_master64 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_q:denoiser_master64 --db valentini --out-dir "%OUT%\cascade__mdx_q__denoiser_master64__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_q x denoiser_dns64 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_q:denoiser_dns64 --db valentini --out-dir "%OUT%\cascade__mdx_q__denoiser_dns64__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_q x denoiser_dns48 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_q:denoiser_dns48 --db valentini --out-dir "%OUT%\cascade__mdx_q__denoiser_dns48__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_q x mel_roformer_denoise_aggr ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_q:mel_roformer_denoise_aggr --db valentini --out-dir "%OUT%\cascade__mdx_q__mel_roformer_denoise_aggr__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_q x wiener_filter ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_q:wiener_filter --db valentini --out-dir "%OUT%\cascade__mdx_q__wiener_filter__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_extra_q x denoiser_master64 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_extra_q:denoiser_master64 --db valentini --out-dir "%OUT%\cascade__mdx_extra_q__denoiser_master64__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_extra_q x denoiser_dns64 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_extra_q:denoiser_dns64 --db valentini --out-dir "%OUT%\cascade__mdx_extra_q__denoiser_dns64__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_extra_q x denoiser_dns48 ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_extra_q:denoiser_dns48 --db valentini --out-dir "%OUT%\cascade__mdx_extra_q__denoiser_dns48__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_extra_q x mel_roformer_denoise_aggr ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_extra_q:mel_roformer_denoise_aggr --db valentini --out-dir "%OUT%\cascade__mdx_extra_q__mel_roformer_denoise_aggr__valentini" >> "%LOG%" 2>&1

echo [S2] mdx_extra_q x wiener_filter ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_eval_pipeline.py --pipeline cascade:mdx_extra_q:wiener_filter --db valentini --out-dir "%OUT%\cascade__mdx_extra_q__wiener_filter__valentini" >> "%LOG%" 2>&1

REM ============================================================
REM Build Excel
REM ============================================================
echo [EXCEL] build xlsx ... >> "%LOG%"
"%PY%" -X utf8 -u tools\_build_eval_excel.py --root "%OUT%" --out "E:\FYP_HKBU\03_outputs\Model_Eval_Report.xlsx" >> "%LOG%" 2>&1

echo ===== ALL EXIT %ERRORLEVEL% %DATE% %TIME% ===== >> "%LOG%"
echo.
echo Done. Excel: E:\FYP_HKBU\03_outputs\Model_Eval_Report.xlsx
echo Log: %LOG%
pause

@echo off
rem Backfill 2007-2012 settlement totals (village, town, neighbourhood) for every
rem province from MEDAS. Runs for hours; safe to rerun - provinces already on disk
rem are skipped. Log: raw\medas\yerlesim\backfill.log
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
for %%L in (Köy Belediye Mahalle) do (
  C:\veri\.venv\Scripts\python.exe scripts\fetch_medas_settlement_totals.py --level %%L --years 2007,2008,2009,2010,2011,2012 --all >> raw\medas\yerlesim\backfill.log 2>&1
)
echo BITTI >> raw\medas\yerlesim\backfill.log

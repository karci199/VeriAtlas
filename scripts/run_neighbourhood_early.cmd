@echo off
rem 2007-2012 neighbourhood 0-17/18+ for every province. Log: raw\medas\mahalle\early.log
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
C:\veri\.venv\Scripts\python.exe -u scripts\fetch_medas_neighbourhoods_early.py --all > raw\medas\mahalle\early.log 2>&1
echo BITTI >> raw\medas\mahalle\early.log

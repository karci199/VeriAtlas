@echo off
rem District-level household count and size from MEDAS (2007+). Log: raw\medas\basit\hane-ilce.log
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
C:\veri\.venv\Scripts\python.exe scripts\fetch_medas_simple.py hane-sayisi-ilce hane-buyuklugu-ilce > raw\medas\basit\hane-ilce.log 2>&1
echo BITTI >> raw\medas\basit\hane-ilce.log

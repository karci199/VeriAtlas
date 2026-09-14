# Long MEDAS pull: prison admissions and releases, one breakdown per query.
# Runs detached from the chat session; resumable (the fetcher skips files already on disk),
# so starting it again continues where it stopped. Log: C:\veri-ham\medas\uzun\ceza-infaz.log
#
#   powershell -ExecutionPolicy Bypass -File scripts\uzun_ceza_infaz.ps1

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:VERIATLAS_RAW = "C:/veri-ham"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:KIRILIM_KIRILIM = "1"
$log = "C:\veri-ham\medas\uzun\ceza-infaz.log"
"=== basladi $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $log
& .venv\Scripts\python.exe scripts\fetch_medas_topic.py `
    "ceza-giren=Ceza İnfaz Kurumuna Giren Hükümlü İstatistikleri" `
    "ceza-cikan=Ceza İnfaz Kurumundan Çıkan/Tahliye Edilen Hükümlü İstatistikleri" `
    *>> $log
"=== bitti $(Get-Date -Format s) cikis $LASTEXITCODE" | Out-File -Append -Encoding utf8 $log

# Whole EVDS catalogue, raw, groups already on disk skipped. Detached from the chat session.
# Saved as UTF-8 with BOM (Windows PowerShell 5). Log: C:\veri-ham\evds\_tum_cekim-<zaman>.log
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:VERIATLAS_RAW = "C:/veri-ham"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:EVDS_ATLA = "1"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$groups = (Get-Content "C:\veri-ham\evds\_tum_gruplar.txt" -Raw).Trim() -split "\s+"
$p = Start-Process -FilePath ".venv\Scripts\python.exe" -NoNewWindow -Wait -PassThru `
    -RedirectStandardOutput "C:\veri-ham\evds\_tum_cekim-$stamp.log" `
    -RedirectStandardError "C:\veri-ham\evds\_tum_cekim-$stamp.err" `
    -ArgumentList (@("scripts\fetch_evds_housing.py") + $groups)
"bitti $(Get-Date -Format s) cikis $($p.ExitCode)" | Out-File -Append -Encoding utf8 "C:\veri-ham\evds\_tum_cekim-$stamp.log"
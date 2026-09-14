# Long MEDAS pull: prison admissions and releases, one breakdown per query.
# Runs detached from the chat session; resumable (the fetcher skips files already on disk),
# so starting it again continues where it stopped. Log: C:\veri-ham\medas\uzun\ceza-infaz.log
#
# Saved as UTF-8 *with BOM*: Windows PowerShell 5 reads a BOM-less file as ANSI, and the
# Turkish topic names reached MEDAS garbled — every query timed out on the topic dropdown.
#
#   powershell -ExecutionPolicy Bypass -File scripts\uzun_ceza_infaz.ps1

Set-Location (Split-Path $PSScriptRoot -Parent)
$env:VERIATLAS_RAW = "C:/veri-ham"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:KIRILIM_KIRILIM = "1"
$dir = "C:\veri-ham\medas\uzun"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$p = Start-Process -FilePath ".venv\Scripts\python.exe" -NoNewWindow -Wait -PassThru `
    -RedirectStandardOutput "$dir\ceza-infaz-$stamp.log" `
    -RedirectStandardError "$dir\ceza-infaz-$stamp.err" `
    -ArgumentList @(
        "scripts\fetch_medas_topic.py",
        '"ceza-giren=Ceza İnfaz Kurumuna Giren Hükümlü İstatistikleri"',
        '"ceza-cikan=Ceza İnfaz Kurumundan Çıkan (Tahliye Edilen) Hükümlü İstatistikleri"'
    )
"bitti $(Get-Date -Format s) cikis $($p.ExitCode)" | Out-File -Append -Encoding utf8 "$dir\ceza-infaz-$stamp.log"
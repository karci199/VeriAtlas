# Completes the prison releases by residence (measure 02): the province files of 2026-09-14
# held only 1990-2008, 2015-2018 and 2020, not 2009-2014 and 2019 (found 2026-09-30 when the
# provinces did not add up to Türkiye). The incomplete files were moved to
# basit\_eksik-2026-09-30; the fetcher skips what is on disk, so this refetches exactly those.
# Waits for the new-topics job first: two MEDAS sessions at once collide.
# Saved as UTF-8 *with BOM* (Windows PowerShell 5 reads a BOM-less file as ANSI).

Set-Location (Split-Path $PSScriptRoot -Parent)
$env:VERIATLAS_RAW = "C:/veri-ham"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:KIRILIM_KIRILIM = "1"
$env:OLCULER = "2"
$dir = "C:\veri-ham\medas\uzun"
Start-Sleep -Seconds 30
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uzun_yeni_konular*' -or $_.CommandLine -like '*uzun_bitkisel_ilce*' -or $_.CommandLine -like '*fetch_medas_districts*' -or $_.CommandLine -like '*fetch_medas_topic*' }) { Start-Sleep -Seconds 60 }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$p = Start-Process -FilePath "C:\veri\.venv\Scripts\python.exe" -NoNewWindow -Wait -PassThru `
    -RedirectStandardOutput "$dir\ceza-cikan-tamamla-$stamp.log" `
    -RedirectStandardError "$dir\ceza-cikan-tamamla-$stamp.err" `
    -ArgumentList @(
        "scripts\fetch_medas_topic.py",
        '"ceza-cikan=Ceza İnfaz Kurumundan Çıkan (Tahliye Edilen) Hükümlü İstatistikleri"'
    )
"bitti $(Get-Date -Format s) cikis $($p.ExitCode)" | Out-File -Append -Encoding utf8 "$dir\ceza-cikan-tamamla-$stamp.log"
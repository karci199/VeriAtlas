# Long MEDAS pull: topics not yet fetched (labour force by region, income distribution, poverty,
# household consumption). Runs detached; resumable (the fetcher skips files already on disk).
# Waits for the bitkisel district job first: two MEDAS sessions at once collide.
# Saved as UTF-8 *with BOM* (Windows PowerShell 5 reads a BOM-less file as ANSI).
#
#   powershell -ExecutionPolicy Bypass -File scripts\uzun_yeni_konular.ps1

Set-Location (Split-Path $PSScriptRoot -Parent)
$env:VERIATLAS_RAW = "C:/veri-ham"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:KIRILIM_KIRILIM = "1"
$dir = "C:\veri-ham\medas\uzun"
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*uzun_bitkisel_ilce*' -or $_.CommandLine -like '*fetch_medas_districts*' }) { Start-Sleep -Seconds 60 }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$p = Start-Process -FilePath "C:\veri\.venv\Scripts\python.exe" -NoNewWindow -Wait -PassThru `
    -RedirectStandardOutput "$dir\yeni-konular-$stamp.log" `
    -RedirectStandardError "$dir\yeni-konular-$stamp.err" `
    -ArgumentList @(
        "scripts\fetch_medas_topic.py",
        '"isgucu-bolg=İşgücü İstatistikleri Bölgesel Sonuçlar"',
        '"gelir=Gelir Dağılımı ve Yaşam Koşulları İstatistikleri"',
        '"yoksulluk=Yoksulluk İstatistikleri"',
        '"tuketim=Hanehalkı Tüketim Harcaması İstatistikleri"'
    )
"bitti $(Get-Date -Format s) cikis $($p.ExitCode)" | Out-File -Append -Encoding utf8 "$dir\yeni-konular-$stamp.log"
# start.ps1 — Chay app (Windows). Sau khi da chay setup.ps1 1 lan.
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) {
  Write-Host "Chua setup. Chay .\setup.ps1 truoc." -ForegroundColor Red
  Read-Host "Enter de thoat"; exit 1
}
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "server.py" -WorkingDirectory $PSScriptRoot
Start-Sleep -Seconds 3
Start-Process "http://localhost:7788"
Write-Host "App da mo: http://localhost:7788" -ForegroundColor Green
Write-Host "(Dong cua so 'python server.py' la tat server.)"

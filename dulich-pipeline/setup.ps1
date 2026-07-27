# setup.ps1 — Cai dat 1 lan (Windows). Yeu cau: da cai Python 3.10+.
# Chay:  Right-click > Run with PowerShell   HOAC   .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"

Write-Host "== 1/5 Kiem tra Python ==" -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
  Write-Host "Chua co Python. Tai tai https://www.python.org/downloads/ (NHO tick 'Add Python to PATH'), roi chay lai script nay." -ForegroundColor Red
  Read-Host "Enter de thoat"; exit 1
}
$ver = (python -c "import sys;print('%d.%d'%sys.version_info[:2])")
Write-Host "   Python $ver OK"

Write-Host "== 2/5 Tao moi truong .venv ==" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { python -m venv .venv }

Write-Host "== 3/5 Cai thu vien (vai phut) ==" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "== 4/5 Cai trinh duyet Chromium (Playwright, ~150MB) ==" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m playwright install chromium

Write-Host "== 5/5 FFmpeg + file .env ==" -ForegroundColor Cyan
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "   Chua co FFmpeg. Thu cai bang winget..." -ForegroundColor Yellow
  try { winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements } catch {}
  if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "   Chua cai duoc FFmpeg tu dong. Tai 'ffmpeg-release-essentials' tai" -ForegroundColor Red
    Write-Host "   https://www.gyan.dev/ffmpeg/builds/ , giai nen, them thu muc bin\ vao PATH, roi mo lai cua so." -ForegroundColor Red
  } else { Write-Host "   FFmpeg da cai (co the can mo lai cua so de nhan PATH)." -ForegroundColor Yellow }
} else { Write-Host "   FFmpeg OK" }
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "   Da tao .env (chay FREE; dien API key sau neu can)." }

Write-Host "`nXONG! Chay app bang:  .\start.ps1" -ForegroundColor Green
Read-Host "Enter de thoat"

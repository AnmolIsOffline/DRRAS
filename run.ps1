# DRRAS PowerShell Startup Launcher
$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " DRRAS — Disaster Relief Resource Allocation System" -ForegroundColor White
Write-Host " One-Click Turnkey Launcher (Python + SQLite + Chrome)" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $alt = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (Test-Path $alt) {
        $python = $alt
    } else {
        Write-Error "Python was not found. Please install Python 3.10+."
        exit 1
    }
}

Write-Host "`n[1/4] Using Python: $python" -ForegroundColor Green
& $python -c "import flask" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[2/4] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    & $python -m pip install -r requirements.txt
} else {
    Write-Host "[2/4] Dependencies satisfied." -ForegroundColor Green
}

Write-Host "[3/4] Ensuring database migrations and demo scenario are seeded..." -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot
& $python seed_demo.py

Write-Host "[4/4] Starting DRRAS Flask Server on http://127.0.0.1:5055 ..." -ForegroundColor Cyan
Write-Host "Opening Google Chrome directly..." -ForegroundColor Green
$env:PORT = '5055'

# Launch Chrome specifically if present, otherwise default browser
$chrome = (Get-Command chrome -ErrorAction SilentlyContinue).Source
if ($chrome) {
    Start-Process chrome -ArgumentList "http://127.0.0.1:5055"
} elseif (Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe") {
    Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "http://127.0.0.1:5055"
} else {
    Start-Process "http://127.0.0.1:5055"
}

Write-Host "`nServer is running! Press Ctrl+C in this console to stop." -ForegroundColor Yellow
& $python app.py

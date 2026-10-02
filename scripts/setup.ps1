# Configura el entorno de Mano Musical (Windows PowerShell).
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== Mano Musical :: setup ==" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv .venv
}

$python = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "Instalando dependencias (python -m pip)..." -ForegroundColor Yellow
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m pip install pytest

Write-Host "Descargando modelo de MediaPipe..." -ForegroundColor Yellow
& $python scripts\download_models.py

Write-Host "Listo. Activa el entorno con:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "Ejecuta el juego con:          powershell -File scripts\run.ps1 --mode game" -ForegroundColor Green

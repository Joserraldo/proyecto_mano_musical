# Ejecuta Mano Musical usando el entorno virtual si existe.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\run.ps1 --mode game

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$env:PYTHONPATH = Join-Path $root "src"
& $python -m mano_musical @args

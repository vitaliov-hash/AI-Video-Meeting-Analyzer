$ErrorActionPreference = 'Stop'
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    $pythonCommand = py -3.11 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0) { $pythonCommand = py -3.12 -c "import sys; print(sys.executable)" 2>$null }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or 3.12 is required. Install one and run setup again.' }
    & $pythonCommand -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the project virtual environment.' }
}
& '.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Setup complete. Add your private provider key to .env, then run .\start.ps1.'

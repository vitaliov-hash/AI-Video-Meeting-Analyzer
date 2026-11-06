$ErrorActionPreference = 'Stop'
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run .\setup.ps1 first.' }
if (-not (Test-Path '.env')) { throw 'Copy .env.example to .env and add a provider API key.' }
& '.venv\Scripts\python.exe' -m meeting_analyzer

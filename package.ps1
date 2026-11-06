$ErrorActionPreference = 'Stop'
$root = (Resolve-Path '.').Path
$dist = Join-Path $root 'dist'
New-Item -ItemType Directory -Force -Path $dist | Out-Null
$zip = Join-Path $dist 'AI-Video-Meeting-Analyzer-DZ-Pro.zip'
if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force }
$include = @('meeting_analyzer','static','prompts','tests','docs/showcase','scripts/build_frontend.mjs','scripts/verify_frontend_build.mjs','scripts/test_showcase_mode.mjs','scripts/security_check.py','.github/workflows/quality.yml','README.md','SUBMISSION.md','SUBMISSION-LITE.md','DZ-PRO-SUBMISSION.md','DEPLOYMENT_READINESS.md','DEMO_GUIDE.md','DEMO_MODES.md','TEACHER_HANDOUT.md','ACCEPTANCE.md','PROJECT_CONTEXT.md','TECHNICAL_SPEC.md','SYSTEM_PROMPT.md','MEDIA_LICENSE_NOTES.md','requirements.txt','requirements-dev.txt','.env.example','setup.ps1','start.ps1','Dockerfile','.dockerignore','vercel.json')
$files = foreach ($item in $include) {
    $p = Join-Path $root $item
    if (Test-Path $p -PathType Container) {
        Get-ChildItem -LiteralPath $p -File -Recurse | Where-Object { $_.FullName -notmatch '[\\/](__pycache__|\.pytest_cache|\.ruff_cache)[\\/]' }
    } elseif (Test-Path $p -PathType Leaf) { Get-Item -LiteralPath $p }
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in $files) {
        $entry = $file.FullName.Substring($root.Length + 1).Replace([char]92, '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $entry, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally { $archive.Dispose() }
Write-Host "Created $zip"

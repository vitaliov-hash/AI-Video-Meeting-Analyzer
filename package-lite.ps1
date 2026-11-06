$ErrorActionPreference = 'Stop'
$root = (Resolve-Path '.').Path
$dist = Join-Path $root 'dist'
$archive = Join-Path $dist 'AI-Video-Meeting-Analyzer-DZ-Light.zip'
$sourceZip = Join-Path $dist '.dz-lite-source.zip'

if (-not (git tag --list dz-lite-v1)) { throw 'Verified tag dz-lite-v1 is missing.' }
New-Item -ItemType Directory -Force -Path $dist | Out-Null
if (Test-Path -LiteralPath $sourceZip) { Remove-Item -LiteralPath $sourceZip -Force }
git archive --format=zip --output=$sourceZip dz-lite-v1
if ($LASTEXITCODE -ne 0) { throw 'Could not export the verified Lite tag.' }

Add-Type -AssemblyName System.IO.Compression.FileSystem
$bundle = [System.IO.Compression.ZipFile]::Open($sourceZip, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    $oldReadme = $bundle.GetEntry('README.md')
    if ($oldReadme) { $oldReadme.Delete() }
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $bundle, (Join-Path $root 'README-LITE.md'), 'README.md',
        [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
    foreach ($name in @('SUBMISSION-LITE.md', 'setup.ps1', 'start.ps1')) {
        $path = Join-Path $root $name
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $bundle, $path, $name, [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
} finally { $bundle.Dispose() }

Move-Item -LiteralPath $sourceZip -Destination $archive -Force
Write-Host "Created $archive from dz-lite-v1"

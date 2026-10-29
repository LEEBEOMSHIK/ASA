$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    & uv sync --locked --project services/backend --python cpython-3.13-windows-x86_64-none
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency setup failed. Use Python 3.13 x64 on Windows.' }
    & npm.cmd ci --prefix apps/web
    if ($LASTEXITCODE -ne 0) { throw 'Web dependency setup failed.' }
    if (-not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
    }
    Write-Host 'Dependencies ready. Configure .env and your local PostgreSQL database; see docs/local-development.md.'
} finally { Pop-Location }

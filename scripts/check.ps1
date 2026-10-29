$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    & uv run --locked --project services/backend pytest services/backend/tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
    & uv run --locked --project services/backend ruff check services/backend
    if ($LASTEXITCODE -ne 0) { throw 'Backend lint failed.' }
    & uv run --locked --project services/backend mypy services/backend/src
    if ($LASTEXITCODE -ne 0) { throw 'Backend typecheck failed.' }
    & npm.cmd run typecheck --prefix apps/web
    if ($LASTEXITCODE -ne 0) { throw 'Web typecheck failed.' }
    & npm.cmd run build --prefix apps/web
    if ($LASTEXITCODE -ne 0) { throw 'Web build failed.' }
} finally { Pop-Location }

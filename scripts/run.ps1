param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('web', 'api', 'worker-check', 'automation-worker', 'script-worker', 'image-worker')]
    [string]$Service
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
$previousEnvironment = $env:ASA_ENVIRONMENT
$previousDevLogin = $env:ASA_DEV_LOGIN_ENABLED
try {
    switch ($Service) {
        'web' { & npm.cmd run dev --prefix apps/web }
        'api' {
            $env:ASA_ENVIRONMENT = 'development'
            $env:ASA_DEV_LOGIN_ENABLED = 'true'
            & uv run --locked --project services/backend uvicorn asa.api:app --host 127.0.0.1 --port 8127 --no-proxy-headers --reload --reload-dir services/backend/src
        }
        'worker-check' { & uv run --locked --project services/backend python -m asa.worker check }
        'script-worker' { & uv run --locked --project services/backend python -m asa.script_queue_worker --allow-paid-call }
        'image-worker' { & uv run --locked --project services/backend python -m asa.image_worker }
        'automation-worker' { & uv run --locked --project services/backend python -m asa.runtime_worker }
    }
    if ($LASTEXITCODE -ne 0) { throw "Service command failed: $Service" }
} finally {
    $env:ASA_ENVIRONMENT = $previousEnvironment
    $env:ASA_DEV_LOGIN_ENABLED = $previousDevLogin
    Pop-Location
}

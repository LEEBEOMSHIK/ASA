param([ValidateSet('start','stop','status')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$dataPath = Join-Path $repoRoot '.local/postgres'
$pgBin = if ($env:ASA_POSTGRES_BIN) { $env:ASA_POSTGRES_BIN } else { 'C:/Program Files/PostgreSQL/18/bin' }
if (-not (Test-Path (Join-Path $dataPath 'PG_VERSION'))) { throw 'ASA cluster is not initialized.' }
if ($Action -eq 'start') {
    & (Join-Path $pgBin 'pg_ctl.exe') -D $dataPath -l (Join-Path $repoRoot '.local/postgres.log') -w start
} elseif ($Action -eq 'stop') {
    & (Join-Path $pgBin 'pg_ctl.exe') -D $dataPath -m fast -w stop
} else {
    & (Join-Path $pgBin 'pg_ctl.exe') -D $dataPath status
}
if ($LASTEXITCODE -ne 0) { throw "ASA database $Action returned $LASTEXITCODE" }

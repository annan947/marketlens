# Explicit lightweight development alternative; Docker uses PostgreSQL instead.
param([int]$ApiPort = 8001, [int]$WebPort = 5174)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$data = Join-Path $root 'data'
$logs = Join-Path $root 'work\servers'
$temporary = Join-Path $root 'work\temp'
New-Item -ItemType Directory -Force $data,$logs,$temporary | Out-Null
$env:TEMP = $temporary
$env:TMP = $temporary
$env:MARKETLENS_DATABASE_URL = 'sqlite:///' + ((Join-Path $data 'marketlens-dev.db') -replace '\\','/')
$env:MARKETLENS_DEV_API_URL = "http://127.0.0.1:$ApiPort"
foreach ($port in @($ApiPort, $WebPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is in use. Stop your previous MarketLens server or choose another port."
    }
}
Push-Location $root
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed; servers were not started.' }
    $api = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',$ApiPort -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs\api.log" -RedirectStandardError "$logs\api-error.log"
    $vite = Join-Path $root 'frontend\node_modules\vite\bin\vite.js'
    $web = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList "`"$vite`"",'--host','127.0.0.1','--port',$WebPort,'--strictPort' -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs\web.log" -RedirectStandardError "$logs\web-error.log"
    Write-Output "Started API process $($api.Id), frontend process $($web.Id)."
    Write-Output "Open http://127.0.0.1:$WebPort . Logs: $logs . Database: $data\marketlens-dev.db"
} finally { Pop-Location }

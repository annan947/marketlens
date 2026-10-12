$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot '.env'
if (Test-Path -LiteralPath $target) {
    Write-Output 'Existing deploy/.env preserved.'
    exit 0
}
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 32
$random.GetBytes($bytes)
$random.Dispose()
$password = ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
[IO.File]::WriteAllText($target, "POSTGRES_PASSWORD=$password`nMARKETLENS_WEB_PORT=8080`n")
Write-Output 'Created deploy/.env. Password contents were not printed. Keep this file private.'

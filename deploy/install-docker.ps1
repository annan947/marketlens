# Approved system setup. Run from an Administrator PowerShell window.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$installer = Join-Path $root 'downloads\Docker Desktop Installer.exe'
$signature = Get-AuthenticodeSignature -LiteralPath $installer
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Docker') {
    throw 'Installer signature is not valid for Docker. Do not execute it.'
}
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from Windows PowerShell as Administrator. It does not self-elevate.'
}
$env:TEMP = Join-Path $root 'work\temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
$arguments = @('install', "--installation-dir=$root\tools\Docker", '--backend=wsl-2', "--wsl-default-data-root=$root\data\docker-wsl")
$process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -notin @(0, 3010)) { throw "Docker installer exited with code $($process.ExitCode)." }
Write-Output 'Installer finished. Open Docker Desktop to complete setup and review its license.'
Write-Output 'Verify the main disk location is on D: before pulling images. Windows/WSL may require a restart.'

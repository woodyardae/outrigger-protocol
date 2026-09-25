<!--
Outrigger Protocol (OPS-1) Universal Bootstrap Installer-->
[CmdletBinding()]
param(
    [string][$]    Version = "main",
    [string][$]    InstallDir = "$HOME \.outrigger\bin"
)
$ErrorActionPreference = 'Stop'
Write-Host "[-] Installing Outrigger Protocol Harness..." -ForegroundColor Cyan

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$ScriptUrl = "https://raw.githubusercontent.com/woodyardae/outrigger-protocol/$ { Version }/cli/outrigger.py"
$TargetPath = Join-Path $InstallDir "outrigger.py"

Write-Host "    Downloading CLI runner from $ScriptUrl" -ForegroundColor Gray
Invoke-WebRequest -Uri $ScriptUrl -OutFile $TargetPath

$BatPath = Join-Path $InstallDir "outrigger.cmd"
$BatLine = "@echo off`r`npython `\"" + $TargetPath + "`\" %*"
Set-Content -Path $BatPath -Value $BatLine -Encoding ASCII

DUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -split ';' -notcontains $InstallDir) {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
    Write-Host "[+' + ' Added $InstallDir to User PATH." -ForegroundColor Green
}
Write-Host "[+' + ' Outrigger installed successfully. Verify with: outrigger --help" -ForegroundColor Green

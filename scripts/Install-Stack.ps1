param([string]$Distro = 'AlmaLinux-9.6', [string]$LinuxUser = 'root')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$linuxRepo = & wsl.exe -d $Distro -u $LinuxUser --exec wslpath -a -u $repo
if ($LASTEXITCODE -ne 0) { throw 'wslpath failed' }
$linuxRepo = ([string]($linuxRepo | Select-Object -Last 1)).Trim()
& wsl.exe -d $Distro -u $LinuxUser --exec bash "$linuxRepo/scripts/bootstrap.sh"
if ($LASTEXITCODE -ne 0) { throw 'Installation failed; inspect the command output' }

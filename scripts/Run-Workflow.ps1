param([string]$Distro = 'AlmaLinux-9.6', [string]$LinuxUser = 'root', [string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$argsForRun = @()
if ($OutputDirectory) {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $linuxOut = & wsl.exe -d $Distro -u $LinuxUser --exec wslpath -a -u (Resolve-Path -LiteralPath $OutputDirectory).Path
    if ($LASTEXITCODE -ne 0) { throw 'wslpath failed' }
    $argsForRun += ([string]($linuxOut | Select-Object -Last 1)).Trim()
}
& wsl.exe -d $Distro -u $LinuxUser --cd $repo --exec bash scripts/run.sh @argsForRun
if ($LASTEXITCODE -ne 0) { throw 'Workflow failed; inspect the logs in the result directory' }

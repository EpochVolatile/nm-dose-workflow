param([string]$RunDirectory, [string]$Distro = 'AlmaLinux-9.6', [string]$LinuxUser = 'root')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not $RunDirectory) {
    $RunDirectory = & wsl.exe -d $Distro -u $LinuxUser --exec bash -c 'ls -dt "$HOME"/sim-data/nm-dose-workflow/*/dosimetry.mrb 2>/dev/null | head -1'
    if ($LASTEXITCODE -ne 0 -or -not $RunDirectory) { throw 'No saved dosimetry.mrb found; pass -RunDirectory' }
    $scene = ([string]($RunDirectory | Select-Object -Last 1)).Trim()
} elseif ($RunDirectory.StartsWith('/')) {
    $scene = $RunDirectory.TrimEnd('/') + '/dosimetry.mrb'
} else {
    $path = (Resolve-Path -LiteralPath $RunDirectory).Path
    $linuxPath = & wsl.exe -d $Distro -u $LinuxUser --exec wslpath -a -u $path
    if ($LASTEXITCODE -ne 0) { throw 'wslpath failed' }
    $scene = ([string]($linuxPath | Select-Object -Last 1)).Trim().TrimEnd('/') + '/dosimetry.mrb'
}
& wsl.exe -d $Distro -u $LinuxUser --cd $repo --exec bash scripts/slicer.sh $scene
if ($LASTEXITCODE -ne 0) { throw 'Slicer failed to launch' }

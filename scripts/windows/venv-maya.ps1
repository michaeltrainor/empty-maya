# Create .venv.maya from Maya's python and install debugpy into it.
#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Show-Usage {
    @'
Usage: venv-maya.ps1 [VERSION] [--dry-run] [--force] [--help]

Create .venv.maya with Maya's python and install debugpy into it.
The project .venv is left unchanged. debugpy is not a dependency of mtmaya.

Arguments:
  VERSION     Maya year to target (default: 2027)

Options:
  --dry-run   Print the uv commands without writing .venv.maya
  --force     Replace an existing .venv.maya
  --help      Show this help

Environment:
  MAYA_LOCATION   If set, use $MAYA_LOCATION\bin instead of the default
                  $Env:ProgramFiles\Autodesk\MayaVERSION\bin
  UV_PYTHON       If set, it must be Maya's python.exe next to mayapy.exe.
                  Otherwise the script sets it for `uv venv` only.

The python.exe symlink comes from scripts/windows/link-mayapy.ps1.
This script does not put Maya's bin on PATH, does not install into Maya's
site-packages, and does not install PyPI PySide6.
'@
}

function Write-ErrorLine {
    param([string]$Message)
    [Console]::Error.WriteLine("error: $Message")
}

function Test-MayapyLink {
    param(
        [string]$PythonLink,
        [string]$Mayapy
    )
    if (-not (Test-Path -LiteralPath $PythonLink)) {
        return $false
    }
    $item = Get-Item -LiteralPath $PythonLink -Force
    $reparse = [IO.FileAttributes]::ReparsePoint
    if (($item.Attributes -band $reparse) -eq 0 -or $item.LinkType -ne "SymbolicLink") {
        return $false
    }
    foreach ($target in @($item.Target)) {
        $name = [IO.Path]::GetFileName($target)
        if ($name -eq "mayapy.exe" -or $target -eq $Mayapy) {
            return $true
        }
    }
    return $false
}

function Format-UvCommand {
    param([string[]]$Arguments)
    $parts = New-Object System.Collections.Generic.List[string]
    $parts.Add("uv")
    foreach ($arg in $Arguments) {
        if ($arg -match '[\s"]') {
            $parts.Add('"' + ($arg -replace '"', '\"') + '"')
        } else {
            $parts.Add($arg)
        }
    }
    return ($parts -join " ")
}

function Assert-DebugpyRequirements {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-ErrorLine "requirements not found at $Path"
        exit 1
    }
    $names = New-Object System.Collections.Generic.List[string]
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#")) {
            continue
        }
        $name = ($trimmed -split '[<>=!;\s\[]', 2)[0]
        if ($name -ne "debugpy") {
            Write-ErrorLine "scripts/maya-debug.txt may only install debugpy (got: $name)"
            exit 1
        }
        $names.Add($name)
    }
    if ($names.Count -eq 0) {
        Write-ErrorLine "scripts/maya-debug.txt does not list debugpy"
        exit 1
    }
}

function Read-CfgValue {
    param(
        [string[]]$Lines,
        [string]$Key
    )
    $prefix = "$Key = "
    foreach ($line in $Lines) {
        if ($line.StartsWith($prefix)) {
            return $line.Substring($prefix.Length).Trim()
        }
    }
    return $null
}

function Assert-VenvIsReplaceable {
    param(
        [string]$RepoRoot,
        [string]$VenvDir,
        [string]$MayaBin
    )
    $root = [IO.Path]::GetFullPath($RepoRoot)
    $target = [IO.Path]::GetFullPath($VenvDir)
    $expected = [IO.Path]::GetFullPath((Join-Path $root ".venv.maya"))
    if (-not $target.Equals($expected, [StringComparison]::OrdinalIgnoreCase)) {
        Write-ErrorLine "refusing to remove $target"
        exit 1
    }
    $mayaFull = [IO.Path]::GetFullPath($MayaBin).TrimEnd('\')
    if ($target.StartsWith($mayaFull + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Write-ErrorLine "refusing to remove a path inside Maya"
        exit 1
    }
    if (Test-Path -LiteralPath $target) {
        $item = Get-Item -LiteralPath $target -Force
        $reparse = [IO.FileAttributes]::ReparsePoint
        if (($item.Attributes -band $reparse) -ne 0) {
            Write-ErrorLine ".venv.maya is a link; refusing to replace it"
            exit 1
        }
    }
}

function Assert-InstallInterpreter {
    param(
        [string]$VenvDir,
        [string]$VenvPython,
        [string]$MayaBin
    )
    $pythonFull = [IO.Path]::GetFullPath($VenvPython)
    $venvFull = [IO.Path]::GetFullPath($VenvDir).TrimEnd('\')
    $mayaFull = [IO.Path]::GetFullPath($MayaBin).TrimEnd('\')
    if (-not $pythonFull.StartsWith($venvFull + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Write-ErrorLine "refusing to install outside .venv.maya ($pythonFull)"
        exit 1
    }
    if ($pythonFull.StartsWith($mayaFull + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $pythonFull.Equals($mayaFull, [StringComparison]::OrdinalIgnoreCase)) {
        Write-ErrorLine "refusing to install into Maya ($pythonFull)"
        exit 1
    }
}

function Invoke-Uv {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [hashtable]$Set = @{},
        [string[]]$Clear = @()
    )
    $names = New-Object System.Collections.Generic.List[string]
    foreach ($name in @($Set.Keys) + @($Clear)) {
        if (-not $names.Contains($name)) {
            $names.Add($name)
        }
    }
    $saved = @{}
    foreach ($name in $names) {
        $saved[$name] = @{
            Had = Test-Path -Path "Env:$name"
            Value = [Environment]::GetEnvironmentVariable($name, "Process")
        }
    }
    try {
        foreach ($name in $Clear) {
            Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        }
        foreach ($entry in $Set.GetEnumerator()) {
            Set-Item -Path "Env:$($entry.Key)" -Value $entry.Value
        }
        & uv @Arguments
        $script:UvExit = $LASTEXITCODE
    } finally {
        foreach ($name in $names) {
            if ($saved[$name].Had) {
                Set-Item -Path "Env:$name" -Value $saved[$name].Value
            } else {
                Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
            }
        }
    }
}

$dryRun = $false
$force = $false
$mayaVersion = "2027"
$sawVersion = $false

foreach ($arg in $args) {
    if ($arg -eq "--help" -or $arg -eq "-h") {
        Show-Usage
        exit 0
    }
    if ($arg -eq "--dry-run") {
        $dryRun = $true
        continue
    }
    if ($arg -eq "--force") {
        $force = $true
        continue
    }
    if ($arg.StartsWith("-")) {
        Write-ErrorLine "unknown option: $arg"
        [Console]::Error.WriteLine((Show-Usage))
        exit 2
    }
    if ($sawVersion) {
        Write-ErrorLine "unexpected argument: $arg"
        exit 2
    }
    $mayaVersion = $arg
    $sawVersion = $true
}

if ($mayaVersion -notmatch '^[0-9]{4}$') {
    Write-ErrorLine "VERSION must be a four-digit Maya year (got: $mayaVersion)"
    exit 2
}

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$venvDir = Join-Path $repoRoot ".venv.maya"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirements = Join-Path $repoRoot "scripts\maya-debug.txt"
$verifier = Join-Path $repoRoot "scripts\verify_maya_venv.py"

if ($env:MAYA_LOCATION) {
    $mayaRoot = $env:MAYA_LOCATION.TrimEnd('\', '/')
    $mayaBin = Join-Path $mayaRoot "bin"
} else {
    $mayaBin = Join-Path $env:ProgramFiles "Autodesk\Maya$mayaVersion\bin"
}

$mayapy = Join-Path $mayaBin "mayapy.exe"
$pythonLink = Join-Path $mayaBin "python.exe"

if (-not (Test-Path -LiteralPath $mayapy)) {
    Write-ErrorLine "mayapy.exe not found at $mayapy"
    Write-ErrorLine "install Maya $mayaVersion or set MAYA_LOCATION"
    exit 1
}

if (-not (Test-Path -LiteralPath $pythonLink)) {
    Write-ErrorLine "python.exe not found at $pythonLink"
    Write-ErrorLine "run scripts/windows/link-mayapy.ps1 to create it"
    exit 1
}

if (-not (Test-MayapyLink -PythonLink $pythonLink -Mayapy $mayapy)) {
    Write-ErrorLine "$pythonLink exists and is not a symlink to mayapy.exe"
    exit 1
}

if ($env:UV_PYTHON) {
    if (-not (Test-Path -LiteralPath $env:UV_PYTHON)) {
        Write-ErrorLine "UV_PYTHON does not exist: $($env:UV_PYTHON)"
        exit 1
    }
    $given = [IO.Path]::GetFullPath($env:UV_PYTHON)
    $expectedPython = [IO.Path]::GetFullPath($pythonLink)
    if (-not $given.Equals($expectedPython, [StringComparison]::OrdinalIgnoreCase)) {
        Write-ErrorLine "UV_PYTHON must be Maya's python.exe next to mayapy.exe ($pythonLink)"
        exit 1
    }
}

Assert-DebugpyRequirements -Path $requirements

if (-not (Test-Path -LiteralPath $verifier)) {
    Write-ErrorLine "verifier not found at $verifier"
    exit 1
}

Assert-VenvIsReplaceable -RepoRoot $repoRoot -VenvDir $venvDir -MayaBin $mayaBin

$venvExists = Test-Path -LiteralPath $venvDir
if ($venvExists -and -not $force) {
    Write-ErrorLine ".venv.maya already exists at $venvDir"
    Write-ErrorLine "re-run with --force to replace it"
    exit 1
}

$venvArgs = @(
    "venv", ".venv.maya",
    "--no-managed-python",
    "--no-python-downloads",
    "--no-project"
)
$pipArgs = @(
    "pip", "install",
    "--python", $venvPython,
    "--no-deps",
    "--requirement", $requirements,
    "--no-managed-python",
    "--no-python-downloads"
)

if ($dryRun) {
    if ($venvExists) {
        Write-Output "dry-run: replace $venvDir"
    }
    Write-Output "directory=$repoRoot"
    Write-Output "UV_PYTHON=$pythonLink"
    Write-Output (Format-UvCommand -Arguments $venvArgs)
    Write-Output (Format-UvCommand -Arguments $pipArgs)
    exit 0
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-ErrorLine "uv is not on PATH"
    exit 1
}

if ($venvExists) {
    Remove-Item -LiteralPath $venvDir -Recurse -Force
}

Push-Location -LiteralPath $repoRoot
try {
    Invoke-Uv -Arguments $venvArgs -Set @{ UV_PYTHON = $pythonLink } -Clear @("UV_MANAGED_PYTHON", "VIRTUAL_ENV")
    if ($script:UvExit -ne 0) {
        exit $script:UvExit
    }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-ErrorLine "uv venv did not create $venvPython"
    exit 1
}

$cfgPath = Join-Path $venvDir "pyvenv.cfg"
if (-not (Test-Path -LiteralPath $cfgPath)) {
    Write-ErrorLine "pyvenv.cfg is missing from .venv.maya"
    exit 1
}
$cfg = @(Get-Content -LiteralPath $cfgPath)
$cfgHome = Read-CfgValue -Lines $cfg -Key "home"
$systemSite = Read-CfgValue -Lines $cfg -Key "include-system-site-packages"
if ($null -eq $cfgHome -or
    -not ([IO.Path]::GetFullPath($cfgHome)).Equals(
        [IO.Path]::GetFullPath($mayaBin),
        [StringComparison]::OrdinalIgnoreCase
    )) {
    Write-ErrorLine ".venv.maya was not created from Maya's python"
    exit 1
}
if ($systemSite -ne "false") {
    Write-ErrorLine ".venv.maya must not include system site-packages"
    exit 1
}

Assert-InstallInterpreter -VenvDir $venvDir -VenvPython $venvPython -MayaBin $mayaBin

Invoke-Uv -Arguments $pipArgs -Clear @("UV_PYTHON", "UV_SYSTEM_PYTHON", "UV_MANAGED_PYTHON", "VIRTUAL_ENV")
if ($script:UvExit -ne 0) {
    Write-ErrorLine "debugpy install failed"
    exit $script:UvExit
}

$savedVenvDir = $env:MTMAYA_VENV_DIR
$savedMayaBin = $env:MTMAYA_MAYA_BIN
$hadVenvDir = Test-Path -Path "Env:MTMAYA_VENV_DIR"
$hadMayaBin = Test-Path -Path "Env:MTMAYA_MAYA_BIN"
try {
    $env:MTMAYA_VENV_DIR = $venvDir
    $env:MTMAYA_MAYA_BIN = $mayaBin
    & $venvPython $verifier
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    if ($hadVenvDir) { $env:MTMAYA_VENV_DIR = $savedVenvDir } else { Remove-Item -Path "Env:MTMAYA_VENV_DIR" -ErrorAction SilentlyContinue }
    if ($hadMayaBin) { $env:MTMAYA_MAYA_BIN = $savedMayaBin } else { Remove-Item -Path "Env:MTMAYA_MAYA_BIN" -ErrorAction SilentlyContinue }
}

Write-Output "created $venvDir"

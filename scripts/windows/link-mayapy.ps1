# Create Autodesk's required python.exe -> mayapy.exe symlink so uv can use Maya's interpreter.
#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Show-Usage {
    @'
Usage: link-mayapy.ps1 [VERSION] [--dry-run] [--help]

Create a python.exe symlink next to mayapy.exe in Maya's bin directory (Windows).
uv and venv require an executable named python; mayapy.exe alone is not enough.

Arguments:
  VERSION     Maya year to target (default: 2027)

Options:
  --dry-run   Print the symlink command without creating it
  --help      Show this help

Environment:
  MAYA_LOCATION   If set, use $MAYA_LOCATION\bin instead of the default
                  $Env:ProgramFiles\Autodesk\MayaVERSION\bin
'@
}

function Write-ErrorLine {
    param([string]$Message)
    [Console]::Error.WriteLine("error: $Message")
}

$dryRun = $false
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

function Test-MayapyLink {
    if (-not (Test-Path -LiteralPath $pythonLink)) {
        return $false
    }
    $item = Get-Item -LiteralPath $pythonLink -Force
    $reparse = [IO.FileAttributes]::ReparsePoint
    if (($item.Attributes -band $reparse) -eq 0 -or $item.LinkType -ne "SymbolicLink") {
        return $false
    }
    foreach ($target in @($item.Target)) {
        $name = [IO.Path]::GetFileName($target)
        if ($name -eq "mayapy.exe" -or $target -eq $mayapy) {
            return $true
        }
    }
    return $false
}

function Write-UvHints {
    Write-Output "UV_PYTHON=$pythonLink"
    Write-Output "uv venv --python `"$pythonLink`""
    Write-Output ('$env:UV_PYTHON = "{0}"' -f $pythonLink)
}

if (Test-MayapyLink) {
    Write-Output "python.exe already links to mayapy.exe: $pythonLink"
    if (-not $dryRun) {
        & $pythonLink -c "import sys; print(sys.version)"
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    Write-UvHints
    exit 0
}

if (Test-Path -LiteralPath $pythonLink) {
    Write-ErrorLine "$pythonLink exists and is not a symlink to mayapy.exe"
    exit 1
}

if ($dryRun) {
    Write-Output "dry-run: New-Item -ItemType SymbolicLink -Path '$pythonLink' -Target 'mayapy.exe'"
    Write-UvHints
    exit 0
}

Push-Location -LiteralPath $mayaBin
try {
    New-Item -ItemType SymbolicLink -Name "python.exe" -Target "mayapy.exe" | Out-Null
} catch {
    Write-ErrorLine "failed to create $pythonLink -> mayapy.exe"
    Write-ErrorLine $_.Exception.Message
    Write-ErrorLine "re-run this script from an elevated PowerShell when Maya is installed under Program Files"
    exit 1
} finally {
    Pop-Location
}

if (-not (Test-MayapyLink)) {
    Write-ErrorLine "failed to create $pythonLink -> mayapy.exe"
    exit 1
}

Write-Output "created $pythonLink -> mayapy.exe"
& $pythonLink -c "import sys; print(sys.version)"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
Write-UvHints

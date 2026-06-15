param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter(Mandatory = $true)]
    [string]$InputExe,

    [string]$OutputDir = "dist\desktop",

    [string]$LicenseFile = "LICENSE",

    [string]$SetupIconFile = "svg_to_drawio_desktop\assets\app_logo.ico"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$resolvedExe = Resolve-Path $InputExe
$resolvedOutputDir = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDir))
$installerScript = Join-Path $repoRoot "packaging\windows\svg-to-drawio.iss"
$licensePath = Join-Path $repoRoot $LicenseFile
$iconPath = Join-Path $repoRoot $SetupIconFile

New-Item -ItemType Directory -Force -Path $resolvedOutputDir | Out-Null

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$isccPath = $null
if ($iscc) {
    $isccPath = $iscc.Source
} else {
    $defaultIsccPath = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    if (Test-Path $defaultIsccPath) {
        $isccPath = $defaultIsccPath
    }
}

if (-not $isccPath) {
    throw "ISCC.exe was not found in PATH or the default Inno Setup install directory."
}

$arguments = @(
    "/DMyAppVersion=$Version",
    "/DMyAppSourceExe=$resolvedExe",
    "/DMyOutputDir=$resolvedOutputDir"
)

if (Test-Path $licensePath) {
    $arguments += "/DMyLicenseFile=$licensePath"
}

if (Test-Path $iconPath) {
    $arguments += "/DMySetupIconFile=$iconPath"
}

$arguments += $installerScript

Write-Host "Building Windows installer with Inno Setup..."
& $isccPath $arguments

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compiler failed with exit code $LASTEXITCODE."
}

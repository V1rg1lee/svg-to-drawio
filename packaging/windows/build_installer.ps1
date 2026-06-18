[CmdletBinding(DefaultParameterSetName = "Exe")]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter(Mandatory = $true, ParameterSetName = "Exe")]
    [string]$InputExe,

    [Parameter(Mandatory = $true, ParameterSetName = "Dir")]
    [string]$InputDir,

    [string]$OutputDir = "dist\desktop",

    [string]$LicenseFile = "LICENSE",

    [string]$SetupIconFile = "svg_to_drawio_desktop\assets\app_logo.ico",

    [ValidateSet("x64", "arm64")]
    [string]$PackageArchitecture = "x64"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$resolvedOutputDir = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDir))
$installerScript = Join-Path $repoRoot "packaging\windows\svg-to-drawio.iss"
$licensePath = Join-Path $repoRoot $LicenseFile
$iconPath = Join-Path $repoRoot $SetupIconFile
$resolvedExe = $null
$resolvedInputDir = $null

if ($PSCmdlet.ParameterSetName -eq "Exe") {
    $resolvedExe = Resolve-Path $InputExe
} else {
    $resolvedInputDir = Resolve-Path $InputDir
}

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
    "/DMyOutputDir=$resolvedOutputDir",
    "/DMyPackageArchitecture=$PackageArchitecture"
)

if ($PackageArchitecture -eq "arm64") {
    $arguments += "/DMyArchitecturesAllowed=arm64"
    $arguments += "/DMyArchitecturesInstallIn64BitMode=arm64"
} else {
    $arguments += "/DMyArchitecturesAllowed=x64compatible"
    $arguments += "/DMyArchitecturesInstallIn64BitMode=x64compatible"
}

if ($resolvedExe) {
    $arguments += "/DMyAppSourceExe=$resolvedExe"
}

if ($resolvedInputDir) {
    $arguments += "/DMyAppSourceDir=$resolvedInputDir"
}

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

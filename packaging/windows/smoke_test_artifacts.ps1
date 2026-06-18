[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter(Mandatory = $true)]
    [ValidateSet("x64", "arm64")]
    [string]$PackageArchitecture
)

$ErrorActionPreference = "Stop"

function Invoke-SmokeTestExecutable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath
    )

    if (-not (Test-Path $ExecutablePath)) {
        throw "Smoke-test executable not found: $ExecutablePath"
    }

    $process = Start-Process -FilePath $ExecutablePath -ArgumentList "--smoke-test" -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Smoke test failed for $ExecutablePath with exit code $($process.ExitCode)."
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$releaseDir = Join-Path $repoRoot "dist\release"
$zipPath = Join-Path $releaseDir "svg-to-drawio-$Version-windows-$PackageArchitecture.zip"
$setupPath = Join-Path $releaseDir "svg-to-drawio-$Version-windows-$PackageArchitecture-setup.exe"

if (-not (Test-Path $zipPath)) {
    throw "Windows ZIP artifact not found: $zipPath"
}
if (-not (Test-Path $setupPath)) {
    throw "Windows setup artifact not found: $setupPath"
}

$extractRoot = Join-Path $env:RUNNER_TEMP "svg-to-drawio-zip-$PackageArchitecture"
$installRoot = Join-Path $env:RUNNER_TEMP "svg-to-drawio-installed-$PackageArchitecture"

if (Test-Path $extractRoot) {
    Remove-Item -LiteralPath $extractRoot -Recurse -Force
}
if (Test-Path $installRoot) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
}

Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force
Invoke-SmokeTestExecutable -ExecutablePath (Join-Path $extractRoot "svg-to-drawio.exe")

$installer = Start-Process `
    -FilePath $setupPath `
    -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/DIR=$installRoot") `
    -Wait `
    -PassThru
if ($installer.ExitCode -ne 0) {
    throw "Installer smoke test failed with exit code $($installer.ExitCode)."
}

Invoke-SmokeTestExecutable -ExecutablePath (Join-Path $installRoot "svg-to-drawio.exe")

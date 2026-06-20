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
$portableExePath = Join-Path $releaseDir "svg-to-drawio-$Version-windows-$PackageArchitecture.exe"
$setupPath = Join-Path $releaseDir "svg-to-drawio-$Version-windows-$PackageArchitecture-setup.exe"

if (-not (Test-Path $portableExePath)) {
    throw "Windows portable executable artifact not found: $portableExePath"
}
if (-not (Test-Path $setupPath)) {
    throw "Windows setup artifact not found: $setupPath"
}

$installRoot = Join-Path $env:RUNNER_TEMP "svg-to-drawio-installed-$PackageArchitecture"

if (Test-Path $installRoot) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
}

Invoke-SmokeTestExecutable -ExecutablePath $portableExePath

$installer = Start-Process `
    -FilePath $setupPath `
    -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/DIR=$installRoot") `
    -Wait `
    -PassThru
if ($installer.ExitCode -ne 0) {
    throw "Installer smoke test failed with exit code $($installer.ExitCode)."
}

Invoke-SmokeTestExecutable -ExecutablePath (Join-Path $installRoot "svg-to-drawio.exe")

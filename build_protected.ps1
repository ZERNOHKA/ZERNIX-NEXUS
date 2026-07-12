# ZERNIX protected release build.
#
# Single source of truth for application logic:
#   - main.py, licensing.py, app\, core\, ui\  (repository root)
# This script wipes .secure_build\, regenerates .secure_build\obf\ from those paths via PyArmor, then compiles with Nuitka.
#
# Parameters:
#   -StrictObfuscation  Fail the build if PyArmor falls back to copying plain main.py and/or plain core\ + ui\
#                       (trial limits / errors). Use for release pipelines so partial protection cannot ship unnoticed.

param(
    [switch]$StrictObfuscation
)

$ErrorActionPreference = "Stop"

function Assert-StepSuccess {
    param(
        [string]$StepName
    )
    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE"
    }
}

Write-Host "== ZERNIX Protected Build ==" -ForegroundColor Cyan
if ($StrictObfuscation) {
    Write-Host "StrictObfuscation: ON (fallback paths will fail the build)" -ForegroundColor Yellow
}

python -m pip install --upgrade pip
Assert-StepSuccess "pip upgrade"
python -m pip install --upgrade pyarmor nuitka ordered-set zstandard
Assert-StepSuccess "dependency install"
$pythonExe = (Get-Command python).Source
$pythonDir = Split-Path $pythonExe -Parent
$pyarmorExe = Join-Path $pythonDir "Scripts\pyarmor.exe"
if (-not (Test-Path $pyarmorExe)) {
    $pyarmorExe = "pyarmor"
}

if (Test-Path "dist_protected") { Remove-Item "dist_protected" -Recurse -Force }
if (Test-Path "build_protected") { Remove-Item "build_protected" -Recurse -Force }
if (Test-Path ".secure_build") { Remove-Item ".secure_build" -Recurse -Force }

New-Item -ItemType Directory -Path ".secure_build" | Out-Null

Write-Host "Step 1/3: Obfuscating sources with PyArmor..." -ForegroundColor Yellow
$sourceEntry = ".secure_build\obf\main.py"
$ObfuscationFallbackUsed = $false
& $pyarmorExe gen --recursive --output ".secure_build\obf" "main.py" "licensing.py" "app" "core" "ui"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $sourceEntry) -or -not (Test-Path ".secure_build\obf\licensing.py") -or -not (Test-Path ".secure_build\obf\app\actions.py")) {
    $ObfuscationFallbackUsed = $true
    Write-Warning "Full PyArmor obfuscation failed, likely because trial PyArmor cannot process the large main.py. Retrying critical modules only."
    if (Test-Path ".secure_build\obf") { Remove-Item ".secure_build\obf" -Recurse -Force }
    & $pyarmorExe gen --recursive --output ".secure_build\obf" "licensing.py" "app" "core" "ui"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path ".secure_build\obf\licensing.py") -or -not (Test-Path ".secure_build\obf\app\actions.py")) {
        Write-Warning "Critical module obfuscation hit the PyArmor trial limit. Retrying licensing.py only."
        if (Test-Path ".secure_build\obf") { Remove-Item ".secure_build\obf" -Recurse -Force }
        & $pyarmorExe gen --output ".secure_build\obf" "licensing.py"
        Assert-StepSuccess "licensing PyArmor obfuscation"
        Copy-Item "app" ".secure_build\obf\app" -Recurse -Force
        Copy-Item "core" ".secure_build\obf\core" -Recurse -Force
        Copy-Item "ui" ".secure_build\obf\ui" -Recurse -Force
    }
    Copy-Item "main.py" $sourceEntry -Force
}
if (-not (Test-Path ".secure_build\obf\licensing.py")) {
    throw "PyArmor did not obfuscate licensing.py"
}
if (-not (Test-Path ".secure_build\obf\app\actions.py")) {
    throw "Application package is missing from the protected build workspace"
}
if ($StrictObfuscation -and $ObfuscationFallbackUsed) {
    Write-Error "StrictObfuscation: PyArmor used a fallback (plain main.py and/or plain app\core\ui). Aborting release build."
    exit 2
}
if ($ObfuscationFallbackUsed) {
    Write-Warning "PyArmor fallback was used; review protection level before distributing this build."
}
Write-Host "PyArmor obfuscation: OK" -ForegroundColor Green

Write-Host "Step 2/3: Building onefile EXE with Nuitka..." -ForegroundColor Yellow
python -m nuitka `
  --onefile `
  --standalone `
  --enable-plugin=tk-inter `
  --windows-icon-from-ico="assets\logotip.ico" `
  --windows-uac-admin `
  --windows-console-mode=disable `
  --assume-yes-for-downloads `
  --remove-output `
  --lto=yes `
  --output-dir="dist_protected" `
  --output-filename="ZERNIX_v3_PROTECTED.exe" `
  --include-package="customtkinter" `
  --include-package="cryptography" `
  --include-package="PIL" `
  --include-package="requests" `
  --include-package="wmi" `
  --include-data-dir="assets=assets" `
  --nofollow-import-to="build_integrity_manifest" `
  --nofollow-import-to="check_license" `
  --nofollow-import-to="win32security" `
  $sourceEntry
Assert-StepSuccess "nuitka build"

Write-Host "Step 3/3: Writing integrity manifest..." -ForegroundColor Yellow
$exePath = Join-Path "dist_protected" "ZERNIX_v3_PROTECTED.exe"
if (-not (Test-Path $exePath)) {
    throw "Built EXE not found: $exePath"
}
python build_integrity_manifest.py $exePath (Join-Path "dist_protected" "zernix.integrity.json")
Assert-StepSuccess "integrity manifest"

Write-Host "Build complete." -ForegroundColor Green
Write-Host "Output: dist_protected\ZERNIX_v3_PROTECTED.exe"
Write-Host "Integrity: dist_protected\zernix.integrity.json"
Write-Host "Note: keep release signing keys outside the repository."

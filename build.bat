@echo off
cls
echo === ZERNIX BUILD SYSTEM ===

echo [1/4] Killing existing processes...
taskkill /f /im ZERNIX_v3_PRO.exe >nul 2>&1

echo [2/4] Cleaning old build files...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [3/5] Running PyInstaller...
pyinstaller --noconfirm "ZERNIX_v3_Pro.spec"
if errorlevel 1 exit /b 1

echo [4/5] Writing signed integrity manifest...
python build_integrity_manifest.py "dist\ZERNIX_v3_PRO.exe" "dist\zernix.integrity.json"
if errorlevel 1 exit /b 1

echo [5/5] Build complete!
echo Your file is in the "dist" folder.
pause
@echo off
set ZERNIX_PORTFOLIO_MODE=1
where python >nul 2>&1
if %errorlevel%==0 (
    python main.py --demo
) else (
    py -3 main.py --demo
)
pause

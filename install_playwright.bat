@echo off
REM Install Playwright for Home Assistant Green Button integration
REM Run this from Home Assistant Terminal add-on (Windows version)

echo Installing Playwright for Green Button integration...
echo.

REM Try to install with pip
pip install playwright
if %errorlevel% equ 0 (
    echo.
    echo Installing Chromium browser...
    playwright install chromium
    if %errorlevel% equ 0 (
        echo.
        echo Success! Playwright installed.
        echo.
        echo Next steps:
        echo 1. Restart Home Assistant
        echo 2. Go to Settings ^> Devices ^& Services
        echo 3. Click 'Create Integration'
        echo 4. Search for 'Green Button'
        echo 5. Enter your Eversource credentials
        pause
        exit /b 0
    )
)

REM Try python -m pip if pip failed
echo.
echo Trying python -m pip...
python -m pip install playwright
if %errorlevel% equ 0 (
    python -m pip install playwright install chromium
    echo.
    echo Success! Playwright installed.
    pause
    exit /b 0
)

echo.
echo ERROR: Could not install Playwright
echo.
echo Home Assistant OS may have pip access restricted.
echo.
echo Try these alternatives:
echo 1. Switch to Home Assistant Container (Docker) for more control
echo 2. Run Home Assistant in a virtual environment with pip access
echo 3. Contact Home Assistant community for ARM64 musl support
echo.
pause
exit /b 1

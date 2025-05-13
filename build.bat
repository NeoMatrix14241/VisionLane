@echo off

title Build VisionLane Application
REM --------------------------------------------------------
REM VisionLane Build Script
REM --------------------------------------------------------

REM This script is used to build the VisionLane application using PyInstaller.
REM It cleans up any previous builds and then creates a new build.
REM Make sure to run this script from the command line with administrative privileges.
REM This script assumes that you have PyInstaller installed in a virtual environment located at .\.venv\Scripts\pyinstaller
REM and that the build.spec file is located in the same directory as this script.
REM This script is intended for use on Windows systems.
REM --------------------------------------------------------
REM Filepath:
REM .\build.bat
REM .\build.spec
REM .\.venv\Scripts\pyinstaller

echo Cleaning up old build...
rmdir /s /q build dist 2>nul
echo Building application...
.\.venv\Scripts\pyinstaller --clean build.spec
if %ERRORLEVEL% NEQ 0 (
    echo Build failed! Check the error messages above.
    echo This might be due to an incorrect spec file configuration.
    pause
    exit /b 1
)
echo Build complete!
pause
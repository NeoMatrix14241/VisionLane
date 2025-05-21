@echo off

title App Builder: VisionLane OCR Application
REM --------------------------------------------------------
REM VisionLane Build Script
REM --------------------------------------------------------

REM This script is used to build the VisionLane application using PyInstaller.
REM It cleans up any previous builds and then creates a new build.
REM This script assumes that you have PyInstaller installed in a virtual environment located at .\.venv\Scripts\pyinstaller
REM and that the build.spec file is located in the same directory as this script.
REM This script is intended for use on Windows systems.
REM --------------------------------------------------------
REM Filepath (Assume relative path to this script):
REM .\build.bat
REM .\build.spec
REM .\.venv\Scripts\pyinstaller

REM Clean old build artifacts
echo Cleaning up old build...
rmdir /s /q "%~dp0build" 2>nul
rmdir /s /q "%~dp0dist" 2>nul

REM Ensure models are downloaded first
echo Downloading DocTR models if not present...
.\.venv\Scripts\python.exe verify_models.py

IF %ERRORLEVEL% NEQ 0 (
    echo Failed to download doctr models. Aborting build.
    pause
    exit /b 1
)

REM then tart PyInstaller build
echo Building application with PyInstaller...
.\.venv\Scripts\pyinstaller --clean build.spec

IF %ERRORLEVEL% NEQ 0 (
    echo Build failed! Check the error messages above.
    pause
    exit /b 1
) ELSE (
    echo Build complete!
    pause
)
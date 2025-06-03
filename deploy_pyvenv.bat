@echo off
setlocal enabledelayedexpansion

title VisionLane OCR - Virtual Environment Setup
echo ========================================
echo VisionLane OCR Virtual Environment Setup
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and add it to your PATH
    echo.
    pause
    exit /b 1
)

echo Python found. Creating virtual environment...

REM Remove existing virtual environment if it exists
if exist ".venv" (
    echo Removing existing virtual environment...
    rmdir /s /q .venv 2>nul
)

REM Create virtual environment
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    echo Please check your Python installation and permissions
    echo.
    pause
    exit /b 1
)

echo Virtual environment created successfully.
echo.

REM Check if requirements.txt exists
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found
    echo Please ensure requirements.txt is in the same directory as this script
    echo.
    pause
    exit /b 1
)

echo Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo WARNING: Failed to upgrade pip, continuing anyway...
)

echo.
echo Installing requirements from requirements.txt...
.venv\Scripts\python.exe -m pip install -r requirements.txt --upgrade
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    echo Please check your requirements.txt file and internet connection
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Virtual environment setup completed successfully!
echo ========================================
echo.
echo To activate the virtual environment manually, run:
echo   .venv\Scripts\activate
echo.
echo To run the application with created virtual environment, use:
echo   .venv\Scripts\python main.py
echo.
echo Or use the build script:
echo   build_nuitka.bat --> for nuitka
echo   build_pyinstaller.bat --> for pyinstaller
echo.
echo Press any key to exit...
pause >nul
@echo off
setlocal enabledelayedexpansion

echo Cleaning up Python cache and virtual environment...
echo.

REM Remove virtual environment
if exist ".venv" (
    echo Removing virtual environment (.venv)...
    rmdir /s /q ".venv" 2>nul
    if exist ".venv" (
        echo Warning: Some .venv files may be in use. Try closing Python processes.
    ) else (
        echo .venv removed successfully.
    )
) else (
    echo No .venv directory found.
)

REM Remove all __pycache__ directories recursively
echo.
echo Removing __pycache__ directories...
for /f "delims=" %%d in ('dir /s /b /ad "__pycache__" 2^>nul') do (
    echo Removing: %%d
    rmdir /s /q "%%d" 2>nul
)

REM Remove .pyc files
echo.
echo Removing .pyc files...
for /f "delims=" %%f in ('dir /s /b "*.pyc" 2^>nul') do (
    echo Removing: %%f
    del /f /q "%%f" 2>nul
)

REM Remove .pyo files
echo.
echo Removing .pyo files...
for /f "delims=" %%f in ('dir /s /b "*.pyo" 2^>nul') do (
    echo Removing: %%f
    del /f /q "%%f" 2>nul
)

echo.
echo Cleanup completed!
echo You can now recreate your virtual environment with: python -m venv .venv
echo.
pause
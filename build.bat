REM filepath: e:\VisionLane\build.bat
@echo off
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
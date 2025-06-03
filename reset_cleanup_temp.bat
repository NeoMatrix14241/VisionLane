@echo off
REM This script cleans up temporary files and directories
rmdir /s /q "%~dp0temp_binaries" 2>nul
rmdir /s /q "%~dp0logs" 2>nul
rmdir /s /q "%~dp0dist_nuitka" 2>nul
rmdir /s /q "%~dp0dist_pyinstaller" 2>nul
del /q "%~dp0pylint_cleanup.log" 2>nul
del /q "%~dp0temp_files.txt" 2>nul
echo Cleanup completed.
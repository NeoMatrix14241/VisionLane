@echo off
setlocal enabledelayedexpansion

:: Clean up temp files at the start
del temp_files.txt 2>nul
del temp_module_count.txt 2>nul
del temp_error_count.txt 2>nul
del temp_warning_count.txt 2>nul

:: Set Python and Pip executables to use the virtual environment
set "PYTHON_EXEC=.venv\Scripts\python.exe"
set "PIP_EXEC=.venv\Scripts\pip.exe"

:: Set colors for output
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "BLUE=[34m"
set "RESET=[0m"

echo %BLUE%============================================================%RESET%
echo %BLUE%            VisionLaneOCR - Pylint Code Analysis           %RESET%
echo %BLUE%============================================================%RESET%
echo.

:: Create logs directory if it doesn't exist
if not exist logs mkdir logs

:: Set timestamp for log files
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "timestamp=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,2%-%dt:~10,2%-%dt:~12,2%"

:: Set log file paths
set "log_file=logs\pylint_report_%timestamp%.txt"
set "summary_file=logs\pylint_summary_%timestamp%.txt"
set "json_file=logs\pylint_results_%timestamp%.json"

echo %YELLOW%[INFO]%RESET% Starting Pylint analysis at %date% %time%
echo %YELLOW%[INFO]%RESET% Log files will be saved to:
echo        - Full report: %log_file%
echo        - Summary: %summary_file%
echo        - JSON data: %json_file%
echo.

:: Check if virtual environment is activated
if defined VIRTUAL_ENV (
    echo %GREEN%[INFO]%RESET% Virtual environment detected: %VIRTUAL_ENV%
) else (
    echo %YELLOW%[WARN]%RESET% No virtual environment detected. Consider activating .venv
    echo %YELLOW%[WARN]%RESET% Run: .venv\Scripts\activate
)
echo.

:: Check if Pylint is installed
%PYTHON_EXEC% -m pylint --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%RESET% Pylint not found. Installing from requirements.txt...
    %PIP_EXEC% install pylint==3.3.7
    if errorlevel 1 (
        echo %RED%[ERROR]%RESET% Failed to install Pylint. Exiting.
        pause
        exit /b 1
    )
) else (
    echo %GREEN%[INFO]%RESET% Pylint is installed and ready
    %PYTHON_EXEC% -m pylint --version
)

:: Define directories to exclude
set "EXCLUDE_DIRS=.venv venv build dist __pycache__ .git logs temp .pytest_cache .mypy_cache node_modules"

:: Get list of Python files with exclusions
echo %YELLOW%[INFO]%RESET% Scanning for Python files...
echo %YELLOW%[INFO]%RESET% Excluding directories: %EXCLUDE_DIRS%

if exist .git (
    :: Use git ls-files if in a git repository (respects .gitignore)
    git ls-files "*.py" > temp_files.txt 2>nul
    if errorlevel 1 (
        echo %RED%[ERROR]%RESET% Git command failed, falling back to manual scan...
        goto manual_scan
    ) else (
        echo %GREEN%[INFO]%RESET% Using git ls-files - automatically respects .gitignore
    )
) else (
    :manual_scan
    echo %YELLOW%[WARN]%RESET% No git repository detected, using manual exclusions...
    (
        for /r %%f in (*.py) do (
            set "file_path=%%f"
            set "skip_file=false"
            
            for %%d in (%EXCLUDE_DIRS%) do (
                echo !file_path! | findstr /i "\\%%d\\" >nul && set "skip_file=true"
            )
            
            if "!skip_file!"=="false" echo %%f
        )
    ) > temp_files.txt
)

:: Count Python files
set /a file_count=0
for /f %%i in (temp_files.txt) do set /a file_count+=1

if %file_count% equ 0 (
    echo %RED%[ERROR]%RESET% No Python files found to analyze!
    echo %RED%[ERROR]%RESET% Make sure you're in the correct directory.
    pause
    exit /b 1
)

echo %GREEN%[INFO]%RESET% Found %file_count% Python files to analyze
echo.

:: Display some of the files that will be analyzed
echo %BLUE%[FILES]%RESET% Python files to be analyzed:
set /a count=0
for /f %%i in (temp_files.txt) do (
    set /a count+=1
    if !count! leq 10 (
        echo        - %%i
    )
    if !count! equ 11 (
        echo        - ... and %file_count% more files
        goto continue_analysis
    )
)
:continue_analysis
echo.

:: Check if .pylintrc exists
if exist .pylintrc (
    echo %GREEN%[INFO]%RESET% Using custom .pylintrc configuration
) else (
    echo %YELLOW%[WARN]%RESET% No .pylintrc found, using default Pylint configuration
)
echo.

:: Run Pylint with comprehensive logging
echo %BLUE%[RUNNING]%RESET% Executing Pylint analysis...
echo ============================================================ > "%log_file%"
echo VisionLaneOCR Pylint Analysis Report >> "%log_file%"
echo Generated: %date% %time% >> "%log_file%"
echo Python files analyzed: %file_count% >> "%log_file%"
echo Configuration: .pylintrc >> "%log_file%"
echo Minimum score threshold: 6.0 >> "%log_file%"
echo ============================================================ >> "%log_file%"
echo. >> "%log_file%"

:: Create file list for pylint input
set "pylint_files="
for /f %%i in (temp_files.txt) do (
    set "pylint_files=!pylint_files! "%%i""
)

:: Run Pylint with text output
echo %YELLOW%[INFO]%RESET% Running Pylint with text output...
echo [PYLINT ANALYSIS RESULTS] >> "%log_file%"
echo. >> "%log_file%"

if exist .pylintrc (
    %PYTHON_EXEC% -m pylint --rcfile=.pylintrc --output-format=text --reports=yes --score=yes --fail-under=6.0 %pylint_files% >> "%log_file%" 2>&1
) else (
    %PYTHON_EXEC% -m pylint --output-format=text --reports=yes --score=yes --fail-under=6.0 %pylint_files% >> "%log_file%" 2>&1
)

:: Capture return code
set pylint_exit_code=%errorlevel%

:: Generate JSON output for detailed analysis
echo %YELLOW%[INFO]%RESET% Generating JSON output for detailed analysis...
if exist .pylintrc (
    %PYTHON_EXEC% -m pylint --rcfile=.pylintrc --output-format=json --reports=no %pylint_files% > "%json_file%" 2>nul
) else (
    %PYTHON_EXEC% -m pylint --output-format=json --reports=no %pylint_files% > "%json_file%" 2>nul
)

:: Extract score from log file
set "score_line="
for /f "tokens=*" %%a in ('findstr /c:"Your code has been rated at" "%log_file%" 2^>nul') do set "score_line=%%a"

:: Generate summary
echo %YELLOW%[INFO]%RESET% Generating summary report...
(
    echo ============================================================
    echo PYLINT ANALYSIS SUMMARY - VisionLaneOCR
    echo ============================================================
    echo Analysis Date: %date% %time%
    echo Python Files Analyzed: %file_count%
    echo Configuration: %~dp0.pylintrc
    echo Minimum Score Threshold: 6.0
    echo Exit Code: %pylint_exit_code%
    echo ============================================================
    echo.
) > "%summary_file%"

if defined score_line (
    echo SCORE RESULTS: >> "%summary_file%"
    echo %score_line% >> "%summary_file%"
) else (
    echo SCORE RESULTS: Unable to extract score from analysis >> "%summary_file%"
)

(
    echo.
    echo LOG FILES GENERATED:
    echo - Full Report: %log_file%
    echo - JSON Data: %json_file%
    echo - This Summary: %summary_file%
    echo.
    
    echo ISSUE ANALYSIS:
    findstr /c:"************* Module" "%log_file%" | find /c "Module" > temp_module_count.txt
    set /p module_count=<temp_module_count.txt
    del temp_module_count.txt 2>nul
    echo - Modules analyzed: %module_count%
    
    findstr /c:": error " "%log_file%" > nul 2>&1
    if not errorlevel 1 (
        echo - ERRORS: Found critical issues that need attention
        findstr /c:": error " "%log_file%" | find /c ": error " > temp_error_count.txt
        set /p error_count=<temp_error_count.txt
        echo   Count: %error_count%
        del temp_error_count.txt 2>nul
    ) else (
        echo - ERRORS: None found
    )
    
    findstr /c:": warning " "%log_file%" > nul 2>&1
    if not errorlevel 1 (
        echo - WARNINGS: Found potential issues
        findstr /c:": warning " "%log_file%" | find /c ": warning " > temp_warning_count.txt
        set /p warning_count=<temp_warning_count.txt
        echo   Count: %warning_count%
        del temp_warning_count.txt 2>nul
    ) else (
        echo - WARNINGS: None found
    )
    
    findstr /c:": convention " "%log_file%" > nul 2>&1
    if not errorlevel 1 (
        echo - CONVENTIONS: Found style/convention suggestions
    ) else (
        echo - CONVENTIONS: All good
    )
    
    findstr /c:": refactor " "%log_file%" > nul 2>&1
    if not errorlevel 1 (
        echo - REFACTORING: Found improvement suggestions
    ) else (
        echo - REFACTORING: No suggestions
    )
    
    echo.
    echo COMMON ISSUES TO CHECK:
    echo - Import organization and unused imports
    echo - Variable naming conventions
    echo - Function complexity and length
    echo - Missing docstrings
    echo - Code duplication
    echo.
    echo NEXT STEPS:
    echo 1. Review the full report: type "%log_file%"
    echo 2. Focus on errors and warnings first
    echo 3. Consider refactoring suggestions
    echo 4. Update code and re-run analysis
    echo.
    echo ============================================================
) >> "%summary_file%"

:: Clean up temp files
del temp_files.txt 2>nul
del temp_module_count.txt 2>nul
del temp_error_count.txt 2>nul
del temp_warning_count.txt 2>nul

:: Display results
echo.
echo %BLUE%============================================================%RESET%
echo %BLUE%                    ANALYSIS COMPLETE                      %RESET%
echo %BLUE%============================================================%RESET%

if %pylint_exit_code% equ 0 (
    echo %GREEN%[SUCCESS]%RESET% Pylint analysis completed successfully!
    echo %GREEN%[SUCCESS]%RESET% Code quality meets the minimum threshold (6.0)
) else if %pylint_exit_code% equ 1 (
    echo %YELLOW%[COMPLETED]%RESET% Pylint analysis finished with issues found
    echo %YELLOW%[INFO]%RESET% Check the detailed report for improvement suggestions
) else (
    echo %RED%[ERROR]%RESET% Pylint analysis encountered errors (Exit code: %pylint_exit_code%)
    echo %RED%[ERROR]%RESET% Check the log files for details
)

:: Display score if available
if defined score_line (
    echo %BLUE%[SCORE]%RESET% %score_line%
)

echo.
echo %YELLOW%[INFO]%RESET% Analysis results saved to:
echo         Full report: %log_file%
echo         Summary: %summary_file%
echo         JSON data: %json_file%
echo.

:: Quick stats from summary
echo %BLUE%[QUICK STATS]%RESET%
findstr /c:"Python Files Analyzed:" "%summary_file%"
findstr /c:"ERRORS:" "%summary_file%" | findstr /v "None found"
findstr /c:"WARNINGS:" "%summary_file%" | findstr /v "None found"
echo.

:: Ask user if they want to view the summary
set /p view_summary="View detailed summary now? (y/n): "
if /i "%view_summary%"=="y" (
    echo.
    echo %BLUE%============================================================%RESET%
    echo %BLUE%                    DETAILED SUMMARY                       %RESET%
    echo %BLUE%============================================================%RESET%
    type "%summary_file%"
    echo.
)

:: Ask user if they want to open logs folder
set /p open_logs="Open logs folder? (y/n): "
if /i "%open_logs%"=="y" (
    start explorer logs
)

:: Ask user if they want to view the full report
set /p view_report="View full Pylint report? (y/n): "
if /i "%view_report%"=="y" (
    start notepad "%log_file%"
)

echo.
echo %GREEN%[DONE]%RESET% Pylint analysis script completed at %time%
echo %GREEN%[DONE]%RESET% Thank you for maintaining code quality in VisionLaneOCR!
echo.
pause
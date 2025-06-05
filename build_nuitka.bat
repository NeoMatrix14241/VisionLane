@echo off
setlocal enabledelayedexpansion

REM Add error handling to prevent script from closing unexpectedly
set "ORIGINAL_ERRORLEVEL_HANDLING="
if defined ERRORLEVEL set "ORIGINAL_ERRORLEVEL_HANDLING=%ERRORLEVEL%"

title App Builder: VisionLane OCR Application (Nuitka)
REM --------------------------------------------------------
REM VisionLane Build Script (Nuitka version)
REM --------------------------------------------------------

echo Starting VisionLane OCR Build Process...
echo Script is running from: %~dp0
echo Current directory: %CD%
echo.

REM Clean up any previous temp_binaries from interrupted builds
echo Cleaning up any previous temporary files...
rmdir /s /q temp_binaries 2>nul
if exist temp_binaries (
    echo Warning: Could not remove existing temp_binaries directory
) else (
    echo Previous temp_binaries cleaned up successfully
)

REM Check for critical dependencies first
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found at .venv\Scripts\python.exe
    echo Please ensure you have created and activated a virtual environment.
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

if not exist "main.py" (
    echo ERROR: main.py not found in current directory
    echo Please ensure you are running this script from the project root.
    echo Current directory: %CD%
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

REM Check for existing build tools and ask user about installation, cleanup first
rmdir /s /q temp_binaries 2>nul

REM Check if cache_binaries.zip exists early to decide on prompts
set "CACHE_BINARIES_AVAILABLE=0"
if exist "%~dp0cache_binaries.zip" (
    set "CACHE_BINARIES_AVAILABLE=1"
    echo Found cache_binaries.zip - local cache tools available
)

REM Ask about downloading latest build tools at start (only if no local cache available)
if "%CACHE_BINARIES_AVAILABLE%"=="0" (
    echo.
    echo No local cache_binaries.zip found.
    echo Would you like to download the latest build tools including ccache and clcache?
    echo This will provide faster compilation caching.
    echo.
    set /p "DOWNLOAD_TOOLS=Download latest build tools? (y/n): "
    
    if /i "!DOWNLOAD_TOOLS!"=="y" (
        echo Downloading latest build tools...
        REM Add download logic here if needed
        echo Note: Manual download of cache_binaries.zip may be required
    )
    echo.
)

echo Checking for existing build tools...

REM Check for complete Visual Studio Build Tools installation first
set "VS_BUILD_TOOLS_FOUND=0"

REM Method 1: Use vswhere.exe to find any VS installation with VC tools
if exist "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe" (
    for /f "tokens=*" %%i in ('C:\Program Files ^(x86^)\Microsoft Visual Studio\Installer\vswhere.exe -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul') do (
        if exist "%%i\VC\Tools\MSVC" (
            echo Found Visual Studio installation with C++ tools at: %%i
            set "VS_BUILD_TOOLS_FOUND=1"
        )
    )
)

REM Method 2: Check for manual installations in common paths
if "!VS_BUILD_TOOLS_FOUND!"=="0" (
    for %%p in (
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"
        "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC"
        "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\MSVC"
        "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Tools\MSVC"
        "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC"
        "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC"
    ) do (
        if exist "%%p" (
            echo Found Visual Studio Build Tools at: %%p
            set "VS_BUILD_TOOLS_FOUND=1"
            
            REM Set up MSVC environment for Nuitka - use the correct path
            for %%v in ("%%p\*") do (
                if exist "%%v\bin\Hostx64\x64\cl.exe" (
                    echo Setting up MSVC environment for Nuitka...
                    
                    REM Find vcvars64.bat dynamically based on any year
                    set "VCVARS_FOUND=0"
                    
                    REM Check x86 Program Files for any year
                    for /d %%y in ("C:\Program Files (x86)\Microsoft Visual Studio\*") do (
                        if exist "%%y\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
                            echo Found vcvars64.bat at %%y\BuildTools
                            call "%%y\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
                            set "VCVARS_FOUND=1"
                            goto :vcvars_done
                        )
                        if exist "%%y\Community\VC\Auxiliary\Build\vcvars64.bat" (
                            echo Found vcvars64.bat at %%y\Community
                            call "%%y\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
                            set "VCVARS_FOUND=1"
                            goto :vcvars_done
                        )
                        if exist "%%y\Professional\VC\Auxiliary\Build\vcvars64.bat" (
                            echo Found vcvars64.bat at %%y\Professional
                            call "%%y\Professional\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
                            set "VCVARS_FOUND=1"
                            goto :vcvars_done
                        )
                        if exist "%%y\Enterprise\VC\Auxiliary\Build\vcvars64.bat" (
                            echo Found vcvars64.bat at %%y\Enterprise
                            call "%%y\Enterprise\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
                            set "VCVARS_FOUND=1"
                            goto :vcvars_done
                        )
                    )
                    
                    REM Check regular Program Files for any year
                    if "!VCVARS_FOUND!"=="0" (
                        for /d %%y in ("C:\Program Files\Microsoft Visual Studio\*") do (
                            if exist "%%y\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
                                echo Found vcvars64.bat at %%y\BuildTools
                                call "%%y\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
                                set "VCVARS_FOUND=1"
                                goto :vcvars_done
                            )
                            if exist "%%y\Community\VC\Auxiliary\Build\vcvars64.bat" (
                                echo Found vcvars64.bat at %%y\Community
                                call "%%y\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>nul
                                set "VCVARS_FOUND=1"
                                goto :vcvars_done
                            )
                        )
                    )
                    
                    :vcvars_done
                    if "!VCVARS_FOUND!"=="0" (
                        echo Warning: Could not find vcvars64.bat for MSVC environment setup
                    )
                    goto :vs_found
                )
            )
        )
    )
)
:vs_found

REM If no complete build tools found, ask user if they want to install
if "!VS_BUILD_TOOLS_FOUND!"=="0" (
    echo.
    echo Visual Studio Build Tools not found.
    echo Installing VS Build Tools will enable clcache for faster MSVC compilation.
    echo Without it, Nuitka will download MinGW-w64 automatically as fallback.
    echo.
    set /p "INSTALL_VS=Do you want to install Visual Studio Build Tools? (y/n): "
    
    if /i "!INSTALL_VS!"=="y" (
        echo Installing Visual Studio Build Tools 2022 with Windows SDK...
        echo This may take several minutes...
        
        REM Install with Windows 11 SDK (required for Nuitka MSVC support)
        winget install Microsoft.VisualStudio.2022.BuildTools --silent --accept-package-agreements --accept-source-agreements --override "--wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.22000 --add Microsoft.VisualStudio.Component.Windows10SDK.19041 --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.VC.ATL"
        
        if !ERRORLEVEL! NEQ 0 (
            echo Failed to install Visual Studio Build Tools!
            echo.
            echo Alternative: You can manually install Visual Studio Build Tools and ensure you include:
            echo - MSVC v143 - VS 2022 C++ x64/x86 build tools
            echo - Windows 11 SDK (10.0.22000 or later)
            echo - Windows 10 SDK (10.0.19041 or later)
            echo.
            echo Continuing with Nuitka's automatic MinGW-w64 fallback...
        ) else (
            echo Visual Studio Build Tools with Windows SDK installed successfully!
            call refreshenv 2>nul || echo Warning: refreshenv not available
            set "VS_BUILD_TOOLS_FOUND=1"
        )
    ) else (
        echo Skipping VS Build Tools installation. Nuitka will use MinGW-w64 fallback.
    )
) else (
    echo Checking Windows SDK availability for MSVC...
    REM Check if Windows SDK is available
    set "WINDOWS_SDK_FOUND=0"
    for %%s in (
        "C:\Program Files (x86)\Windows Kits\10\Include\*"
        "C:\Program Files\Windows Kits\10\Include\*"
    ) do (
        if exist "%%s\um\windows.h" (
            echo Found Windows SDK at: %%s
            set "WINDOWS_SDK_FOUND=1"
        )
    )
    
    if "!WINDOWS_SDK_FOUND!"=="0" (
        echo.
        echo WARNING: Visual Studio Build Tools found but Windows SDK is missing!
        echo This may cause Nuitka to fall back to MinGW instead of using MSVC.
        echo.
        echo To fix this, install Windows SDK via:
        echo 1. Visual Studio Installer ^> Modify ^> Individual Components
        echo 2. Check "Windows 11 SDK" or "Windows 10 SDK"
        echo 3. Or run: winget install Microsoft.WindowsSDK.10.0.22000
        echo.
    )
)
REM Now check for MSVC compiler
set "MSVC_FOUND=0"
where cl >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Found MSVC compiler (cl.exe)
    set "MSVC_FOUND=1"
) else (
    REM Check common VS installation paths
    for %%p in (
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe"
        "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe"
        "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe"
        "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe"
    ) do (
        if exist "%%p" (
            echo Found MSVC compiler at %%p
            set "MSVC_FOUND=1"
            goto :msvc_found
        )
    )
)
:msvc_found

REM Check for MinGW as fallback
set "MINGW_FOUND=0"
where gcc >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Found MinGW compiler (gcc.exe)
    set "MINGW_FOUND=1"
)

REM Check for ccache
set "CCACHE_FOUND=0"
where ccache >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Found ccache for faster compilation
    set "CCACHE_FOUND=1"
    set "CCACHE_DIR=%USERPROFILE%\.ccache"
)

REM Check for clcache
set "CLCACHE_FOUND=0"
where clcache >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Found clcache for faster compilation
    set "CLCACHE_FOUND=1"
    set "CLCACHE_DIR=%USERPROFILE%\.clcache"
) else (
    REM Check if clcache exists in common installation paths
    for %%p in ("C:\Python*\Scripts\clcache.exe" "%USERPROFILE%\AppData\Local\Programs\Python\Python*\Scripts\clcache.exe" "%LOCALAPPDATA%\Programs\Python\Python*\Scripts\clcache.exe") do (
        if exist "%%p" (
            echo Found clcache at: %%p
            for %%i in ("%%p") do set "PATH=%%~dpi;%PATH%"
            set "CLCACHE_FOUND=1"
            set "CLCACHE_DIR=%USERPROFILE%\.clcache"
            goto :clcache_found
        )
    )
)
:clcache_found

REM Report compiler status
echo.
echo === Compiler Detection Summary ===
if "%MSVC_FOUND%"=="1" (
    echo Primary Compiler: MSVC available (preferred)
) else if "%MINGW_FOUND%"=="1" (
    echo Primary Compiler: MinGW available (fallback)
) else (
    echo Primary Compiler: None found - Nuitka will download MinGW-w64 automatically
)

if "%CCACHE_FOUND%"=="1" (
    echo Cache Tool: ccache available in PATH
) else if "%CLCACHE_FOUND%"=="1" (
    echo Cache Tool: clcache available in PATH
) else (
    echo Cache Tool: None found in PATH
)
echo ================================

echo Proceeding with build...

REM Always try to extract cache tools if cache_binaries.zip exists, regardless of what's in PATH
if exist "%~dp0cache_binaries.zip" (
    echo Found cache_binaries.zip, extracting cache tools...
    
    set "TEMP_BINARY_DIR=%~dp0temp_binaries"
    
    REM Clean existing temp directory if it exists
    if exist "!TEMP_BINARY_DIR!" (
        echo Cleaning existing temp_binaries directory...
        rmdir /s /q "!TEMP_BINARY_DIR!" 2>nul
    )
    
    REM Create temp_binaries directory
    if not exist "!TEMP_BINARY_DIR!" mkdir "!TEMP_BINARY_DIR!"
    echo Created directory: !TEMP_BINARY_DIR!

    REM Extract cache_binaries.zip with better error handling
    echo Extracting cache_binaries.zip...
    
    REM Method 1: Try PowerShell expansion
    echo Attempting PowerShell extraction...
    powershell -Command "try { Expand-Archive -Path '%~dp0cache_binaries.zip' -DestinationPath '!TEMP_BINARY_DIR!' -Force; Write-Host 'PowerShell extraction successful' } catch { Write-Host 'PowerShell extraction failed:' $_.Exception.Message; exit 1 }"
    
    if !ERRORLEVEL! NEQ 0 (
        echo PowerShell extraction failed, trying alternative method...
        REM Method 2: Try 7zip if available
        where 7z >nul 2>nul && (
            echo Trying 7zip extraction...
            7z x "%~dp0cache_binaries.zip" -o"!TEMP_BINARY_DIR!" -y >nul 2>nul
            if !ERRORLEVEL! EQU 0 echo 7zip extraction successful
        ) || (
            echo 7zip not available, trying WinRAR...
            REM Method 3: Try WinRAR if available
            where winrar >nul 2>nul && (
                winrar x "%~dp0cache_binaries.zip" "!TEMP_BINARY_DIR!\" >nul 2>nul
                if !ERRORLEVEL! EQU 0 echo WinRAR extraction successful
            ) || (
                echo No suitable extraction tool found. Manual extraction may be required.
            )
        )
    )

    REM Show what was extracted
    echo.
    echo Contents of temp_binaries:
    if exist "!TEMP_BINARY_DIR!" (
        dir "!TEMP_BINARY_DIR!" /s /b 2>nul
        if !ERRORLEVEL! NEQ 0 (
            echo No files found in temp_binaries directory
        )
    ) else (
        echo temp_binaries directory was not created
    )
    
    REM Add temp_binaries and all subdirectories to PATH
    set "PATH=!TEMP_BINARY_DIR!;%PATH%"
    echo Added !TEMP_BINARY_DIR! to PATH
    
    REM Look for cache tools recursively
    echo.
    echo Searching for cache tools in extracted files...
    
    for /f "delims=" %%f in ('dir /b /s "!TEMP_BINARY_DIR!\ccache*.exe" 2^>nul') do (
        echo - Found ccache at: %%f
        for %%i in ("%%f") do (
            set "CCACHE_PATH=%%~dpi"
            set "PATH=!CCACHE_PATH!;%PATH%"
            set "CCACHE_FOUND=1"
            set "CCACHE_DIR=%USERPROFILE%\.ccache"
            echo - Added ccache directory to PATH: !CCACHE_PATH!
        )
    )
    
    for /f "delims=" %%f in ('dir /b /s "!TEMP_BINARY_DIR!\clcache*.exe" 2^>nul') do (
        echo - Found clcache at: %%f
        for %%i in ("%%f") do (
            set "CLCACHE_PATH=%%~dpi"
            set "PATH=!CLCACHE_PATH!;%PATH%"
            set "CLCACHE_FOUND=1"
            set "CLCACHE_DIR=%USERPROFILE%\.clcache"
            echo - Added clcache directory to PATH: !CLCACHE_PATH!
        )
    )
    
    REM Verify PATH accessibility for extracted tools
    echo.
    echo Verifying PATH accessibility of extracted tools:
    where ccache >nul 2>nul && (
        echo - ccache: accessible in PATH
        ccache --version 2>nul | findstr /i "version" && echo   → ccache version check passed
    ) || (
        echo - ccache: not accessible in PATH
    )
    
    where clcache >nul 2>nul && (
        echo - clcache: accessible in PATH
        clcache --help >nul 2>nul && echo   → clcache help check passed
    ) || (
        echo - clcache: not accessible in PATH
    )
    
    REM Also look for any .exe files to see what's actually in the zip
    echo.
    echo All .exe files found in extraction:
    dir /b /s "!TEMP_BINARY_DIR!\*.exe" 2>nul
    
    REM Test functionality of extracted tools
    echo.
    echo Testing extracted cache tools...
    
    if "!CCACHE_FOUND!"=="1" (
        ccache --version >nul 2>nul && (
            echo - ccache: functional and accessible
        ) || (
            echo - ccache: found but not functional
        )
    )
    
    if "!CLCACHE_FOUND!"=="1" (
        clcache --help >nul 2>nul && (
            echo - clcache: functional and accessible
        ) || (
            echo - clcache: found but not functional
        )
    )
    
    REM Configure cache tools based on what we found
    if "!CLCACHE_FOUND!"=="1" if "%MSVC_FOUND%"=="1" (
        echo Configuring extracted clcache for MSVC compilation
        set "CC=clcache"
        set "CXX=clcache"
    ) else if "!CCACHE_FOUND!"=="1" (
        echo Configuring extracted ccache for compilation
        if "%MSVC_FOUND%"=="1" (
            set "CC=ccache cl"
            set "CXX=ccache cl"
        ) else (
            set "CC=ccache gcc"
            set "CXX=ccache g++"
        )
    )
    
    if "!CCACHE_FOUND!"=="1" if "!CLCACHE_FOUND!"=="1" (
        echo Both ccache and clcache successfully extracted and configured!
    ) else if "!CCACHE_FOUND!"=="1" (
        echo ccache successfully extracted and configured!
    ) else if "!CLCACHE_FOUND!"=="1" (
        echo clcache successfully extracted and configured!
    ) else (
        echo WARNING: No cache tools found in cache_binaries.zip
        echo Please verify the contents of cache_binaries.zip
    )
) else (
    echo cache_binaries.zip not found in project directory.
)

REM Final cache tool configuration for existing tools
if not defined CC (
    if "%CLCACHE_FOUND%"=="1" if "%MSVC_FOUND%"=="1" (
        echo Configuring existing clcache for MSVC compilation
        set "CC=clcache"
        set "CXX=clcache"
    ) else if "%CCACHE_FOUND%"=="1" (
        echo Configuring existing ccache for compilation
        if "%MSVC_FOUND%"=="1" (
            set "CC=ccache cl"
            set "CXX=ccache cl"
        ) else (
            set "CC=ccache gcc"
            set "CXX=ccache g++"
        )
    )
)

REM IMPORTANT: DO NOT REMOVE ANY --include-package=... LINES BELOW!
REM These are required for Nuitka to bundle PyQt6, torch, doctr, and all dependencies.
REM If you remove them, your app will not run after building.

REM Clean old build artifacts
echo Cleaning up old build...
rmdir /s /q "%~dp0dist_nuitka" 2>nul

REM Ensure models are downloaded first
echo Downloading DocTR models if not present...
.\.venv\Scripts\python.exe verify_models.py

IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to download doctr models. 
    echo This could be due to network issues or missing dependencies.
    echo.
    echo Press any key to continue anyway, or Ctrl+C to abort...
    pause >nul
    echo Continuing build without model verification...
    echo.
)

REM Build with Nuitka
echo Building application with Nuitka...
echo.

REM Show what compiler Nuitka will likely use
echo === Build Environment Report ===
if "%MSVC_FOUND%"=="1" (
    echo Nuitka will prefer: MSVC compiler (cl.exe)
    if defined CC (
        echo Cache tool configured: !CC!
    ) else (
        echo Cache tool: None configured
    )
) else if "%MINGW_FOUND%"=="1" (
    echo Nuitka will use: Existing MinGW compiler
    if defined CC (
        echo Cache tool configured: !CC!
    ) else (
        echo Cache tool: None configured
    )
) else (
    echo Nuitka will: Download and use MinGW-w64 automatically
    if "%CCACHE_FOUND%"=="1" (
        echo Cache tool: ccache available for integration
    ) else (
        echo Cache tool: None available
    )
)

REM Show available cache tools in PATH
echo.
echo Available cache tools in PATH:
where ccache >nul 2>nul && echo - ccache: available || echo - ccache: not available
where clcache >nul 2>nul && echo - clcache: available || echo - clcache: not available

REM Show environment variables that affect compilation
echo.
echo Environment Variables:
if defined CC echo   CC=!CC!
if defined CXX echo   CXX=!CXX!
if defined CCACHE_DIR echo   CCACHE_DIR=!CCACHE_DIR!
if defined CLCACHE_DIR echo   CLCACHE_DIR=!CLCACHE_DIR!

REM Predict exactly which compiler Nuitka will use - SAFE VERSION
echo.
echo === Nuitka Compiler Prediction ===
echo Testing compiler availability in Nuitka's preference order:

REM 1. Check if CC/CXX environment variables are set (highest priority)
if defined CC (
    echo 1. CC environment variable set: !CC!
    echo   Testing CC command...
    call :test_compiler "!CC!" && (
        echo   → CC command works - Nuitka will use: !CC!
        set "PREDICTED_COMPILER=!CC!"
        goto :compiler_predicted
    ) || (
        echo   → CC command failed - Nuitka will ignore this
    )
)

REM 2. Check for MSVC (cl.exe) in PATH
echo 2. Testing MSVC availability...
call :test_compiler "cl" && (
    echo   → MSVC is functional - Nuitka will use: MSVC (cl.exe)
    set "PREDICTED_COMPILER=MSVC (cl.exe)"
    goto :compiler_predicted
) || (
    echo   → MSVC not available or not functional
)

REM 3. Check for GCC in PATH
echo 3. Testing GCC availability...
call :test_compiler "gcc" && (
    echo   → GCC is functional - Nuitka will use: GCC
    set "PREDICTED_COMPILER=GCC"
    goto :compiler_predicted
) || (
    echo   → GCC not available or not functional
)

REM 4. Check for Clang in PATH
echo 4. Testing Clang availability...
call :test_compiler "clang" && (
    echo   → Clang is functional - Nuitka will use: Clang
    set "PREDICTED_COMPILER=Clang"
    goto :compiler_predicted
) || (
    echo   → Clang not available or not functional
)

REM 5. No compiler found - Nuitka will download MinGW
echo 5. No system compilers found
echo   → Nuitka will download MinGW-w64 automatically
set "PREDICTED_COMPILER=MinGW-w64 (auto-download)"

:compiler_predicted
echo.
echo *** FINAL PREDICTION: Nuitka will use %PREDICTED_COMPILER% ***

REM Show cache tool integration
if defined CC (
    echo !CC! | findstr /i "ccache" >nul && (
        echo *** CACHE: ccache will accelerate compilation ***
    ) || (
        echo !CC! | findstr /i "clcache" >nul && (
            echo *** CACHE: clcache will accelerate compilation ***
        ) || (
            echo *** CACHE: No cache tool integration ***
        )
    )
) else (
    echo *** CACHE: No cache tool integration ***
)

echo ================================
echo.
goto :start_compilation

REM Safe compiler testing function
:test_compiler
where %~1 >nul 2>nul || exit /b 1
%~1 --version >nul 2>nul && exit /b 0
%~1 /? >nul 2>nul && exit /b 0
exit /b 1

:start_compilation
echo Starting Nuitka compilation...
echo This may take several minutes depending on your system and cache status.
echo The script will NOT close automatically - please wait for completion.
echo.

REM Add timeout before starting compilation to ensure user sees the message
timeout /t 3 /nobreak >nul

.\.venv\Scripts\python.exe -m nuitka^
    --standalone^
    --show-progress^
    --nofollow-import-to=onnx^
    --follow-import-to=doctr^
    --enable-plugin=pylint-warnings^
    --enable-plugin=pyqt6^
    --include-qt-plugins=platforms,imageformats^
    --include-data-file=icon.ico=icon.ico^
    --include-data-file=config.ini=config.ini^
    --include-package=doctr^
    --include-package=doctr.models^
    --include-package=doctr.models.detection^
    --include-package=doctr.models.recognition^
    --include-package=doctr.models.predictor^
    --include-package=doctr.io^
    --include-package=doctr.utils^
    --include-package=doctr.utils.multithreading^
    --include-package=doctr.datasets^
    --include-package=doctr.transforms^
    --include-package=doctr.file_utils^
    --include-package=langdetect^
    --include-package=langdetect.detector^
    --include-package=langdetect.detector_factory^
    --include-package=langdetect.lang_detect_exception^
    --include-package=langdetect.utils^
    --include-package=langdetect.utils.ngram^
    --include-package=langdetect.utils.messages^
    --include-package-data=langdetect^
    --include-data-dir=.venv\Lib\site-packages\langdetect=langdetect^
    --include-package=torch^
    --include-package=torch.nn^
    --include-package=torch.cuda^
    --include-package=torch.backends^
    --include-package=torch.backends.cudnn^
    --include-package=torch.jit^
    --include-package=torch.autograd^
    --include-package=torch.optim^
    --include-package=torch.utils^
    --include-package=torch.utils.data^
    --include-package=torch.distributed^
    --include-package=torch._C^
    --include-package=torchvision^
    --include-package=torchvision.models^
    --include-package=torchvision.transforms^
    --include-package=torchvision.datasets^
    --include-package=torchvision.ops^
    --include-package=torchaudio^
    --include-package=PIL^
    --include-package=numpy^
    --include-package=cv2^
    --include-package=scipy^
    --include-package=psutil^
    --include-package=pynvml^
    --include-package=GPUtil^
    --include-package=subprocess^
    --include-package=platform^
    --include-package=PyPDF2^
    --include-package=ocrmypdf^
    --include-package=ocrmypdf.data^
    --include-package=ocrmypdf.api^
    --include-package=pdf2image^
    --include-package=PyQt6^
    --include-package=wmi^
    --include-package=gui^
    --include-package=gui.processing_thread^
    --include-package=gui.log_handler^
    --include-package=gui.main_window^
    --include-package=gui.splash_screen^
    --include-package=utils^
    --include-package=utils.image_processor^
    --include-package=utils.pypdfcompressor^
    --include-package=utils.debug_helper^
    --include-package=utils.process_manager^
    --include-package=utils.thread_killer^
    --include-package=utils.logging_config^
    --include-package=utils.safe_logger^
    --include-package=utils.hocr_to_pdf^
    --include-package=utils.parallel_loader^
    --include-package=utils.system_diagnostics^
    --include-package=utils.startup_cache^
    --include-package=utils.startup_config^
    --include-package=utils.model_downloader^
    --include-package=core^
    --include-package=core.cuda_compat_plugin^
    --include-package=core.cuda_env_patch^
    --include-package=core.cuda_patch_wrapper^
    --include-package=core.doctr_patch^
    --include-package=core.doctr_torch_setup^
    --include-package=core.hardware_monitoring_patch^
    --include-package=core.nuitka_cuda_patch^
    --include-package=core.ocr_processor^
    --include-package=core.runtime_cuda_patch^
    --include-package-data=doctr^
    --include-package-data=torch^
    --include-package-data=torchvision^
    --include-package-data=torchaudio^
    --include-package-data=PIL^
    --include-package-data=ocrmypdf^
    --include-package-data=GPUtil^
    --include-package-data=core^
    --include-data-dir=.venv\Lib\site-packages\torch=torch^
    --include-data-dir=.venv\Lib\site-packages\torchvision=torchvision^
    --include-data-dir=.venv\Lib\site-packages\torch\lib=torch\lib^
    --output-dir=dist_nuitka^
    --windows-icon-from-ico=icon.ico^
    --windows-console-mode=force^
    main.py

set "NUITKA_EXIT_CODE=%ERRORLEVEL%"
echo.
echo Nuitka process completed with exit code: %NUITKA_EXIT_CODE%
echo.

REM Always pause here regardless of success or failure
echo ========================================
echo Build process completed.
echo Exit code: %NUITKA_EXIT_CODE%
echo ========================================
echo.

echo Cleaning up temporary build files...
rmdir /s /q temp_binaries 2>nul
if exist temp_binaries (
    echo Warning: Could not remove temp_binaries directory - may need manual cleanup
) else (
    echo Temporary files cleaned up successfully
)

rmdir /s /q temp_binaries 2>nul

IF %NUITKA_EXIT_CODE% NEQ 0 (
    echo.
    echo === Build Failed Analysis ===
    echo Exit Code: %NUITKA_EXIT_CODE%
    echo Check the output above for compiler-related errors.
    echo If you see MinGW download messages, Nuitka used its fallback.
    echo If you see MSVC-related messages, it used your installed compiler.
    echo.
    echo Common issues:
    echo - Missing dependencies in virtual environment
    echo - Insufficient disk space
    echo - Antivirus interference
    echo - Network issues during MinGW download
    echo.
    echo Press any key to exit with error code %NUITKA_EXIT_CODE%...
    pause >nul
    exit /b %NUITKA_EXIT_CODE%
) ELSE (
    echo.
    echo === Build Success Analysis ===
    
    REM Check the build log for compiler evidence
    if exist "dist_nuitka\main.build\build.log" (
        echo Checking build log for compiler usage...
        findstr /i "cl.exe mingw gcc clang" "dist_nuitka\main.build\build.log" > nul
        if !ERRORLEVEL! EQU 0 (
            echo Found compiler references in build log:
            findstr /i "cl.exe mingw gcc clang" "dist_nuitka\main.build\build.log"
        )
    )
    
    REM Check for cache usage evidence
    if exist "dist_nuitka\main.build\build.log" (
        findstr /i "ccache clcache cache" "dist_nuitka\main.build\build.log" > nul
        if !ERRORLEVEL! EQU 0 (
            echo Found cache tool usage:
            findstr /i "ccache clcache cache" "dist_nuitka\main.build\build.log"
        )
    )
    
    REM Performing post-build fixes for PyTorch detection
    echo Performing post-build library copying and fixes...
    
    REM Create environment file to ensure PyTorch is detected
    echo Creating PyTorch detection file...
    echo USE_TORCH=1 > "dist_nuitka\main.dist\USE_TORCH"
    echo DOCTR_BACKEND=torch >> "dist_nuitka\main.dist\USE_TORCH"
    
    REM Copy PyTorch DLLs
    if exist ".venv\Lib\site-packages\torch\lib" (
        echo Copying PyTorch libraries...
        xcopy ".venv\Lib\site-packages\torch\lib\*" "dist_nuitka\main.dist\torch\lib\" /Y /E /I 2>nul
    )
    
    REM Copy NVIDIA libraries - Enhanced (remove duplicate)
    if exist ".venv\Lib\site-packages\nvidia" (
        echo Copying NVIDIA libraries...
        xcopy ".venv\Lib\site-packages\nvidia\*" "dist_nuitka\main.dist\nvidia\" /Y /E /I 2>nul
    )
    
    REM Copy pynvml data files
    if exist ".venv\Lib\site-packages\pynvml" (
        echo Copying pynvml data files...
        xcopy ".venv\Lib\site-packages\pynvml\*" "dist_nuitka\main.dist\pynvml\" /Y /E /I 2>nul
    )
    
    REM Copy NVML DLLs from system
    if exist "C:\Windows\System32\nvml.dll" (
        echo Copying NVML system libraries...
        copy "C:\Windows\System32\nvml.dll" "dist_nuitka\main.dist\" /Y 2>nul
    )
    
    REM Copy NVIDIA driver DLLs
    if exist "C:\Windows\System32\nvcuda.dll" (
        echo Copying NVIDIA CUDA driver...
        copy "C:\Windows\System32\nvcuda.dll" "dist_nuitka\main.dist\" /Y 2>nul
    )
    
    REM Copy additional NVIDIA DLLs
    for %%f in ("C:\Windows\System32\nvapi*.dll") do (
        copy "%%f" "dist_nuitka\main.dist\" /Y 2>nul
    )
    
    REM Copy CUDA libraries if found in system
    for %%d in ("C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v*") do (
        if exist "%%d\bin\*.dll" (
            echo Copying CUDA libraries from %%d...
            xcopy "%%d\bin\cudart*.dll" "dist_nuitka\main.dist\" /Y 2>nul
            xcopy "%%d\bin\cublas*.dll" "dist_nuitka\main.dist\" /Y 2>nul
            xcopy "%%d\bin\curand*.dll" "dist_nuitka\main.dist\" /Y 2>nul
            xcopy "%%d\bin\cusolver*.dll" "dist_nuitka\main.dist\" /Y 2>nul
            xcopy "%%d\bin\cusparse*.dll" "dist_nuitka\main.dist\" /Y 2>nul
            xcopy "%%d\bin\cufft*.dll" "dist_nuitka\main.dist\" /Y 2>nul
        )
    )

    REM Copy DocTR models cache
    set "doctr_cache=%USERPROFILE%\.cache\doctr"
    if exist "%doctr_cache%" (
        echo Copying DocTR model cache...
        xcopy "%doctr_cache%\*" "dist_nuitka\main.dist\.cache\doctr\" /Y /E /I 2>nul
    )
    
    echo.
    echo Build complete! Your application is ready in the dist_nuitka folder.
    echo Run main.exe from the dist_nuitka\main.dist\ folder.
    echo.
    echo ========================================
    echo SUCCESS: Build completed successfully!
    echo ========================================
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 0
)

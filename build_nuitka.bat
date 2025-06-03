@echo off
setlocal enabledelayedexpansion

title App Builder: VisionLane OCR Application (Nuitka)
REM --------------------------------------------------------
REM VisionLane Build Script (Nuitka version)
REM --------------------------------------------------------

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
        echo Installing Visual Studio Build Tools 2022...
        echo This may take several minutes...
        
        winget install Microsoft.VisualStudio.2022.BuildTools --silent --accept-package-agreements --accept-source-agreements --override "--wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.22000 --add Microsoft.VisualStudio.Component.VC.CMake.Project --add Microsoft.VisualStudio.Component.VC.ATL"
        
        if !ERRORLEVEL! NEQ 0 (
            echo Failed to install Visual Studio Build Tools!
            echo Continuing with Nuitka's automatic MinGW-w64 fallback...
        ) else (
            echo Visual Studio Build Tools installed successfully!
            call refreshenv 2>nul || echo Warning: refreshenv not available
            set "VS_BUILD_TOOLS_FOUND=1"
        )
    ) else (
        echo Skipping VS Build Tools installation. Nuitka will use MinGW-w64 fallback.
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
)

REM Report compiler status
if "%MSVC_FOUND%"=="1" (
    echo Compiler Status: MSVC available (preferred)
) else if "%MINGW_FOUND%"=="1" (
    echo Compiler Status: MinGW available (fallback)
) else (
    echo Compiler Status: None found - Nuitka will download MinGW-w64 automatically
)

echo Proceeding with build...

REM Install cache tools if not found
if "%CCACHE_FOUND%"=="0" if "%CLCACHE_FOUND%"=="0" (
    REM Check if cache_binaries.zip exists in project folder
    if exist "%~dp0cache_binaries.zip" (
        echo Found cache_binaries.zip, extracting cache tools...
        
        set "TEMP_BINARY_DIR=%~dp0temp_binaries"
        
        REM Clean existing temp directory if it exists with better handling
        if exist "!TEMP_BINARY_DIR!" (
            echo Cleaning existing temp_binaries directory...
            
            REM Show what processes might be using files in the directory
            echo Checking for processes using files in temp_binaries...
            for /f "tokens=2 delims=," %%a in ('tasklist /fo csv ^| findstr /i "ccache\|clcache\|python\|nuitka"') do (
                echo Found potential process: %%a
            )
            
            REM Check if any handles are open to our directory
            echo Checking file handles...
            handle.exe "!TEMP_BINARY_DIR!" 2>nul || echo Handle.exe not available for detailed analysis
            
            REM Try to kill any processes that might be using files in temp_binaries
            taskkill /f /im ccache.exe 2>nul && echo Killed ccache.exe
            taskkill /f /im clcache.exe 2>nul && echo Killed clcache.exe
            
            REM Wait for processes to terminate
            timeout /t 2 /nobreak >nul
            
            REM Try to see what's preventing deletion
            echo Attempting directory removal...
            rmdir /s /q "!TEMP_BINARY_DIR!" 2>nul
            if exist "!TEMP_BINARY_DIR!" (
                echo Directory removal failed. Checking specific files...
                dir "!TEMP_BINARY_DIR!" /a 2>nul
                
                REM Try to delete individual files to see which ones are locked
                for %%f in ("!TEMP_BINARY_DIR!\*.*") do (
                    del /f /q "%%f" 2>nul || echo File locked: %%f
                )
                
                set "TEMP_BINARY_DIR=%~dp0temp_binaries_%RANDOM%"
                echo Using alternative directory: !TEMP_BINARY_DIR!
            ) else (
                echo Directory successfully removed.
            )
        )
        
        REM Create temp_binaries directory
        if not exist "!TEMP_BINARY_DIR!" mkdir "!TEMP_BINARY_DIR!"

        REM Extract cache_binaries.zip using simple PowerShell command to temp_binaries subfolder...
        
        REM Try PowerShell with explicit module import first - extract directly to temp_binaries
        powershell -command "Import-Module Microsoft.PowerShell.Archive -Force; Expand-Archive -Force '%~dp0cache_binaries.zip' '!TEMP_BINARY_DIR!'" 2>nul
        
        REM If that fails, try without explicit import - extract directly to temp_binaries
        if not exist "!TEMP_BINARY_DIR!\ccache.exe" if not exist "!TEMP_BINARY_DIR!\clcache.exe" (
            echo First method failed, trying alternative PowerShell extraction...
            powershell -command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%~dp0cache_binaries.zip', '!TEMP_BINARY_DIR!')" 2>nul
        )

        REM No need to move files since they're extracted directly to temp_binaries
        REM Add temp_binaries to PATH so Nuitka can find cache tools
        set "PATH=!TEMP_BINARY_DIR!;%PATH%"
        echo Added !TEMP_BINARY_DIR! to PATH for this session
        
        REM Check what we actually extracted
        echo Checking extracted cache tools...
        
        REM Look for cache tools in subdirectories
        for /f "delims=" %%f in ('dir /b /s "!TEMP_BINARY_DIR!\ccache.exe" 2^>nul') do (
            echo - Found ccache.exe at %%f
            for %%i in ("%%f") do set "CCACHE_PATH=%%~dpi"
            set "PATH=!CCACHE_PATH!;%PATH%"
            set "CCACHE_FOUND=1"
            set "CCACHE_DIR=%USERPROFILE%\.ccache"
            echo - Added ccache directory to PATH: !CCACHE_PATH!
        )
        
        for /f "delims=" %%f in ('dir /b /s "!TEMP_BINARY_DIR!\clcache.exe" 2^>nul') do (
            echo - Found clcache.exe at %%f
            for %%i in ("%%f") do set "CLCACHE_PATH=%%~dpi"
            set "PATH=!CLCACHE_PATH!;%PATH%"
            set "CLCACHE_FOUND=1"
            set "CLCACHE_DIR=%USERPROFILE%\.clcache"
            echo - Added clcache directory to PATH: !CLCACHE_PATH!
        )
        
        REM Verify PATH access with actual functionality test
        echo.
        echo Verifying cache tool functionality...
        
        REM Test clcache functionality
        if "!CLCACHE_FOUND!"=="1" (
            clcache -V >nul 2>nul
            if !ERRORLEVEL! EQU 0 (
                echo - clcache: functional and accessible
            ) else (
                echo - clcache: accessible but may have issues
            )
        )
        
        REM Test ccache functionality  
        if "!CCACHE_FOUND!"=="1" (
            ccache --version >nul 2>nul
            if !ERRORLEVEL! EQU 0 (
                echo - ccache: functional and accessible
            ) else (
                echo - ccache: accessible but may have issues
            )
        )
        
        REM Configure cache tools - prefer clcache for MSVC, set up both
        if "!CLCACHE_FOUND!"=="1" if "%MSVC_FOUND%"=="1" if "!VS_BUILD_TOOLS_FOUND!"=="1" (
            echo Using extracted clcache for MSVC compilation
            set "CC=clcache"
            set "CXX=clcache"
        ) else if "!CCACHE_FOUND!"=="1" (
            echo Using extracted ccache for compilation
            if "%MSVC_FOUND%"=="1" (
                set "CC=ccache cl"
                set "CXX=ccache cl"
            ) else (
                set "CC=ccache gcc"
                set "CXX=ccache g++"
            )
        )
        
        REM Check if we found any cache tools in extracted files
        if "!CCACHE_FOUND!"=="1" (
            if "!CLCACHE_FOUND!"=="1" (
                echo Both ccache and clcache successfully extracted and configured!
            ) else (
                echo ccache successfully extracted and configured!
            )
            goto :cache_tools_ready
        ) else if "!CLCACHE_FOUND!"=="1" (
            echo clcache successfully extracted and configured!
            goto :cache_tools_ready
        ) else (
            echo No cache tools found in extracted temp_binaries directory.
            echo Please check that cache_binaries.zip contains ccache.exe and/or clcache.exe
            goto :cache_tools_ready
        )
    ) else (
        echo cache_binaries.zip not found in project directory.
        echo Cache tools will not be available for this build.
        goto :cache_tools_ready
    )
) else (
    echo Using existing cache tools found in system PATH
    if "%CLCACHE_FOUND%"=="1" (
        echo Using existing clcache installation
        set "CC=clcache"
        set "CXX=clcache"
    ) else if "%CCACHE_FOUND%"=="1" (
        echo Using existing ccache installation
        if "%MSVC_FOUND%"=="1" (
            set "CC=ccache cl"
            set "CXX=ccache cl"
        ) else (
            set "CC=ccache gcc"
            set "CXX=ccache g++"
        )
    )
    goto :cache_tools_ready
)

:cache_tools_ready

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
    echo Failed to download doctr models. Aborting build.
    pause
    exit /b 1
)

REM Build with Nuitka
echo Building application with Nuitka...
echo.
echo === Build Environment Report ===

REM Show what compiler Nuitka will likely use
if "%MSVC_FOUND%"=="1" (
    echo Nuitka will prefer: MSVC compiler (cl.exe)
    if defined CC (
        echo Cache tool: !CC!
    ) else (
        echo Cache tool: None configured
    )
) else if "%MINGW_FOUND%"=="1" (
    echo Nuitka will use: Existing MinGW compiler
    if defined CC (
        echo Cache tool: !CC!
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
where ccache >nul 2>nul && echo - ccache: available
where clcache >nul 2>nul && echo - clcache: available

REM Show environment variables that affect compilation
echo.
echo Environment Variables:
if defined CC echo   CC=!CC!
if defined CXX echo   CXX=!CXX!
if defined CCACHE_DIR echo   CCACHE_DIR=!CCACHE_DIR!
if defined CLCACHE_DIR echo   CLCACHE_DIR=!CLCACHE_DIR!

REM Predict exactly which compiler Nuitka will use
echo.
echo === Nuitka Compiler Prediction ===

REM Test compiler detection in order of Nuitka's preference
echo Testing compiler availability in Nuitka's preference order:

REM 1. Check if CC/CXX environment variables are set (highest priority)
if defined CC (
    echo 1. CC environment variable set: !CC!
    !CC! --version >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo   → CC command works - Nuitka will use: !CC!
        set "PREDICTED_COMPILER=!CC!"
        goto :compiler_predicted
    ) else (
        echo   → CC command failed - Nuitka will ignore this
    )
)

REM 2. Check for MSVC (cl.exe) in PATH
where cl >nul 2>nul
if !ERRORLEVEL! EQU 0 (
    echo 2. MSVC (cl.exe) found in PATH
    cl 2>nul | findstr /i "Microsoft" >nul
    if !ERRORLEVEL! EQU 0 (
        echo   → MSVC is functional - Nuitka will use: MSVC (cl.exe)
        set "PREDICTED_COMPILER=MSVC (cl.exe)"
        goto :compiler_predicted
    )
)

REM 3. Check for GCC in PATH
where gcc >nul 2>nul
if !ERRORLEVEL! EQU 0 (
    echo 3. GCC found in PATH
    gcc --version >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo   → GCC is functional - Nuitka will use: GCC
        set "PREDICTED_COMPILER=GCC"
        goto :compiler_predicted
    )
)

REM 4. Check for Clang in PATH
where clang >nul 2>nul
if !ERRORLEVEL! EQU 0 (
    echo 4. Clang found in PATH
    clang --version >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        echo   → Clang is functional - Nuitka will use: Clang
        set "PREDICTED_COMPILER=Clang"
        goto :compiler_predicted
    )
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
    if "!CC:ccache=!" neq "!CC!" (
        echo *** CACHE: ccache will accelerate compilation ***
    ) else if "!CC:clcache=!" neq "!CC!" (
        echo *** CACHE: clcache will accelerate compilation ***
    )
) else (
    echo *** CACHE: No cache tool integration ***
)

echo ================================
echo.

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
    --include-package=core.gpu_monitoring_patch^
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
    --include-data-dir=.venv\Lib\site-packages\torch=torch^
    --include-data-dir=.venv\Lib\site-packages\torchvision=torchvision^
    --include-data-dir=.venv\Lib\site-packages\torch\lib=torch\lib^
    --output-dir=dist_nuitka^
    --windows-icon-from-ico=icon.ico^
    --windows-console-mode=force^
    main.py

rmdir /s /q temp_binaries 2>nul

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo === Build Failed Analysis ===
    echo Check the output above for compiler-related errors.
    echo If you see MinGW download messages, Nuitka used its fallback.
    echo If you see MSVC-related messages, it used your installed compiler.
    pause
    exit /b 1
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
    
    pause
)

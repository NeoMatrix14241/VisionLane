@echo off

title App Builder: VisionLane OCR Application (Nuitka)
REM --------------------------------------------------------
REM VisionLane Build Script (Nuitka version)
REM --------------------------------------------------------

REM IMPORTANT: DO NOT REMOVE ANY --include-package=... LINES BELOW!
REM These are required for Nuitka to bundle PyQt6, torch, doctr, and all dependencies.
REM If you remove them, your app will not run after building.

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

REM Build with Nuitka
echo Building application with Nuitka...
.\.venv\Scripts\python.exe -m nuitka ^
    --standalone ^
    --nofollow-import-to=onnx ^
    --nofollow-imports ^
    --enable-plugin=pyqt6 ^
    --enable-plugin=multiprocessing ^
    --include-qt-plugins=platforms,imageformats ^
    --include-data-file=icon.ico=icon.ico ^
    --include-data-file=config.ini=config.ini ^
    --include-package=doctr ^
    --include-package=doctr.models ^
    --include-package=doctr.io ^
    --include-package=doctr.utils ^
    --include-package=torch ^
    --include-package=torchvision ^
    --include-package=PIL ^
    --include-package=numpy ^
    --include-package=psutil ^
    --include-package=pynvml ^
    --include-package=GPUtil ^
    --include-package=PyPDF2 ^
    --include-package=ocrmypdf ^
    --include-package=ocrmypdf.data ^
    --include-package=ocrmypdf.api ^
    --include-package=pdf2image ^
    --include-package=PyQt6 ^
    --include-package=gui.processing_thread ^
    --include-package=gui.log_handler ^
    --include-package=utils.image_processor ^
    --include-package=utils.pypdfcompressor ^
    --include-package=utils.debug_helper ^
    --include-package-data=doctr ^
    --include-package-data=torch ^
    --include-package-data=torchvision ^
    --include-package-data=PIL ^
    --include-package-data=ocrmypdf ^
    --include-data-dir=.venv\Lib\site-packages\torch=torch ^
    --output-dir=dist ^
    --windows-icon-from-ico=icon.ico ^
    main.py

IF %ERRORLEVEL% NEQ 0 (
    echo Build failed! Check the error messages above.
    pause
    exit /b 1
) ELSE (
    echo Build complete!
    pause
)

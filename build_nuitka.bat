@echo off

title App Builder: VisionLane OCR Application (Nuitka)
REM --------------------------------------------------------
REM VisionLane Build Script (Nuitka version)
REM --------------------------------------------------------

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
    --enable-plugin=tk-inter ^
    --enable-plugin=pyqt6 ^
    --enable-plugin=multiprocessing ^
    --enable-plugin=pylint-warnings ^
    --include-qt-plugins=all ^
    --include-data-file=icon.ico=icon.ico ^
    --include-data-file=config.ini=config.ini ^
    --include-data-file=README.md=README.md ^
    --include-data-file=LICENSE=LICENSE ^
    --include-package-data=doctr ^
    --include-package-data=ocrmypdf ^
    --include-package-data=PyPDF2 ^
    --include-package-data=pymupdf ^
    --include-package-data=PIL ^
    --include-package-data=pdfminer ^
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

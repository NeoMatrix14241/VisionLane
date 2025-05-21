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
    --enable-plugin=pyqt6 ^
    --enable-plugin=multiprocessing ^
    --include-qt-plugins=all ^
    --include-data-file=icon.ico=icon.ico ^
    --include-data-file=config.ini=config.ini ^
    --include-data-file=README.md=README.md ^
    --include-data-file=LICENSE=LICENSE ^
    --include-package=doctr ^
    --include-package=doctr.models ^
    --include-package=doctr.datasets ^
    --include-package=doctr.io ^
    --include-package=doctr.utils ^
    --include-package=torch ^
    --include-package=torch.nn ^
    --include-package=torch.optim ^
    --include-package=torch.cuda ^
    --include-package=torchvision ^
    --include-package=torchvision.transforms ^
    --include-package=PIL ^
    --include-package=numpy ^
    --include-package=psutil ^
    --include-package=pynvml ^
    --include-package=GPUtil ^
    --include-package=PyPDF2 ^
    --include-package=ocrmypdf ^
    --include-package=ocrmypdf.data ^
    --include-package=ocrmypdf.api ^
    --include-package=ocrmypdf.helpers ^
    --include-package=pdf2image ^
    --include-package=PyQt6 ^
    --include-package=PyQt6.QtWidgets ^
    --include-package=PyQt6.QtGui ^
    --include-package=PyQt6.QtCore ^
    --include-package=PyQt6.QtPrintSupport ^
    --include-package=multiprocessing ^
    --include-package=magic ^
    --include-package=magic.loader ^
    --include-package=tqdm ^
    --include-package=colorama ^
    --include-package=typing_extensions ^
    --include-package=gui ^
    --include-package=utils ^
    --include-package-data=doctr ^
    --include-package-data=torch ^
    --include-package-data=torch.cuda ^
    --include-package-data=torchvision ^
    --include-package-data=PIL ^
    --include-package-data=ocrmypdf ^
    --include-data-dir=.venv\Lib\site-packages\torch\lib=torch\lib ^
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

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
rmdir /s /q "%~dp0dist_nuitka" 2>nul

REM Ensure models are downloaded first
echo Downloading DocTR models if not present...
.\.venv\Scripts\python.exe verify_models.py

IF %ERRORLEVEL% NEQ 0 (
    echo Failed to download doctr models. Aborting build.
    pause
    exit /b 1
)

REM Check PyTorch installation (skip if file doesn't exist)
if exist "test_cuda.py" (
    echo Verifying PyTorch installation...
    .\.venv\Scripts\python.exe test_cuda.py
    
    IF %ERRORLEVEL% NEQ 0 (
        echo Warning: PyTorch verification failed. Build may not include CUDA support.
    )
) else (
    echo Skipping PyTorch verification (test_cuda.py not found)...
)

REM Build with Nuitka
echo Building application with Nuitka...
.\.venv\Scripts\python.exe -m nuitka^
    --standalone^
    --nofollow-import-to=onnx^
    --nofollow-imports^
    --follow-import-to=doctr^
    --enable-plugin=pylint-warnings^
    --enable-plugin=numpy^
    --enable-plugin=torch^
    --enable-plugin=pyqt6^
    --enable-plugin=multiprocessing^
    --include-qt-plugins=platforms,imageformats^
    --include-data-file=icon.ico=icon.ico^
    --include-data-file=config.ini=config.ini^
    --include-data-file=doctr_torch_setup.py=doctr_torch_setup.py^
    --include-data-file=doctr_patch.py=doctr_patch.py^
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
    --include-package=nvidia-ml-py3^
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
    --include-package-data=doctr^
    --include-package-data=torch^
    --include-package-data=torchvision^
    --include-package-data=torchaudio^
    --include-package-data=PIL^
    --include-package-data=ocrmypdf^
    --include-data-dir=.venv\Lib\site-packages\torch=torch^
    --include-data-dir=.venv\Lib\site-packages\torchvision=torchvision^
    --include-data-dir=.venv\Lib\site-packages\torchaudio=torchaudio^
    --include-data-dir=.venv\Lib\site-packages\doctr=doctr^
    --include-data-dir=.venv\Lib\site-packages\torch\lib=torch\lib^
    --include-data-dir=.venv\Lib\site-packages\torchvision\datasets=torchvision\datasets^
    --include-data-file=doctr_torch_setup.py=doctr_torch_setup.py^
    --output-dir=dist_nuitka^
    --windows-icon-from-ico=icon.ico^
    --windows-console-mode=force^
    main.py

IF %ERRORLEVEL% NEQ 0 (
    echo Build failed! Check the error messages above.
    pause
    exit /b 1
) ELSE (
    echo Build complete!
    
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
    
    REM Copy NVIDIA libraries
    if exist ".venv\Lib\site-packages\nvidia" (
        echo Copying NVIDIA libraries...
        xcopy ".venv\Lib\site-packages\nvidia\*" "dist_nuitka\main.dist\nvidia\" /Y /E /I 2>nul
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

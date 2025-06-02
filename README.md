# VisionLane OCR

[EXPERIMENTAL RELEASE AND WILL BE UPDATED IN THE FUTURE, KNOWN BUGS ARE INCLUDED IN ROADMAP]

![icon_landscape_transparent_bg2](https://github.com/user-attachments/assets/c05d5fa0-7f75-4382-b300-8884ccbe196b)

A powerful OCR (Optical Character Recognition) application built with DocTR and PyQt6, designed for high-performance document processing with GPU acceleration support.

![image](https://github.com/user-attachments/assets/743cbdf4-a95b-4129-adeb-ad7cd4154c10)
![image](https://github.com/user-attachments/assets/f7f58880-f111-4671-ad9e-aafdc233e78b)


![Apache License](https://img.shields.io/badge/license-Apache-blue.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)
![GPU Support](https://img.shields.io/badge/GPU-CUDA_Support-green.svg)
[![Download](https://img.shields.io/badge/Download-v0.1.0-blue?logo=github)](https://github.com/NeoMatrix14241/VisionLaneOCR/releases/download/v0.1.0/VisionLaneOCR-v0.1.0.7z)

## Features

- 🚀 GPU-accelerated OCR processing using CUDA
- 📁 Batch processing support for multiple files
- 📄 Support for multiple input formats (TIFF, JPEG, PNG, BMP, GIF, and more)
- 🔄 Concurrent processing with multi-threading
- 💾 Output in PDF and HOCR formats
- 🖥️ PyQt6-based GUI interface
- 📊 Real-time processing status and GPU metrics
- 🔍 High-accuracy text recognition using DocTR
- 🌙 Dark mode, light mode, and night mode themes with system default support
- 🧩 User-selectable DocTR detection and recognition models with auto-download if missing
- ⚙️ Configurable DPI, output format, and compression options (JPEG, JPEG2000, LZW, PNG)
- 🗜️ PDF compression with GhostScript auto-detection (PATH or Program Files, highest version auto-selected)
- 🛠️ Performance tuning: adjustable thread count and timeouts
- 🧹 Safe resource cleanup and robust error handling
- 📂 Remembers last used input/output directories and settings
- 🖼️ Real-time progress display with current file and processed count
- 🔒 Settings saved to config.ini for persistent preferences
- 🧭 Guided dialogs for missing dependencies (e.g., GhostScript "Learn More" button)
- 📝 Logging to file for troubleshooting
- 📦 **Archiving Option:** After processing, optionally move input files/folders to a specified archive directory, preserving the original folder structure. Archiving is configurable per input mode and settings are saved in config.ini.

## Requirements

- **Python 3.10 or higher**  
  _(Tested from 3.10 to 3.12.6)_
- ⚠️ **CRITICAL: NVIDIA GPU with 8GB+ VRAM**  
  The app **WILL CRASH** and must be restarted when error occured.  
  CUDA and recent drivers are **recommended** (will fallback to CPU if GPU is not supported).
- **Windows 10 or higher**
- [**GhostScript**](https://www.ghostscript.com/releases/gsdnld.html)  
  Required **only** for PDF compression features; optional otherwise.

## Roadmap

The following features and improvements are planned for future releases:

### 🚀 Enhanced Startup System ✨ NEW
- [x] **Instant splash screen with progressive loading**  
  _→ Splash screen appears immediately on startup with detailed progress tracking during module loading_
- [x] **Enhanced startup caching system**  
  _→ Caches DocTR setup, model status, and system diagnostics to dramatically reduce subsequent startup times (24h DocTR cache, 7 days model cache, 1h system cache)_
- [x] **Parallel loading architecture**  
  _→ Loads application components in parallel with dependency management for faster startup_
- [x] **Advanced system diagnostics**  
  _→ Comprehensive system health checks including PyTorch/CUDA detection, memory analysis, and performance metrics_
- [x] **Configurable startup preferences**  
  _→ Advanced startup configuration options in config.ini including parallel loading toggles, cache settings, timeout controls, and fast startup mode_

### 🔧 Backend & Performance Improvements ✨ NEW
- [x] **DocTR PyTorch backend patching system**  
  _→ Ensures reliable PyTorch detection in compiled environments with import hooks and fallback mechanisms_
- [x] **Enhanced progress tracking**  
  _→ Real-time file counting and accurate progress display during batch processing with current file indicators_
- [x] **Smart cache invalidation**  
  _→ Hash-based config change detection with automatic cache invalidation when settings are modified_
- [x] **Unified configuration management**  
  _→ All settings consolidated in config.ini with automatic defaults, validation, and experimental startup controls_
- [x] Enhanced threading with daemon threads
  _→ Implement daemon threads for improved clean up during shutdown_

### 🛠️ Developer Tools & Debugging ✨ NEW
- [x] **Enhanced startup demo system**  
  _→ Interactive GUI demo (`demo_enhanced_startup.py`) showcasing all 5 startup enhancements with both console and GUI modes_
- [x] **Comprehensive logging system**  
  _→ Detailed startup logging with configurable levels, crash reporting, and session tracking_
- [x] **Model verification and auto-download**  
  _→ Automatic model validation and download with progress tracking and caching_

### 🔧 Functional Improvements
- [x] Fix initialization of models if not found after build  
  _→ Automatically download or notify if models are missing in cache directory (`C:\Users\%USERNAME%\.doctr\cache\*.pt`)_
- [x] Add custom selection for DocTR text detection and recognition models  
  _→ User-selectable models for more flexibility and accuracy tuning_
- [x] Implement a config file to persist user settings  
  _→ Save UI preferences, text detection and text recognition model selections, input/output/archive options, select processor if CPU or GPU etc._
- [x] **Archiving option for processed files**  
  _→ Optionally move processed input files/folders to a specified archive directory, preserving folder structure. Archive settings are saved and restored from config.ini._
- [x] **Hotfix:** App builder now includes all modules needed for PyPDFCompressor  
  _→ The module: fitz (PyMuPDF) are not included in build.spec file which is required for PyPDFCompressor_
- [x] **Hotfix:** Removed PyMuPDF/fitz import/module  
  _→ PDF compression now relies solely on Ghostscript; all fitz/PyMuPDF code and dependencies have been removed for better compatibility for Nuitka._
- [x] Fix unsupported images, apparently only the TIFF files are getting processed
  _→ Added support for various image formats including JPEG, PNG, BMP, GIF, and more_
- [ ] Add an option to switch GPU and CPU  
  _→ GPU acceleration can be disabled and use CPU instead_
- [ ] Add a function to check if the recommended 8GB VRAM is met, else suggest to switch to CPU  
  _→ Below 6GB are crashing often based on my tests when CUDA out of memory_
- [ ] Integrate super-image (PyTorch) Library for image enhancement to standardize image sizes  
  _→ Use super-image and a formula (see paper_sizes_formula.xlsl) to automatically resize/enhance images so all output PDFs have consistent paper sizes (e.g., A4), ensuring uniform appearance in any PDF viewer._
- [x] Fix OCRmyPDF related bugs causing no output when HOCR output is selected
  _→ OCRmyPDF causes "Division By Zero Error" resulting without any output at all_
- [x] Fix RGBA issues on some image
  _→ RGB is the only channel supported by HOCR transform of OCRmyPDF_
- [x] Fix PyPDFCompressor (using GhostScript) don't properly compress PDF
  _→ There is no difference in size_
- [ ] Fix "Single File" option not working
  _→ Currently, the only working feature is "Folder" which is batch processing_
- [ ] Fix "PDF" option not working
  _→ Currently, the only working feature is "Folder" which is batch processing_

### 📁 File Handling Enhancements
- [x] Add option to archive processed files  
  _→ Automatically move completed input files to a separate folder preserving structure_
- [x] Add compression function for output PDFs  
  _→ Preserve searchable text while applying JPEG-based compression_
- [x] Fix where it suddenly creates output folder in the repository when running  
  _→ It remains there ever since I started making it as CLI based OCR processor_
- [x] Fix PDF output's folder structure when processing PDF files
  _→ PDF files have incorrect output and folder structure after processing_
- [x] Fix unsupported images, apparently only the TIFF files are getting processed
  _→ Will add various images supported in the future_
- [ ] Enhanced PDF output pathing
  _→ Will remove additional unecessary subfolder next to the PDF naming convention_
- [ ] Remove '_ocr' suffix when processing PDF files for OCR in to PDF output format
  _→ The goal is to preserve folder structure and file naming convention and is used for debugging purposes during development only_

### 🎨 UI/UX Features
- [x] Add dark mode toggle and various bug fixes  
  _→ Supports system default, with manual switch option_  
  _→ Includes various bug fixes to the GUI also_
- [x] Add night mode and improved theme switching
- [x] Change GUI style/theme
- [x] Show real-time progress and current file being processed
- [x] Add "Unavailable: Learn More?" button for missing GhostScript with helpful dialog
- [x] Improved error dialogs and resource cleanup
- [x] Save and restore all user settings (including last-used paths, models, compression, and archiving options)
- [x] Auto-detect GhostScript in PATH and Program Files (uses highest version found)
- [x] Robust logging to file for all sessions

## Installation

1. Clone the repository:
```bash
git clone https://github.com/NeoMatrix14241/VisionLane.git
cd VisionLane
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Build

You can build VisionLane OCR as a standalone executable using either Nuitka (recommended for fast startup) or PyInstaller.

### Build with Nuitka (Recommended)

1. Make sure all dependencies are installed:
    ```bash
    pip install -r requirements.txt
    ```

2. Run the build script:
    ```bat
    build_nuitka.bat
    ```

   - The output will be in the `dist_nuitka` directory.
   - By default, this uses "onedir" mode (a folder with all dependencies).

### Build with PyInstaller (Alternative)

1. Make sure all dependencies are installed:
    ```bash
    pip install -r requirements.txt
    ```

2. Run the PyInstaller build script:
    ```bat
    build_pyinstaller.bat
    ```

   - The output will be in the `dist_pyinstaller` directory.
   - This uses the `build.spec` file for configuration.

**Note:**  
- Ensure you have the correct Python version (3.10–3.12) and a compatible NVIDIA GPU for best performance.
- The build scripts will automatically verify and download required DocTR models before building.

## Usage

1. Start the application:
```bash
python main.py
```

2. Using the GUI:
   - Select input mode (Single File/Folder/PDF)
   - Choose input file(s) and output directory
   - (Optional) Enable "Archiving?" and specify an archive directory to move processed input files/folders after OCR. The original folder structure will be preserved in the archive.
   - Configure processing options (DPI, output format, compression)
   - Click "Start Processing" to begin OCR

### Input Formats Supported:
- Images: TIFF, JPEG, PNG, BMP, GIF, and more
- Documents: PDF

### Output Formats:
- Searchable PDFs
- HOCR (HTML-based OCR) files

### Archiving Option

- If "Archiving?" is enabled, after successful processing, input files/folders are moved to the specified archive directory, preserving their folder structure.
- Archive settings are saved in `config.ini` and restored on next launch.
- If archiving is not enabled or the archive path is not specified, input files are not moved.
- Proper error handling is provided if the archive directory is missing or invalid.

# VisionLane OCR

[EXPERIMENTAL RELEASE AND WILL BE UPDATED IN THE FUTURE]

![icon_landscape_transparent_bg2](https://github.com/user-attachments/assets/c05d5fa0-7f75-4382-b300-8884ccbe196b)

A powerful OCR (Optical Character Recognition) application built with DocTR and PyQt6, designed for high-performance document processing with GPU acceleration support.

![gui](https://github.com/user-attachments/assets/8bba62e9-20bf-4c7e-b0ac-fd264b09202d)

![Apache License](https://img.shields.io/badge/license-Apache-blue.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)
![GPU Support](https://img.shields.io/badge/GPU-CUDA_Support-green.svg)

## Features

- 🚀 GPU-accelerated OCR processing using CUDA
- 📁 Batch processing support for multiple files
- 📄 Support for multiple input formats (TIFF, JPEG, PNG, PDF)
- 🔄 Concurrent processing with multi-threading
- 💾 Output in PDF and HOCR formats
- 🖥️ PyQt6-based GUI interface
- 📊 Real-time processing status and GPU metrics
- 🔍 High-accuracy text recognition using DocTR

## Requirements

- Python 3.10 or higher
- NVIDIA GPU with CUDA support (optional, but recommended)
- Windows/Linux OS

Roadmap
The following features and improvements are planned for future releases:

🔧 Functional Improvements
 Fix initialization of models if not found after build
→ Automatically download or notify if models are missing in cache directory (C:\Users\%USERNAME%\.doctr\cache\*.pt)

 Add custom selection for DocTR text detection and recognition models
→ User-selectable models for more flexibility and accuracy tuning

 Implement a config file to persist user settings
→ Save UI preferences, model selections, output options, etc.

📁 File Handling Enhancements
 Add option to archive processed files
→ Automatically move completed input files to a separate folder

 Add compression function for output PDFs
→ Preserve searchable text while applying JPEG-based compression

🎨 UI/UX Features
 Add dark mode toggle
→ Supports system default, with manual switch option

## Installation

1. Clone the repository:
```bash
git clone https://github.com/NeoMatrix14241/VisionLane.git
cd VisionLane
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/Mac:
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Test CUDA availability (optional):
```bash
python test_cuda.py
```

## Usage

1. Start the application:
```bash
python main.py
```

2. Using the GUI:
   - Select input mode (Single File/Folder/PDF)
   - Choose input file(s) and output directory
   - Configure processing options (DPI, output format)
   - Click "Start Processing" to begin OCR

### Input Formats Supported:
- Images: TIFF, JPEG, PNG
- Documents: PDF

### Output Formats:
- Searchable PDFs
- HOCR (HTML-based OCR) files

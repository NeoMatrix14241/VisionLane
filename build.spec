# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    get_package_paths,
    copy_metadata
)

block_cipher = None

# Skip problematic modules
# The subprocess is dying when trying to import onnx.reference
excludes = [
    'onnx.reference',  # Main problematic module
    'onnx.reference.ops',
    'onnx.reference.ops.aionnxml',
    'onnx.reference.ops.experimental',
    'onnx.reference.ops.aionnx_preview_training',
    'onnx.reference.ops_optimized'
]

# Explicit hidden imports for GUI/OCR/ML
hiddenimports = [
    'doctr',
    'doctr.models',
    'doctr.datasets',
    'doctr.io',
    'doctr.utils',
    'torch',
    'torch.nn',
    'torch.optim',
    'torch.cuda',
    'torchvision',
    'torchvision.transforms',
    'PIL',
    'PIL._imagingtk',
    'PIL._tkinter_finder',
    'numpy',
    'cv2',
    'psutil',
    'pynvml',
    'GPUtil',
    'PyPDF2',
    'ocrmypdf',
    'ocrmypdf.data',
    'ocrmypdf.api',
    'ocrmypdf.helpers',
    'pdf2image',
    'img2pdf',
    'pdfminer',
    'pdfminer.six',
    'pdfminer.high_level',
    'pdfminer.layout',
    'pdfminer.converter',
    'pdfminer.pdfinterp',
    'pdfminer.pdfpage',
    'PyQt6',
    'PyQt6.QtWidgets',
    'PyQt6.QtGui',
    'PyQt6.QtCore',
    'PyQt6.QtPrintSupport',
    'multiprocessing',
    'multiprocessing.context',
    'multiprocessing.connection',
    'multiprocessing.spawn',
    'multiprocessing.util',
    'multiprocessing.pool',
    'multiprocessing.managers',
    'multiprocessing.sharedctypes',
    'torch.multiprocessing',
    'torch.multiprocessing.spawn',
    'magic',  # python-magic
    'magic.loader',
    'tqdm',
    'colorama',
    'typing_extensions',
    # Add the base onnx module - but exclude onnx.reference which is causing the crash
    'onnx',
    'onnx.defs',
    'onnx.backend',
    'onnx.checker',
    'onnx.helper',
    'onnx.mapping',
    'onnx.numpy_helper',
    'onnx.shape_inference',
    'onnx.version',
]

# Add package submodules PyInstaller may miss 
# BUT exclude the problematic onnx.reference and related modules
hiddenimports += collect_submodules('ocrmypdf')
hiddenimports += collect_submodules('doctr')
hiddenimports += collect_submodules('pdfminer')
hiddenimports += collect_submodules('PyQt6')

# Remove any excluded modules from hiddenimports
hiddenimports = [m for m in hiddenimports if not any(m.startswith(ex) for ex in excludes)]

# Initialize datas list
datas = []

# Safely collect package metadata
def safe_copy_metadata(package_name):
    try:
        return copy_metadata(package_name)
    except Exception as e:
        print(f"Warning: Could not copy metadata for {package_name}: {e}")
        return []

# Collect package metadata
packages_for_metadata = ['torch', 'ocrmypdf', 'pdf2image']
for package in packages_for_metadata:
    datas += safe_copy_metadata(package)

# Special handling for doctr - try to find its location manually if metadata is missing
try:
    import doctr
    doctr_path = os.path.dirname(doctr.__file__)
    # Include the package directory directly instead of using metadata
    datas.append((doctr_path, 'doctr'))
    print(f"Added doctr package files from {doctr_path}")
    
    # Specifically add the models directory
    doctr_models_path = os.path.join(doctr_path, 'models')
    if os.path.exists(doctr_models_path):
        datas.append((doctr_models_path, 'doctr/models'))
        print(f"Added doctr models from {doctr_models_path}")
except ImportError:
    print("Warning: DocTR not found!")

# Gather necessary data files
datas += collect_data_files('ocrmypdf')
datas += collect_data_files('doctr')
datas += collect_data_files('PIL')
datas += collect_data_files('pdfminer')

# OCRmyPDF resources
try:
    ocrmypdf_path = Path(get_package_paths('ocrmypdf')[0])
    data_dir = ocrmypdf_path / 'data'
    if data_dir.exists():
        datas.append((str(data_dir), 'ocrmypdf/data'))
        
    # Explicitly include pdf.ttf
    pdf_ttf = data_dir / 'pdf.ttf'
    if pdf_ttf.exists():
        datas.append((str(pdf_ttf), 'ocrmypdf/data'))
    else:
        print("Warning: pdf.ttf not found!")
except ImportError:
    print("Warning: ocrmypdf package not found!")

# Add Poppler binaries for pdf2image if on Windows
if sys.platform.startswith('win'):
    # Check if POPPLER_PATH environment variable exists
    poppler_path = os.environ.get('POPPLER_PATH')
    if poppler_path and os.path.exists(poppler_path):
        datas.append((poppler_path, 'poppler'))
    else:
        print("Warning: POPPLER_PATH not set or directory doesn't exist!")

# Add Tesseract binaries for OCRmyPDF if on Windows
if sys.platform.startswith('win'):
    # Check if TESSERACT_PATH environment variable exists
    tesseract_path = os.environ.get('TESSERACT_PATH')
    if tesseract_path and os.path.exists(tesseract_path):
        datas.append((tesseract_path, 'tesseract'))
    else:
        print("Warning: TESSERACT_PATH not set or directory doesn't exist!")

# Collect all QT plugins
from PyInstaller.utils.hooks import collect_all

for module in ['PyQt6']:
    try:
        data_temp, bin_temp, hiddenimports_temp = collect_all(module)
        datas.extend(data_temp)
        hiddenimports.extend(hiddenimports_temp)
    except Exception as e:
        print(f"Warning: Error collecting {module}: {e}")

# Add environment variables to help torch find its libraries
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,  # Explicitly exclude problematic modules
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out problematic binaries related to onnx.reference
a.binaries = [(name, path, type_) for name, path, type_ in a.binaries 
             if not any(excluded in path for excluded in excludes)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VisionLaneOCR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging, change to False for production
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VisionLaneOCR',
)
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
    # --- Add your own modules ---
    'gui.main_window',
    'gui.splash_screen',
    'gui.processing_thread',
    'gui.log_handler',
    'ocr_processor',
    'utils.process_manager',
    'utils.thread_killer',
    'utils.logging_config',
    'utils.safe_logger',
    'utils.image_processor',
    'utils.pypdfcompressor',
    'utils.debug_helper',
]

# Add package submodules PyInstaller may miss 
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

# Collect all QT plugins
from PyInstaller.utils.hooks import collect_all

for module in ['PyQt6']:
    try:
        data_temp, bin_temp, hiddenimports_temp = collect_all(module)
        datas.extend(data_temp)
        hiddenimports.extend(hiddenimports_temp)
    except Exception as e:
        print(f"Warning: Error collecting {module}: {e}")

# Add more explicit hidden imports for Windows compatibility and PyQt6 plugins
if sys.platform.startswith('win'):
    # Ensure PyQt6 plugins are included (platforms, imageformats, etc.)
    from PyInstaller.utils.hooks import collect_dynamic_libs
    pyqt6_plugins = [
        ('PyQt6', 'Qt6/plugins/platforms'),
        ('PyQt6', 'Qt6/plugins/imageformats'),
        ('PyQt6', 'Qt6/plugins/printsupport'),
        ('PyQt6', 'Qt6/plugins/styles'),
    ]
    for mod, subdir in pyqt6_plugins:
        try:
            datas += collect_data_files(mod, subdir=subdir)
        except Exception as e:
            print(f"Warning: Could not collect {mod} {subdir}: {e}")

    # Add tcl/tk DLLs if needed (for PIL, image processing)
    import glob
    tcl_dirs = [
        os.path.join(sys.base_prefix, 'DLLs'),
        os.path.join(sys.base_prefix, 'Library', 'bin'),
    ]
    for tcl_dir in tcl_dirs:
        if os.path.exists(tcl_dir):
            for dll in glob.glob(os.path.join(tcl_dir, 'tcl*.dll')) + glob.glob(os.path.join(tcl_dir, 'tk*.dll')):
                datas.append((dll, '.'))

# Add Windows-specific binaries for Ghostscript, Poppler, Tesseract if available
if sys.platform.startswith('win'):
    # Ghostscript
    gs_path = os.environ.get('GHOSTSCRIPT_PATH')
    if gs_path and os.path.exists(gs_path):
        datas.append((gs_path, 'ghostscript'))
    else:
        # Try common install locations
        for base in [
            r"C:\Program Files\gs",
            r"C:\Program Files (x86)\gs"
        ]:
            if os.path.exists(base):
                for sub in os.listdir(base):
                    exe = os.path.join(base, sub, "bin", "gswin64c.exe")
                    if os.path.exists(exe):
                        datas.append((exe, 'ghostscript'))
                        break

# Add config.ini as a data file if present
if os.path.exists('config.ini'):
    datas.append(('config.ini', '.'))

# Add icon.ico as a data file if present
if os.path.exists('icon.ico'):
    datas.append(('icon.ico', '.'))

# Add README.md and LICENSE for completeness
for docfile in ['README.md', 'LICENSE']:
    if os.path.exists(docfile):
        datas.append((docfile, '.'))

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
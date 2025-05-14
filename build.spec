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

# ADD DOCTR CACHE MODELS - Find automatically using user's home directory
print("\n=== DEBUGGING DOCTR MODELS INCLUSION ===")
found_doctr_models = False

if sys.platform.startswith('win'):
    # Windows path
    user_home = os.path.expanduser('~')
    doctr_cache_path = os.path.join(user_home, '.cache', 'doctr', 'models')
else:
    # Linux/Mac path
    user_home = os.path.expanduser('~')
    doctr_cache_path = os.path.join(user_home, '.cache', 'doctr', 'models')

print(f"Looking for DocTR models in primary location: {doctr_cache_path}")
if os.path.exists(doctr_cache_path):
    # List files found to confirm content
    print(f"Found DocTR cache directory at {doctr_cache_path}")
    print("Files found in this directory:")
    for root, dirs, files in os.walk(doctr_cache_path):
        for file in files:
            print(f"  - {os.path.join(root, file)}")
    
    # Add with a more explicit destination path
    datas.append((doctr_cache_path, os.path.join('doctr', 'cache', 'models')))
    print(f"Added DocTR cached models from {doctr_cache_path} to 'doctr/cache/models'")
    found_doctr_models = True
else:
    print(f"Warning: DocTR cache directory not found at {doctr_cache_path}")
    
    # Try alternative locations with more verbose logging
    print("Searching alternative DocTR model locations:")
    alternate_paths = []
    
    # Try to find through doctr package
    try:
        import doctr
        pkg_path = os.path.dirname(doctr.__file__)
        print(f"Found DocTR package at: {pkg_path}")
        
        # Check for models directory within the package
        pkg_models_path = os.path.join(pkg_path, 'models')
        if os.path.exists(pkg_models_path):
            print(f"Found DocTR package models at: {pkg_models_path}")
            alternate_paths.append(pkg_models_path)
        
        # Look for cache relative to package
        cache_rel_path = os.path.join(os.path.dirname(pkg_path), '.cache', 'doctr', 'models')
        alternate_paths.append(cache_rel_path)
    except ImportError:
        print("Could not import doctr package")
        
    # Try common alternative locations
    if sys.platform.startswith('win'):
        appdata_path = os.path.join(os.environ.get('APPDATA', ''), 'doctr', 'models')
        localappdata_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'doctr', 'models')
        alternate_paths.append(appdata_path)
        alternate_paths.append(localappdata_path)
        print(f"Checking Windows-specific paths: \n  - {appdata_path}\n  - {localappdata_path}")
    
    # Check all alternate paths
    for alt_path in alternate_paths:
        print(f"Checking alternate path: {alt_path}")
        if os.path.exists(alt_path):
            print(f"Found DocTR models at alternate path: {alt_path}")
            print("Files found in this directory:")
            for root, dirs, files in os.walk(alt_path):
                for file in files:
                    print(f"  - {os.path.join(root, file)}")
            
            datas.append((alt_path, os.path.join('doctr', 'models')))
            print(f"Added DocTR models from alternate path: {alt_path} to 'doctr/models'")
            found_doctr_models = True
            break
            
# If we still haven't found the models, try a direct import to learn how doctr locates its models
if not found_doctr_models:
    print("No DocTR model directories found in standard locations. Trying to detect via doctr import...")
    try:
        import doctr
        import doctr.models
        print("Successfully imported doctr.models")
        
        # Try to find any relevant methods that might help us locate models
        model_funcs = [attr for attr in dir(doctr.models) if callable(getattr(doctr.models, attr)) and attr.startswith("get_")]
        print(f"Found possible model getter functions: {model_funcs}")
        
        # If there's a get_model_dir function or similar, try to use it
        if hasattr(doctr.models, "get_model_dir"):
            model_dir = doctr.models.get_model_dir()
            print(f"DocTR model directory according to get_model_dir(): {model_dir}")
            if os.path.exists(model_dir):
                datas.append((model_dir, os.path.join('doctr', 'models')))
                print(f"Added DocTR models from detected path: {model_dir}")
                found_doctr_models = True
    except Exception as e:
        print(f"Error while trying to detect DocTR models via import: {e}")

print("=== END OF DOCTR MODELS DEBUGGING ===\n")

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
    console=True,  # Set to True for debugging, change to False for production
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
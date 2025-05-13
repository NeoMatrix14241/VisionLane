# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, get_package_paths

# Custom hidden imports - be more selective with torch imports
hiddenimports = [
    'doctr',
    'torch.nn',
    'torch.optim',
    'torch.utils.data',
    'torchvision.transforms',
    'PIL',
    'numpy',
    'cv2',
    'psutil',
    'pynvml',
    'GPUtil',
    'PyPDF2',
    'ocrmypdf',
    'ocrmypdf.data',
    'pdf2image'
] + collect_submodules('ocrmypdf')

# Start with a focused set of data files
datas = []

# Add application assets
if os.path.exists('./assets'):
    datas.append(('./assets', 'assets'))

# Add splash screen image explicitly
if os.path.exists('./assets/splash.png'):
    datas.append(('./assets/splash.png', 'assets'))

# Add critical OCRmyPDF data files, but be more selective
ocrmypdf_path = Path(get_package_paths('ocrmypdf')[0])
ocrmypdf_data_path = ocrmypdf_path / 'data'
if ocrmypdf_data_path.exists():
    for file in ocrmypdf_data_path.glob('*'):
        datas.append((str(file), str(file.relative_to(ocrmypdf_path.parent))))

# Explicitly handle pdf.ttf
pdf_ttf = ocrmypdf_data_path / 'pdf.ttf'
if pdf_ttf.exists():
    datas.append((str(pdf_ttf), 'ocrmypdf/data'))
else:
    print("Warning: pdf.ttf not found at", str(pdf_ttf))

# Add doctr model files, but be selective
doctr_data = collect_data_files('doctr', include_py_files=True, 
                               subdir='models')
datas.extend(doctr_data)

# We'll be more selective with torch - only include what's essential
# This is a significant improvement over collecting all of torch

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'notebook'],  # Exclude unnecessary packages
    noarchive=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None
)

# Remove duplicate files to reduce size
def remove_duplicates(list_of_tuples):
    seen = set()
    result = []
    for item in list_of_tuples:
        if item[0] not in seen:
            seen.add(item[0])
            result.append(item)
    return result

a.datas = remove_duplicates(a.datas)

pyz = PYZ(a.pure)
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
    console=False,  # Set to True temporarily for debugging if needed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
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
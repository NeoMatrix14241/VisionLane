# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    get_package_paths
)

# Explicit hidden imports for GUI/OCR/ML
hiddenimports = [
    'doctr',
    'torch',
    'torchvision',
    'PIL',
    'numpy',
    'cv2',
    'psutil',
    'pynvml',
    'GPUtil',
    'PyPDF2',
    'ocrmypdf',
    'ocrmypdf.data',
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
    'multiprocessing.forking',
    'multiprocessing.spawn',
    'multiprocessing.util',
    'multiprocessing.pool',
    'multiprocessing.managers',
    'multiprocessing.sharedctypes',
    'torch.multiprocessing',
    'torch.multiprocessing.spawn',
]

# Add package submodules PyInstaller may miss
hiddenimports += collect_submodules('ocrmypdf')
hiddenimports += collect_submodules('doctr')
hiddenimports += collect_submodules('pdfminer')

# Gather necessary data files
datas = (
    collect_data_files('ocrmypdf') +
    collect_data_files('doctr') +
    collect_data_files('torch') +
    collect_data_files('PIL') +
    collect_data_files('pdfminer')
)

# Include ocrmypdf font
ocrmypdf_path = Path(get_package_paths('ocrmypdf')[0])
pdf_ttf = ocrmypdf_path / 'data' / 'pdf.ttf'
if pdf_ttf.exists():
    datas.append(('ocrmypdf/data/pdf.ttf', str(pdf_ttf)))
else:
    print("Warning: pdf.ttf not found!")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

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
    console=False,  # GUI mode, no console window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='VisionLaneOCR',
)

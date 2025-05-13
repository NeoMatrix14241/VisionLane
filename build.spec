# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, get_package_paths

# Custom hidden imports
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
    'pdf2image'
] + collect_submodules('ocrmypdf')

# Collect package data
datas = collect_data_files('ocrmypdf') + collect_data_files('doctr') + collect_data_files('torch')

# Ensure pdf.ttf is included
ocrmypdf_path = Path(get_package_paths('ocrmypdf')[0])
pdf_ttf = ocrmypdf_path / 'data' / 'pdf.ttf'
if pdf_ttf.exists():
    datas.append(('ocrmypdf/data/pdf.ttf', str(pdf_ttf)))
else:
    print("Warning: pdf.ttf not found!")

a = Analysis(
    ['main.py'],  # Make sure your entry script is 'main.py'
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VisionLane',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VisionLane',
)

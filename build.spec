import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
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
        'ocrmypdf.data',  # Add ocrmypdf.data module
        'pdf2image'
    ] + collect_submodules('ocrmypdf'),  # Include all ocrmypdf submodules
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Add ocrmypdf data files
ocrmypdf_files = [(dest, src, 'DATA') for dest, src in collect_data_files('ocrmypdf')]
a.datas.extend(ocrmypdf_files)

# Ensure proper collection format for torch and model files
model_files = [(dest, src, 'DATA') for dest, src in collect_data_files('doctr')]
a.datas.extend(model_files)

torch_files = [(dest, src, 'DATA') for dest, src in collect_data_files('torch')]
a.datas.extend(torch_files)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    console=True,
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
    name='VisionLane'
)

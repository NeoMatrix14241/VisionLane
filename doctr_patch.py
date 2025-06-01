"""
DocTR Patch Module: Ensures PyTorch is properly detected in compiled environments.
This module should be imported before any DocTR imports.
"""

import os
import sys
import importlib

# Force PyTorch backend by setting environment variables
os.environ['USE_TORCH'] = '1'
os.environ['DOCTR_BACKEND'] = 'torch'

# Check if PyTorch is available and patch detection
try:
    import torch
    TORCH_AVAILABLE = True
    print("DocTR Patch: PyTorch detected successfully")
except ImportError:
    TORCH_AVAILABLE = False
    print("DocTR Patch: PyTorch import failed!")

# Patch DocTR's file_utils directly if it's already loaded
if 'doctr.file_utils' in sys.modules:
    sys.modules['doctr.file_utils']._TORCH_AVAILABLE = TORCH_AVAILABLE

# Apply patches to DocTR if already imported
if 'doctr' in sys.modules:
    if hasattr(sys.modules['doctr'], 'file_utils'):
        sys.modules['doctr'].file_utils._TORCH_AVAILABLE = TORCH_AVAILABLE

# Create a custom importer to patch doctr.file_utils when it's imported
_original_import = __import__

def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):
    module = _original_import(name, globals, locals, fromlist, level)
    
    # Patch doctr.file_utils after it's imported
    if name == 'doctr.file_utils' or (name == 'file_utils' and fromlist and 'doctr' in globals.get('__name__', '')):
        if hasattr(module, '_TORCH_AVAILABLE'):
            module._TORCH_AVAILABLE = TORCH_AVAILABLE
            print("DocTR Patch: Patched doctr.file_utils._TORCH_AVAILABLE")
        
        # Patch is_torch_available function
        if hasattr(module, 'is_torch_available'):
            original_is_torch_available = module.is_torch_available
            module.is_torch_available = lambda: TORCH_AVAILABLE
            print("DocTR Patch: Patched doctr.file_utils.is_torch_available function")
    
    return module

# Install the patched importer
sys.modules['builtins'].__import__ = _patched_import

print("DocTR Patch: PyTorch detection patching complete")

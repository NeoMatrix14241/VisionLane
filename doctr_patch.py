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
    if not hasattr(sys.modules['doctr.file_utils'], 'ENV_VARS_TRUE_VALUES'):
        sys.modules['doctr.file_utils'].ENV_VARS_TRUE_VALUES = ['TRUE', 'True', 'true', '1', 'YES', 'Yes', 'yes']

# Apply patches to DocTR if already imported
if 'doctr' in sys.modules:
    if hasattr(sys.modules['doctr'], 'file_utils'):
        sys.modules['doctr'].file_utils._TORCH_AVAILABLE = TORCH_AVAILABLE
        if not hasattr(sys.modules['doctr'].file_utils, 'ENV_VARS_TRUE_VALUES'):
            sys.modules['doctr'].file_utils.ENV_VARS_TRUE_VALUES = ['TRUE', 'True', 'true', '1', 'YES', 'Yes', 'yes']

# Create a custom importer to patch doctr.file_utils when it's imported
_original_import = __import__
_patch_in_progress = set()  # Prevent infinite loops

def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):
    # Prevent infinite import loops
    if name in _patch_in_progress:
        return _original_import(name, globals, locals, fromlist, level)
    
    try:
        _patch_in_progress.add(name)
        module = _original_import(name, globals, locals, fromlist, level)
        
        # Patch doctr.file_utils after it's imported
        if name == 'doctr.file_utils' or (name == 'file_utils' and fromlist and globals and 'doctr' in globals.get('__name__', '')):
            if hasattr(module, '_TORCH_AVAILABLE'):
                module._TORCH_AVAILABLE = TORCH_AVAILABLE
                print("DocTR Patch: Patched doctr.file_utils._TORCH_AVAILABLE")
            
            # Add missing ENV_VARS_TRUE_VALUES
            if not hasattr(module, 'ENV_VARS_TRUE_VALUES'):
                module.ENV_VARS_TRUE_VALUES = ['TRUE', 'True', 'true', '1', 'YES', 'Yes', 'yes']
                print("DocTR Patch: Added ENV_VARS_TRUE_VALUES")
            
            # Patch is_torch_available function
            if hasattr(module, 'is_torch_available'):
                original_is_torch_available = module.is_torch_available
                module.is_torch_available = lambda: TORCH_AVAILABLE
                print("DocTR Patch: Patched doctr.file_utils.is_torch_available function")
        
        return module
    finally:
        _patch_in_progress.discard(name)

# Install the patched importer
sys.modules['builtins'].__import__ = _patched_import

print("DocTR Patch: PyTorch detection patching complete")

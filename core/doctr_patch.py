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

# DISABLE IMPORT HOOK TO PREVENT CONFLICTS WITH doctr_torch_setup.py
# The comprehensive patching is handled by doctr_torch_setup.py instead
print("DocTR Patch: Basic patching complete (import hook disabled to prevent conflicts)")
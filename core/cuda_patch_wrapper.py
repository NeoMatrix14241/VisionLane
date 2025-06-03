"""
CUDA Patch Wrapper for Nuitka
This module combines all CUDA compatibility patches and should be imported
as early as possible in the application startup process.
"""
import os
import sys
def apply_all_cuda_patches():
    """Apply all CUDA compatibility patches in the correct order"""
    print("CUDA Patch Wrapper: Applying comprehensive CUDA patches for Nuitka...")
    # Step 1: Apply environment patches first
    try:
        from .cuda_env_patch import apply_cuda_environment_patches
        apply_cuda_environment_patches()
        print("CUDA Patch Wrapper: Environment patches applied successfully")
    except ImportError:
        try:
            from cuda_env_patch import apply_cuda_environment_patches
            apply_cuda_environment_patches()
            print("CUDA Patch Wrapper: Environment patches applied successfully")
        except ImportError:
            print("CUDA Patch Wrapper: Warning - Could not import environment patches")
    # Step 2: Apply Nuitka-specific CUDA patches
    try:
        from .nuitka_cuda_patch import apply_nuitka_cuda_patches, is_nuitka_environment
        if is_nuitka_environment():
            apply_nuitka_cuda_patches()
            print("CUDA Patch Wrapper: Nuitka CUDA patches applied successfully")
        else:
            print("CUDA Patch Wrapper: Not in Nuitka environment, skipping Nuitka patches")
    except ImportError:
        try:
            from nuitka_cuda_patch import apply_nuitka_cuda_patches, is_nuitka_environment
            if is_nuitka_environment():
                apply_nuitka_cuda_patches()
                print("CUDA Patch Wrapper: Nuitka CUDA patches applied successfully")
            else:
                print("CUDA Patch Wrapper: Not in Nuitka environment, skipping Nuitka patches")
        except ImportError:
            print("CUDA Patch Wrapper: Warning - Could not import Nuitka CUDA patches")
    # Step 3: Apply DocTR patches
    try:
        from .doctr_patch import TORCH_AVAILABLE
        print(f"CUDA Patch Wrapper: DocTR patch loaded, PyTorch available: {TORCH_AVAILABLE}")
    except ImportError:
        try:
            from doctr_patch import TORCH_AVAILABLE
            print(f"CUDA Patch Wrapper: DocTR patch loaded, PyTorch available: {TORCH_AVAILABLE}")
        except ImportError:
            print("CUDA Patch Wrapper: Warning - Could not import DocTR patches")
    # Step 4: Apply DocTR torch setup
    try:
        from .doctr_torch_setup import _TORCH_AVAILABLE
        print(f"CUDA Patch Wrapper: DocTR torch setup loaded, PyTorch available: {_TORCH_AVAILABLE}")
    except ImportError:
        try:
            from doctr_torch_setup import _TORCH_AVAILABLE
            print(f"CUDA Patch Wrapper: DocTR torch setup loaded, PyTorch available: {_TORCH_AVAILABLE}")
        except ImportError:
            print("CUDA Patch Wrapper: Warning - Could not import DocTR torch setup")
    
    # Step 5: Apply hardware monitoring patches for Nuitka
    try:
        from .hardware_monitoring_patch import apply_hardware_monitoring_patches
        apply_hardware_monitoring_patches()
        print("CUDA Patch Wrapper: Hardware monitoring patches applied successfully")
    except ImportError:
        try:
            from hardware_monitoring_patch import apply_hardware_monitoring_patches
            apply_hardware_monitoring_patches()
            print("CUDA Patch Wrapper: Hardware monitoring patches applied successfully")
        except ImportError:
            print("CUDA Patch Wrapper: Warning - Could not import hardware monitoring patches")
    
    print("CUDA Patch Wrapper: All CUDA patches applied")
def patch_torch_cuda():
    """Legacy torch CUDA monkey patch"""
    try:
        import torch
        import torch.version
        # Store original functions
        if not hasattr(torch, '_original_cuda_version'):
            torch._original_cuda_version = torch.version.cuda
        # Override version checks
        if torch.version.cuda == "12.8":
            torch.version.cuda = "12.9"  # Match your driver
        # Patch CUDA runtime checks
        if hasattr(torch, 'cuda') and hasattr(torch.cuda, 'is_available'):
            original_is_available = torch.cuda.is_available
            def patched_is_available():
                try:
                    return original_is_available()
                except RuntimeError as e:
                    if "API call is not supported" in str(e):
                        # Try to recover by initializing with different settings
                        return True  # Assume available for compilation
                    raise
            torch.cuda.is_available = patched_is_available
    except ImportError:
        pass  # torch not available yet
def is_cuda_available_safe():
    """Safely check if CUDA is available after patching"""
    try:
        import torch
        return torch.cuda.is_available()
    except Exception as e:
        print(f"CUDA Patch Wrapper: CUDA availability check failed: {e}")
        return False
# Auto-apply all patches when imported
apply_all_cuda_patches()
patch_torch_cuda()

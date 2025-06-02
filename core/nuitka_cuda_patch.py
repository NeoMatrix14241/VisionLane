"""
Nuitka CUDA Compatibility Patch
This module provides comprehensive CUDA monkey patching for Nuitka compiled applications.
It addresses specific CUDA initialization issues that occur in Nuitka but not PyInstaller.
"""
import os
import sys
import functools
import warnings
from typing import Any, Optional, Callable, Dict
# Set environment variables early
os.environ['CUDA_LAUNCH_BLOCKING'] = '0'  # Disable blocking to prevent hangs
os.environ['CUDA_CACHE_DISABLE'] = '0'    # Allow caching for better performance
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'
class NuitkaCudaPatch:
    """Comprehensive CUDA patching for Nuitka compatibility"""
    def __init__(self):
        self.patches_applied = False
        self.cuda_available = None
        self.device_count = 0
        self.fallback_mode = False
    def apply_patches(self) -> bool:
        """Apply all necessary CUDA patches for Nuitka"""
        if self.patches_applied:
            return True
        print("Nuitka CUDA Patch: Applying comprehensive CUDA compatibility patches...")
        try:
            # First, try to import torch safely
            import torch
            # Patch torch.cuda early to prevent initialization errors
            self._patch_torch_cuda_early()
            # Apply specific Nuitka compatibility patches
            self._patch_cuda_initialization()
            self._patch_cuda_device_queries()
            self._patch_cuda_memory_management()
            self._patch_cuda_streams()
            # Test CUDA availability safely
            self._test_cuda_safely()
            self.patches_applied = True
            print(f"Nuitka CUDA Patch: Successfully applied patches. CUDA available: {self.cuda_available}")
            return True
        except Exception as e:
            print(f"Nuitka CUDA Patch: Failed to apply patches: {e}")
            self._enable_fallback_mode()
            return False
    def _patch_torch_cuda_early(self):
        """Apply early patches before any CUDA calls"""
        import torch
        # Store original methods
        if not hasattr(torch.cuda, '_original_is_available'):
            torch.cuda._original_is_available = torch.cuda.is_available
            torch.cuda._original_device_count = torch.cuda.device_count
            torch.cuda._original_get_device_name = torch.cuda.get_device_name
            torch.cuda._original_get_device_properties = torch.cuda.get_device_properties
            torch.cuda._original_get_device_capability = torch.cuda.get_device_capability
            torch.cuda._original_current_device = torch.cuda.current_device
        # Create safe wrapper for is_available
        def safe_is_available():
            try:
                if self.cuda_available is not None:
                    return self.cuda_available
                return torch.cuda._original_is_available()
            except Exception as e:
                print(f"Nuitka CUDA Patch: is_available error: {e}")
                self.cuda_available = False
                return False
        # Create safe wrapper for device_count
        def safe_device_count():
            try:
                if self.device_count > 0:
                    return self.device_count
                count = torch.cuda._original_device_count()
                self.device_count = count
                return count
            except Exception as e:
                print(f"Nuitka CUDA Patch: device_count error: {e}")
                self.device_count = 0
                return 0
        # Apply the patches
        torch.cuda.is_available = safe_is_available
        torch.cuda.device_count = safe_device_count
    def _patch_cuda_initialization(self):
        """Patch CUDA initialization to handle Nuitka-specific issues"""
        import torch
        # Patch _lazy_init to be more resilient
        if hasattr(torch.cuda, '_lazy_init'):
            original_lazy_init = torch.cuda._lazy_init
            def safe_lazy_init():
                try:
                    if self.fallback_mode:
                        return
                    return original_lazy_init()
                except Exception as e:
                    print(f"Nuitka CUDA Patch: _lazy_init failed, enabling fallback: {e}")
                    self.fallback_mode = True
                    self.cuda_available = False
            torch.cuda._lazy_init = safe_lazy_init
    def _patch_cuda_device_queries(self):
        """Patch device query functions to handle API call failures"""
        import torch
        def safe_get_device_name(device=None):
            try:
                if self.fallback_mode:
                    return f"CUDA Device {device if device is not None else 0} (Nuitka Fallback)"
                return torch.cuda._original_get_device_name(device)
            except Exception as e:
                print(f"Nuitka CUDA Patch: get_device_name error: {e}")
                return f"CUDA Device {device if device is not None else 0} (Patched)"
        def safe_get_device_properties(device=None):
            try:
                if self.fallback_mode:
                    # Return a mock device properties object
                    return self._create_mock_device_properties(device)
                return torch.cuda._original_get_device_properties(device)
            except Exception as e:
                print(f"Nuitka CUDA Patch: get_device_properties error: {e}")
                return self._create_mock_device_properties(device)
        def safe_get_device_capability(device=None):
            try:
                if self.fallback_mode:
                    return (7, 5)  # Mock compute capability
                return torch.cuda._original_get_device_capability(device)
            except Exception as e:
                print(f"Nuitka CUDA Patch: get_device_capability error: {e}")
                return (7, 5)  # Return reasonable default
        def safe_current_device():
            try:
                if self.fallback_mode:
                    return 0
                return torch.cuda._original_current_device()
            except Exception as e:
                print(f"Nuitka CUDA Patch: current_device error: {e}")
                return 0
        # Apply patches
        torch.cuda.get_device_name = safe_get_device_name
        torch.cuda.get_device_properties = safe_get_device_properties
        torch.cuda.get_device_capability = safe_get_device_capability
        torch.cuda.current_device = safe_current_device
    def _patch_cuda_memory_management(self):
        """Patch CUDA memory management functions"""
        import torch
        # Patch memory functions to be safe
        if hasattr(torch.cuda, 'memory_allocated'):
            original_memory_allocated = torch.cuda.memory_allocated
            def safe_memory_allocated(device=None):
                try:
                    if self.fallback_mode:
                        return 0
                    return original_memory_allocated(device)
                except Exception:
                    return 0
            torch.cuda.memory_allocated = safe_memory_allocated
        if hasattr(torch.cuda, 'memory_reserved'):
            original_memory_reserved = torch.cuda.memory_reserved
            def safe_memory_reserved(device=None):
                try:
                    if self.fallback_mode:
                        return 0
                    return original_memory_reserved(device)
                except Exception:
                    return 0
            torch.cuda.memory_reserved = safe_memory_reserved
        if hasattr(torch.cuda, 'empty_cache'):
            original_empty_cache = torch.cuda.empty_cache
            def safe_empty_cache():
                try:
                    if self.fallback_mode:
                        return
                    return original_empty_cache()
                except Exception:
                    pass
            torch.cuda.empty_cache = safe_empty_cache
    def _patch_cuda_streams(self):
        """Patch CUDA stream operations"""
        import torch
        if hasattr(torch.cuda, 'synchronize'):
            original_synchronize = torch.cuda.synchronize
            def safe_synchronize(device=None):
                try:
                    if self.fallback_mode:
                        return
                    return original_synchronize(device)
                except Exception:
                    pass
            torch.cuda.synchronize = safe_synchronize
    def _test_cuda_safely(self):
        """Test CUDA availability with comprehensive error handling"""
        import torch
        try:
            # Test basic CUDA availability
            self.cuda_available = torch.cuda._original_is_available()
            if self.cuda_available:
                # Test device count
                self.device_count = torch.cuda._original_device_count()
                # Test device properties access (this often fails in Nuitka)
                for i in range(self.device_count):
                    try:
                        _ = torch.cuda._original_get_device_name(i)
                        _ = torch.cuda._original_get_device_capability(i)
                    except Exception as e:
                        print(f"Nuitka CUDA Patch: Device {i} query failed: {e}")
                        # Don't disable CUDA just because device queries fail
                        # The GPU might still be usable for computation
                        continue
                print(f"Nuitka CUDA Patch: CUDA test passed with {self.device_count} device(s)")
            else:
                print("Nuitka CUDA Patch: CUDA not available")
        except Exception as e:
            print(f"Nuitka CUDA Patch: CUDA test failed: {e}")
            self.cuda_available = False
            self.device_count = 0
    def _create_mock_device_properties(self, device=None):
        """Create a mock device properties object for fallback"""
        class MockDeviceProperties:
            def __init__(self, device_id=0):
                self.name = f"CUDA Device {device_id} (Nuitka Fallback)"
                self.major = 7
                self.minor = 5
                self.total_memory = 8 * 1024 * 1024 * 1024  # 8GB mock
                self.multi_processor_count = 80
            def __getattr__(self, name):
                # Return reasonable defaults for any missing attributes
                if 'memory' in name.lower():
                    return self.total_memory
                elif 'count' in name.lower():
                    return self.multi_processor_count
                else:
                    return 0
        return MockDeviceProperties(device if device is not None else 0)
    def _enable_fallback_mode(self):
        """Enable fallback mode when CUDA patches fail"""
        self.fallback_mode = True
        self.cuda_available = False
        self.device_count = 0
        print("Nuitka CUDA Patch: Fallback mode enabled - CUDA operations will be mocked")
# Global patch instance
_cuda_patch = NuitkaCudaPatch()
def apply_nuitka_cuda_patches() -> bool:
    """Apply Nuitka CUDA compatibility patches"""
    return _cuda_patch.apply_patches()
def is_nuitka_environment() -> bool:
    """Detect if running in Nuitka compiled environment"""
    return (
        hasattr(sys, 'frozen') or
        '__compiled__' in globals() or
        'nuitka' in sys.version.lower() or
        any('nuitka' in str(path).lower() for path in sys.path) or
        os.environ.get('__NUITKA_BINARY__') == '1'
    )
# Auto-apply patches if in Nuitka environment
if is_nuitka_environment():
    print("Nuitka CUDA Patch: Nuitka environment detected, auto-applying patches...")
    apply_nuitka_cuda_patches()
else:
    print("Nuitka CUDA Patch: Not in Nuitka environment, patches not needed")

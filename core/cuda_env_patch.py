"""
Comprehensive CUDA Environment Patch for Nuitka
This module should be imported very early in the application lifecycle,
preferably before any PyTorch or CUDA-related imports.
"""

import os
import sys
import warnings
from typing import Dict, Any, Optional

class CudaEnvironmentPatch:
    """Comprehensive environment patching for CUDA in Nuitka"""
    
    def __init__(self):
        self.applied = False
        self.environment_vars = {}
        
    def apply_environment_patches(self) -> None:
        """Apply comprehensive environment variable patches for CUDA compatibility"""
        if self.applied:
            return
            
        print("CUDA Environment Patch: Applying comprehensive environment patches...")
        
        # Core CUDA environment variables
        cuda_env_vars = {
            # Prevent blocking behavior that can cause hangs in Nuitka
            'CUDA_LAUNCH_BLOCKING': '0',
            
            # Memory management settings
            'PYTORCH_CUDA_ALLOC_CONF': 'max_split_size_mb:512,roundup_power2_divisions:16',
            'CUDA_MEMORY_FRACTION': '0.8',
            
            # Performance and compatibility settings
            'CUDA_CACHE_DISABLE': '0',  # Enable caching for better performance
            'CUDA_FORCE_PTX_JIT': '0',  # Disable forced PTX JIT compilation
            'CUDA_DISABLE_PTX_JIT': '0', # Don't disable PTX JIT entirely
            
            # Error handling and debugging
            'CUDA_DEVICE_ORDER': 'PCI_BUS_ID',  # Consistent device ordering
            'CUDA_VISIBLE_DEVICES': '',  # Will be set dynamically if needed
            
            # Driver compatibility
            'CUDA_DRIVER_LIBRARY_PATH': '',  # Will be set if needed
            'CUDA_TOOLKIT_ROOT_DIR': '',     # Will be set if needed
            
            # Suppress warnings that might interfere with Nuitka
            'PYTHONWARNINGS': 'ignore::UserWarning:torch',
            
            # Force PyTorch to use CUDA if available
            'PYTORCH_ENABLE_MPS_FALLBACK': '1',
            'PYTORCH_MPS_HIGH_WATERMARK_RATIO': '0.0',  # Disable MPS on macOS to prefer CUDA
        }
        
        # Apply environment variables
        for key, value in cuda_env_vars.items():
            if key not in os.environ or not os.environ[key]:
                os.environ[key] = value
                self.environment_vars[key] = value
                
        # Try to detect and set CUDA paths automatically
        self._detect_cuda_paths()
        
        # Apply additional Windows-specific patches
        if sys.platform.startswith('win'):
            self._apply_windows_patches()
            
        self.applied = True
        print(f"CUDA Environment Patch: Applied {len(self.environment_vars)} environment variables")
        
    def _detect_cuda_paths(self) -> None:
        """Automatically detect and set CUDA paths"""
        try:
            # Try to find CUDA installation
            cuda_paths = []
            
            if sys.platform.startswith('win'):
                # Windows CUDA paths
                program_files = [
                    os.environ.get('PROGRAMFILES', r'C:\Program Files'),
                    os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'),
                ]
                
                for pf in program_files:
                    nvidia_path = os.path.join(pf, 'NVIDIA GPU Computing Toolkit', 'CUDA')
                    if os.path.exists(nvidia_path):
                        # Find the latest version
                        versions = [d for d in os.listdir(nvidia_path) if os.path.isdir(os.path.join(nvidia_path, d))]
                        if versions:
                            latest_version = sorted(versions, reverse=True)[0]
                            cuda_path = os.path.join(nvidia_path, latest_version)
                            cuda_paths.append(cuda_path)
                            
            else:
                # Unix-like systems
                common_paths = [
                    '/usr/local/cuda',
                    '/opt/cuda',
                    '/usr/lib/cuda',
                ]
                cuda_paths.extend([p for p in common_paths if os.path.exists(p)])
                
            # Set CUDA toolkit path if found
            if cuda_paths:
                cuda_path = cuda_paths[0]  # Use the first/latest found
                if not os.environ.get('CUDA_TOOLKIT_ROOT_DIR'):
                    os.environ['CUDA_TOOLKIT_ROOT_DIR'] = cuda_path
                    self.environment_vars['CUDA_TOOLKIT_ROOT_DIR'] = cuda_path
                    
                # Set library path
                if sys.platform.startswith('win'):
                    lib_path = os.path.join(cuda_path, 'bin')
                else:
                    lib_path = os.path.join(cuda_path, 'lib64')
                    
                if os.path.exists(lib_path) and not os.environ.get('CUDA_DRIVER_LIBRARY_PATH'):
                    os.environ['CUDA_DRIVER_LIBRARY_PATH'] = lib_path
                    self.environment_vars['CUDA_DRIVER_LIBRARY_PATH'] = lib_path
                    
                print(f"CUDA Environment Patch: Found CUDA installation at {cuda_path}")
            else:
                print("CUDA Environment Patch: No CUDA installation found in standard locations")
                
        except Exception as e:
            print(f"CUDA Environment Patch: Error detecting CUDA paths: {e}")
            
    def _apply_windows_patches(self) -> None:
        """Apply Windows-specific CUDA patches"""
        try:
            # Add NVIDIA paths to PATH if they exist
            nvidia_paths = [
                r'C:\Program Files\NVIDIA Corporation\NVSMI',
                r'C:\Windows\System32',  # Where nvidia-ml.dll might be
            ]
            
            current_path = os.environ.get('PATH', '')
            path_additions = []
            
            for path in nvidia_paths:
                if os.path.exists(path) and path not in current_path:
                    path_additions.append(path)
                    
            if path_additions:
                new_path = os.pathsep.join(path_additions + [current_path])
                os.environ['PATH'] = new_path
                print(f"CUDA Environment Patch: Added {len(path_additions)} NVIDIA paths to PATH")
                
        except Exception as e:
            print(f"CUDA Environment Patch: Error applying Windows patches: {e}")


# Global instance
_env_patch = CudaEnvironmentPatch()

def apply_cuda_environment_patches() -> None:
    """Apply CUDA environment patches"""
    _env_patch.apply_environment_patches()

def get_applied_environment_vars() -> Dict[str, str]:
    """Get the environment variables that were applied"""
    return _env_patch.get_applied_vars() if hasattr(_env_patch, 'get_applied_vars') else {}

def is_nuitka_compiled() -> bool:
    """Check if running in Nuitka compiled environment"""
    return (
        hasattr(sys, 'frozen') or
        '__compiled__' in globals() or
        'nuitka' in sys.version.lower() or
        any('nuitka' in str(path).lower() for path in sys.path)
    )

def patch_cuda_environment():
    """Legacy function for backward compatibility"""
    apply_cuda_environment_patches()

# Auto-apply patches if in Nuitka environment
if is_nuitka_compiled():
    print("CUDA Environment Patch: Nuitka environment detected, auto-applying environment patches...")
    apply_cuda_environment_patches()
else:
    print("CUDA Environment Patch: Development environment detected, minimal patching applied")
    # Still apply some basic patches for consistency
    _env_patch.apply_environment_patches()
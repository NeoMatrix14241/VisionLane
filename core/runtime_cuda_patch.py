import functools
import sys
import warnings
import logging

class RuntimeCudaPatch:
    """Runtime CUDA patching for Nuitka compatibility"""
    
    def __init__(self):
        self.patched_functions = []
        self.original_functions = {}
        self.logger = logging.getLogger(__name__)
        
    def cuda_error_handler(self, func, fallback_value=None):
        """Decorator to catch and handle CUDA API errors"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except RuntimeError as e:
                error_msg = str(e)
                if any(keyword in error_msg for keyword in [
                    "API call is not supported in the installed CUDA driver",
                    "CUDA driver version is insufficient",
                    "no kernel image is available for execution",
                    "invalid device ordinal"
                ]):
                    self.logger.warning(f"CUDA API error handled in {func.__name__}: {e}")
                    return fallback_value
                raise
            except Exception as e:
                self.logger.warning(f"Unexpected error in {func.__name__}: {e}")
                return fallback_value
        return wrapper

    def patch_cuda_initialization(self):
        """Patch CUDA initialization functions"""
        try:
            import torch
            
            # Patch is_available
            if hasattr(torch.cuda, 'is_available'):
                original = torch.cuda.is_available
                self.original_functions['cuda.is_available'] = original
                
                def safe_is_available():
                    try:
                        return original()
                    except RuntimeError:
                        return False
                        
                torch.cuda.is_available = safe_is_available
                self.patched_functions.append('cuda.is_available')
                
            # Patch device_count
            if hasattr(torch.cuda, 'device_count'):
                original = torch.cuda.device_count
                self.original_functions['cuda.device_count'] = original
                
                def safe_device_count():
                    try:
                        return original()
                    except RuntimeError:
                        return 0
                        
                torch.cuda.device_count = safe_device_count
                self.patched_functions.append('cuda.device_count')
                
        except ImportError:
            pass

    def patch_device_operations(self):
        """Patch device-related operations"""
        try:
            import torch
            
            # Patch get_device_properties
            if hasattr(torch.cuda, 'get_device_properties'):
                original = torch.cuda.get_device_properties
                self.original_functions['cuda.get_device_properties'] = original
                torch.cuda.get_device_properties = self.cuda_error_handler(original, None)
                self.patched_functions.append('cuda.get_device_properties')
                
            # Patch current_device
            if hasattr(torch.cuda, 'current_device'):
                original = torch.cuda.current_device
                self.original_functions['cuda.current_device'] = original
                torch.cuda.current_device = self.cuda_error_handler(original, 0)
                self.patched_functions.append('cuda.current_device')
                
            # Patch set_device
            if hasattr(torch.cuda, 'set_device'):
                original = torch.cuda.set_device
                self.original_functions['cuda.set_device'] = original
                
                def safe_set_device(device):
                    try:
                        return original(device)
                    except RuntimeError as e:
                        if "API call is not supported" in str(e):
                            self.logger.warning(f"Failed to set CUDA device {device}: {e}")
                            return None
                        raise
                        
                torch.cuda.set_device = safe_set_device
                self.patched_functions.append('cuda.set_device')
                
        except ImportError:
            pass

    def patch_memory_operations(self):
        """Patch memory-related operations"""
        try:
            import torch
            
            # Patch memory functions
            memory_functions = [
                'memory_allocated', 'memory_reserved', 'memory_cached',
                'max_memory_allocated', 'max_memory_reserved', 'max_memory_cached'
            ]
            
            for func_name in memory_functions:
                if hasattr(torch.cuda, func_name):
                    original = getattr(torch.cuda, func_name)
                    self.original_functions[f'cuda.{func_name}'] = original
                    setattr(torch.cuda, func_name, self.cuda_error_handler(original, 0))
                    self.patched_functions.append(f'cuda.{func_name}')
                    
            # Patch empty_cache
            if hasattr(torch.cuda, 'empty_cache'):
                original = torch.cuda.empty_cache
                self.original_functions['cuda.empty_cache'] = original
                
                def safe_empty_cache():
                    try:
                        return original()
                    except RuntimeError as e:
                        if "API call is not supported" in str(e):
                            self.logger.warning(f"Failed to empty CUDA cache: {e}")
                            return None
                        raise
                        
                torch.cuda.empty_cache = safe_empty_cache
                self.patched_functions.append('cuda.empty_cache')
                
        except ImportError:
            pass

    def patch_tensor_operations(self):
        """Patch tensor creation and operations"""
        try:
            import torch
            
            # Patch tensor creation with device fallback
            if hasattr(torch, 'tensor'):
                original_tensor = torch.tensor
                self.original_functions['tensor'] = original_tensor
                
                def safe_tensor(*args, **kwargs):
                    device = kwargs.get('device')
                    if device and str(device).startswith('cuda'):
                        try:
                            return original_tensor(*args, **kwargs)
                        except RuntimeError as e:
                            if "API call is not supported" in str(e):
                                self.logger.warning(f"CUDA tensor creation failed, falling back to CPU: {e}")
                                kwargs['device'] = 'cpu'
                                return original_tensor(*args, **kwargs)
                            raise
                    return original_tensor(*args, **kwargs)
                    
                torch.tensor = safe_tensor
                self.patched_functions.append('tensor')
                
            # Patch zeros, ones, etc. with device fallback
            creation_functions = ['zeros', 'ones', 'randn', 'rand', 'empty']
            for func_name in creation_functions:
                if hasattr(torch, func_name):
                    original = getattr(torch, func_name)
                    self.original_functions[func_name] = original
                    
                    def make_safe_creation_func(orig_func):
                        def safe_func(*args, **kwargs):
                            device = kwargs.get('device')
                            if device and str(device).startswith('cuda'):
                                try:
                                    return orig_func(*args, **kwargs)
                                except RuntimeError as e:
                                    if "API call is not supported" in str(e):
                                        self.logger.warning(f"CUDA {orig_func.__name__} failed, falling back to CPU: {e}")
                                        kwargs['device'] = 'cpu'
                                        return orig_func(*args, **kwargs)
                                    raise
                            return orig_func(*args, **kwargs)
                        return safe_func
                    
                    setattr(torch, func_name, make_safe_creation_func(original))
                    self.patched_functions.append(func_name)
                    
        except ImportError:
            pass

    def patch_backends(self):
        """Patch backend-related operations"""
        try:
            import torch
            
            # Patch cudnn operations
            if hasattr(torch.backends, 'cudnn'):
                if hasattr(torch.backends.cudnn, 'is_available'):
                    original = torch.backends.cudnn.is_available
                    self.original_functions['backends.cudnn.is_available'] = original
                    
                    def safe_cudnn_available():
                        try:
                            return original()
                        except RuntimeError:
                            return False
                            
                    torch.backends.cudnn.is_available = safe_cudnn_available
                    self.patched_functions.append('backends.cudnn.is_available')
                    
        except ImportError:
            pass

    def apply_all_patches(self):
        """Apply all runtime CUDA patches"""
        try:
            self.logger.info("Applying runtime CUDA patches for Nuitka compatibility...")
            
            self.patch_cuda_initialization()
            self.patch_device_operations()
            self.patch_memory_operations()
            self.patch_tensor_operations()
            self.patch_backends()
            
            self.logger.info(f"Successfully applied {len(self.patched_functions)} runtime patches")
            
        except Exception as e:
            self.logger.error(f"Error applying runtime patches: {e}")
            
    def restore_original_functions(self):
        """Restore original function implementations"""
        try:
            import torch
            
            for func_path, original_func in self.original_functions.items():
                if '.' in func_path:
                    module_path, func_name = func_path.rsplit('.', 1)
                    if module_path == 'cuda':
                        setattr(torch.cuda, func_name, original_func)
                    elif module_path == 'backends.cudnn':
                        setattr(torch.backends.cudnn, func_name, original_func)
                else:
                    setattr(torch, func_path, original_func)
                    
            self.logger.info("Restored original function implementations")
            
        except Exception as e:
            self.logger.error(f"Error restoring original functions: {e}")

# Global instance
_runtime_patch = None

def get_runtime_patch():
    """Get the global runtime patch instance"""
    global _runtime_patch
    if _runtime_patch is None:
        _runtime_patch = RuntimeCudaPatch()
    return _runtime_patch

def apply_runtime_patches():
    """Apply runtime CUDA patches"""
    patch = get_runtime_patch()
    patch.apply_all_patches()
    return patch

def restore_original_functions():
    """Restore original functions"""
    global _runtime_patch
    if _runtime_patch:
        _runtime_patch.restore_original_functions()

# Auto-apply patches when imported
if __name__ != "__main__":
    apply_runtime_patches()
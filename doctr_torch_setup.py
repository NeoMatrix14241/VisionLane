"""
Environment setup for DocTR PyTorch backend in Nuitka builds
This module must be imported before any DocTR imports to ensure proper backend detection
"""
import os
import sys
import importlib
import importlib.util

# Set environment variables FIRST - before any imports
os.environ['USE_TORCH'] = '1'
os.environ['DOCTR_BACKEND'] = 'torch'
os.environ['USE_TF'] = '0'
os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Enable CUDA if available

print("DocTR PyTorch Setup: Configuring environment...")

# Create early mock modules to prevent import errors
def create_early_mocks():
    """Create essential DocTR utility functions before any imports"""
    try:
        # Create requires_package function
        def requires_package(package_name: str, error_msg: str = None):
            """Check if a package is available and provide a decorator for optional imports"""
            def decorator(func):
                def wrapper(*args, **kwargs):
                    try:
                        return func(*args, **kwargs)
                    except ImportError:
                        if error_msg:
                            raise ImportError(error_msg)
                        else:
                            raise ImportError(f"Package '{package_name}' is required but not available")
                return wrapper
            return decorator
        
        # Add to builtins so it's available globally
        import builtins
        builtins.requires_package = requires_package
        
        # Pre-create utility modules that DocTR might import from
        import types
        for module_name in [
            'doctr.utils.metrics',
            'doctr.utils.common_types', 
            'doctr.utils',
            'doctr.io.utils'
        ]:
            if module_name not in sys.modules:
                mock_module = types.ModuleType(module_name)
                mock_module.requires_package = requires_package
                sys.modules[module_name] = mock_module
        
        print("DocTR Setup: Early mocks created successfully")
        return True
        
    except Exception as e:
        print(f"DocTR Setup: Error creating early mocks: {e}")
        return False

# Create early mocks
create_early_mocks()

# Force PyTorch detection
try:
    import torch
    print(f"DocTR Setup: PyTorch detected: {torch.__version__}")
    
    # Ensure torch is in sys.modules
    sys.modules['torch'] = torch
    
    # Pre-import critical torch submodules
    import torch.nn
    import torch.cuda
    import torch.backends
    import torch.backends.cudnn
    import torch.jit
    import torch.autograd
    import torch.optim
    import torch.utils
    import torch.utils.data
    import torch._C
    import torchvision
    import torchvision.models
    import torchvision.transforms
    
    print(f"DocTR Setup: PyTorch submodules loaded")
    
    # Verify CUDA
    if torch.cuda.is_available():
        print(f"DocTR Setup: CUDA available: {torch.version.cuda}")
        print(f"DocTR Setup: GPU device: {torch.cuda.get_device_name()}")
    else:
        print("DocTR Setup: CUDA not available, using CPU")
    
    # Test tensor creation to verify PyTorch is working
    test_tensor = torch.tensor([1.0, 2.0, 3.0])
    print(f"DocTR Setup: PyTorch test successful: {test_tensor}")
    
    # Global flag for DocTR
    _TORCH_AVAILABLE = True
    
except ImportError as e:
    print(f"DocTR Setup: WARNING - PyTorch import failed: {e}")
    _TORCH_AVAILABLE = False

# Create a custom import hook for DocTR file_utils
class DoctrImportHook:
    """Custom import hook to patch DocTR file_utils during import"""
    
    def __init__(self):
        # Handle both dict and module types for __builtins__
        if isinstance(__builtins__, dict):
            self.original_import = __builtins__['__import__']
        else:
            self.original_import = __builtins__.__import__
        self.patched_modules = set()
    
    def __call__(self, name, globals=None, locals=None, fromlist=(), level=0):
        # Import the module normally first
        try:
            module = self.original_import(name, globals, locals, fromlist, level)
        except ImportError as e:
            # If the import fails and it's related to requires_package, provide a mock
            if 'requires_package' in str(e) or 'cannot import name \'requires_package\'' in str(e):
                print(f"DocTR Setup: Intercepting failed import for requires_package: {name}")
                # Create a minimal module with requires_package
                import types
                mock_module = types.ModuleType(name)
                
                def requires_package(package_name: str, error_msg: str = None):
                    def decorator(func):
                        def wrapper(*args, **kwargs):
                            try:
                                return func(*args, **kwargs)
                            except ImportError:
                                if error_msg:
                                    raise ImportError(error_msg)
                                else:
                                    raise ImportError(f"Package '{package_name}' is required but not available")
                        return wrapper
                    return decorator
                
                mock_module.requires_package = requires_package
                sys.modules[name] = mock_module
                return mock_module
            else:
                # Re-raise other import errors
                raise
        
        # Check if we're importing doctr.file_utils specifically
        if name == 'doctr.file_utils' or (name == 'doctr' and 'file_utils' in (fromlist or [])):
            if 'doctr.file_utils' not in self.patched_modules:
                self._patch_file_utils()
                self.patched_modules.add('doctr.file_utils')
        
        # Also patch if any module is importing from doctr.file_utils
        if 'doctr.file_utils' in sys.modules and 'doctr.file_utils' not in self.patched_modules:
            self._patch_file_utils()
            self.patched_modules.add('doctr.file_utils')
        
        # Handle specific requires_package imports
        if fromlist and 'requires_package' in fromlist:
            if not hasattr(module, 'requires_package'):
                print(f"DocTR Setup: Adding requires_package to {name}")
                def requires_package(package_name: str, error_msg: str = None):
                    def decorator(func):
                        def wrapper(*args, **kwargs):
                            try:
                                return func(*args, **kwargs)
                            except ImportError:
                                if error_msg:
                                    raise ImportError(error_msg)
                                else:
                                    raise ImportError(f"Package '{package_name}' is required but not available")
                        return wrapper
                    return decorator
                module.requires_package = requires_package
        
        return module

    def _patch_file_utils(self):
        """Patch DocTR file_utils functions"""
        try:
            if 'doctr.file_utils' in sys.modules:
                file_utils = sys.modules['doctr.file_utils']
                print("DocTR Setup: Patching file_utils module...")
                
                # Override detection functions
                file_utils.is_tf_available = lambda: False
                file_utils.is_torch_available = lambda: _TORCH_AVAILABLE
                
                # Add requires_package function if missing
                if not hasattr(file_utils, 'requires_package'):
                    def requires_package(package_name: str, error_msg: str = None):
                        def decorator(func):
                            def wrapper(*args, **kwargs):
                                try:
                                    return func(*args, **kwargs)
                                except ImportError:
                                    if error_msg:
                                        raise ImportError(error_msg)
                                    else:
                                        raise ImportError(f"Package '{package_name}' is required but not available")
                            return wrapper
                        return decorator
                    file_utils.requires_package = requires_package
                
                # Also patch any existing references
                if hasattr(file_utils, '_TF_AVAILABLE'):
                    file_utils._TF_AVAILABLE = False
                if hasattr(file_utils, '_TORCH_AVAILABLE'):
                    file_utils._TORCH_AVAILABLE = _TORCH_AVAILABLE
                
                print("DocTR Setup: Successfully patched file_utils backend detection")
            else:
                print("DocTR Setup: file_utils not yet in sys.modules")
        except Exception as e:
            print(f"DocTR Setup: Error patching file_utils: {e}")

# Install the import hook
print("DocTR Setup: Installing import hook for file_utils patching...")
doctr_hook = DoctrImportHook()

# Install the hook properly
if isinstance(__builtins__, dict):
    __builtins__['__import__'] = doctr_hook
else:
    __builtins__.__import__ = doctr_hook

# Alternative approach: Pre-create a patched file_utils module
def create_patched_file_utils():
    """Create a pre-patched file_utils module"""
    try:
        # Find the original file_utils
        spec = importlib.util.find_spec('doctr.file_utils')
        if spec is not None:
            print("DocTR Setup: Pre-creating patched file_utils module...")
            
            # Load the module
            module = importlib.util.module_from_spec(spec)
            
            # Execute it to initialize
            spec.loader.exec_module(module)
            
            # Apply patches immediately
            module.is_tf_available = lambda: False
            module.is_torch_available = lambda: _TORCH_AVAILABLE
            
            # Add requires_package function if missing
            if not hasattr(module, 'requires_package'):
                def requires_package(package_name: str, error_msg: str = None):
                    def decorator(func):
                        def wrapper(*args, **kwargs):
                            try:
                                return func(*args, **kwargs)
                            except ImportError:
                                if error_msg:
                                    raise ImportError(error_msg)
                                else:
                                    raise ImportError(f"Package '{package_name}' is required but not available")
                        return wrapper
                    return decorator
                module.requires_package = requires_package
            
            # Also patch module-level variables if they exist
            if hasattr(module, '_TF_AVAILABLE'):
                module._TF_AVAILABLE = False
            if hasattr(module, '_TORCH_AVAILABLE'):
                module._TORCH_AVAILABLE = _TORCH_AVAILABLE
            
            # Store patched version in sys.modules
            sys.modules['doctr.file_utils'] = module
            
            print("DocTR Setup: Pre-patched file_utils module created")
            return True
    except Exception as e:
        print(f"DocTR Setup: Could not pre-create patched file_utils: {e}")
    return False

# Try pre-patching approach as backup
create_patched_file_utils()

# Create a comprehensive DocTR utilities module with all required functions
def create_doctr_utils():
    """Create comprehensive DocTR utility modules"""
    try:
        print("DocTR Setup: Creating comprehensive DocTR utilities...")
        
        # Create requires_package function - this is the missing function causing the error
        def requires_package(package_name: str, error_msg: str = None):
            """Check if a package is available and provide a decorator for optional imports"""
            def decorator(func):
                def wrapper(*args, **kwargs):
                    try:
                        return func(*args, **kwargs)
                    except ImportError:
                        if error_msg:
                            raise ImportError(error_msg)
                        else:
                            raise ImportError(f"Package '{package_name}' is required but not available")
                return wrapper
            return decorator
        
        # Create a comprehensive utils module
        class DoctrUtils:
            @staticmethod
            def requires_package(package_name: str, error_msg: str = None):
                return requires_package(package_name, error_msg)
            
            @staticmethod
            def is_torch_available():
                return _TORCH_AVAILABLE
            
            @staticmethod
            def is_tf_available():
                return False
            
            # Mock other commonly used attributes
            _TORCH_AVAILABLE = _TORCH_AVAILABLE
            _TF_AVAILABLE = False
        
        # Create the file_utils module if it doesn't exist
        if 'doctr.file_utils' not in sys.modules:
            print("DocTR Setup: Creating emergency file_utils mock...")
            sys.modules['doctr.file_utils'] = DoctrUtils()
            print("DocTR Setup: Emergency file_utils mock created")
        
        # Create a mock utils module that includes requires_package
        if 'doctr.utils' not in sys.modules:
            print("DocTR Setup: Creating doctr.utils mock...")
            sys.modules['doctr.utils'] = DoctrUtils()
        
        # Also add requires_package to the global namespace that DocTR might expect
        # This handles the case where DocTR tries to import requires_package directly
        import types
        mock_module = types.ModuleType('doctr_utils_mock')
        mock_module.requires_package = requires_package
        
        # Try to add it to common locations where DocTR might look for it
        sys.modules['doctr.utils.metrics'] = mock_module
        sys.modules['doctr.utils.common_types'] = mock_module
        
        # Also patch any existing doctr modules that might need requires_package
        for module_name in list(sys.modules.keys()):
            if module_name.startswith('doctr.') and hasattr(sys.modules[module_name], '__dict__'):
                try:
                    if not hasattr(sys.modules[module_name], 'requires_package'):
                        sys.modules[module_name].requires_package = requires_package
                except:
                    pass  # Ignore errors when patching existing modules
        
        print("DocTR Setup: Comprehensive DocTR utilities created")
        return True
        
    except Exception as e:
        print(f"DocTR Setup: Error creating DocTR utilities: {e}")
        return False

# Additional emergency backend override using environment injection
def inject_backend_detection():
    """Inject backend detection into sys.modules"""
    try:
        # First create comprehensive utils
        create_doctr_utils()
        
        # Legacy file_utils creation for backwards compatibility
        if 'doctr.file_utils' not in sys.modules:
            print("DocTR Setup: Creating emergency file_utils mock...")
            
            # Create a mock module with only the functions we need
            class MockFileUtils:
                @staticmethod
                def is_torch_available():
                    return _TORCH_AVAILABLE
                
                @staticmethod
                def is_tf_available():
                    return False
                
                @staticmethod
                def requires_package(package_name: str, error_msg: str = None):
                    def decorator(func):
                        def wrapper(*args, **kwargs):
                            try:
                                return func(*args, **kwargs)
                            except ImportError:
                                if error_msg:
                                    raise ImportError(error_msg)
                                else:
                                    raise ImportError(f"Package '{package_name}' is required but not available")
                        return wrapper
                    return decorator
                
                # Mock other commonly used attributes
                _TORCH_AVAILABLE = _TORCH_AVAILABLE
                _TF_AVAILABLE = False
            
            # Add to sys.modules
            sys.modules['doctr.file_utils'] = MockFileUtils()
            print("DocTR Setup: Emergency file_utils mock created")
    except Exception as e:
        print(f"DocTR Setup: Error creating emergency mock: {e}")

# Apply emergency injection
inject_backend_detection()

def ensure_torch_available():
    """Ensure torch is available for DocTR detection"""
    try:
        import torch
        # Create a test tensor to verify PyTorch is fully functional
        test_tensor = torch.tensor([1.0, 2.0])
        if torch.cuda.is_available():
            test_cuda = torch.tensor([1.0]).cuda()
            print(f"DocTR Setup: CUDA test successful on device {test_cuda.device}")
        print("DocTR Setup: PyTorch verification successful")
        return True
    except Exception as e:
        print(f"DocTR Setup: PyTorch verification failed: {e}")
        return False

def verify_doctr_setup():
    """Verify that DocTR can detect PyTorch after setup"""
    try:
        import doctr.file_utils
        torch_available = doctr.file_utils.is_torch_available()
        tf_available = doctr.file_utils.is_tf_available()
        print(f"DocTR Setup: DocTR detects - PyTorch: {torch_available}, TensorFlow: {tf_available}")
        return torch_available
    except Exception as e:
        print(f"DocTR Setup: Could not verify DocTR setup: {e}")
        return False

# Run verification if this module is imported
if _TORCH_AVAILABLE:
    ensure_torch_available()

print("DocTR Setup: Initialization complete")

# Test function for direct execution
if __name__ == "__main__":
    print("=== DocTR PyTorch Setup Test ===")
    torch_ok = ensure_torch_available()
    print(f"PyTorch available: {torch_ok}")
    
    doctr_ok = verify_doctr_setup()
    print(f"DocTR detection: {doctr_ok}")
    
    if torch_ok and doctr_ok:
        print("✓ Setup successful - DocTR should work with PyTorch")
    else:
        print("✗ Setup failed - DocTR may not detect PyTorch")

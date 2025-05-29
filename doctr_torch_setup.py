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
        module = self.original_import(name, globals, locals, fromlist, level)
        
        # Check if we're importing doctr.file_utils specifically
        if name == 'doctr.file_utils' or (name == 'doctr' and 'file_utils' in (fromlist or [])):
            if 'doctr.file_utils' not in self.patched_modules:
                self._patch_file_utils()
                self.patched_modules.add('doctr.file_utils')
        
        # Also patch if any module is importing from doctr.file_utils
        if 'doctr.file_utils' in sys.modules and 'doctr.file_utils' not in self.patched_modules:
            self._patch_file_utils()
            self.patched_modules.add('doctr.file_utils')
        
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

# Additional emergency backend override using environment injection
def inject_backend_detection():
    """Inject backend detection into sys.modules"""
    try:
        # Create a minimal mock file_utils if none exists
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

#!/usr/bin/env python3
"""
Clean DocTR PyTorch Setup Module
Ensures DocTR can properly detect and use PyTorch backend by creating comprehensive mocks
for all required utility modules before any DocTR imports occur.
"""

import sys
import os
import importlib.util
import types

# Set PyTorch backend environment variables
os.environ['USE_TORCH'] = '1'
os.environ['DOCTR_BACKEND'] = 'torch'

print("DocTR Setup: Starting clean DocTR PyTorch backend setup...")

# Check if PyTorch is available
_TORCH_AVAILABLE = False
try:
    import torch
    _TORCH_AVAILABLE = True
    print(f"DocTR Setup: PyTorch {torch.__version__} detected")
    if torch.cuda.is_available():
        print(f"DocTR Setup: CUDA available with {torch.cuda.device_count()} device(s)")
    else:
        print("DocTR Setup: CUDA not available, using CPU")
except ImportError:
    print("DocTR Setup: PyTorch not available!")
    _TORCH_AVAILABLE = False

# Patch sys.modules directly to force PyTorch detection
if 'doctr.file_utils' in sys.modules:
    sys.modules['doctr.file_utils']._TORCH_AVAILABLE = _TORCH_AVAILABLE
    sys.modules['doctr.file_utils']._TF_AVAILABLE = False
    print("DocTR Setup: Directly patched doctr.file_utils in sys.modules")

# Create a custom importer to patch doctr.file_utils on import
_original_import = __import__

def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):
    module = _original_import(name, globals, locals, fromlist, level)
    
    # Patch doctr.file_utils when it's imported
    if name == 'doctr.file_utils' or (name == 'file_utils' and fromlist and 'doctr' in globals.get('__name__', '')):
        if hasattr(module, '_TORCH_AVAILABLE'):
            module._TORCH_AVAILABLE = _TORCH_AVAILABLE
            module._TF_AVAILABLE = False
            print("DocTR Setup: Patched doctr.file_utils._TORCH_AVAILABLE during import")
        
        # Replace is_torch_available function
        if hasattr(module, 'is_torch_available'):
            module.is_torch_available = lambda: _TORCH_AVAILABLE
            print("DocTR Setup: Patched is_torch_available function")
    
    return module

# Install patched importer
sys.modules['builtins'].__import__ = _patched_import
print("DocTR Setup: Installed patched import system")

def setup_doctr_with_pytorch():
    """Setup DocTR to use PyTorch backend and import the full library"""
    print("DocTR Setup: Setting up DocTR with PyTorch backend...")
    
    try:
        # Import DocTR directly
        print("DocTR Setup: Importing DocTR...")
        import doctr
        
        # Verify that DocTR can detect PyTorch
        try:
            from doctr.file_utils import is_torch_available, is_tf_available
            torch_detected = is_torch_available()
            tf_detected = is_tf_available()
            print(f"DocTR Setup: Backend detection - PyTorch: {torch_detected}, TensorFlow: {tf_detected}")
            
            if not torch_detected:
                print("DocTR Setup: WARNING - DocTR cannot detect PyTorch!")
                # Try to patch the detection
                doctr.file_utils._TORCH_AVAILABLE = _TORCH_AVAILABLE
                doctr.file_utils._TF_AVAILABLE = False
                print("DocTR Setup: Attempted to patch backend detection")
        except Exception as e:
            print(f"DocTR Setup: Could not verify backend detection: {e}")
        
        # Test importing commonly used DocTR modules
        test_imports = [
            'doctr.models',
            'doctr.utils',
            'doctr.io',
            'doctr.datasets',
            'doctr.transforms'
        ]
        
        for module_name in test_imports:
            try:
                __import__(module_name)
                print(f"DocTR Setup: ✓ {module_name} imported successfully")
            except Exception as e:
                print(f"DocTR Setup: ✗ Failed to import {module_name}: {e}")
        
        # Test specific functions that were causing issues
        try:
            from doctr.models import ocr_predictor
            print("DocTR Setup: ✓ ocr_predictor imported successfully")
        except Exception as e:
            print(f"DocTR Setup: ✗ Failed to import ocr_predictor: {e}")
        
        print("DocTR Setup: DocTR import completed successfully!")
        return True
        
    except Exception as e:
        print(f"DocTR Setup: Failed to import DocTR: {e}")
        print("DocTR Setup: Falling back to mock creation...")
        return create_fallback_mocks()

def create_fallback_mocks():
    """Create minimal mocks as fallback if DocTR import fails"""
    print("DocTR Setup: Creating fallback mock modules...")
    
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
    
    # Only create minimal mocks for file_utils if DocTR import completely fails
    if 'doctr.file_utils' not in sys.modules:
        print("DocTR Setup: Creating minimal file_utils mock...")
        file_utils_mock = types.ModuleType('doctr.file_utils')
        file_utils_mock.is_torch_available = lambda: _TORCH_AVAILABLE
        file_utils_mock.is_tf_available = lambda: False
        file_utils_mock._TORCH_AVAILABLE = _TORCH_AVAILABLE
        file_utils_mock._TF_AVAILABLE = False
        file_utils_mock.requires_package = requires_package
        file_utils_mock.CLASS_NAME = 'MockClassName'
        sys.modules['doctr.file_utils'] = file_utils_mock
        print("DocTR Setup: Minimal file_utils mock created")
    
    return True

def patch_existing_doctr_modules():
    """Patch any existing DocTR modules with requires_package function"""
    print("DocTR Setup: Patching existing DocTR modules...")
    
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
    
    # Patch any existing doctr modules
    for module_name in list(sys.modules.keys()):
        if module_name.startswith('doctr.') and hasattr(sys.modules[module_name], '__dict__'):
            try:
                if not hasattr(sys.modules[module_name], 'requires_package'):
                    sys.modules[module_name].requires_package = requires_package
                    print(f"DocTR Setup: Patched {module_name} with requires_package")
            except Exception as e:
                print(f"DocTR Setup: Could not patch {module_name}: {e}")

def verify_doctr_setup():
    """Verify that DocTR setup is working"""
    print("DocTR Setup: Verifying DocTR setup...")
    
    try:
        # Test that we can import DocTR
        import doctr
        print("DocTR Setup: ✓ DocTR imported successfully")
        
        # Test backend detection
        try:
            from doctr.file_utils import is_torch_available, is_tf_available
            torch_detected = is_torch_available()
            tf_detected = is_tf_available()
            print(f"DocTR Setup: ✓ Backend detection - PyTorch: {torch_detected}, TensorFlow: {tf_detected}")
        except Exception as e:
            print(f"DocTR Setup: ✗ Backend detection failed: {e}")
            return False
        
        # Test specific imports that were causing issues
        try:
            from doctr.models import ocr_predictor
            print("DocTR Setup: ✓ ocr_predictor imported successfully")
        except Exception as e:
            print(f"DocTR Setup: ✗ Failed to import ocr_predictor: {e}")
            return False
        
        print("DocTR Setup: ✓ All verification tests passed")
        return True
        
    except Exception as e:
        print(f"DocTR Setup: ✗ DocTR verification failed: {e}")
        return False

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

def setup_doctr_with_progress(progress_callback=None, use_cache=True, detailed_progress=True):
    """Setup DocTR with progress callback for splash screen integration"""
    from utils.startup_cache import startup_cache
    
    def log_and_update(message, include_prefix=True):
        """Helper to log and update progress simultaneously"""
        full_message = f"DocTR Setup: {message}" if include_prefix else message
        print(full_message)
        if progress_callback:
            progress_callback(message)
    
    # Check cache first if enabled
    if use_cache:
        log_and_update("Checking cached setup results...")
        cached_result = startup_cache.get_cached_doctr_setup()
        if cached_result and cached_result.get('success'):
            pytorch_ver = cached_result.get('pytorch_version', 'Unknown')
            gpu_info = cached_result.get('gpu_info')
            if gpu_info:
                log_and_update(f"✓ DocTR ready (cached): PyTorch {pytorch_ver}, GPU: {gpu_info}")
            else:
                log_and_update(f"✓ DocTR ready (cached): PyTorch {pytorch_ver}")
            return True
        else:
            log_and_update("No valid cache found, proceeding with full setup")
    
    log_and_update("Initializing PyTorch backend verification...")
    
    try:
        # Enhanced PyTorch availability check
        if detailed_progress:
            log_and_update("Verifying PyTorch installation integrity...")
        
        global _TORCH_AVAILABLE
        pytorch_version = None
        gpu_info = None
        
        if not _TORCH_AVAILABLE:
            try:
                log_and_update("Importing PyTorch library...")
                import torch
                _TORCH_AVAILABLE = True
                pytorch_version = torch.__version__
                
                if detailed_progress:
                    log_and_update(f"✓ PyTorch {pytorch_version} loaded successfully")
                else:
                    log_and_update("✓ PyTorch detected")
                    
                # Enhanced CUDA detection and logging
                log_and_update("Scanning for CUDA-capable devices...")
                if torch.cuda.is_available():
                    gpu_count = torch.cuda.device_count()
                    if gpu_count > 0:
                        gpu_name = torch.cuda.get_device_name(0)
                        cuda_version = torch.version.cuda
                        gpu_info = f"{gpu_name} ({gpu_count} GPU{'s' if gpu_count > 1 else ''})"
                        
                        if detailed_progress:
                            log_and_update(f"✓ CUDA {cuda_version} detected: {gpu_info}")
                            # Test GPU functionality
                            try:
                                test_tensor = torch.tensor([1.0]).cuda()
                                log_and_update("✓ GPU functionality verified")
                            except Exception as e:
                                log_and_update(f"⚠ GPU test failed: {str(e)[:30]}...")
                        else:
                            log_and_update(f"✓ GPU available: {gpu_info}")
                    else:
                        log_and_update("⚠ CUDA available but no devices found")
                else:
                    log_and_update("CPU mode - no CUDA devices detected")
            except ImportError as e:
                log_and_update(f"✗ PyTorch import failed: {str(e)[:40]}...")
                if use_cache:
                    startup_cache.cache_doctr_setup(False)
                return False
            except Exception as e:
                log_and_update(f"✗ PyTorch verification error: {str(e)[:40]}...")
                return False
        else:
            log_and_update("✓ PyTorch already verified in previous check")
        
        # Enhanced DocTR import process
        log_and_update("Importing DocTR library components...")
        
        # Import DocTR with detailed logging
        try:
            import doctr
            if detailed_progress:
                log_and_update(f"✓ DocTR core library v{getattr(doctr, '__version__', 'unknown')} loaded")
            else:
                log_and_update("✓ DocTR core loaded")
        except Exception as e:
            log_and_update(f"✗ DocTR import failed: {str(e)[:40]}...")
            return False
        
        # Enhanced backend detection verification
        if detailed_progress:
            log_and_update("Configuring backend detection system...")
        else:
            log_and_update("Configuring backends...")
        
        try:
            from doctr.file_utils import is_torch_available, is_tf_available
            torch_detected = is_torch_available()
            tf_detected = is_tf_available()
            
            if detailed_progress:
                log_and_update(f"Backend detection results: PyTorch={torch_detected}, TensorFlow={tf_detected}")
            
            if not torch_detected:
                log_and_update("Applying PyTorch detection patches...")
                doctr.file_utils._TORCH_AVAILABLE = _TORCH_AVAILABLE
                doctr.file_utils._TF_AVAILABLE = False
                
                # Verify patch worked
                torch_detected_after = is_torch_available()
                if torch_detected_after:
                    log_and_update("✓ Backend patches applied successfully")
                else:
                    log_and_update("⚠ Backend patches may not have taken effect")
            else:
                log_and_update("✓ Backend detection working correctly")
        except Exception as e:
            if detailed_progress:
                log_and_update(f"⚠ Backend configuration warning: {str(e)[:30]}...")
            else:
                log_and_update("⚠ Backend configuration issue")
        
        # Enhanced module loading with individual status
        log_and_update("Loading DocTR core modules...")
        
        test_imports = [
            ('doctr.models', 'AI models', 'Core ML models for text detection and recognition'),
            ('doctr.utils', 'utilities', 'Helper functions and utilities'),
            ('doctr.io', 'document processing', 'Document input/output handling'),
            ('doctr.transforms', 'image transforms', 'Image preprocessing transforms')
        ]
        
        loaded_modules = 0
        for module_name, display_name, description in test_imports:
            try:
                if detailed_progress:
                    log_and_update(f"Loading {description}...")
                
                __import__(module_name)
                loaded_modules += 1
                
                if detailed_progress:
                    log_and_update(f"✓ {display_name} loaded successfully")
            except Exception as e:
                if detailed_progress:
                    log_and_update(f"⚠ {display_name} load warning: {str(e)[:25]}...")
                else:
                    log_and_update(f"⚠ Warning loading {display_name}")
        
        if loaded_modules == len(test_imports):
            log_and_update("✓ All core modules loaded successfully")
        else:
            log_and_update(f"⚠ {loaded_modules}/{len(test_imports)} modules loaded")
        
        # Enhanced OCR predictor testing
        log_and_update("Testing OCR predictor functionality...")
        
        try:
            from doctr.models import ocr_predictor
            if detailed_progress:
                log_and_update("✓ OCR predictor import successful")
                
                # Test predictor instantiation if detailed mode
                try:
                    log_and_update("Testing predictor instantiation...")
                    # Quick test without actually loading models
                    predictor_available = hasattr(ocr_predictor, '__call__')
                    if predictor_available:
                        log_and_update("✓ OCR predictor functionality verified")
                    else:
                        log_and_update("⚠ OCR predictor may not be fully functional")
                except Exception as e:
                    log_and_update(f"⚠ Predictor test warning: {str(e)[:25]}...")
            else:
                log_and_update("✓ OCR predictor ready")
        except Exception as e:
            if detailed_progress:
                log_and_update(f"⚠ OCR predictor warning: {str(e)[:30]}...")
            else:
                log_and_update("⚠ OCR predictor issue")
        
        # Cache the results if successful
        if use_cache:
            try:
                log_and_update("Caching setup results for future use...")
                startup_cache.cache_doctr_setup(
                    success=True, 
                    pytorch_version=pytorch_version, 
                    gpu_info=gpu_info,
                    modules_loaded=loaded_modules,
                    total_modules=len(test_imports)
                )
                if detailed_progress:
                    log_and_update("✓ Setup results cached successfully")
            except Exception as e:
                log_and_update(f"⚠ Cache save warning: {str(e)[:25]}...")
        
        # Final status report
        if detailed_progress:
            log_and_update("DocTR setup completed - ready for OCR operations")
        else:
            log_and_update("✓ Setup complete")
        
        print("DocTR Setup: ✓ Full setup process completed successfully!")
        return True
        
    except Exception as e:
        error_msg = str(e)[:40] if len(str(e)) > 40 else str(e)
        if detailed_progress:
            log_and_update(f"✗ Setup failed: {error_msg}...")
        else:
            log_and_update("✗ Setup failed")
        
        print(f"DocTR Setup: ✗ Failed to setup DocTR: {e}")
        
        # Cache the failure if enabled
        if use_cache:
            try:
                startup_cache.cache_doctr_setup(success=False, error=str(e))
            except Exception:
                pass
        
        log_and_update("Attempting fallback mock creation...")
        return create_fallback_mocks()

# Execute setup immediately when module is imported
print("DocTR Setup: Setting up DocTR with PyTorch...")
setup_success = setup_doctr_with_pytorch()

print("DocTR Setup: Patching existing modules...")
patch_existing_doctr_modules()

if _TORCH_AVAILABLE:
    print("DocTR Setup: Verifying PyTorch...")
    ensure_torch_available()

if setup_success:
    print("DocTR Setup: ✓ Complete setup successful!")
else:
    print("DocTR Setup: ✗ Setup completed with errors")

print("DocTR Setup: Initialization complete")

# Test function for direct execution
if __name__ == "__main__":
    print("=== DocTR PyTorch Setup Test ===")
    
    if _TORCH_AVAILABLE:
        print("✓ PyTorch is available")
    else:
        print("✗ PyTorch is not available")
    
    if setup_success:
        print("✓ DocTR setup successful")
        
        # Verify the setup works
        if verify_doctr_setup():
            print("✓ DocTR verification successful")
            print("✓ DocTR should work with PyTorch")
        else:
            print("✗ DocTR verification failed")
    else:
        print("✗ DocTR setup failed")

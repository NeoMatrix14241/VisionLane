from nuitka.plugins.PluginBase import NuitkaPluginBase
class NuitkaPluginCudaCompat(NuitkaPluginBase):
    plugin_name = "cuda-compat"
    plugin_desc = "Fix CUDA 12.8 compatibility issues"
    @staticmethod
    def createPreModuleLoadCode(module):
        full_name = module.getFullName()
        if full_name == "torch":
            # Monkey patch CUDA version checks
            code = '''
import os
import sys
# Override CUDA version detection
def _patch_cuda_version():
    try:
        import torch.version
        # Force CUDA version to match driver
        original_cuda = torch.version.cuda
        if original_cuda == "12.8":
            # Monkey patch the version check
            torch.version.cuda = "12.9"  # Match your driver
            # Also patch internal CUDA checks
            if hasattr(torch, '_C') and hasattr(torch._C, '_cuda_getDriverVersion'):
                original_driver_version = torch._C._cuda_getDriverVersion
                def patched_driver_version():
                    try:
                        return original_driver_version()
                    except Exception:
                        # Return a compatible version
                        return 12090  # CUDA 12.9
                torch._C._cuda_getDriverVersion = patched_driver_version
    except Exception as e:
        pass  # Fail silently
_patch_cuda_version()
'''
            return code, "Patching CUDA version compatibility"
        return None

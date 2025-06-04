"""
Hardware Monitoring Patch for Nuitka Compatibility
This module provides patches for hardware monitoring libraries that may not work correctly
when compiled with Nuitka, particularly for GPU and system monitoring.
"""

import sys
import logging
import warnings
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class HardwareMonitoringPatch:
    """Patches hardware monitoring libraries for Nuitka compatibility"""
    
    def __init__(self):
        self.patched_modules = []
        self.is_nuitka = self._detect_nuitka_environment()
        self.gpu_info_cache = None
        self.system_info_cache = None
        
    def _detect_nuitka_environment(self) -> bool:
        """Detect if running under Nuitka"""
        try:
            # Check for Nuitka-specific attributes
            if hasattr(sys, 'frozen') and hasattr(sys, '_NUITKA_BINARY_PATH'):
                return True
            # Check for __compiled__ module (Nuitka specific)
            try:
                import __compiled__
                return True
            except ImportError:
                pass
            return False
        except Exception:
            return False
    
    def patch_pynvml(self):
        """Patch pynvml for Nuitka compatibility"""
        if not self.is_nuitka:
            return
            
        try:
            import pynvml
            logger.info("Applying pynvml patches for Nuitka compatibility")
            
            # Store original functions
            original_init = pynvml.nvmlInit
            original_device_count = pynvml.nvmlDeviceGetCount
            original_device_name = pynvml.nvmlDeviceGetName
            original_driver_version = pynvml.nvmlSystemGetDriverVersion
            
            def safe_nvml_init():
                """Safe NVML initialization with error handling"""
                try:
                    return original_init()
                except Exception as e:
                    logger.warning(f"NVML initialization failed: {e}")
                    # Create mock NVML state
                    return None
            
            def safe_device_count():
                """Safe device count with fallback"""
                try:
                    return original_device_count()
                except Exception as e:
                    logger.warning(f"NVML device count failed: {e}")
                    return 0
            
            def safe_device_name(handle):
                """Safe device name retrieval"""
                try:
                    result = original_device_name(handle)
                    if isinstance(result, bytes):
                        return result.decode('utf-8', errors='ignore')
                    return str(result)
                except Exception as e:
                    logger.warning(f"NVML device name failed: {e}")
                    return "Unknown GPU"
            
            def safe_driver_version():
                """Safe driver version retrieval"""
                try:
                    result = original_driver_version()
                    if isinstance(result, bytes):
                        return result.decode('utf-8', errors='ignore')
                    return str(result)
                except Exception as e:
                    logger.warning(f"NVML driver version failed: {e}")
                    return "Unknown Version"
            
            # Apply patches
            pynvml.nvmlInit = safe_nvml_init
            pynvml.nvmlDeviceGetCount = safe_device_count
            pynvml.nvmlDeviceGetName = safe_device_name
            pynvml.nvmlSystemGetDriverVersion = safe_driver_version
            
            self.patched_modules.append('pynvml')
            logger.info("pynvml patching completed")
            
        except ImportError:
            logger.debug("pynvml not available, skipping patches")
        except Exception as e:
            logger.error(f"Failed to patch pynvml: {e}")
    
    def patch_psutil(self):
        """Patch psutil for Nuitka compatibility"""
        if not self.is_nuitka:
            return
            
        try:
            import psutil
            logger.info("Applying psutil patches for Nuitka compatibility")
            
            # Store original functions
            original_cpu_percent = psutil.cpu_percent
            original_virtual_memory = psutil.virtual_memory
            original_disk_usage = psutil.disk_usage
            
            def safe_cpu_percent(interval=None, percpu=False):
                """Safe CPU percentage monitoring"""
                try:
                    return original_cpu_percent(interval, percpu)
                except Exception as e:
                    logger.warning(f"CPU monitoring failed: {e}")
                    return [0.0] if percpu else 0.0
            
            def safe_virtual_memory():
                """Safe memory monitoring"""
                try:
                    return original_virtual_memory()
                except Exception as e:
                    logger.warning(f"Memory monitoring failed: {e}")
                    # Return mock memory info
                    from collections import namedtuple
                    MemInfo = namedtuple('MemInfo', ['total', 'available', 'percent', 'used', 'free'])
                    return MemInfo(8589934592, 4294967296, 50.0, 4294967296, 4294967296)
            
            def safe_disk_usage(path):
                """Safe disk usage monitoring"""
                try:
                    return original_disk_usage(path)
                except Exception as e:
                    logger.warning(f"Disk monitoring failed: {e}")
                    # Return mock disk info
                    from collections import namedtuple
                    DiskUsage = namedtuple('DiskUsage', ['total', 'used', 'free'])
                    return DiskUsage(1073741824000, 536870912000, 536870912000)
            
            # Apply patches
            psutil.cpu_percent = safe_cpu_percent
            psutil.virtual_memory = safe_virtual_memory
            psutil.disk_usage = safe_disk_usage
            
            self.patched_modules.append('psutil')
            logger.info("psutil patching completed")
            
        except ImportError:
            logger.debug("psutil not available, skipping patches")
        except Exception as e:
            logger.error(f"Failed to patch psutil: {e}")
    
    def patch_wmi(self):
        """Patch WMI for Windows Nuitka compatibility"""
        if not self.is_nuitka or sys.platform != 'win32':
            return
            
        try:
            import wmi
            logger.info("Applying WMI patches for Nuitka compatibility")
            
            # Store original WMI class
            original_wmi = wmi.WMI
            
            class SafeWMI:
                """Safe WMI wrapper with error handling"""
                
                def __init__(self, *args, **kwargs):
                    try:
                        self._wmi = original_wmi(*args, **kwargs)
                        self._available = True
                    except Exception as e:
                        logger.warning(f"WMI initialization failed: {e}")
                        self._wmi = None
                        self._available = False
                
                def Win32_VideoController(self):
                    """Safe GPU enumeration"""
                    if not self._available:
                        return []
                    try:
                        return self._wmi.Win32_VideoController()
                    except Exception as e:
                        logger.warning(f"WMI GPU enumeration failed: {e}")
                        return []
                
                def Win32_Processor(self):
                    """Safe CPU enumeration"""
                    if not self._available:
                        return []
                    try:
                        return self._wmi.Win32_Processor()
                    except Exception as e:
                        logger.warning(f"WMI CPU enumeration failed: {e}")
                        return []
                
                def __getattr__(self, name):
                    """Fallback for other WMI queries"""
                    if not self._available:
                        return lambda: []
                    try:
                        return getattr(self._wmi, name)
                    except Exception:
                        return lambda: []
            
            # Apply patch
            wmi.WMI = SafeWMI
            
            self.patched_modules.append('wmi')
            logger.info("WMI patching completed")
            
        except ImportError:
            logger.debug("WMI not available, skipping patches")
        except Exception as e:
            logger.error(f"Failed to patch WMI: {e}")
    
    def get_safe_gpu_info(self) -> List[Dict[str, Any]]:
        """Get GPU information safely with fallbacks"""
        if self.gpu_info_cache:
            return self.gpu_info_cache
        
        gpu_info = []
        
        # Try PyTorch CUDA first
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    try:
                        props = torch.cuda.get_device_properties(i)
                        gpu_info.append({
                            'name': props.name,
                            'memory_total': props.total_memory,
                            'compute_capability': f"{props.major}.{props.minor}",
                            'source': 'torch'
                        })
                    except Exception as e:
                        logger.warning(f"Failed to get GPU {i} info from torch: {e}")
        except ImportError:
            pass
        
        # Try pynvml as fallback
        if not gpu_info:
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                for i in range(device_count):
                    try:
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        name = pynvml.nvmlDeviceGetName(handle)
                        if isinstance(name, bytes):
                            name = name.decode('utf-8', errors='ignore')
                        gpu_info.append({
                            'name': name,
                            'memory_total': 'Unknown',
                            'compute_capability': 'Unknown',
                            'source': 'pynvml'
                        })
                    except Exception as e:
                        logger.warning(f"Failed to get GPU {i} info from pynvml: {e}")
            except Exception:
                pass
        
        # Try WMI as last resort (Windows only)
        if not gpu_info and sys.platform == 'win32':
            try:
                import wmi
                c = wmi.WMI()
                for gpu in c.Win32_VideoController():
                    if gpu.Name:
                        gpu_info.append({
                            'name': gpu.Name,
                            'memory_total': 'Unknown',
                            'compute_capability': 'Unknown',
                            'source': 'wmi'
                        })
            except Exception:
                pass
        
        self.gpu_info_cache = gpu_info
        return gpu_info
    
    def get_safe_system_info(self) -> Dict[str, Any]:
        """Get system information safely with fallbacks"""
        if self.system_info_cache:
            return self.system_info_cache
        
        system_info = {
            'cpu_count': 1,
            'cpu_percent': 0.0,
            'memory_total': 0,
            'memory_available': 0,
            'memory_percent': 0.0,
            'disk_total': 0,
            'disk_free': 0,
            'disk_percent': 0.0
        }
        
        try:
            import psutil
            
            # CPU info
            try:
                system_info['cpu_count'] = psutil.cpu_count() or 1
                system_info['cpu_percent'] = psutil.cpu_percent(interval=0.1) or 0.0
            except Exception:
                pass
            
            # Memory info
            try:
                mem = psutil.virtual_memory()
                system_info['memory_total'] = mem.total
                system_info['memory_available'] = mem.available
                system_info['memory_percent'] = mem.percent
            except Exception:
                pass
            
            # Disk info
            try:
                disk = psutil.disk_usage('/')
                system_info['disk_total'] = disk.total
                system_info['disk_free'] = disk.free
                system_info['disk_percent'] = (disk.used / disk.total) * 100
            except Exception:
                try:
                    disk = psutil.disk_usage('C:')
                    system_info['disk_total'] = disk.total
                    system_info['disk_free'] = disk.free
                    system_info['disk_percent'] = (disk.used / disk.total) * 100
                except Exception:
                    pass
        
        except ImportError:
            pass
        
        self.system_info_cache = system_info
        return system_info
    
    def apply_all_patches(self):
        """Apply all hardware monitoring patches"""
        if not self.is_nuitka:
            logger.info("Not running under Nuitka, skipping hardware monitoring patches")
            return
        
        logger.info("Applying hardware monitoring patches for Nuitka compatibility...")
        
        self.patch_pynvml()
        self.patch_psutil()
        self.patch_wmi()
        
        logger.info(f"Hardware monitoring patches applied: {', '.join(self.patched_modules)}")
    
    def get_patch_status(self) -> Dict[str, Any]:
        """Get status of applied patches"""
        return {
            'is_nuitka': self.is_nuitka,
            'patched_modules': self.patched_modules,
            'gpu_info_available': len(self.get_safe_gpu_info()) > 0,
            'system_info_available': self.get_safe_system_info()['cpu_count'] > 0
        }

# Global instance
_hardware_patch = None

def get_hardware_patch() -> HardwareMonitoringPatch:
    """Get the global hardware monitoring patch instance"""
    global _hardware_patch
    if _hardware_patch is None:
        _hardware_patch = HardwareMonitoringPatch()
    return _hardware_patch

def apply_hardware_monitoring_patches():
    """Apply hardware monitoring patches"""
    patch = get_hardware_patch()
    patch.apply_all_patches()
    return patch

def get_safe_gpu_info() -> List[Dict[str, Any]]:
    """Get GPU information safely"""
    patch = get_hardware_patch()
    return patch.get_safe_gpu_info()

def get_safe_system_info() -> Dict[str, Any]:
    """Get system information safely"""
    patch = get_hardware_patch()
    return patch.get_safe_system_info()

# Auto-apply patches when imported
if __name__ != "__main__":
    apply_hardware_monitoring_patches()

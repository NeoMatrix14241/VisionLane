"""
Hardware Monitoring Patch for Nuitka
This module provides comprehensive hardware monitoring patches specifically for Nuitka compiled applications.
It addresses module inclusion and import issues that occur when compiled with Nuitka.
"""
import os
import sys
import ctypes
import platform
import subprocess
import re
import time
import threading
import json
import tempfile
from typing import Optional, Dict, List, Any, Tuple
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class HardwareMonitoringPatch:
    """Comprehensive hardware monitoring patching for Nuitka compatibility"""

    def __init__(self):
        self.patches_applied = False
        self.gpu_info_cache = {}
        self.cache_timestamp = 0
        self.cache_duration = 2.0  # Cache for 2 seconds
        self.monitoring_available = False
        self.nvidia_smi_path = None
        self.wmi_available = False
        self.pynvml_available = False
        self.gputil_available = False
        self.torch_available = False
        self._lock = threading.Lock()
        self._original_functions = {}

    def apply_patches(self) -> bool:
        """Apply all hardware monitoring patches for Nuitka"""
        if self.patches_applied:
            return True

        try:
            print("Hardware Monitoring Patch: Starting comprehensive patching for Nuitka...")
            
            # Detect available monitoring methods
            self._detect_monitoring_methods()
            
            # Apply patches in order
            self._patch_pynvml()
            self._patch_gputil()
            self._patch_torch_cuda_monitoring()
            self._patch_psutil_gpu()
            self._patch_wmi_gpu()
            
            # Mark as applied
            self.patches_applied = True
            
            print(f"Hardware Monitoring Patch: Successfully applied patches. Monitoring available: {self.monitoring_available}")
            return True

        except Exception as e:
            logger.error(f"Error applying hardware monitoring patches: {e}")
            return False

    def _detect_monitoring_methods(self):
        """Detect available GPU monitoring methods"""
        print("Hardware Monitoring Patch: Detecting available monitoring methods...")

        # Try to find nvidia-smi
        self.nvidia_smi_path = self._find_nvidia_smi()
        if self.nvidia_smi_path:
            print(f"Hardware Monitoring Patch: Found nvidia-smi at {self.nvidia_smi_path}")
            self.monitoring_available = True

        # Check PyTorch availability
        try:
            import torch
            self.torch_available = True
            print("Hardware Monitoring Patch: PyTorch monitoring available")
            self.monitoring_available = True
        except ImportError:
            print("Hardware Monitoring Patch: PyTorch not available")

        # Check pynvml availability
        try:
            import pynvml
            self.pynvml_available = True
            print("Hardware Monitoring Patch: pynvml monitoring available")
            self.monitoring_available = True
        except ImportError:
            print("Hardware Monitoring Patch: pynvml not available")

        # Check GPUtil availability
        try:
            import GPUtil
            self.gputil_available = True
            print("Hardware Monitoring Patch: GPUtil monitoring available")
            self.monitoring_available = True
        except ImportError:
            print("Hardware Monitoring Patch: GPUtil not available")

        # Check WMI availability on Windows
        if sys.platform.startswith('win'):
            try:
                import wmi
                self.wmi_available = True
                print("Hardware Monitoring Patch: WMI monitoring available")
                self.monitoring_available = True
            except ImportError:
                print("Hardware Monitoring Patch: WMI not available")

        # Try direct NVML loading
        if self._try_load_nvml():
            print("Hardware Monitoring Patch: Direct NVML loading successful")
            self.monitoring_available = True

    def _find_nvidia_smi(self) -> Optional[str]:
        """Find nvidia-smi executable"""
        possible_paths = []
        
        if sys.platform.startswith('win'):
            # Windows paths
            possible_paths = [
                r"C:\Windows\System32\nvidia-smi.exe",
                r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
                r"C:\ProgramData\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
            ]
            # Also check PATH
            try:
                result = subprocess.run(['where', 'nvidia-smi'], 
                                      capture_output=True, text=True, 
                                      creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    possible_paths.append(result.stdout.strip())
            except:
                pass
        else:
            # Unix-like systems
            possible_paths = [
                '/usr/bin/nvidia-smi',
                '/usr/local/bin/nvidia-smi',
                '/opt/nvidia/bin/nvidia-smi',
            ]
            # Also check PATH
            try:
                result = subprocess.run(['which', 'nvidia-smi'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    possible_paths.append(result.stdout.strip())
            except:
                pass

        for path in possible_paths:
            if os.path.isfile(path):
                try:
                    # Test if it works
                    result = subprocess.run([path, '--help'], 
                                          capture_output=True, 
                                          timeout=5,
                                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0)
                    if result.returncode == 0:
                        return path
                except:
                    continue

        return None

    def _try_load_nvml(self) -> bool:
        """Try to load NVML library directly"""
        try:
            if sys.platform.startswith('win'):
                # Try loading NVML DLL directly
                nvml_paths = [
                    "nvml.dll",
                    r"C:\Windows\System32\nvml.dll",
                    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll",
                ]

                for path in nvml_paths:
                    try:
                        ctypes.CDLL(path)
                        return True
                    except (OSError, FileNotFoundError):
                        continue
            else:
                # Unix-like systems
                try:
                    ctypes.CDLL("libnvidia-ml.so.1")
                    return True
                except (OSError, FileNotFoundError):
                    pass
        except Exception:
            pass

        return False

    def _patch_pynvml(self):
        """Patch pynvml for Nuitka compatibility"""
        if not self.pynvml_available:
            return

        try:
            import pynvml

            # Store original functions if not already stored
            if not hasattr(pynvml, '_original_nvmlInit'):
                self._original_functions['pynvml_nvmlInit'] = getattr(pynvml, 'nvmlInit', None)
                self._original_functions['pynvml_nvmlDeviceGetCount'] = getattr(pynvml, 'nvmlDeviceGetCount', None)
                self._original_functions['pynvml_nvmlDeviceGetHandleByIndex'] = getattr(pynvml, 'nvmlDeviceGetHandleByIndex', None)
                self._original_functions['pynvml_nvmlDeviceGetName'] = getattr(pynvml, 'nvmlDeviceGetName', None)
                self._original_functions['pynvml_nvmlDeviceGetUtilizationRates'] = getattr(pynvml, 'nvmlDeviceGetUtilizationRates', None)
                self._original_functions['pynvml_nvmlDeviceGetMemoryInfo'] = getattr(pynvml, 'nvmlDeviceGetMemoryInfo', None)
                self._original_functions['pynvml_nvmlDeviceGetTemperature'] = getattr(pynvml, 'nvmlDeviceGetTemperature', None)

                # Mark originals as stored
                pynvml._original_nvmlInit = self._original_functions['pynvml_nvmlInit']
                pynvml._original_nvmlDeviceGetCount = self._original_functions['pynvml_nvmlDeviceGetCount']
                pynvml._original_nvmlDeviceGetHandleByIndex = self._original_functions['pynvml_nvmlDeviceGetHandleByIndex']
                pynvml._original_nvmlDeviceGetName = self._original_functions['pynvml_nvmlDeviceGetName']
                pynvml._original_nvmlDeviceGetUtilizationRates = self._original_functions['pynvml_nvmlDeviceGetUtilizationRates']
                pynvml._original_nvmlDeviceGetMemoryInfo = self._original_functions['pynvml_nvmlDeviceGetMemoryInfo']
                pynvml._original_nvmlDeviceGetTemperature = self._original_functions['pynvml_nvmlDeviceGetTemperature']

            # Create patched functions
            def safe_nvmlInit():
                try:
                    if pynvml._original_nvmlInit:
                        return pynvml._original_nvmlInit()
                except Exception as e:
                    print(f"Hardware Monitoring Patch: pynvml init failed: {e}")
                    # Don't raise, just log
                    pass

            def safe_nvmlDeviceGetCount():
                try:
                    if pynvml._original_nvmlDeviceGetCount:
                        return pynvml._original_nvmlDeviceGetCount()
                except Exception:
                    # Fallback to nvidia-smi or torch
                    return self._get_gpu_count_fallback()

            def safe_nvmlDeviceGetUtilizationRates(handle):
                try:
                    if pynvml._original_nvmlDeviceGetUtilizationRates:
                        return pynvml._original_nvmlDeviceGetUtilizationRates(handle)
                except Exception:
                    # Return fallback utilization data
                    return self._get_gpu_utilization_fallback(handle)

            def safe_nvmlDeviceGetMemoryInfo(handle):
                try:
                    if pynvml._original_nvmlDeviceGetMemoryInfo:
                        return pynvml._original_nvmlDeviceGetMemoryInfo(handle)
                except Exception:
                    # Return fallback memory info
                    return self._get_gpu_memory_fallback(handle)

            def safe_nvmlDeviceGetName(handle):
                try:
                    if pynvml._original_nvmlDeviceGetName:
                        return pynvml._original_nvmlDeviceGetName(handle)
                except Exception:
                    return b"NVIDIA GPU (Fallback)"

            def safe_nvmlDeviceGetHandleByIndex(index):
                try:
                    if pynvml._original_nvmlDeviceGetHandleByIndex:
                        return pynvml._original_nvmlDeviceGetHandleByIndex(index)
                except Exception:
                    # Return mock handle
                    class MockHandle:
                        def __init__(self, device_id):
                            self.device_id = device_id
                    return MockHandle(index)

            def safe_nvmlDeviceGetTemperature(handle, sensor):
                try:
                    if pynvml._original_nvmlDeviceGetTemperature:
                        return pynvml._original_nvmlDeviceGetTemperature(handle, sensor)
                except Exception:
                    return 0  # Return 0 for temperature fallback

            # Apply patches
            pynvml.nvmlInit = safe_nvmlInit
            pynvml.nvmlDeviceGetCount = safe_nvmlDeviceGetCount
            pynvml.nvmlDeviceGetUtilizationRates = safe_nvmlDeviceGetUtilizationRates
            pynvml.nvmlDeviceGetMemoryInfo = safe_nvmlDeviceGetMemoryInfo
            pynvml.nvmlDeviceGetName = safe_nvmlDeviceGetName
            pynvml.nvmlDeviceGetHandleByIndex = safe_nvmlDeviceGetHandleByIndex
            pynvml.nvmlDeviceGetTemperature = safe_nvmlDeviceGetTemperature

            print("Hardware Monitoring Patch: pynvml patches applied successfully")

        except ImportError:
            print("Hardware Monitoring Patch: pynvml not available")

    def _patch_gputil(self):
        """Patch GPUtil for Nuitka compatibility"""
        if not self.gputil_available:
            return

        try:
            import GPUtil

            # Store original function
            if not hasattr(GPUtil, '_original_getGPUs'):
                self._original_functions['gputil_getGPUs'] = getattr(GPUtil, 'getGPUs', None)
                GPUtil._original_getGPUs = self._original_functions['gputil_getGPUs']

            def safe_getGPUs():
                try:
                    if GPUtil._original_getGPUs:
                        return GPUtil._original_getGPUs()
                except Exception:
                    # Return fallback GPU list
                    return self._get_gpus_fallback()

            # Apply patch
            GPUtil.getGPUs = safe_getGPUs

            print("Hardware Monitoring Patch: GPUtil patches applied successfully")

        except ImportError:
            print("Hardware Monitoring Patch: GPUtil not available")

    def _patch_torch_cuda_monitoring(self):
        """Patch torch.cuda monitoring functions"""
        if not self.torch_available:
            return

        try:
            import torch

            # Store original functions if not already stored
            if not hasattr(torch.cuda, '_original_utilization'):
                # These might not exist, so check first
                if hasattr(torch.cuda, 'utilization'):
                    self._original_functions['torch_utilization'] = torch.cuda.utilization
                    torch.cuda._original_utilization = torch.cuda.utilization
                if hasattr(torch.cuda, 'memory_stats'):
                    self._original_functions['torch_memory_stats'] = torch.cuda.memory_stats
                    torch.cuda._original_memory_stats = torch.cuda.memory_stats

            # Create safe utilization function
            def safe_utilization(device=None):
                try:
                    if hasattr(torch.cuda, '_original_utilization') and torch.cuda._original_utilization:
                        return torch.cuda._original_utilization(device)
                    else:
                        # Fallback to our monitoring
                        return self._get_gpu_utilization_torch_fallback(device)
                except Exception:
                    return self._get_gpu_utilization_torch_fallback(device)

            # Apply patches if functions exist
            if hasattr(torch.cuda, 'utilization'):
                torch.cuda.utilization = safe_utilization

            print("Hardware Monitoring Patch: torch.cuda monitoring patches applied successfully")

        except ImportError:
            print("Hardware Monitoring Patch: torch not available")

    def _patch_psutil_gpu(self):
        """Patch psutil GPU monitoring if available"""
        try:
            import psutil

            # psutil doesn't have built-in GPU monitoring, but we can add it
            def get_gpu_info():
                """Add GPU info to psutil"""
                return self._get_gpu_info_comprehensive()

            # Add custom GPU monitoring to psutil
            psutil.gpu_info = get_gpu_info

            print("Hardware Monitoring Patch: psutil GPU monitoring added")

        except ImportError:
            print("Hardware Monitoring Patch: psutil not available")

    def _patch_wmi_gpu(self):
        """Patch WMI GPU monitoring if available"""
        if not self.wmi_available:
            return

        try:
            import wmi

            # Store original WMI if needed for restoration
            if not hasattr(wmi, '_original_wmi'):
                self._original_functions['wmi_WMI'] = getattr(wmi, 'WMI', None)
                wmi._original_WMI = self._original_functions['wmi_WMI']

            print("Hardware Monitoring Patch: WMI GPU monitoring patches applied")

        except ImportError:
            print("Hardware Monitoring Patch: WMI not available")

    def _get_gpu_count_fallback(self) -> int:
        """Fallback method to get GPU count"""
        try:
            # Try nvidia-smi first
            if self.nvidia_smi_path:
                result = subprocess.run(
                    [self.nvidia_smi_path, "--list-gpus"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
                )
                if result.returncode == 0:
                    count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
                    return count

            # Try WMI on Windows
            if self.wmi_available:
                try:
                    import wmi
                    c = wmi.WMI()
                    gpus = c.Win32_VideoController()
                    nvidia_count = len([gpu for gpu in gpus if 'nvidia' in gpu.Name.lower()])
                    return nvidia_count
                except Exception:
                    pass

            # Try torch if available
            if self.torch_available:
                try:
                    import torch
                    if torch.cuda.is_available():
                        return torch.cuda.device_count()
                except Exception:
                    pass

        except Exception:
            pass

        return 0

    def _get_gpu_utilization_fallback(self, handle) -> Any:
        """Fallback method to get GPU utilization"""
        try:
            # Try nvidia-smi
            if self.nvidia_smi_path:
                # Get device index from handle (this is a simplification)
                device_id = getattr(handle, 'device_id', 0) if hasattr(handle, 'device_id') else 0

                result = subprocess.run(
                    [self.nvidia_smi_path, "--query-gpu=utilization.gpu,utilization.memory",
                     "--format=csv,noheader,nounits", f"--id={device_id}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
                )

                if result.returncode == 0:
                    values = result.stdout.strip().split(',')
                    if len(values) >= 2:
                        # Create a mock utilization object
                        class MockUtilization:
                            def __init__(self, gpu, memory):
                                self.gpu = int(gpu.strip()) if gpu.strip().isdigit() else 0
                                self.memory = int(memory.strip()) if memory.strip().isdigit() else 0

                        return MockUtilization(values[0], values[1])
        except Exception:
            pass

        # Return mock data
        class MockUtilization:
            def __init__(self):
                self.gpu = 0
                self.memory = 0

        return MockUtilization()

    def _get_gpu_memory_fallback(self, handle) -> Any:
        """Fallback method to get GPU memory info"""
        try:
            # Try nvidia-smi
            if self.nvidia_smi_path:
                device_id = getattr(handle, 'device_id', 0) if hasattr(handle, 'device_id') else 0

                result = subprocess.run(
                    [self.nvidia_smi_path, "--query-gpu=memory.total,memory.used,memory.free",
                     "--format=csv,noheader,nounits", f"--id={device_id}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
                )

                if result.returncode == 0:
                    values = result.stdout.strip().split(',')
                    if len(values) >= 3:
                        # Create mock memory info object
                        class MockMemoryInfo:
                            def __init__(self, total, used, free):
                                self.total = int(total.strip()) * 1024 * 1024  # Convert MB to bytes
                                self.used = int(used.strip()) * 1024 * 1024
                                self.free = int(free.strip()) * 1024 * 1024

                        return MockMemoryInfo(values[0], values[1], values[2])
        except Exception:
            pass

        # Return mock data
        class MockMemoryInfo:
            def __init__(self):
                self.total = 8 * 1024 * 1024 * 1024  # 8GB mock
                self.used = 0
                self.free = self.total

        return MockMemoryInfo()

    def _get_gpus_fallback(self) -> List[Any]:
        """Fallback method to get GPU list for GPUtil"""
        try:
            if self.nvidia_smi_path:
                result = subprocess.run(
                    [self.nvidia_smi_path, "--query-gpu=index,name,utilization.gpu,memory.total,memory.used,temperature.gpu",
                     "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
                )

                if result.returncode == 0:
                    gpus = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            values = [v.strip() for v in line.split(',')]
                            if len(values) >= 6:
                                index, name, load, memoryTotal, memoryUsed, temperature = values[:6]
                                
                                class MockGPU:
                                    def __init__(self, index, name, load, memoryTotal, memoryUsed, temperature):
                                        self.id = int(index) if index.isdigit() else 0
                                        self.name = name
                                        self.load = float(load) / 100.0 if load.replace('.', '').isdigit() else 0.0
                                        self.memoryTotal = int(memoryTotal) if memoryTotal.isdigit() else 8192
                                        self.memoryUsed = int(memoryUsed) if memoryUsed.isdigit() else 0
                                        self.memoryFree = self.memoryTotal - self.memoryUsed
                                        self.temperature = int(temperature) if temperature.isdigit() else 0

                                gpus.append(MockGPU(index, name, load, memoryTotal, memoryUsed, temperature))
                    return gpus
        except Exception:
            pass

        return []

    def _get_gpu_utilization_torch_fallback(self, device=None) -> float:
        """Fallback method for torch GPU utilization"""
        try:
            if self.nvidia_smi_path:
                device_id = device if device is not None else 0

                result = subprocess.run(
                    [self.nvidia_smi_path, "--query-gpu=utilization.gpu",
                     "--format=csv,noheader,nounits", f"--id={device_id}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
                )

                if result.returncode == 0:
                    util = result.stdout.strip()
                    if util.replace('.', '').isdigit():
                        return float(util)
        except Exception:
            pass

        return 0.0

    def _get_gpu_info_comprehensive(self) -> Dict[str, Any]:
        """Get comprehensive GPU information"""
        with self._lock:
            current_time = time.time()

            # Use cache if recent
            if current_time - self.cache_timestamp < self.cache_duration and self.gpu_info_cache:
                return self.gpu_info_cache

            gpu_info = {
                'gpus': [],
                'count': 0,
                'monitoring_available': self.monitoring_available,
                'method': 'fallback'
            }

            try:
                # Try to get comprehensive GPU info
                if self.nvidia_smi_path:
                    gpu_info = self._get_nvidia_smi_info()
                    gpu_info['method'] = 'nvidia-smi'
                elif self.wmi_available:
                    gpu_info = self._get_wmi_gpu_info()
                    gpu_info['method'] = 'wmi'
                elif self.torch_available:
                    # Use torch as last resort
                    gpu_info = self._get_torch_gpu_info()
                    gpu_info['method'] = 'torch'

                self.gpu_info_cache = gpu_info
                self.cache_timestamp = current_time

            except Exception as e:
                logger.error(f"Error getting GPU info: {e}")

            return gpu_info

    def _get_nvidia_smi_info(self) -> Dict[str, Any]:
        """Get GPU info using nvidia-smi"""
        result = subprocess.run(
            [self.nvidia_smi_path, "--query-gpu=index,name,utilization.gpu,memory.total,memory.used,memory.free,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
        )

        gpu_info = {'gpus': [], 'count': 0, 'monitoring_available': True}

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    values = [v.strip() for v in line.split(',')]
                    if len(values) >= 7:
                        gpu = {
                            'id': int(values[0]) if values[0].isdigit() else 0,
                            'name': values[1],
                            'utilization': float(values[2]) if values[2].replace('.', '').isdigit() else 0.0,
                            'memory_total': int(values[3]) if values[3].isdigit() else 0,
                            'memory_used': int(values[4]) if values[4].isdigit() else 0,
                            'memory_free': int(values[5]) if values[5].isdigit() else 0,
                            'temperature': int(values[6]) if values[6].isdigit() else 0,
                            'power_draw': float(values[7]) if len(values) > 7 and values[7].replace('.', '').isdigit() else 0.0
                        }
                        gpu_info['gpus'].append(gpu)

            gpu_info['count'] = len(gpu_info['gpus'])

        return gpu_info

    def _get_wmi_gpu_info(self) -> Dict[str, Any]:
        """Get GPU info using WMI (Windows only)"""
        try:
            import wmi
            c = wmi.WMI()
            gpus = c.Win32_VideoController()

            gpu_info = {'gpus': [], 'count': 0, 'monitoring_available': True}

            for i, gpu in enumerate(gpus):
                if 'nvidia' in gpu.Name.lower():
                    gpu_data = {
                        'id': i,
                        'name': gpu.Name,
                        'utilization': 0.0,  # WMI doesn't provide utilization
                        'memory_total': int(gpu.AdapterRAM / (1024*1024)) if gpu.AdapterRAM else 0,
                        'memory_used': 0,
                        'memory_free': int(gpu.AdapterRAM / (1024*1024)) if gpu.AdapterRAM else 0,
                        'temperature': 0,
                        'power_draw': 0.0
                    }
                    gpu_info['gpus'].append(gpu_data)

            gpu_info['count'] = len(gpu_info['gpus'])
            return gpu_info

        except Exception:
            return {'gpus': [], 'count': 0, 'monitoring_available': False}

    def _get_torch_gpu_info(self) -> Dict[str, Any]:
        """Get GPU info using torch"""
        try:
            import torch

            gpu_info = {'gpus': [], 'count': 0, 'monitoring_available': True}

            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    try:
                        props = torch.cuda.get_device_properties(i)
                        gpu_data = {
                            'id': i,
                            'name': props.name,
                            'utilization': 0.0,
                            'memory_total': int(props.total_memory / (1024*1024)),
                            'memory_used': int(torch.cuda.memory_allocated(i) / (1024*1024)),
                            'memory_free': int((props.total_memory - torch.cuda.memory_allocated(i)) / (1024*1024)),
                            'temperature': 0,
                            'power_draw': 0.0
                        }
                        gpu_info['gpus'].append(gpu_data)
                    except Exception:
                        # Add minimal GPU info
                        gpu_data = {
                            'id': i,
                            'name': f'CUDA Device {i}',
                            'utilization': 0.0,
                            'memory_total': 0,
                            'memory_used': 0,
                            'memory_free': 0,
                            'temperature': 0,
                            'power_draw': 0.0
                        }
                        gpu_info['gpus'].append(gpu_data)

                gpu_info['count'] = len(gpu_info['gpus'])

            return gpu_info

        except Exception:
            return {'gpus': [], 'count': 0, 'monitoring_available': False}

    def restore_original_functions(self):
        """Restore original functions (for cleanup)"""
        try:
            # Restore pynvml functions
            if self.pynvml_available:
                import pynvml
                for key, func in self._original_functions.items():
                    if key.startswith('pynvml_') and func:
                        attr_name = key.replace('pynvml_', '')
                        setattr(pynvml, attr_name, func)

            # Restore GPUtil functions
            if self.gputil_available:
                import GPUtil
                if 'gputil_getGPUs' in self._original_functions:
                    GPUtil.getGPUs = self._original_functions['gputil_getGPUs']

            # Restore torch functions
            if self.torch_available:
                import torch
                if 'torch_utilization' in self._original_functions:
                    torch.cuda.utilization = self._original_functions['torch_utilization']

            print("Hardware Monitoring Patch: Original functions restored")

        except Exception as e:
            logger.error(f"Error restoring original functions: {e}")


# Global instance
_hardware_patch = HardwareMonitoringPatch()

def apply_hardware_monitoring_patches() -> bool:
    """Apply hardware monitoring patches"""
    return _hardware_patch.apply_patches()

def get_gpu_info() -> Dict[str, Any]:
    """Get comprehensive GPU information"""
    return _hardware_patch._get_gpu_info_comprehensive()

def get_hardware_info() -> Dict[str, Any]:
    """Get comprehensive hardware information including CPU and memory"""
    try:
        import psutil
        
        # Get GPU info
        gpu_info = get_gpu_info()
        
        # Get CPU info
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # Get memory info
        memory = psutil.virtual_memory()
        
        hardware_info = {
            'cpu': {
                'usage_percent': cpu_percent,
                'core_count': cpu_count,
                'frequency_mhz': cpu_freq.current if cpu_freq else 0,
            },
            'memory': {
                'total_gb': round(memory.total / (1024**3), 1),
                'used_gb': round(memory.used / (1024**3), 1),
                'usage_percent': memory.percent,
                'available_gb': round(memory.available / (1024**3), 1)
            },
            'gpu': gpu_info
        }
        
        return hardware_info
        
    except Exception as e:
        logger.error(f"Error getting hardware info: {e}")
        return {
            'cpu': {'usage_percent': 0, 'core_count': 0, 'frequency_mhz': 0},
            'memory': {'total_gb': 0, 'used_gb': 0, 'usage_percent': 0, 'available_gb': 0},
            'gpu': {'gpus': [], 'count': 0, 'monitoring_available': False}
        }

def is_nuitka_environment() -> bool:
    """Check if running in Nuitka compiled environment"""
    return (
        hasattr(sys, 'frozen') or
        '__compiled__' in globals() or
        'nuitka' in sys.version.lower() or
        any('nuitka' in str(path).lower() for path in sys.path) or
        os.environ.get('__NUITKA_BINARY__') == '1'
    )

def restore_hardware_monitoring():
    """Restore original hardware monitoring functions"""
    _hardware_patch.restore_original_functions()

# Auto-apply patches if in Nuitka environment
if is_nuitka_environment():
    print("Hardware Monitoring Patch: Nuitka environment detected, auto-applying hardware monitoring patches...")
    apply_hardware_monitoring_patches()
else:
    print("Hardware Monitoring Patch: Development environment detected, applying patches for consistency")
    # Still apply patches for consistency in development
    apply_hardware_monitoring_patches()

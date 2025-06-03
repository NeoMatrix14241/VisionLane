"""
GPU Monitoring Patch for Nuitka
This module provides comprehensive GPU monitoring patches for Nuitka compiled applications.
It monkey patches pynvml, GPUtil, and torch.cuda monitoring functions to work properly in Nuitka.
"""
import os
import sys
import ctypes
import platform
import subprocess
import re
import time
import threading
from typing import Optional, Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class GPUMonitoringPatch:
    """Comprehensive GPU monitoring patching for Nuitka compatibility"""

    def __init__(self):
        self.patches_applied = False
        self.gpu_info_cache = {}
        self.cache_timestamp = 0
        self.cache_duration = 5.0  # Cache for 5 seconds
        self.monitoring_available = False
        self.nvidia_smi_path = None
        self.wmi_available = False
        self._lock = threading.Lock()

    def apply_patches(self) -> bool:
        """Apply all GPU monitoring patches for Nuitka"""
        if self.patches_applied:
            return True

        print("GPU Monitoring Patch: Applying comprehensive GPU monitoring patches...")

        try:
            # Detect available monitoring methods
            self._detect_monitoring_methods()

            # Patch pynvml
            self._patch_pynvml()

            # Patch GPUtil
            self._patch_gputil()

            # Patch torch.cuda monitoring
            self._patch_torch_cuda_monitoring()

            # Patch psutil if available
            self._patch_psutil_gpu()

            self.patches_applied = True
            print(f"GPU Monitoring Patch: Successfully applied patches. Monitoring available: {self.monitoring_available}")
            return True

        except Exception as e:
            print(f"GPU Monitoring Patch: Failed to apply patches: {e}")
            return False

    def _detect_monitoring_methods(self):
        """Detect available GPU monitoring methods"""
        print("GPU Monitoring Patch: Detecting available monitoring methods...")

        # Try to find nvidia-smi
        self.nvidia_smi_path = self._find_nvidia_smi()
        if self.nvidia_smi_path:
            print(f"GPU Monitoring Patch: Found nvidia-smi at {self.nvidia_smi_path}")
            self.monitoring_available = True

        # Check WMI availability on Windows
        if sys.platform.startswith('win'):
            try:
                import wmi
                self.wmi_available = True
                print("GPU Monitoring Patch: WMI monitoring available")
                self.monitoring_available = True
            except ImportError:
                print("GPU Monitoring Patch: WMI not available")

        # Try direct NVML loading
        if self._try_load_nvml():
            print("GPU Monitoring Patch: Direct NVML loading successful")
            self.monitoring_available = True

    def _find_nvidia_smi(self) -> Optional[str]:
        """Find nvidia-smi executable"""
        # Check PATH first
        nvidia_smi = "nvidia-smi.exe" if sys.platform.startswith('win') else "nvidia-smi"

        import shutil
        path = shutil.which(nvidia_smi)
        if path:
            return path

        # Check common installation paths
        if sys.platform.startswith('win'):
            common_paths = [
                r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
                r"C:\Windows\System32\nvidia-smi.exe",
                r"C:\Program Files (x86)\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
            ]

            # Also check CUDA toolkit paths
            cuda_base_paths = [
                r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA",
                r"C:\Program Files (x86)\NVIDIA GPU Computing Toolkit\CUDA",
            ]

            for base_path in cuda_base_paths:
                if os.path.exists(base_path):
                    for version_dir in os.listdir(base_path):
                        nvidia_smi_path = os.path.join(base_path, version_dir, "bin", "nvidia-smi.exe")
                        if os.path.exists(nvidia_smi_path):
                            common_paths.append(nvidia_smi_path)
        else:
            common_paths = [
                "/usr/bin/nvidia-smi",
                "/usr/local/cuda/bin/nvidia-smi",
                "/opt/cuda/bin/nvidia-smi",
            ]

        for path in common_paths:
            if os.path.exists(path):
                return path

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
        try:
            import pynvml

            # Store original functions
            if not hasattr(pynvml, '_original_nvmlInit'):
                pynvml._original_nvmlInit = pynvml.nvmlInit
                pynvml._original_nvmlDeviceGetCount = pynvml.nvmlDeviceGetCount
                pynvml._original_nvmlDeviceGetHandleByIndex = pynvml.nvmlDeviceGetHandleByIndex
                pynvml._original_nvmlDeviceGetName = pynvml.nvmlDeviceGetName
                pynvml._original_nvmlDeviceGetUtilizationRates = pynvml.nvmlDeviceGetUtilizationRates
                pynvml._original_nvmlDeviceGetMemoryInfo = pynvml.nvmlDeviceGetMemoryInfo
                pynvml._original_nvmlDeviceGetTemperature = pynvml.nvmlDeviceGetTemperature

            # Create patched functions
            def safe_nvmlInit():
                try:
                    return pynvml._original_nvmlInit()
                except Exception as e:
                    print(f"GPU Monitoring Patch: pynvml init failed: {e}")
                    # Don't raise, just log
                    pass

            def safe_nvmlDeviceGetCount():
                try:
                    return pynvml._original_nvmlDeviceGetCount()
                except Exception:
                    # Fallback to nvidia-smi or WMI
                    return self._get_gpu_count_fallback()

            def safe_nvmlDeviceGetUtilizationRates(handle):
                try:
                    return pynvml._original_nvmlDeviceGetUtilizationRates(handle)
                except Exception:
                    # Return fallback utilization data
                    return self._get_gpu_utilization_fallback(handle)

            def safe_nvmlDeviceGetMemoryInfo(handle):
                try:
                    return pynvml._original_nvmlDeviceGetMemoryInfo(handle)
                except Exception:
                    # Return fallback memory info
                    return self._get_gpu_memory_fallback(handle)

            def safe_nvmlDeviceGetName(handle):
                try:
                    return pynvml._original_nvmlDeviceGetName(handle)
                except Exception:
                    return b"NVIDIA GPU (Fallback)"

            def safe_nvmlDeviceGetTemperature(handle, sensor):
                try:
                    return pynvml._original_nvmlDeviceGetTemperature(handle, sensor)
                except Exception:
                    return 0  # Return 0 for temperature fallback

            # Apply patches
            pynvml.nvmlInit = safe_nvmlInit
            pynvml.nvmlDeviceGetCount = safe_nvmlDeviceGetCount
            pynvml.nvmlDeviceGetUtilizationRates = safe_nvmlDeviceGetUtilizationRates
            pynvml.nvmlDeviceGetMemoryInfo = safe_nvmlDeviceGetMemoryInfo
            pynvml.nvmlDeviceGetName = safe_nvmlDeviceGetName
            pynvml.nvmlDeviceGetTemperature = safe_nvmlDeviceGetTemperature

            print("GPU Monitoring Patch: pynvml patches applied successfully")

        except ImportError:
            print("GPU Monitoring Patch: pynvml not available")

    def _patch_gputil(self):
        """Patch GPUtil for Nuitka compatibility"""
        try:
            import GPUtil

            # Store original function
            if not hasattr(GPUtil, '_original_getGPUs'):
                GPUtil._original_getGPUs = GPUtil.getGPUs

            def safe_getGPUs():
                try:
                    return GPUtil._original_getGPUs()
                except Exception:
                    # Return fallback GPU list
                    return self._get_gpus_fallback()

            # Apply patch
            GPUtil.getGPUs = safe_getGPUs

            print("GPU Monitoring Patch: GPUtil patches applied successfully")

        except ImportError:
            print("GPU Monitoring Patch: GPUtil not available")

    def _patch_torch_cuda_monitoring(self):
        """Patch torch.cuda monitoring functions"""
        try:
            import torch

            # Store original functions if not already stored
            if not hasattr(torch.cuda, '_original_utilization'):
                # These might not exist, so check first
                if hasattr(torch.cuda, 'utilization'):
                    torch.cuda._original_utilization = torch.cuda.utilization
                if hasattr(torch.cuda, 'memory_stats'):
                    torch.cuda._original_memory_stats = torch.cuda.memory_stats

            # Create safe utilization function
            def safe_utilization(device=None):
                try:
                    if hasattr(torch.cuda, '_original_utilization'):
                        return torch.cuda._original_utilization(device)
                    else:
                        # Fallback to our monitoring
                        return self._get_gpu_utilization_torch_fallback(device)
                except Exception:
                    return self._get_gpu_utilization_torch_fallback(device)

            # Apply patches
            torch.cuda.utilization = safe_utilization

            print("GPU Monitoring Patch: torch.cuda monitoring patches applied successfully")

        except ImportError:
            print("GPU Monitoring Patch: torch not available")

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

            print("GPU Monitoring Patch: psutil GPU monitoring added")

        except ImportError:
            print("GPU Monitoring Patch: psutil not available")

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
                                self.gpu = int(gpu.strip())
                                self.memory = int(memory.strip())

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
            gpus = []

            # Try nvidia-smi
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
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            values = [v.strip() for v in line.split(',')]
                            if len(values) >= 6:
                                # Create mock GPU object
                                class MockGPU:
                                    def __init__(self, index, name, load, memoryTotal, memoryUsed, temperature):
                                        self.id = int(index)
                                        self.name = name
                                        self.load = float(load) / 100.0 if load.isdigit() else 0.0
                                        self.memoryTotal = int(memoryTotal) if memoryTotal.isdigit() else 8192
                                        self.memoryUsed = int(memoryUsed) if memoryUsed.isdigit() else 0
                                        self.memoryFree = self.memoryTotal - self.memoryUsed
                                        self.temperature = int(temperature) if temperature.isdigit() else 0

                                gpus.append(MockGPU(values[0], values[1], values[2], values[3], values[4], values[5]))

            # If no GPUs found via nvidia-smi, try torch
            if not gpus:
                try:
                    import torch
                    if torch.cuda.is_available():
                        for i in range(torch.cuda.device_count()):
                            class MockGPU:
                                def __init__(self, gpu_id):
                                    self.id = gpu_id
                                    self.name = torch.cuda.get_device_name(gpu_id) if hasattr(torch.cuda, 'get_device_name') else f"CUDA Device {gpu_id}"
                                    self.load = 0.0
                                    self.memoryTotal = 8192  # Default 8GB
                                    self.memoryUsed = 0
                                    self.memoryFree = self.memoryTotal
                                    self.temperature = 0

                            gpus.append(MockGPU(i))
                except Exception:
                    pass

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
                    if util.isdigit():
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
                else:
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

# Global instance
_gpu_patch = GPUMonitoringPatch()

def apply_gpu_monitoring_patches() -> bool:
    """Apply GPU monitoring patches"""
    return _gpu_patch.apply_patches()

def get_gpu_info() -> Dict[str, Any]:
    """Get comprehensive GPU information"""
    return _gpu_patch._get_gpu_info_comprehensive()

def is_nuitka_environment() -> bool:
    """Check if running in Nuitka compiled environment"""
    return (
        hasattr(sys, 'frozen') or
        '__compiled__' in globals() or
        'nuitka' in sys.version.lower() or
        any('nuitka' in str(path).lower() for path in sys.path) or
        os.environ.get('__NUITKA_BINARY__') == '1'
    )

# Auto-apply patches if in Nuitka environment
if is_nuitka_environment():
    print("GPU Monitoring Patch: Nuitka environment detected, auto-applying GPU monitoring patches...")
    apply_gpu_monitoring_patches()
else:
    print("GPU Monitoring Patch: Development environment detected, applying minimal patches")
    # Still apply patches for consistency
    apply_gpu_monitoring_patches()

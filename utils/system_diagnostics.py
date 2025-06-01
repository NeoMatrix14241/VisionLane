# utils/system_diagnostics.py
"""
Advanced System Diagnostics for VisionLane OCR
Provides detailed system information and checks during startup
"""

import platform
import sys
import psutil
import time
import logging
import threading
import socket
import hashlib
from pathlib import Path
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)

class SystemDiagnostics:
    """Advanced system diagnostics and health checks"""
    
    def __init__(self, progress_callback: Callable[[str], None] = None):
        self.progress_callback = progress_callback or (lambda x: print(x))
        self.diagnostics_data = {}
        
    def update_progress(self, message: str):
        """Update progress message"""
        if self.progress_callback:
            self.progress_callback(message)
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        self.update_progress("Analyzing system hardware...")
        
        info = {}
        
        # Basic system info
        info['platform'] = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'architecture': platform.architecture()[0]
        }
        
        # Python info
        info['python'] = {
            'version': sys.version,
            'executable': sys.executable,
            'path': sys.path[0] if sys.path else 'Unknown'
        }
        
        # Memory info
        try:
            memory = psutil.virtual_memory()
            info['memory'] = {
                'total': self._format_bytes(memory.total),
                'available': self._format_bytes(memory.available),
                'percent': memory.percent,
                'used': self._format_bytes(memory.used)
            }
        except Exception as e:
            info['memory'] = {'error': str(e)}
        
        # CPU info
        try:
            info['cpu'] = {
                'cores': psutil.cpu_count(logical=False),
                'logical_cores': psutil.cpu_count(logical=True),
                'current_freq': psutil.cpu_freq().current if psutil.cpu_freq() else 'Unknown',
                'max_freq': psutil.cpu_freq().max if psutil.cpu_freq() else 'Unknown'
            }
        except Exception as e:
            info['cpu'] = {'error': str(e)}
        
        # Disk info
        try:
            disk = psutil.disk_usage('/')
            info['disk'] = {
                'total': self._format_bytes(disk.total),
                'used': self._format_bytes(disk.used),
                'free': self._format_bytes(disk.free),
                'percent': (disk.used / disk.total) * 100
            }
        except Exception as e:
            info['disk'] = {'error': str(e)}
        
        return info
    
    def check_pytorch_installation(self) -> Dict[str, Any]:
        """Check PyTorch installation and capabilities"""
        self.update_progress("Checking PyTorch installation...")
        
        pytorch_info = {}
        
        try:
            import torch
            pytorch_info['installed'] = True
            pytorch_info['version'] = torch.__version__
            pytorch_info['cuda_available'] = torch.cuda.is_available()
            
            if torch.cuda.is_available():
                pytorch_info['cuda_version'] = torch.version.cuda
                pytorch_info['cudnn_version'] = torch.backends.cudnn.version()
                pytorch_info['gpu_count'] = torch.cuda.device_count()
                
                # Get GPU details
                gpus = []
                for i in range(torch.cuda.device_count()):
                    gpu_props = torch.cuda.get_device_properties(i)
                    gpus.append({
                        'id': i,
                        'name': gpu_props.name,
                        'memory': self._format_bytes(gpu_props.total_memory),
                        'capability': f"{gpu_props.major}.{gpu_props.minor}"
                    })
                pytorch_info['gpus'] = gpus
            else:
                pytorch_info['cuda_reason'] = "CUDA not available"
                
        except ImportError:
            pytorch_info['installed'] = False
            pytorch_info['error'] = "PyTorch not installed"
        except Exception as e:
            pytorch_info['error'] = str(e)
        
        return pytorch_info
    
    def check_dependencies(self) -> Dict[str, Any]:
        """Check required dependencies"""
        self.update_progress("Checking dependencies...")
        
        dependencies = {}
        
        required_packages = [
            'PyQt6', 'numpy', 'opencv-python', 'Pillow', 
            'requests', 'configparser', 'psutil'
        ]
        
        for package in required_packages:
            try:
                if package == 'opencv-python':
                    import cv2
                    dependencies[package] = {
                        'installed': True,
                        'version': cv2.__version__
                    }
                elif package == 'PyQt6':
                    from PyQt6.QtCore import QT_VERSION_STR
                    dependencies[package] = {
                        'installed': True,
                        'version': QT_VERSION_STR
                    }
                else:
                    module = __import__(package.replace('-', '_'))
                    version = getattr(module, '__version__', 'Unknown')
                    dependencies[package] = {
                        'installed': True,
                        'version': version
                    }
            except ImportError:
                dependencies[package] = {
                    'installed': False,
                    'error': 'Not installed'
                }
            except Exception as e:
                dependencies[package] = {
                    'installed': False,
                    'error': str(e)
                }
        
        return dependencies
    
    def check_doctr_installation(self) -> Dict[str, Any]:
        """Check DocTR installation and configuration"""
        self.update_progress("Checking DocTR installation...")
        
        doctr_info = {}
        
        try:
            import doctr
            doctr_info['installed'] = True
            doctr_info['version'] = getattr(doctr, '__version__', 'Unknown')
            
            # Check backend detection
            try:
                from doctr.file_utils import is_torch_available, is_tf_available
                doctr_info['torch_detected'] = is_torch_available()
                doctr_info['tf_detected'] = is_tf_available()
            except Exception as e:
                doctr_info['backend_error'] = str(e)
            
            # Check model cache
            cache_dir = Path.home() / ".cache" / "doctr" / "models"
            if cache_dir.exists():
                cached_models = list(cache_dir.glob("*.pt"))
                doctr_info['cached_models'] = len(cached_models)
                doctr_info['cache_size'] = self._format_bytes(
                    sum(f.stat().st_size for f in cached_models)
                )
            else:
                doctr_info['cached_models'] = 0
                doctr_info['cache_size'] = '0 B'
                
        except ImportError:
            doctr_info['installed'] = False
            doctr_info['error'] = "DocTR not installed"
        except Exception as e:
            doctr_info['error'] = str(e)
        
        return doctr_info
    
    def check_performance_metrics(self) -> Dict[str, Any]:
        """Check system performance metrics"""
        self.update_progress("Measuring performance metrics...")
        
        metrics = {}
        
        try:
            # CPU usage over short period
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics['cpu_usage'] = cpu_percent
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics['memory_usage'] = memory.percent
            
            # Disk I/O (if available)
            try:
                disk_io = psutil.disk_io_counters()
                metrics['disk_read_speed'] = 'Available'
                metrics['disk_write_speed'] = 'Available'
            except:
                metrics['disk_io'] = 'Not available'
            
            # Network connectivity (basic check)
            try:
                import socket
                socket.create_connection(("8.8.8.8", 53), timeout=3)
                metrics['internet_connection'] = True
            except:
                metrics['internet_connection'] = False
                
        except Exception as e:
            metrics['error'] = str(e)
        
        return metrics
    
    def run_quick_diagnostics(self) -> Dict[str, Any]:
        """Run quick diagnostics for caching"""
        diagnostics = {}
        
        try:
            # Quick system check
            diagnostics['memory_gb'] = round(psutil.virtual_memory().total / (1024**3), 1)
            diagnostics['cpu_cores'] = psutil.cpu_count()
            
            # Quick PyTorch check
            try:
                import torch
                diagnostics['pytorch'] = True
                diagnostics['cuda'] = torch.cuda.is_available()
            except:
                diagnostics['pytorch'] = False
                diagnostics['cuda'] = False
            
            # Quick DocTR check
            try:
                import doctr
                diagnostics['doctr'] = True
            except:
                diagnostics['doctr'] = False
                
        except Exception as e:
            diagnostics['error'] = str(e)
        
        return diagnostics
    
    def run_diagnostics(self, quick: bool = False) -> Dict[str, Any]:
        """Run complete system diagnostics"""
        if quick:
            return self.run_quick_diagnostics()
        
        self.update_progress("Starting system diagnostics...")
        
        diagnostics = {
            'timestamp': time.time(),
            'system_info': self.get_system_info(),
            'pytorch': self.check_pytorch_installation(),
            'dependencies': self.check_dependencies(),
            'doctr': self.check_doctr_installation(),
            'performance': self.check_performance_metrics()
        }
        
        self.update_progress("System diagnostics complete")
        return diagnostics
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    def get_diagnostic_summary(self, diagnostics: Dict[str, Any]) -> str:
        """Generate a human-readable diagnostic summary"""
        summary_lines = []
        
        # System info
        if 'system_info' in diagnostics:
            sys_info = diagnostics['system_info']
            if 'platform' in sys_info:
                platform_info = sys_info['platform']
                summary_lines.append(f"OS: {platform_info.get('system')} {platform_info.get('release')}")
            
            if 'memory' in sys_info and 'total' in sys_info['memory']:
                summary_lines.append(f"RAM: {sys_info['memory']['total']}")
            
            if 'cpu' in sys_info and 'cores' in sys_info['cpu']:
                summary_lines.append(f"CPU: {sys_info['cpu']['cores']} cores")
        
        # PyTorch info
        if 'pytorch' in diagnostics:
            pytorch = diagnostics['pytorch']
            if pytorch.get('installed'):
                summary_lines.append(f"PyTorch: {pytorch.get('version', 'Unknown')}")
                if pytorch.get('cuda_available'):
                    gpu_count = pytorch.get('gpu_count', 0)
                    summary_lines.append(f"CUDA: {gpu_count} GPU(s)")
                else:
                    summary_lines.append("CUDA: Not available")
            else:
                summary_lines.append("PyTorch: Not installed")
        
        # DocTR info
        if 'doctr' in diagnostics:
            doctr = diagnostics['doctr']
            if doctr.get('installed'):
                cached = doctr.get('cached_models', 0)
                summary_lines.append(f"DocTR: Installed ({cached} cached models)")
            else:
                summary_lines.append("DocTR: Not installed")
        
        return " | ".join(summary_lines)

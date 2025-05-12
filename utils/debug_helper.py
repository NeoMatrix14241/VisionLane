import sys
import logging
import traceback
from pathlib import Path
from datetime import datetime
import os
import threading
import psutil
import torch

class CrashHandler:
    def __init__(self, log_dir: Path = None):
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup crash log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.crash_log = self.log_dir / f"crash_{timestamp}.log"
        
        # Install exception hooks
        sys.excepthook = self.handle_exception
        threading.excepthook = self.handle_thread_exception
        
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        try:
            with open(self.crash_log, 'a', encoding='utf-8') as f:
                f.write("\n=== Uncaught Exception ===\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Type: {exc_type.__name__}\n")
                f.write(f"Message: {str(exc_value)}\n")
                f.write("\nStack Trace:\n")
                traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
                f.write("\nThread Information:\n")
                f.write(f"Current Thread: {threading.current_thread().name}\n")
                f.write("Active Threads:\n")
                for thread in threading.enumerate():
                    f.write(f"  - {thread.name} (alive: {thread.is_alive()})\n")
                
                # Add memory info
                f.write("\nMemory Usage:\n")
                process = psutil.Process()
                f.write(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB\n")
                if torch.cuda.is_available():
                    f.write(f"CUDA Memory: {torch.cuda.memory_allocated() / 1024 / 1024:.1f} MB\n")
                
        except Exception as e:
            print(f"Error in crash handler: {e}")
            
        # Call original excepthook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        
    def handle_thread_exception(self, args):
        """Handle uncaught thread exceptions"""
        try:
            with open(self.crash_log, 'a', encoding='utf-8') as f:
                f.write("\n=== Uncaught Thread Exception ===\n")
                f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Thread: {args.thread.name}\n")
                f.write(f"Type: {type(args.exc_value).__name__}\n")
                f.write(f"Message: {str(args.exc_value)}\n")
                f.write("\nStack Trace:\n")
                traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=f)
                
        except Exception as e:
            print(f"Error in thread crash handler: {e}")

class DebugLogger:
    def __init__(self, log_dir: Path = None):
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"debug_{timestamp}.log"
        
        # Configure root logger
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        
        # Create file handler with detailed formatting
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - [%(threadName)s] - '
            '%(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Create console handler with simpler formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # Remove existing handlers and add new ones
        self.logger.handlers.clear()
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Log system info
        self._log_system_info()
        
        # Add crash handler
        self.crash_handler = CrashHandler(log_dir)
        
        # Add detailed logging format
        detailed_formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - [%(threadName)s] - '
            '%(filename)s:%(lineno)d - %(funcName)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add memory usage logging
        self.memory_logger = logging.getLogger('memory')
        memory_handler = logging.FileHandler(log_dir / f"memory_{timestamp}.log")
        memory_handler.setFormatter(detailed_formatter)
        self.memory_logger.addHandler(memory_handler)
        self.memory_logger.setLevel(logging.DEBUG)
        
        # Start memory monitoring
        self._start_memory_monitoring()
    
    def _log_system_info(self):
        """Log detailed system information"""
        import platform
        
        self.logger.info("=" * 80)
        self.logger.info("System Information:")
        self.logger.info("-" * 40)
        self.logger.info(f"OS: {platform.platform()}")
        self.logger.info(f"Python: {sys.version}")
        self.logger.info(f"CPU Cores: {psutil.cpu_count()} (Physical: {psutil.cpu_count(logical=False)})")
        self.logger.info(f"Memory: {psutil.virtual_memory().total / (1024**3):.1f} GB")
        
        # GPU Information
        if torch.cuda.is_available():
            self.logger.info("\nGPU Information:")
            self.logger.info("-" * 40)
            self.logger.info(f"PyTorch CUDA: {torch.version.cuda}")
            for i in range(torch.cuda.device_count()):
                self.logger.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        
        self.logger.info("=" * 80)
    
    def _start_memory_monitoring(self):
        """Monitor memory usage periodically"""
        def log_memory():
            while True:
                try:
                    process = psutil.Process()
                    mem_info = process.memory_info()
                    self.memory_logger.info(
                        f"Memory: RSS={mem_info.rss/1024/1024:.1f}MB, "
                        f"VMS={mem_info.vms/1024/1024:.1f}MB"
                    )
                    if torch.cuda.is_available():
                        self.memory_logger.info(
                            f"CUDA Memory: "
                            f"Allocated={torch.cuda.memory_allocated()/1024/1024:.1f}MB, "
                            f"Cached={torch.cuda.memory_reserved()/1024/1024:.1f}MB"
                        )
                except Exception as e:
                    print(f"Error in memory monitoring: {e}")
                finally:
                    threading.Event().wait(10)  # Log every 10 seconds
                    
        threading.Thread(target=log_memory, daemon=True, name="MemoryMonitor").start()

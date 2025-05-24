import os
import sys
import logging
import signal
from pathlib import Path
from typing import Union, List, Dict
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
from ocrmypdf.hocrtransform import HocrTransform
from PIL import Image
import warnings
from datetime import datetime
from PyPDF2 import PdfMerger
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import get_context
import psutil
import torch
import gc
import time
import threading
import tempfile
import shutil
from utils.thread_killer import ThreadKiller
from utils.pypdfcompressor import compress_pdf  # Add this import

# --- PATCH: Suppress nvidia-smi console window on Windows ---
import subprocess
if sys.platform.startswith("win"):
    _orig_popen = subprocess.Popen
    def _patched_popen(*args, **kwargs):
        # If calling nvidia-smi, suppress window
        cmd = args[0] if args else kwargs.get("args", "")
        if isinstance(cmd, (list, tuple)):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = str(cmd)
        if "nvidia-smi" in cmd_str.lower():
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return _orig_popen(*args, **kwargs)
    subprocess.Popen = _patched_popen
# --- END PATCH ---

# Disable PIL decompression bomb warning
Image.MAX_IMAGE_PIXELS = None  # Add this line to remove the warning
warnings.filterwarnings('ignore', category=Image.DecompressionBombWarning)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Logging setup: always log to both file and console (stdout) ---
def _ensure_console_logging():
    root_logger = logging.getLogger()
    # Remove duplicate StreamHandlers (keep only one)
    stream_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
    if len(stream_handlers) > 1:
        # Keep only the first StreamHandler
        for h in stream_handlers[1:]:
            root_logger.removeHandler(h)
    # Add StreamHandler if none exists
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
_ensure_console_logging()

def _check_gpu_support():
    """Check GPU support and return (is_available, reason, device_info)"""
    gpu_info = []
    detailed_reason = []
    
    # Basic CUDA availability check
    cuda_available = torch.cuda.is_available()
    gpu_info.append(f"CUDA Available: {cuda_available}")
    gpu_info.append(f"PyTorch Version: {torch.__version__}")
    gpu_info.append(f"PyTorch CUDA Version: {torch.version.cuda}")
    
    if not cuda_available:
        # Check NVIDIA driver
        try:
            import pynvml
            pynvml.nvmlInit()
            driver_version = pynvml.nvmlSystemGetDriverVersion().decode()
            gpu_info.append(f"NVIDIA Driver Version: {driver_version}")
            
            # Get GPU details even if CUDA is not available
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                gpu_name = pynvml.nvmlDeviceGetName(handle).decode()
                gpu_info.append(f"GPU {i}: {gpu_name}")
            
            detailed_reason.append("CUDA is not available despite NVIDIA driver being installed")
            detailed_reason.append("Possible causes:")
            detailed_reason.append("1. PyTorch not built with CUDA support")
            detailed_reason.append("2. CUDA toolkit not installed")
            detailed_reason.append("3. PyTorch CUDA version mismatch with driver")
            
        except ImportError:
            gpu_info.append("NVIDIA Management Library (NVML) not available")
            detailed_reason.append("NVML not installed - cannot query GPU information")
        except pynvml.NVMLError as e:
            gpu_info.append(f"NVIDIA Driver: Not detected or not properly installed ({str(e)})")
            detailed_reason.append("NVIDIA driver not installed or not functioning properly")
        except Exception as e:
            gpu_info.append(f"Error checking GPU: {str(e)}")
            detailed_reason.append(f"Unexpected error during GPU check: {str(e)}")
        
        # Check system GPU through Windows Management Interface
        if sys.platform == 'win32':
            try:
                import wmi
                computer = wmi.WMI()
                gpu_devices = computer.Win32_VideoController()
                for gpu in gpu_devices:
                    gpu_info.append(f"System GPU: {gpu.Name}")
            except Exception:
                pass
        
        reason = " | ".join(detailed_reason)
        return False, reason, gpu_info
    
    # CUDA is available, get detailed info
    gpu_count = torch.cuda.device_count()
    min_compute_capability = 3.0
    
    for i in range(gpu_count):
        gpu_name = torch.cuda.get_device_name(i)
        compute_capability = torch.cuda.get_device_capability(i)
        compute_ver = float(f"{compute_capability[0]}.{compute_capability[1]}")
        gpu_info.append(f"GPU {i}: {gpu_name} (Compute {compute_ver})")
        
        if torch.cuda.is_available():
            try:
                total_mem = torch.cuda.get_device_properties(i).total_memory / 1024**2
                free_mem = torch.cuda.memory_allocated(i) / 1024**2
                gpu_info.append(f"GPU {i} Memory: {total_mem:.0f}MB (Used: {free_mem:.0f}MB)")
            except Exception as e:
                gpu_info.append(f"Could not query GPU {i} memory: {str(e)}")
    
    return True, "GPU(s) supported", gpu_info

class OCRProcessor:
    def __init__(self, output_base_dir: str = None, output_formats: List[str] = ["pdf"], detection_model: str = "db_resnet50", recognition_model: str = "crnn_vgg16_bn", dpi: int = None):
        # Set detection/recognition models FIRST
        self.detection_model = detection_model
        self.recognition_model = recognition_model
        
        # Initialize paths but don't create directories yet
        self.output_base_dir = None
        self.pdf_dir = None
        self.hocr_dir = None
        self.temp_dir = None
        
        # Set default temp directory path
        if tempfile.gettempdir():
            self.temp_dir = Path(tempfile.gettempdir()) / "VisionLaneOCR_temp"
        
        # Set output formats
        self.output_formats = [fmt.lower() for fmt in output_formats]
        if not all(fmt in ["pdf", "hocr"] for fmt in self.output_formats):
            raise ValueError("Output formats must be 'pdf', 'hocr', or both")
            
        # Only set output directory if provided
        if output_base_dir:
            self.set_output_directory(Path(output_base_dir))
        
        # Initialize multiprocessing components
        self.mp_context = get_context('spawn')
        self.image_queue = self.mp_context.Queue()
        self.result_queue = self.mp_context.Queue()

        # Add cleanup timing control
        self._last_cleanup = 0
        self._cleanup_interval = 300  # 5 minutes between cleanups

        # Add processed files tracking
        self._processed_files = set()

        # Setup threading with maximum CPU threads
        cpu_info = psutil.cpu_count(logical=True)  # Get logical CPU count (includes hyperthreading)
        physical_cores = psutil.cpu_count(logical=False)  # Get physical core count
        self.max_workers = cpu_info  # Use all available threads
        
        logger.info(f"CPU Information:")
        logger.info(f"Physical CPU cores: {physical_cores}")
        logger.info(f"Total CPU threads: {cpu_info}")
        logger.info(f"Initializing thread pool with {self.max_workers} workers")
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Initialize cancellation flag
        self.is_cancelled = False

        # Initialize progress callback
        self.progress_callback = None

        # Track current processing file
        self.current_file = None

        # Store input path for folder structure preservation
        self.input_path = None

        # Initialize output formats
        self.output_formats = [fmt.lower() for fmt in output_formats]
        if not all(fmt in ["pdf", "hocr"] for fmt in self.output_formats):
            raise ValueError("Output formats must be 'pdf', 'hocr', or both")

        # Add timeout configuration
        self.operation_timeout = 300  # 5 minutes default timeout per file
        self.chunk_timeout = 60  # 1 minute timeout for smaller operations

        # Add signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        self._force_stop = False

        # Add PID tracking
        self.process_pids = set()
        self._main_pid = os.getpid()
        self._parent_process = psutil.Process()
        self._current_processes = []

        # Add process group handling
        self._process_group = os.getpid()
        self._worker_processes = set()

        # Add thread tracking
        self._active_threads = []
        self._should_exit = threading.Event()
        self._exit_event = threading.Event()
        self._running_threads = set()

        # Add thread lock and job tracking
        self.batch_lock = threading.Lock()  # Add thread lock
        self.active_jobs = set()  # Track active jobs
        self.completed_jobs = set()  # Track completed jobs

        # Add image processing configurations
        self.max_image_size = 2000  # Maximum image dimension
        self.batch_size = 1  # Process one file at a time

        # Force cleanup interval = 300  # 5 minutes between cleanups
        self.cleanup_temp_files(force=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Check GPU support and initialize device first
        is_supported, reason, gpu_info = _check_gpu_support()
        self.device = 'cuda' if is_supported else 'cpu'
        
        for info in gpu_info:
            logger.info(info)
            
        if is_supported:
            logger.info(f"Using GPU for processing")
        else:
            logger.warning(f"No GPU available: {reason}")
            
        # Initialize OCR model
        try:
            logger.info("Initializing OCR model...")
            
            # Configure CUDA settings if using GPU
            if self.device == 'cuda':
                torch.backends.cudnn.enabled = True
                torch.backends.cudnn.benchmark = True
                torch.cuda.empty_cache()
            
            self._init_model()
            
            logger.info(f"OCR model initialization successful (using {self.device.upper()})")
            
        except Exception as e:
            logger.error(f"Failed to load OCR model: {str(e)}")
            raise

    def _init_model(self):
        """(Re)initialize the OCR model with current detection/recognition models"""
        import doctr.models as doctr_models
        self.model = ocr_predictor(
            det_arch=self.detection_model,
            reco_arch=self.recognition_model,
            pretrained=True,
            assume_straight_pages=True
        ).to(self.device)
        self.model.eval()
        if self.device == 'cuda':
            torch.cuda.synchronize()
            logger.info(f"GPU Memory Usage: {torch.cuda.memory_allocated() / 1024**2:.2f}MB")
            logger.info(f"GPU Memory Cached: {torch.cuda.memory_reserved() / 1024**2:.2f}MB")
        logger.info(f"OCR model initialized: det={self.detection_model}, reco={self.recognition_model}")

    def set_models(self, detection_model: str, recognition_model: str):
        """Set detection and recognition models and reinitialize if changed"""
        changed = False
        if detection_model and detection_model != self.detection_model:
            self.detection_model = detection_model
            changed = True
        if recognition_model and recognition_model != self.recognition_model:
            self.recognition_model = recognition_model
            changed = True
        if changed:
            logger.info(f"Switching OCR models: det={self.detection_model}, reco={self.recognition_model}")
            self._init_model()

    def set_output_directory(self, path: Path):
        """Set and create output directory structure"""
        self.output_base_dir = Path(path).resolve()
        self.pdf_dir = self.output_base_dir / "pdf"
        self.hocr_dir = self.output_base_dir / "hocr"
        
        # Create temp directory if not already set
        if not self.temp_dir:
            self.temp_dir = Path(tempfile.gettempdir()) / "VisionLaneOCR_temp"
        
        # Create directories only if they're needed
        if "pdf" in self.output_formats:
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
        if "hocr" in self.output_formats:
            self.hocr_dir.mkdir(parents=True, exist_ok=True)
        
        # Always ensure temp directory exists
        if self.temp_dir:
            if self.temp_dir.exists():
                shutil.rmtree(str(self.temp_dir), ignore_errors=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _signal_handler(self, signum, frame):
        """Handle interrupt signal"""
        self._force_stop = True
        self.cancel_processing()
        self._exit_event.clear()

    def cleanup_temp_files(self, force=False):
        """Enhanced temp file cleanup with better null checks"""
        try:
            # Check if temp_dir is set and exists
            if not self.temp_dir or not isinstance(self.temp_dir, Path):
                return
                
            if not self.temp_dir.exists():
                return
                
            # Delete all files in temp directory
            for temp_file in self.temp_dir.glob('*'):
                try:
                    if temp_file.is_file():
                        os.chmod(str(temp_file), 0o666)
                        temp_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file}: {e}")
            
            # Remove temp directory itself if empty or forced
            try:
                if self.temp_dir.exists():
                    if force:
                        shutil.rmtree(str(self.temp_dir), ignore_errors=True)
                    else:
                        # Only remove if empty
                        remaining = list(self.temp_dir.glob('*'))
                        if not remaining:
                            self.temp_dir.rmdir()
            except Exception as e:
                logger.warning(f"Could not remove temp directory: {e}")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def cancel_processing(self):
        """Force terminate all processes and cleanup"""
        try:
            self.is_cancelled = True
            self._force_stop = True
            self._exit_event.set()
            # Force cleanup first
            self.cleanup_temp_files(force=True)
            # Kill all non-Qt threads
            ThreadKiller.terminate_all_threads()
            # Kill processes
            current_pid = os.getpid()
            for pid in list(self._worker_processes):
                if pid != self._main_pid and pid != current_pid:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except:
                        pass
            # Terminate thread pool
            if hasattr(self, 'thread_pool'):
                ThreadKiller.terminate_thread_pool(self.thread_pool)
                self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
            
            # Clear GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            logger.error(f"Error during cancellation: {e}")
        finally:
            # Reset all state
            self._reset_state()

    def _reset_state(self):
        """Reset all internal state"""
        self.is_cancelled = True
        self._force_stop = True
        self._exit_event.set()
        self._should_exit.set()
        self.current_file = None
        self._worker_processes.clear()
        self._running_threads.clear()
        self._active_threads.clear()
        self.process_pids.clear()
        self.active_jobs.clear()
        self.completed_jobs.clear()
        self._processed_files.clear()

    def reset_state(self):
        """Reset all internal state for a new processing session"""
        # Reset flags
        self.is_cancelled = False
        self._force_stop = False
        self._exit_event.clear()
        self._should_exit.clear()
        
        # Reset tracking
        self.current_file = None
        self._worker_processes.clear()
        self._running_threads.clear()
        self._active_threads.clear()
        self.process_pids.clear()
        self.active_jobs.clear()
        self.completed_jobs.clear()
        self._processed_files.clear()
        
        # Force cleanup
        self.cleanup_temp_files(force=True)
        
        # Clear GPU memory if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Reset thread pool if needed
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=False)
            self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        
        logger.debug("OCRProcessor state reset completed")

    def process_image(self, image_path: Union[str, Path]) -> Dict:
        """Track current thread and check cancellation"""
        if self.is_cancelled or self._force_stop:
            return {"status": "cancelled"}
        current_thread = threading.current_thread()
        self._running_threads.add(current_thread)
        self.current_file = None
        try:
            # Check cancellation frequently
            if self._exit_event.is_set():
                return {"status": "cancelled"}
            image_path = Path(image_path).resolve()
            # Track file before processing
            self._processed_files.add(str(image_path))
            logger.debug(f"Added to processed files: {image_path.name}")

            # --- FIX: Calculate relative path from input_path (session root) ---
            try:
                relative_path = image_path.parent.relative_to(self.input_path)
            except ValueError:
                relative_path = image_path.parent

            # --- FIX: Folder key must be unique per subfolder (relative to input_path) ---
            folder_key = str(relative_path).replace(':', '').replace('\\', '-').replace('/', '-')
            if not folder_key or folder_key == '.':
                folder_key = "root"

            # --- FIX: Always create temp_dir if missing (can be deleted after previous merge) ---
            if not self.temp_dir.exists():
                self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Get all images in current folder and sort them
            all_images = sorted([
                p for p in image_path.parent.glob("*.tif")
                if p.is_file()
            ], key=lambda x: x.name)
            current_index = all_images.index(image_path)
            total_images = len(all_images)
            logger.info(f"Processing image {current_index + 1}/{total_images}: {image_path.name}")
            logger.debug(f"Folder key: {folder_key}")
            logger.debug(f"Full path: {image_path}")

            # Create temp PDF with index to maintain order
            temp_pdf_path = self.temp_dir / f"{folder_key}-{current_index:04d}.pdf"
            self._process_single_image(image_path, temp_pdf_path, dpi=self.dpi)

            # Only merge when processing the last image in this subfolder
            if current_index == len(all_images) - 1:
                self._merge_folder_pdfs(folder_key, relative_path)
            return {
                "status": "success",
                "folder": str(relative_path),
                "index": current_index,
                "total": total_images
            }
        except Exception as e:
            # Remove from processed if failed
            self._processed_files.discard(str(image_path))
            logger.error(f"Error processing {image_path}: {e}", exc_info=True)
            raise
        finally:
            self._running_threads.discard(current_thread)

    def process_folder(self, folder_path: Union[str, Path]) -> Dict:
        """Process a folder of images"""
        if not self.output_base_dir:
            raise ValueError("Output directory not set. Call set_output_directory first.")
            
        # Make input path absolute
        folder_path = Path(folder_path).resolve()
        abs_path = str(folder_path.absolute())
        self.input_path = folder_path
        logger.info(f"\nSelected: {abs_path}")

        # Create timestamped subfolder for this processing session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_base_dir / f"OCR_Session_{timestamp}"

        # Update subdirectories to be within the session directory
        self.hocr_dir = self.session_dir / "hocr"
        self.pdf_dir = self.session_dir / "pdf"
        self.temp_dir = self.session_dir / "temp"

        # Create output directories
        for dir_path in [self.session_dir, self.hocr_dir, self.pdf_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {dir_path}")

        logger.info(f"Output will be saved to: {self.session_dir}")

        # Count files by type first
        image_files = []
        pdf_files = []
        for path in folder_path.rglob('*'):
            if path.is_file():
                if path.suffix.lower() in ['.tif', '.tiff']:
                    image_files.append(path)
                elif path.suffix.lower() == '.pdf':
                    pdf_files.append(path)
        logger.info(f"Found: {len(image_files)} images, {len(pdf_files)} pdf\n")

        # Continue with existing processing
        all_files = [('image', p) for p in image_files]
        all_files.extend(('pdf', p) for p in pdf_files)
        total_files = len(all_files)
        if not total_files:
            logger.warning(f"No supported files found in folder: {folder_path}")
            return {"status": "no_files", "processed": 0, "total": 0}
        logger.info(f"Starting batch processing: {len(all_files)} files")

        # Initialize state
        self.is_cancelled = False
        self.current_file = None
        completed = 0
        failed = 0
        # Emit initial progress safely
        if callable(self.progress_callback):
            try:
                if not self.progress_callback(0, total_files):
                    return {"status": "cancelled", "processed": 0, "total": total_files}
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
        try:
            # Process files one at a time to prevent memory issues
            for file_type, file_path in all_files:
                if self.is_cancelled or self._force_stop:
                    break
                    
                self.current_file = str(file_path)
                cancelled = False
                try:
                    # Add to processed files set immediately
                    self._processed_files.add(str(file_path))
                    logger.debug(f"Processing {len(self._processed_files)}/{total_files}: {Path(file_path).name}")
                    # Force cleanup before each file
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    if file_type == 'image':
                        self.process_image(file_path)
                    else:
                        self.process_pdf(file_path)
                    completed += 1
                    # Signal completion of this file
                    if self.progress_callback:
                        self.progress_callback(100, 100)  # Signal file completion

                except Exception as e:
                    # Remove from processed files if failed
                    self._processed_files.discard(str(file_path))
                    logger.error(f"Failed to process {file_path}: {e}")
                    failed += 1
                    continue
            # Clean up after batch
            gc.collect()
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
        except Exception as e:
            logger.error(f"Batch processing error: {e}", exc_info=True)
            raise
        finally:
            # Always try to clean up temp directory at end of processing
            try:
                if self.temp_dir.exists():
                    shutil.rmtree(str(self.temp_dir), ignore_errors=True)
                    logger.info("Cleaned up temp directory after processing")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")

        status = "cancelled" if self.is_cancelled else "success"
        if failed > 0:
            status = "partial"
        return {
            "status": status,
            "processed": completed,
            "failed": failed,
            "total": total_files
        }

    # Add alias for backward compatibility
    def _process_single_file(self, file_path: Union[str, Path]) -> None:
        """Alias for process_image for backward compatibility"""
        return self.process_image(file_path)
                
    def _process_single_image(self, image_path: Path, temp_pdf_path: Path, dpi=None) -> None:
        """Process single image with improved error handling and memory management"""
        if self.is_cancelled or self._force_stop:
            return None
        temp_hocr = None
        intermediate_pdf = None

        # --- Always define processed_image_path at the start ---
        processed_image_path = image_path
        try:
            # --- REMOVE: Compress image before PDF creation ---

            # Check cancellation state
            if self.is_cancelled or self._force_stop:
                return None
                
            # Progress updates
            if self.progress_callback:
                if not self.progress_callback(0, 100):  # Start
                    return None
            
            # Safe GPU memory cleanup before processing
            if torch.cuda.is_available():
                try:
                    # Add synchronization point and environment variable
                    os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                    torch.cuda.reset_peak_memory_stats()
                except Exception as e:
                    # If CUDA fails, force CPU mode
                    logger.warning(f"GPU error detected, switching to CPU: {e}")
                    self.device = 'cpu'
                    if hasattr(self, 'model'):
                        self.model = self.model.cpu()
            
            # Move input to correct device with error handling
            try:
                docs = DocumentFile.from_images(str(processed_image_path))
                if self.device == 'cuda':
                    torch.cuda.synchronize()
            except Exception as e:
                logger.error(f"Error loading image {processed_image_path}: {e}")
                self.device = 'cpu'
                self.model = self.model.cpu()
                docs = DocumentFile.from_images(str(processed_image_path))
            
            if self.progress_callback:
                if not self.progress_callback(25, 100):  # Document loaded
                    return None
            
            # Process with error handling    
            try:
                with torch.no_grad():
                    # Process in smaller batches if needed
                    result = self.model(docs)
                    if self.device == 'cuda':
                        torch.cuda.synchronize()  # Wait for CUDA operations
            except RuntimeError as e:
                if "CUDA" in str(e):
                    # Try to recover by moving to CPU
                    logger.warning("CUDA error encountered, falling back to CPU")
                    self.device = 'cpu'
                    self.model = self.model.cpu()
                    with torch.no_grad():
                        result = self.model(docs)
                else:
                    raise
        
            if self.progress_callback:
                if not self.progress_callback(50, 100):  # OCR done
                    return None
            # Generate and save HOCR file
            xml_outputs = result.export_as_xml()
            timestamp = int(datetime.now().timestamp())
            temp_hocr = self.temp_dir / f"{image_path.stem}_{timestamp}_temp.hocr"
            
            try:
                # Save HOCR if it's in output formats or needed for PDF
                hocr_needed = "hocr" in self.output_formats or "pdf" in self.output_formats
                if hocr_needed:
                    # Save temp HOCR first
                    with open(temp_hocr, "w", encoding="utf-8") as f:
                        f.write(xml_outputs[0][0].decode())
                
                    # If HOCR output is requested, save to final location
                    if "hocr" in self.output_formats:
                        relative_path = image_path.parent.relative_to(self.input_path)
                        hocr_output = self.hocr_dir / relative_path / f"{image_path.stem}.hocr"
                        hocr_output.parent.mkdir(parents=True, exist_ok=True)
                        # Copy content instead of moving to preserve for PDF creation if needed
                        with open(hocr_output, "w", encoding="utf-8") as f:
                            f.write(xml_outputs[0][0].decode())
                        logger.info(f"Created HOCR output: {hocr_output}")
            except Exception as e:
                logger.error(f"Failed to write HOCR file: {e}")
                raise
            
            if self.progress_callback:
                if not self.progress_callback(75, 100):  # HOCR saved
                    return None
            # Cleanup memory
            del result, xml_outputs, docs
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            # Verify HOCR file exists before proceeding
            if not temp_hocr.exists():
                raise FileNotFoundError(f"HOCR file not created: {temp_hocr}")
            
            # Only create PDF if requested
            if "pdf" in self.output_formats:
                # Create temp files with unique names
                timestamp = int(datetime.now().timestamp())
                intermediate_pdf = self.temp_dir / f"{image_path.stem}_{timestamp}_temp.pdf"
                # Create PDF with retries
                max_retries = 3
                last_error = None
                
                # Determine DPI
                dpi_to_use = dpi
                if dpi_to_use is None:
                    # Try to read DPI from image metadata
                    try:
                        with Image.open(image_path) as img:
                            dpi_meta = img.info.get("dpi")
                            if dpi_meta and isinstance(dpi_meta, (tuple, list)) and dpi_meta[0] > 0:
                                dpi_to_use = int(dpi_meta[0])
                            else:
                                dpi_to_use = 300  # Fallback default
                    except Exception:
                        dpi_to_use = 300

                for attempt in range(max_retries):
                    try:
                        hocr = HocrTransform(
                            hocr_filename=str(temp_hocr),
                            dpi=dpi_to_use
                        )
                        hocr.to_pdf(
                            out_filename=str(intermediate_pdf),
                            image_filename=str(processed_image_path)
                        )
                        # Verify intermediate PDF was created and has content
                        if intermediate_pdf.exists() and intermediate_pdf.stat().st_size > 0:
                            if temp_pdf_path.exists():
                                temp_pdf_path.unlink()
                            os.chmod(str(intermediate_pdf), 0o666)  # Ensure we can modify the file
                            intermediate_pdf.replace(temp_pdf_path)
                            
                            # Wait briefly to ensure file is written
                            time.sleep(0.1)
                            if not temp_pdf_path.exists() or temp_pdf_path.stat().st_size == 0:
                                raise FileNotFoundError("PDF file not properly created")
                            logger.debug(f"Created PDF: {temp_pdf_path}")
                            break
                        else:
                            raise FileNotFoundError("Failed to create intermediate PDF")
                    except Exception as e:
                        last_error = e
                        logger.warning(f"Attempt {attempt + 1} failed: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(1)  # Wait longer between retries
                        else:
                            raise last_error
            
            # --- NEW: Compress the PDF after creation ---
            if "pdf" in self.output_formats:
                # After temp_pdf_path is created and verified:
                if getattr(self, "compress_images", False):
                    try:
                        # Compress the temp PDF and overwrite it
                        compressed_pdf_path = temp_pdf_path.with_suffix(".compressed.pdf")
                        compress_pdf(
                            str(temp_pdf_path),
                            str(compressed_pdf_path),
                            quality=getattr(self, "compression_quality", 80),
                            fast_mode=True,
                            compression_type=getattr(self, "compression_type", "jpeg")  # <-- add this
                        )
                        # Replace the original temp PDF with the compressed one
                        if compressed_pdf_path.exists() and compressed_pdf_path.stat().st_size > 0:
                            temp_pdf_path.unlink()
                            compressed_pdf_path.rename(temp_pdf_path)
                            logger.info(f"Compressed PDF: {temp_pdf_path}")
                    except Exception as e:
                        logger.warning(f"PDF compression failed: {e}")
            # Only signal completion if PDF was created successfully               
            if self.progress_callback and temp_pdf_path.exists() and temp_pdf_path.stat().st_size > 0:
                self.progress_callback(100, 100)
                
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            # Safe cleanup on error
            if torch.cuda.is_available():
                try:
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                except:
                    pass
        finally:
            # Clean up resources safely
            if temp_hocr and temp_hocr.exists():
                try:
                    os.chmod(str(temp_hocr), 0o666)
                    temp_hocr.unlink()
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp HOCR file {temp_hocr}: {e}")
        
            if intermediate_pdf and intermediate_pdf.exists():
                try:
                    os.chmod(str(intermediate_pdf), 0o666)
                    intermediate_pdf.unlink()
                except Exception as e:
                    logger.warning(f"Failed to cleanup intermediate PDF {intermediate_pdf}: {e}")
        
            # Clean up compressed image if it was created
            if getattr(self, "compress_images", False):
                try:
                    if processed_image_path != image_path and processed_image_path.exists():
                        processed_image_path.unlink()
                except Exception:
                    pass
            # Safe GPU cleanup
            if torch.cuda.is_available():
                try:
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                except Exception as e:
                    logger.warning(f"GPU cleanup warning: {e}")
            gc.collect()

    def _is_last_image_in_folder(self, image_path: Path) -> bool:
        """
        Check if this is the last image to be processed in the folder
        """
        folder_path = image_path.parent
        all_images = sorted(list(folder_path.glob("*.tif")))
        return image_path == all_images[-1]

    def _merge_folder_pdfs(self, folder_key: str, relative_path: Path) -> None:
        try:
            logger.info(f"Merging PDFs for folder: {relative_path}")
            max_wait = 30  # seconds
            start_time = time.time()
            temp_pattern = f"{folder_key}-*.pdf"

            # --- FIX: Only count images in the current subfolder, not all input_path ---
            folder_abs = self.input_path / relative_path if not relative_path.is_absolute() else relative_path
            expected_count = len(list(folder_abs.glob("*.tif")))
            if expected_count == 0:
                logger.warning(f"No images found in folder: {folder_abs}")
                return

            # --- FIX: Always create temp_dir if missing (can be deleted after previous merge) ---
            if not self.temp_dir.exists():
                self.temp_dir.mkdir(parents=True, exist_ok=True)

            while True:
                temp_pdfs = sorted(
                    list(self.temp_dir.glob(temp_pattern)),
                    key=lambda x: int(x.stem.split('-')[-1])
                )

                if len(temp_pdfs) >= expected_count:
                    break

                if time.time() - start_time > max_wait:
                    logger.warning(f"Timed out waiting for PDFs ({len(temp_pdfs)}/{expected_count})")
                    break
                time.sleep(1)
                logger.debug(f"Waiting for PDFs... {len(temp_pdfs)}/{expected_count}")

            # Verify all files exist and are valid
            temp_pdfs = [pdf for pdf in temp_pdfs if pdf.exists() and pdf.stat().st_size > 0]

            if len(temp_pdfs) != expected_count:
                logger.error(f"Missing PDFs: found {len(temp_pdfs)}/{expected_count}")

            # Create output directories preserving folder structure
            output_folder = self.pdf_dir / relative_path.parent
            output_folder.mkdir(parents=True, exist_ok=True)

            # --- FIX: Handle PDF naming properly ---
            # If relative_path is a directory, use its name
            # If it's a file pattern or empty, use the parent folder name
            if folder_abs.is_dir():
                pdf_name = folder_abs.name + ".pdf"
            else:
                # For cases where the path might represent a pattern or be empty
                # Use the parent folder name
                pdf_name = relative_path.name + ".pdf"
                
            # If the path is empty or just a dot, use the input_path's name
            if pdf_name == ".pdf" or not pdf_name or pdf_name == "*.pdf":
                pdf_name = self.input_path.name + ".pdf"
                
            logger.debug(f"Using PDF name: {pdf_name} for folder: {relative_path}")
            output_pdf = output_folder / pdf_name

            # Create HOCR directory with same structure if needed
            if "hocr" in self.output_formats:
                hocr_folder = self.hocr_dir / relative_path
                hocr_folder.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Output PDF path: {output_pdf}")

            # Merge PDFs
            merger = PdfMerger()
            merged_count = 0
            
            for pdf in temp_pdfs:
                try:
                    merger.append(str(pdf))
                    merged_count += 1
                except Exception as e:
                    logger.error(f"Error adding PDF {pdf}: {e}")
        
            if merged_count > 0:
                merger.write(str(output_pdf))
                merger.close()
                logger.info(f"Created PDF with {merged_count} pages: {output_pdf}")
                
                # Clean up temp PDFs and folder after successful merge
                if output_pdf.exists() and output_pdf.stat().st_size > 0:
                    for pdf in temp_pdfs:
                        try:
                            pdf.unlink()
                        except Exception as e:
                            logger.warning(f"Could not delete temp PDF {pdf}: {e}")
                else:
                    logger.error(f"Failed to create merged PDF at {output_pdf}")
            else:
                logger.error("No PDFs merged")

        except Exception as e:
            logger.error(f"Error merging PDFs: {e}")
            raise

    # Add this dummy method to avoid AttributeError when processing PDFs
    def _track_process(self):
        """Dummy process tracker for compatibility (does nothing)."""
        return None

    def _convert_pdf_to_images(self, pdf_path: Path, output_dir: Path, dpi=300) -> List[Path]:
        """Convert PDF to images using Ghostscript"""
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Find Ghostscript executable
            if sys.platform.startswith("win"):
                exe_name = "gswin64c.exe"
                gs_path = None
                # 1. Check PATH
                gs_path = shutil.which(exe_name)
                if not gs_path:
                    # 2. Search in Program Files
                    import re
                    from pathlib import Path
                    search_dirs = [
                        Path("C:/Program Files/gs"),
                        Path("C:/Program Files (x86)/gs"),
                    ]
                    found = []
                    for base in search_dirs:
                        if base.exists():
                            for sub in base.iterdir():
                                if sub.is_dir():
                                    exe = sub / "bin" / exe_name
                                    if exe.exists():
                                        m = re.search(r'(\d+(\.\d+)*)', sub.name)
                                        version = tuple(map(int, m.group(1).split('.'))) if m else (0,)
                                        found.append((version, exe))
                    if found:
                        found.sort(reverse=True)
                        gs_path = str(found[0][1])
            else:
                exe_name = "gs"
                gs_path = shutil.which(exe_name)
                
            if not gs_path:
                raise RuntimeError("Ghostscript not found")

            # Prepare Ghostscript command for PDF to image conversion
            output_pattern = str(output_dir / "page_%d.tif")
            gs_cmd = [
                f'"{gs_path}"',
                "-dQUIET",
                "-dNOPAUSE",
                "-dBATCH",
                "-dSAFER",
                "-sDEVICE=tiffg4",  # Use TIFF G4 compression for B&W
                f"-r{dpi}",  # Set resolution
                "-dTextAlphaBits=4",
                "-dGraphicsAlphaBits=4",
                "-dFirstPage=1",
                f'-sOutputFile="{output_pattern}"',
                f'"{pdf_path}"'
            ]

            # Execute Ghostscript
            run_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                shell=True
            )
            if sys.platform.startswith("win"):
                run_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            
            process = subprocess.run(' '.join(gs_cmd), **run_kwargs)
            
            if process.returncode != 0:
                raise RuntimeError(f"Ghostscript error: {process.stderr}")

            # Get generated images sorted by page number
            images = sorted(
                [p for p in output_dir.glob("page_*.tif")],
                key=lambda x: int(x.stem.split('_')[1])
            )
            
            if not images:
                raise RuntimeError("No images generated from PDF")
                
            return images

        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            raise

    def process_pdf(self, pdf_path: Union[str, Path]) -> None:
        """Process PDF by converting to images first using Ghostscript"""
        page_pdfs = []
        page_images_dir = None
        
        try:
            if self.is_cancelled or self._force_stop:
                return

            pdf_path = Path(pdf_path)
            self.current_file = str(pdf_path)
            logger.info(f"Processing PDF: {pdf_path}")
            
            # Initialize progress values
            processed_pages = 0
            total_pages = 0
            
            # Track file
            self._processed_files.add(str(pdf_path))
            logger.debug(f"Added to processed files: {pdf_path.name}")

            # Convert PDF to images
            logger.info("Converting PDF to images...")
            page_images_dir = self.temp_dir / "pdf_pages"
            page_images_dir.mkdir(exist_ok=True)
            
            # Convert PDF pages to images
            pages = self._convert_pdf_to_images(
                pdf_path,
                page_images_dir,
                dpi=300
            )
            
            if not pages:
                raise RuntimeError("No pages extracted from PDF")
                
            logger.info(f"Extracted {len(pages)} pages as images")
            total_pages = len(pages)

            # Signal progress for PDF start - treat as 1 file
            if self.progress_callback:
                self.progress_callback(1, 1, 0)  # One file, just started

            # Process each page without individual progress updates
            for idx, page_img in enumerate(pages, 1):
                if self.is_cancelled or self._force_stop:
                    return
                    
                logger.info(f"Processing page {idx}/{total_pages}")
                
                # Create page PDF with consistent naming
                temp_pdf_path = self.temp_dir / f"page_{idx:04d}.pdf"
                
                try:
                    # Process single page
                    self._process_single_image(Path(page_img), temp_pdf_path)
                    if temp_pdf_path.exists() and temp_pdf_path.stat().st_size > 0:
                        page_pdfs.append(temp_pdf_path)
                        
                except Exception as e:
                    logger.error(f"Error processing page {idx}: {e}")
                    continue

            # Merge pages
            if page_pdfs:
                output_folder = self.pdf_dir
                output_folder.mkdir(parents=True, exist_ok=True)
                
                output_pdf = output_folder / f"{pdf_path.stem}_ocr.pdf"
                
                # Merge using same method as folder processing
                merger = PdfMerger()
                merged_count = 0
                
                for pdf in page_pdfs:
                    try:
                        merger.append(str(pdf))
                        merged_count += 1
                    except Exception as e:
                        logger.error(f"Error adding PDF {pdf}: {e}")
                
                if merged_count > 0:
                    merger.write(str(output_pdf))
                    merger.close()
                    logger.info(f"Created merged PDF with {merged_count} pages: {output_pdf}")
                else:
                    raise RuntimeError("No pages were successfully processed and merged")
                
            # Signal completion - PDF counts as one completed file
            if self.progress_callback:
                self.progress_callback(1, 1, 100)  # One file, completed
                
        except Exception as e:
            self._processed_files.discard(str(pdf_path))
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            raise
            
        finally:
            # Clean up temp files safely
            try:
                if page_images_dir and page_images_dir.exists():
                    shutil.rmtree(str(page_images_dir))
                for pdf in page_pdfs:
                    try:
                        if pdf.exists():
                            pdf.unlink()
                    except Exception as e:
                        logger.warning(f"Could not delete temp PDF {pdf}: {e}")
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

    def __del__(self):
        """Ensure cleanup on deletion"""
        try:
            # Cleanup thread pool
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=False)
            
            # Force cleanup temp files and directory
            self.cleanup_temp_files(force=True)
            
            # Clear GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
        except Exception as e:
            print(f"Error during OCRProcessor cleanup: {e}")

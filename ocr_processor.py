import os
import logging
import signal
from pathlib import Path
from typing import Union, List, Dict
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
from ocrmypdf.hocrtransform import HocrTransform
from PIL import Image
import warnings
from datetime import datetime, UTC
from PyPDF2 import PdfMerger
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count, get_context
import psutil
import torch
import cv2
import gc
import numpy as np
import time
import sys
import threading
from utils.thread_killer import ThreadKiller
from utils.image_processor import ImageProcessor

# Disable PIL decompression bomb warning
Image.MAX_IMAGE_PIXELS = None  # Add this line to remove the warning
warnings.filterwarnings('ignore', category=Image.DecompressionBombWarning)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    def __init__(self, output_base_dir: str = "./output", output_formats: List[str] = ["pdf"]):
        """
        Initialize OCR processor with output directories and formats
        Args:
            output_base_dir: Base directory for outputs
            output_formats: List of formats to output ("pdf", "hocr", or ["pdf", "hocr"] for both)
        """
        # Make output base dir absolute
        self.output_base_dir = Path(output_base_dir).resolve()
        self.hocr_dir = self.output_base_dir / "hocr"
        self.pdf_dir = self.output_base_dir / "pdf"
        self.temp_dir = self.output_base_dir / "temp"
        
        # Create output directories
        for dir_path in [self.hocr_dir, self.pdf_dir, self.temp_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {dir_path}")
        
        # Check GPU availability and support with more logging
        is_supported, reason, gpu_info = _check_gpu_support()
        self.device = 'cuda' if is_supported else 'cpu'
        
        # Log all GPU info
        for info in gpu_info:
            logger.info(info)
            
        if is_supported:
            logger.info(f"Using GPU for processing")
        else:
            logger.warning(f"No GPU available: {reason}")
            
        # Initialize OCR model
        try:
            logger.info("Initializing OCR model...")
            
            # Set device before model initialization
            if self.device == 'cuda':
                # Configure CUDA settings
                torch.backends.cudnn.enabled = True
                torch.backends.cudnn.benchmark = True
                torch.cuda.empty_cache()
            
            self.model = ocr_predictor(
                det_arch='db_resnet50',
                reco_arch='crnn_vgg16_bn',
                pretrained=True,
                assume_straight_pages=True
            ).to(self.device)  # Move entire model to device
            
            # Set model to evaluation mode
            self.model.eval()
            
            if self.device == 'cuda':
                # Enable CUDA optimizations
                torch.cuda.synchronize()
                logger.info(f"GPU Memory Usage: {torch.cuda.memory_allocated() / 1024**2:.2f}MB")
                logger.info(f"GPU Memory Cached: {torch.cuda.memory_reserved() / 1024**2:.2f}MB")
            
            logger.info(f"OCR model initialization successful (using {self.device.upper()})")
            
        except Exception as e:
            logger.error(f"Failed to load OCR model: {str(e)}")
            raise

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

    def _signal_handler(self, signum, frame):
        """Handle interrupt signal"""
        self._force_stop = True
        self.cancel_processing()
        self._exit_event.clear()

    def cleanup_temp_files(self, force=False):
        """Improved temp file cleanup"""
        try:
            if not self.temp_dir.exists():
                return
            # When forcing cleanup, remove everything
            if force:
                for temp_file in self.temp_dir.glob("*"):
                    try:
                        if temp_file.is_file():
                            os.chmod(str(temp_file), 0o666)
                            temp_file.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {temp_file}: {e}")
                return
            # For non-forced cleanup, preserve active PDFs
            current_time = time.time()
            for temp_file in self.temp_dir.glob("*"):
                try:
                    # Skip recent PDFs
                    if (temp_file.suffix.lower() == '.pdf' and 
                        current_time - temp_file.stat().st_mtime < 300):  # 5 min
                        continue
                        
                    if temp_file.is_file():
                        os.chmod(str(temp_file), 0o666)
                        temp_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file}: {e}")
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
            # Calculate relative path from absolute input path
            try:
                relative_path = image_path.parent.relative_to(self.input_path)
            except ValueError:
                # If path is not relative to input_path, use full path
                relative_path = image_path.parent
            
            # Create folder key from absolute path to avoid collisions
            folder_key = str(image_path.parent).replace(':', '').replace('\\', '-').replace('/', '-')
            
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
            self._process_single_image(image_path, temp_pdf_path)
            
            # Only merge when processing the last image
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
        if self.is_cancelled or self._force_stop:
            raise InterruptedError("Processing cancelled")

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
                
    def _process_single_image(self, image_path: Path, temp_pdf_path: Path) -> None:
        """Process single image with improved state checking"""
        if self.is_cancelled or self._force_stop:
            return None
        temp_hocr = None
        intermediate_pdf = None
            
        try:
            # Check cancellation state
            if self.is_cancelled or self._force_stop:
                return None
            # Progress updates
            if self.progress_callback:
                if not self.progress_callback(0, 100):  # Start
                    return None
            # Move input to correct device
            docs = DocumentFile.from_images(str(image_path))
            if self.device == 'cuda':
                torch.cuda.synchronize()  # Ensure GPU operations are completed
            
            if self.progress_callback:
                if not self.progress_callback(25, 100):  # Document loaded
                    return None
            
            with torch.no_grad():  # Disable gradient computation for inference
                result = self.model(docs)
                if self.device == 'cuda':
                    torch.cuda.synchronize()  # Ensure GPU operations are completed
            
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
                
                for attempt in range(max_retries):
                    try:
                        hocr = HocrTransform(
                            hocr_filename=str(temp_hocr),
                            dpi=300
                        )
                        # Save to intermediate file first
                        hocr.to_pdf(
                            out_filename=str(intermediate_pdf),
                            image_filename=str(image_path)
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
            # Only signal completion if PDF was created successfully               
            if self.progress_callback and temp_pdf_path.exists() and temp_pdf_path.stat().st_size > 0:
                self.progress_callback(100, 100)
                
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            raise
            
        finally:
            # Only cleanup temp files if they're not needed
            if temp_hocr and temp_hocr.exists():
                if "hocr" not in self.output_formats:
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
            
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

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
            # Wait longer for temp files
            max_wait = 30  # seconds
            start_time = time.time()
            temp_pattern = f"{folder_key}-*.pdf"
            expected_count = len(list(relative_path.glob("*.tif")))
            
            while True:
                temp_pdfs = sorted(
                    list(self.temp_dir.glob(temp_pattern)),
                    key=lambda x: int(x.stem.split('-')[-1])
                )
                
                if len(temp_pdfs) >= expected_count:
                    break
                    
                if time.time() - start_time > max_wait:
                    logger.error(f"Timeout waiting for PDFs. Found {len(temp_pdfs)}/{expected_count}")
                    break
                time.sleep(1)
                logger.debug(f"Waiting for PDFs... {len(temp_pdfs)}/{expected_count}")
            
            # Verify all files exist and are valid
            temp_pdfs = [pdf for pdf in temp_pdfs if pdf.exists() and pdf.stat().st_size > 0]
            
            if len(temp_pdfs) != expected_count:
                logger.error(f"Missing PDFs: found {len(temp_pdfs)}/{expected_count}")
                # Continue anyway with what we have
            
            # Create output directories
            output_pdf = self.pdf_dir / relative_path / f"{relative_path.name}.pdf"
            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            
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
                
                # Only cleanup temp PDFs after successful merge
                if output_pdf.exists() and output_pdf.stat().st_size > 0:
                    for pdf in temp_pdfs:
                        try:
                            pdf.unlink()
                        except Exception as e:
                            logger.warning(f"Failed to delete temp PDF {pdf}: {e}")
                else:
                    logger.error("Output PDF not created properly, keeping temp files")
            else:
                logger.error("No PDFs merged, keeping temp files")
                
        except Exception as e:
            logger.error(f"Error merging PDFs: {e}")
            raise

    def process_pdf(self, pdf_path: Union[str, Path]) -> None:
        pid = self._track_process()  # Track PID for this process
        try:
            if self.is_cancelled or self._force_stop:
                return
                
            pdf_path = Path(pdf_path)
            self.current_file = str(pdf_path)  # Set current file
            logger.info(f"Processing PDF: {pdf_path}")
            
            # Track file before processing
            self._processed_files.add(str(pdf_path))
            logger.debug(f"Added to processed files: {pdf_path.name}")
            
            # Load and process PDF
            doc = DocumentFile.from_pdf(str(pdf_path))
            total_pages = len(doc)
            logger.info(f"PDF contains {total_pages} pages")
            
            # Report initial progress
            if self.progress_callback:
                self.progress_callback(0, 100)
            
            result = self.model(doc)
            if self.progress_callback:
                self.progress_callback(30, 100)
            
            # Generate output filenames
            base_name = pdf_path.stem
            hocr_output = self.hocr_dir / f"{base_name}_hocr.xml"
            pdf_output = self.pdf_dir / f"{base_name}_ocr.pdf"
            
            # Export HOCR XML with page tracking
            xml_outputs = result.export_as_xml()
            if self.progress_callback:
                self.progress_callback(60, 100)
            
            def process_page(page_num, page_xml):
                try:
                    if self.is_cancelled:
                        return False
                    
                    mode = "w" if page_num == 1 else "a"
                    with open(hocr_output, mode, encoding="utf-8") as f:
                        f.write(page_xml.decode())
                    logger.info(f"Processed page {page_num}/{total_pages}")
                    # Update progress for individual pages
                    if self.progress_callback:
                        progress = 60 + int((page_num / total_pages) * 40)  # Scale from 60-100
                        self.progress_callback(progress, 100)
                    return True
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {e}")
                    return False
        
            # Process pages in thread pool
            futures = []
            for page_num, page_xml in enumerate(xml_outputs[0], 1):
                future = self.thread_pool.submit(process_page, page_num, page_xml)
                futures.append(future)
            
            # Wait for completion
            completed_pages = sum(1 for future in as_completed(futures) if future.result())
            logger.info(f"Successfully processed {completed_pages}/{total_pages} pages")
            
            if self.progress_callback:
                self.progress_callback(100, 100)
            
        except Exception as e:
            # Remove from processed if failed
            self._processed_files.discard(str(pdf_path))
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            raise

    def __del__(self):
        """Cleanup thread pool and temporary files on deletion"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=True)
            logger.debug("Thread pool shutdown completed")
        self.cleanup_temp_files()

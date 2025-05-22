from PyQt6.QtCore import QRunnable, QObject, pyqtSignal
import logging
from pathlib import Path
import threading
import signal
import time
from PyQt6.QtWidgets import QApplication
from utils.process_manager import ProcessManager
from utils.safe_logger import SafeLogHandler
import multiprocessing as mp
import numpy as np
from multiprocessing.shared_memory import SharedMemory
from utils.image_processor import ImageProcessor  # Add this import

class WorkerSignals(QObject):
    # Update progress signal to include file progress
    progress = pyqtSignal(int, int, int)  # current_file, total_files, file_progress
    error = pyqtSignal(str)
    finished = pyqtSignal(bool)
    cancelled = pyqtSignal()
    new_log = pyqtSignal(str)  # Re-add log signal for logging handler

class LogHandler(SafeLogHandler):
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self._recursion_prevention = False
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        if self._recursion_prevention:
            return
            
        try:
            self._recursion_prevention = True
            msg = self.format(record)
            # Just log to console instead of emitting signal
            print(msg)
        finally:
            self._recursion_prevention = False

class OCRWorker(QRunnable):
    def __init__(self, ocr_processor, mode, path):
        super().__init__()
        self.ocr = ocr_processor
        self.mode = mode
        self.path = Path(path)
        self.signals = WorkerSignals()
        self.is_running = False
        self._cancel_event = threading.Event()
        self._force_stop = False
        self._batch_cancelled = False
        self._thread = None
        self._processing_complete = False
        self._batch_processing = False
        self._current_batch = None
        self._current_file_count = 0
        self._total_files = 0
        self._batch_start_time = None
        self._last_temp_cleanup = 0  # Add timestamp for last cleanup
        self._cleanup_interval = 300  # Cleanup every 5 minutes
        self._should_cleanup = False  # Add cleanup flag
        self._final_cleanup_done = False
        self._processed_files = set()  # Add to track unique processed files
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Setup custom logging that doesn't depend on signals
        self.log_handler = LogHandler(self.signals)
        self.logger = logging.getLogger('ocr_processor')

        # --- FIX: Remove previous LogHandler instances before adding new one ---
        for handler in list(self.logger.handlers):
            if isinstance(handler, LogHandler):
                self.logger.removeHandler(handler)
        self.logger.addHandler(self.log_handler)
        
        self.process_manager = ProcessManager()
        
        # Add progress timing
        self.last_progress_emit = time.time()
        self.progress_delay = 1.0  # 1 second delay
        
        def progress_callback(current_file, total_files, file_progress=None):
            """Progress callback that handles both file and page progress"""
            if self._force_stop or self.ocr.is_cancelled:
                return False
                
            current_time = time.time()
            
            # Always update on file completion or enough time has passed
            if total_files == 100 or (current_time - self.last_progress_emit >= self.progress_delay):
                # Get actual processed files from OCR
                if hasattr(self.ocr, '_processed_files'):
                    processed = len(self.ocr._processed_files)
                    if processed > len(self._processed_files):
                        # Track new processed file
                        self._processed_files = set(self.ocr._processed_files)
                        
                        # Force progress update
                        self.signals.progress.emit(
                            processed,  # Current count
                            self._total_files,  # Total files
                            file_progress or int((processed / self._total_files) * 100)  # Overall progress
                        )
                        self.last_progress_emit = current_time
                        self.logger.debug(f"Progress update: {processed}/{self._total_files}")
                
            QApplication.processEvents()
            return not (self._force_stop or self.ocr.is_cancelled)

        # Store progress callback as instance attribute
        self.progress_callback = progress_callback
        self.ocr.progress_callback = self.progress_callback
        
        # Reset state flags
        self._force_stop = False
        self._batch_cancelled = False
        self._processing_complete = False
        self._current_file_count = 0
        self._total_files = 0
        
        # Reset OCR processor state
        self.ocr.reset_state()  # Add this method to OCRProcessor

        # Add multiprocessing queues
        self.image_queue = mp.Queue()
        self.result_queue = mp.Queue()
        
        # Create new image processor instance
        if hasattr(self, 'image_processor'):
            self.image_processor.stop()
            self.image_processor = None
        
        self.image_processor = ImageProcessor(self.image_queue, self.result_queue)
        self.image_processor.start()

    def _signal_handler(self, signum, frame):
        self._force_stop = True
        self.stop(force=True)

    def _count_processed_files(self):
        """Count actually processed files in temp directory"""
        try:
            if not self.ocr.temp_dir.exists():
                return 0
            temp_files = [f for f in self.ocr.temp_dir.glob("*.pdf") 
                         if f.stat().st_size > 0 and f.is_file()]
            return len(temp_files)
        except Exception as e:
            self.logger.error(f"Error counting processed files: {e}")
            return self._current_file_count  # Return last known count on error

    def run(self):
        """Improved run method with better error handling and progress tracking"""
        self.is_running = True
        self._processing_complete = False
        self._batch_start_time = time.time()
        
        try:
            # Get total files first
            if self.mode == 'folder':
                files = []
                for ext in ['.tif', '.tiff', '.jpg', '.jpeg', '.png']:
                    files.extend(list(Path(self.path).rglob(f"*{ext}")))
                self._total_files = len(files)
            else:
                self._total_files = 1
                
            # Show initial state with correct total
            self.signals.progress.emit(0, self._total_files, 0)
            
            # Process based on mode
            if self.mode == 'folder':
                result = self.ocr.process_folder(self.path)
                if result.get('status') == 'cancelled':
                    raise InterruptedError("Processing cancelled")
                
                # Update progress with actual processed count
                processed = result.get('processed', 0)
                self.signals.progress.emit(processed, self._total_files, 100)
            else:
                # Single file processing
                if self.mode == 'single':
                    result = self.ocr.process_image(self.path)
                else:
                    result = self.ocr.process_pdf(self.path)
                
                # Update final progress
                self.signals.progress.emit(1, 1, 100)
            
            # Set completion and emit finished
            self._processing_complete = True
            self.signals.finished.emit(True)
            
        except Exception as e:
            self.logger.error(f"Processing error: {e}", exc_info=True)  # Fixed: using self.logger
            self.signals.error.emit(str(e))
            self.signals.finished.emit(False)
            
        finally:
            self.is_running = False
            if hasattr(self, 'ocr'):
                self.ocr.cleanup_temp_files(force=True)
            QApplication.processEvents()

    def process_image_multiprocess(self, image_path):
        """Process image in separate process"""
        try:
            # Create shared memory for image data
            image_shape = (2000, 2000, 3)  # Example shape, adjust as needed
            nbytes = np.prod(image_shape) * np.dtype(np.uint8).itemsize
            shm = SharedMemory(create=True, size=nbytes)  # Fixed class name
            
            # Send task to image processor
            self.image_queue.put((
                str(image_path),
                shm.name,
                image_shape,
                np.uint8
            ))
            
            # Wait for result
            status, error = self.result_queue.get()
            if status == "error":
                raise RuntimeError(f"Image processing failed: {error}")
                
            # Get processed data from shared memory
            result = np.ndarray(image_shape, dtype=np.uint8, buffer=shm.buf)
            
            return result
            
        finally:
            try:
                shm.close()
                shm.unlink()
            except:
                pass

    def stop(self, force=False):
        """Improved stop method with process cleanup"""
        if not self.is_running:
            return
            
        try:
            # Set flags first to prevent new processing
            self._force_stop = True
            self.is_running = False
            
            # Cancel OCR processing first
            if self.ocr:
                self.ocr.cancel_processing()
                self.ocr.cleanup_temp_files(force=True)  # Force cleanup temp files
            
            # Stop image processor
            if hasattr(self, 'image_processor') and self.image_processor:
                self.image_queue.put(None)  # Send shutdown signal
                self.image_processor.stop()
                self.image_processor.join(timeout=1)
                if self.image_processor.is_alive():
                    self.image_processor.terminate()
                self.image_processor = None
                
            # Signal cancellation
            if force and self._batch_processing:
                self.signals.cancelled.emit()
                self.signals.finished.emit(False)
                
            # Clear queues last
            self._clear_queues()
            
        except Exception as e:
            self.logger.error(f"Error during worker stop: {e}")

    def _clear_queues(self):
        """Clear multiprocessing queues"""
        try:
            while not self.image_queue.empty():
                try:
                    self.image_queue.get_nowait()
                except:
                    break
            while not self.result_queue.empty():
                try:
                    self.result_queue.get_nowait()
                except:
                    break
        except:
            pass

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, QPushButton, 
                           QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
                           QTextEdit, QComboBox, QFileDialog, QMessageBox,
                           QLineEdit, QDialogButtonBox, QSpinBox, QCheckBox,
                           QFormLayout, QDialog, QProgressDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QThreadPool
import logging
import sys
import json
import traceback
import psutil
from pathlib import Path
from datetime import datetime
import gc
import torch
import time

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now import project modules
from ocr_processor import OCRProcessor
from .processing_thread import OCRWorker
from utils.process_manager import ProcessManager
from utils.safe_logger import SafeLogHandler

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):  # Remove splash parameter if it exists
        try:
            # Initialize NVML and GPUtil
            self.nvml_initialized = False
            try:
                import pynvml
                pynvml.nvmlInit()
                self.nvml_initialized = True
                logger.info("NVML initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize NVML: {e}")
                try:
                    import GPUtil
                    GPUtil.getGPUs()  # Test if GPUtil works
                    logger.info("GPUtil initialized as fallback")
                except Exception as e:
                    logger.error(f"Failed to initialize GPUtil: {e}")

            logger.debug("Starting MainWindow initialization")
            super().__init__()
            logger.debug("MainWindow parent initialized")
            
            # Ensure window is visible
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            self.setWindowState(Qt.WindowState.WindowActive)
            
            # Initialize core components immediately
            self.selected_paths = {
                'single': None,
                'folder': None,
                'pdf': None
            }
            self.log_file = None
            self.current_worker = None  # Initialize worker reference first
            self.process_manager = ProcessManager()
            self.thread_pool = QThreadPool()
            self.thread_pool.setMaxThreadCount(4)
            
            # Create output directories
            self.output_base_dir = Path(__file__).parent.parent / "output"
            self.pdf_dir = self.output_base_dir / "pdf"
            self.hocr_dir = self.output_base_dir / "hocr"
            self.temp_dir = self.output_base_dir / "temp"  # Add temp dir
            
            # Create directories
            for dir_path in [self.pdf_dir, self.hocr_dir, self.temp_dir]:
                dir_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize progress tracking
            self.processed_files = 0
            self.total_files = 0
            self.last_progress = 0
            self.progress_counter = 0
            self.actual_progress = 0
            self.sync_timer = QTimer()
            self.sync_timer.timeout.connect(self._sync_progress)
            self.sync_timer.setInterval(500)  # Check every 500ms
            
            # Add progress tracking variables
            self.last_valid_progress = 0
            self.max_processed = 0
            
            # Add progress state tracking
            self.progress_state = {
                'current_file': None,
                'displayed_file': None,
                'actual_count': 0,
                'last_sync': 0
            }
            
            # Add file tracking
            self.file_tracking = {
                'processed': set(),  # Track unique files processed
                'failed': set(),     # Track failed files
                'queued': set(),     # Track queued files
                'current': None      # Current file being processed
            }
            
            # Add direct file monitoring
            self.processed_files_set = set()  # Track actual processed files
            self.last_file_check = 0  # Last file check timestamp
            
            # Add direct OCR monitoring
            self.last_ocr_check = 0
            self.real_file_count = 0
            
            # Add progress monitoring
            self.progress_monitor = QTimer()
            self.progress_monitor.timeout.connect(self._check_real_progress)
            self.progress_monitor.setInterval(250)  # Check 4 times per second
            
            # Initialize GUI
            self.setWindowTitle("VisionLane OCR (Can't fix GUI so slow I wanna cry, disappear, and become a potato)")
            self.setMinimumSize(800, 400)
            self._create_ui()
            
            # Initialize OCR model
            QTimer.singleShot(0, lambda: self._delayed_init())
            
            # Add last update time tracking
            self.last_progress_update = time.time()
            self.progress_update_delay = 1.0  # 1 second delay
            
        except Exception as e:
            logger.error(f"Failed to initialize main window: {e}", exc_info=True)
            raise

    def _create_ui(self):
        """Create UI components"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        self._create_menu_bar()
        self._create_input_section(layout)
        self._create_options_section(layout)
        self._create_status_section(layout)
        self._create_action_buttons(layout)

    def _delayed_init(self):
        """Initialize heavy components after window is shown"""
        try:
            # Initialize OCR processor
            self.ocr = OCRProcessor(output_base_dir=str(self.output_base_dir))
            self._setup_logging()
            self._setup_file_logging()
            
            # Setup timers
            self.hw_timer = QTimer(self)
            self.hw_timer.timeout.connect(self._update_hardware_info)
            self.hw_timer.start(1000)
            
            self.progress_timer = QTimer(self)
            self.progress_timer.timeout.connect(self._force_progress_update)
            self.progress_timer.setInterval(100)
            
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self._update_gui)
            self.update_timer.setInterval(100)
            
            self._update_hardware_info()
            
        except Exception as e:
            logger.error(f"Delayed initialization failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to initialize: {e}")

    def show(self):
        """Override show to ensure window appears"""
        super().show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()  # Force window activation

    def closeEvent(self, event):
        """Handle window close"""
        try:
            # Cancel any ongoing processing first
            if self.current_worker and self.current_worker.is_running:
                self._cancel_processing()
            
            # Stop all timers first
            self._stop_all_timers()
            
            # Clean up OCR and resources
            self._cleanup_resources()
            
            # Accept the close event
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during close: {e}")
            event.accept()

    def _stop_all_timers(self):
        """Stop all timers safely"""
        timer_names = ['hw_timer', 'update_timer', 'progress_timer', 
                       'sync_timer', 'progress_monitor']
        for timer_name in timer_names:
            if hasattr(self, timer_name):
                timer = getattr(self, timer_name)
                if timer and timer.isActive():
                    timer.stop()
                    timer.deleteLater()
                    setattr(self, timer_name, None)

    def _cleanup_resources(self):
        """Clean up resources safely"""
        try:
            # Clean up OCR processor first if it exists
            if hasattr(self, 'ocr') and self.ocr:
                try:
                    self.ocr.cleanup_temp_files(force=True)
                except Exception as e:
                    logger.error(f"Error cleaning OCR temp files: {e}")
                self.ocr = None
                
            # Clean up thread pool
            if hasattr(self, 'thread_pool'):
                try:
                    self.thread_pool.clear()
                    self.thread_pool.waitForDone(1000)
                except Exception as e:
                    logger.error(f"Error cleaning thread pool: {e}")
                
            # Clean up logging
            if hasattr(self, 'log_handler'):
                try:
                    logger.removeHandler(self.log_handler)
                except Exception as e:
                    logger.error(f"Error removing log handler: {e}")
                
            # Force garbage collection
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
        except Exception as e:
            logger.error(f"Error during resource cleanup: {e}")

    def cleanup_and_exit(self):
        """Ensure thorough cleanup before exit"""
        try:
            # Cancel processing and stop timers
            self._stop_all_timers()
            
            # Clean up resources
            self._cleanup_resources()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            # Schedule deletion for next event loop iteration
            self.deleteLater()

    def _setup_logging(self):
        """Setup file-only logging"""
        logger = logging.getLogger()
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            
        # Only setup file handler, no GUI logging
        self._setup_file_logging()

    def _setup_file_logging(self):
        try:
            # Create logs directory
            log_dir = Path(__file__).parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            
            # Create log file with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = log_dir / f"ocr_gui_{timestamp}.log"
            
            # Setup file handler with UTF-8 encoding
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            # Get logger
            logger = logging.getLogger()
            
            # Remove existing handlers
            for handler in logger.handlers[:]:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
                    logger.removeHandler(handler)
            
            # Add new handler
            logger.addHandler(file_handler)
            logger.setLevel(logging.DEBUG)
            
            logger.info("=== New OCR Processing Session Started ===")
            logger.info(f"Log file: {self.log_file}")
            
        except Exception as e:
            logger.error(f"Failed to setup logging: {e}", exc_info=True)
            print(f"Failed to setup logging: {e}")

    def _create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        open_action = file_menu.addAction("Open")
        save_action = file_menu.addAction("Save Settings")
        file_menu.addSeparator()
        open_action.triggered.connect(self._on_open_file)
        save_action.triggered.connect(self._save_settings)
        file_menu.addAction("Exit")

        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        path_config_action = settings_menu.addAction("Configure Paths")
        performance_options = settings_menu.addAction("Performance Options")
        path_config_action.triggered.connect(self._show_path_config)
        performance_options.triggered.connect(self._show_performance_options)

        # Help menu
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About").triggered.connect(self._show_about)

    def _create_input_section(self, parent_layout):
        self.tab_widget = QTabWidget()
        self.tab_widget.setMaximumHeight(200)  # Limit tab height
        
        # Styles for labels and buttons
        label_style = "QLabel { font-size: 10pt; padding: 5px; }"
        btn_style = """
            QPushButton { 
                font-size: 10pt; 
                padding: 5px 10px;
                min-height: 25px;
                max-height: 30px;
            }
        """
        
        # Common function to create a tab
        def create_tab(title, select_btn_text):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setSpacing(5)  # Reduce spacing between elements
            layout.setContentsMargins(10, 10, 10, 10)  # Reduce margins
            
            # Input selection
            select_btn = QPushButton(select_btn_text)
            select_btn.setStyleSheet(btn_style)
            label = QLabel("No file selected")
            label.setStyleSheet(label_style)
            
            # Output selection
            out_layout = QHBoxLayout()
            out_layout.setSpacing(5)
            output_path = QLineEdit()
            output_path.setPlaceholderText("Output directory")
            output_path.setMinimumHeight(25)
            browse_btn = QPushButton("Browse Output")
            browse_btn.setStyleSheet(btn_style)
            
            out_layout.addWidget(output_path, stretch=4)
            out_layout.addWidget(browse_btn, stretch=1)
            
            layout.addWidget(select_btn)
            layout.addWidget(label)
            layout.addLayout(out_layout)
            layout.addStretch()  # Add stretch to keep elements at top
            
            return widget, select_btn, label, output_path, browse_btn
        
        # Single File tab
        single_widget, select_file_btn, self.single_file_label, self.single_output_path, single_browse_btn = create_tab(
            "Single File", "Select Input File"
        )
        select_file_btn.clicked.connect(self._select_single_file)
        single_browse_btn.clicked.connect(lambda: self._browse_output(self.single_output_path))
        self.tab_widget.addTab(single_widget, "Single File")
        
        # Folder tab
        folder_widget, select_folder_btn, self.folder_label, self.folder_output_path, folder_browse_btn = create_tab(
            "Folder", "Select Input Folder"
        )
        select_folder_btn.clicked.connect(self._select_folder)
        folder_browse_btn.clicked.connect(lambda: self._browse_output(self.folder_output_path))
        self.tab_widget.addTab(folder_widget, "Folder")
        
        # PDF tab
        pdf_widget, select_pdf_btn, self.pdf_label, self.pdf_output_path, pdf_browse_btn = create_tab(
            "PDF", "Select Input PDF"
        )
        select_pdf_btn.clicked.connect(self._select_pdf)
        pdf_browse_btn.clicked.connect(lambda: self._browse_output(self.pdf_output_path))
        self.tab_widget.addTab(pdf_widget, "PDF")
        
        # Add tab widget to parent layout with reduced height
        parent_layout.addWidget(self.tab_widget)

    def _browse_output(self, line_edit):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            line_edit.text()
        )
        if dir_path:
            line_edit.setText(dir_path)

    def _select_single_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image File",
            "",
            "Image Files (*.tif *.tiff *.jpg *.jpeg *.png)"
        )
        if file_path:
            self.selected_paths['single'] = Path(file_path)
            self.single_file_label.setText(f"Selected: {Path(file_path).name}")

    def _select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder Containing Images/PDFs"
        )
        if folder_path:
            self.selected_paths['folder'] = Path(folder_path)
            self.folder_label.setText(f"Selected: {Path(folder_path).name}")
            
            # Count files
            supported_files = self._count_supported_files(folder_path)
            if supported_files:
                self.folder_label.setText(
                    f"Selected: {Path(folder_path).name}\n"
                    f"Found: {supported_files['images']} images, {supported_files['pdfs']} PDFs"
                )

    def _select_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF File",
            "",
            "PDF Files (*.pdf)"
        )
        if file_path:
            self.selected_paths['pdf'] = Path(file_path)
            self.pdf_label.setText(f"Selected: {Path(file_path).name}")

    def _count_supported_files(self, folder_path: str) -> dict:
        folder = Path(folder_path)
        image_extensions = ['.tif', '.tiff', '.jpg', '.jpeg', '.png']
        images = 0
        pdfs = 0
        
        # Recursively scan for files
        for path in folder.rglob('*'):
            if path.is_file():
                if path.suffix.lower() in image_extensions:
                    images += 1
                elif path.suffix.lower() == '.pdf':
                    pdfs += 1
                    
        return {"images": images, "pdfs": pdfs}

    def _create_options_section(self, parent_layout):
        options_layout = QHBoxLayout()
        
        # DPI Selection
        self.dpi_combo = QComboBox()
        self.dpi_combo.addItems(["300", "600", "900"])
        options_layout.addWidget(QLabel("DPI:"))
        options_layout.addWidget(self.dpi_combo)

        # Output Format - Updated to include HOCR
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PDF", "HOCR", "PDF+HOCR"])
        options_layout.addWidget(QLabel("Output Format:"))
        options_layout.addWidget(self.format_combo)

        parent_layout.addLayout(options_layout)

    def _create_status_section(self, parent_layout):
        """Create minimal status section with file status and overall progress"""
        status_layout = QVBoxLayout()
        
        # Current file label
        self.current_file_label = QLabel("No file processing")
        status_layout.addWidget(self.current_file_label)
        
        # Overall progress
        self.overall_progress_label = QLabel("Total Progress: 0/0")
        self.overall_progress = QProgressBar()
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.overall_progress_label)
        progress_layout.addWidget(self.overall_progress)
        status_layout.addLayout(progress_layout)
        
        # Hardware info layout
        hw_layout = QHBoxLayout()
        self.device_label = QLabel()
        self.cpu_label = QLabel()
        self.memory_label = QLabel()
        
        for label in [self.device_label, self.cpu_label, self.memory_label]:
            hw_layout.addWidget(label)
            label.setStyleSheet("padding: 5px; margin: 2px;")
        
        status_layout.addLayout(hw_layout)
        parent_layout.addLayout(status_layout)

    def _create_action_buttons(self, parent_layout):
        button_layout = QHBoxLayout()
        
        # Add buttons
        self.start_button = QPushButton("Start Processing")
        self.start_button.clicked.connect(self._start_processing)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_processing)
        self.cancel_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)
        
        parent_layout.addLayout(button_layout)

    def _cancel_processing(self):
        """Fixed cancel processing dialog sequence"""
        if not self.current_worker:
            return
            
        try:
            self.start_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            
            # Use a single persistent dialog
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
            dialog.setWindowTitle("Stopping Process")
            dialog.setText("Terminating process and cleaning up, please wait...")
            dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            dialog.show()
            QApplication.processEvents()
            
            # Do cleanup
            self._cleanup_processing(dialog)
            
            # Update dialog text and show completion
            dialog.setText("Processing terminated successfully")
            dialog.setIcon(QMessageBox.Icon.Information)
            dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            dialog.exec()  # Wait for user to click OK
            
            # Final cleanup after user clicks OK
            dialog.deleteLater()
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error in cancel_processing: {e}")
            self._reset_processing_state()

    def _cleanup_processing(self, dialog):
        """Handle cleanup with better temp file handling"""
        try:
            if self.current_worker:
                self.current_worker.stop(force=True)
                self.current_worker = None
            
            # Cancel OCR and clean temp files
            if hasattr(self, 'ocr'):
                self.ocr.cancel_processing()
                try:
                    # Clean temp directory
                    for temp_file in self.temp_dir.glob('*'):
                        try:
                            temp_file.unlink()
                        except:
                            pass
                except Exception as e:
                    logger.error(f"Error cleaning temp files: {e}")
            
            # Clear thread pool
            if hasattr(self, 'thread_pool'):
                self.thread_pool.clear()
            
            # Reset state but preserve progress
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            
            # Force cleanup
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            logger.info("Processing cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            QApplication.processEvents()

    def _reset_processing_state(self):
        """Reset UI state while preserving progress"""
        try:
            # Stop timers safely
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            if hasattr(self, 'progress_timer'):
                self.progress_timer.stop()
            if hasattr(self, 'progress_monitor'):
                self.progress_monitor.stop()
            
            # Keep last progress values
            current_progress = f"Files Processed: {self.processed_files}/{self.total_files}"
            self.overall_progress_label.setText(current_progress)
            self.overall_progress.setValue(self.last_progress)
            
            # Reset buttons
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error in reset_processing_state: {e}")

    def _check_output_conflicts(self, input_path: Path) -> bool:
        """Check if output files would be overwritten"""
        try:
            conflicts = []
            
            if self.tab_widget.currentIndex() == 0:  # Single file
                rel_path = input_path.name
                output_pdf = self.pdf_dir / f"{input_path.stem}.pdf"
                output_hocr = self.hocr_dir / f"{input_path.stem}.xml"
            elif self.tab_widget.currentIndex() == 1:  # Folder
                # For folder, check if output folder exists and has files
                if self.pdf_dir.exists():
                    if any(self.pdf_dir.iterdir()):
                        conflicts.append(str(self.pdf_dir))
                if self.hocr_dir.exists():
                    if any(self.hocr_dir.iterdir()):
                        conflicts.append(str(self.hocr_dir))
                return self._confirm_overwrite(conflicts) if conflicts else True
            else:  # PDF
                output_pdf = self.pdf_dir / f"{input_path.stem}_ocr.pdf"
                output_hocr = self.hocr_dir / f"{input_path.stem}_hocr.xml"

            if output_pdf.exists():
                conflicts.append(str(output_pdf))
            if output_hocr.exists():
                conflicts.append(str(output_hocr))

            return self._confirm_overwrite(conflicts) if conflicts else True

        except Exception as e:
            logger.error(f"Error checking conflicts: {e}")
            return False

    def _confirm_overwrite(self, conflicts: list) -> bool:
        """Ask user confirmation for overwriting files"""
        if not conflicts:
            return True
            
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Output Conflict")
        msg.setText("Output files/folders already exist!")
        msg.setInformativeText(
            "The following will be overwritten:\n" + 
            "\n".join(conflicts) + 
            "\n\nDo you want to continue?"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No
        )
        return msg.exec() == QMessageBox.StandardButton.Yes

    def _update_gui(self):
        """Update GUI elements without blocking"""
        QApplication.processEvents()

    def _sync_progress(self):
        """Enhanced progress sync with real-time file counting"""
        try:
            if not self.current_worker or not self.current_worker.is_running:
                return

            # Direct OCR file monitoring
            if hasattr(self.ocr, 'processed_count'):
                real_count = self.ocr.processed_count
            else:
                # Count files directly from OCR instance
                real_count = len(getattr(self.ocr, '_processed_files', []))

            # Force update if real count is higher
            if real_count > self.processed_files:
                self.processed_files = real_count
                self.max_processed = real_count
                self.real_file_count = real_count
                
                # Force progress update
                progress = int((real_count / self.total_files) * 100)
                self.overall_progress.setValue(progress)
                self.overall_progress_label.setText(
                    f"Files Processed: {real_count}/{self.total_files}"
                )
                
                logger.debug(f"Direct OCR count update: {real_count}/{self.total_files}")

            # Update current file display
            if hasattr(self.ocr, 'current_file'):
                current = self.ocr.current_file
                if current and current != self.file_tracking['current']:
                    self.file_tracking['current'] = current
                    self.current_file_label.setText(f"Processing: {Path(current).name}")
            
            # Force GUI refresh
            self.overall_progress.repaint()
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error in sync_progress: {e}")

    def _check_real_progress(self):
        """Direct monitoring of OCR progress"""
        try:
            if not hasattr(self.ocr, '_processed_files'):
                return

            # Get actual count directly from OCR
            actual_count = len(self.ocr._processed_files)
            current_file = getattr(self.ocr, 'current_file', None)
            
            # Update if changed
            if actual_count != self.processed_files:
                self.processed_files = actual_count
                self.max_processed = max(self.max_processed, actual_count)
                
                # Force progress update
                progress = int((actual_count / self.total_files) * 100) if self.total_files > 0 else 0
                self.overall_progress.setValue(progress)
                self.overall_progress_label.setText(f"Files Processed: {actual_count}/{self.total_files}")
                
                # Log progress
                logger.debug(f"Real progress: {actual_count}/{self.total_files}")
            
            # Update current file
            if current_file:
                self.current_file_label.setText(f"Processing: {Path(current_file).name}")
            
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error checking progress: {e}")

    def _start_processing(self):
        # Add check for processing state
        if self.current_worker and self.current_worker.is_running:
            QMessageBox.warning(self, "Warning", "Processing already in progress")
            return
            
        # Forcefully reset state before starting
        self._reset_processing_state()
        self.ocr.is_cancelled = False
        self.ocr._force_stop = False
        self.ocr._exit_event.clear()
        self.ocr._should_exit.clear()
        
        try:
            # Reset all progress tracking
            self.processed_files = 0
            self.max_processed = 0
            self.last_valid_progress = 0
            self.processed_files_set.clear()
            self.file_tracking['processed'].clear()
            self.file_tracking['current'] = None
            
            # Get mode and path first
            current_tab = self.tab_widget.currentIndex()
            mode, path = self._get_processing_params(current_tab)
            
            # Pre-scan files for folder mode
            if mode == 'folder':
                # Get all files first
                image_files = []
                for ext in ['.tif', '.tiff', '.jpg', '.jpeg', '.png']:
                    image_files.extend(list(Path(path).rglob(f'*{ext}')))
                self.file_tracking['queued'] = set(str(p) for p in image_files)
                self.total_files = len(self.file_tracking['queued'])
                logger.info(f"Found {self.total_files} files to process")
            else:
                self.total_files = 1
                self.file_tracking['queued'].add(str(path))
            
            # Reset other counters
            self.processed_files = 0
            self.last_progress = 0
            self.max_processed = 0
            
            # Check for output conflicts first
            if not self._check_output_conflicts(path):
                logger.info("Processing cancelled due to output conflicts")
                return

            # Create and setup worker
            self.current_worker = OCRWorker(self.ocr, mode, path)
            self.current_worker.signals.progress.connect(self._on_progress)
            self.current_worker.signals.error.connect(self._handle_error)
            self.current_worker.signals.cancelled.connect(self._on_cancelled)
            self.current_worker.signals.finished.connect(self._process_finished)
            logger.debug(f"Created OCR worker for mode: {mode}, path: {path}")
            
            try:
                # Connect worker signals with error checking
                signals = [
                    (self.current_worker.signals.progress, self._update_overall_progress),
                    (self.current_worker.signals.error, self._handle_error),
                    (self.current_worker.signals.finished, self._process_finished),
                    (self.current_worker.signals.cancelled, self._on_cancelled)
                ]
                
                for signal, handler in signals:
                    try:
                        signal.connect(handler)
                    except Exception as e:
                        logger.error(f"Failed to connect signal to {handler.__name__}: {e}")
                        raise
                        
                logger.debug("Successfully connected worker signals")
                
            except Exception as e:
                logger.error(f"Failed to connect worker signals: {e}")
                logger.error(traceback.format_exc())
                raise
            
            # Update UI state
            self.start_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.overall_progress.setValue(0)
            
            # Start progress monitoring
            self.progress_monitor.start()
            
            # Start processing
            logger.info("Starting OCR processing")
            self.thread_pool.start(self.current_worker)
            
        except Exception as e:
            logger.error(f"Error starting processing: {e}", exc_info=True)
            self._handle_error(str(e))

    def _on_progress(self, current_file, total_files, file_progress):
        """Direct progress handler with improved sync"""
        try:
            # Always update if we have a valid count
            if current_file is not None:
                # Get real count from OCR for verification
                if hasattr(self.ocr, '_processed_files'):
                    real_count = len(self.ocr._processed_files)
                    current_file = max(current_file, real_count)
                
                # Update progress
                self.processed_files = current_file
                self.max_processed = max(self.max_processed, current_file)
                
                # Force progress update
                progress = int((current_file / total_files) * 100)
                self.overall_progress.setValue(progress)
                self.overall_progress_label.setText(
                    f"Files Processed: {current_file}/{total_files}"
                )
                
                # Update file display if changed
                if hasattr(self.ocr, 'current_file'):
                    current = self.ocr.current_file
                    if current and current != self.file_tracking['current']:
                        self.file_tracking['current'] = current
                        self.current_file_label.setText(f"Processing: {Path(current).name}")
                
                logger.debug(f"Progress update: {current_file}/{total_files}")
                
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error in progress handler: {e}", exc_info=True)

    def _get_processing_params(self, tab_index: int) -> tuple:
        """Get processing mode and path based on selected tab"""
        # Add output format handling
        output_formats = []
        selected_format = self.format_combo.currentText()
        if selected_format == "PDF":
            output_formats = ["pdf"]
        elif selected_format == "HOCR":
            output_formats = ["hocr"]
        else:  # PDF+HOCR
            output_formats = ["pdf", "hocr"]
            
        if tab_index == 0:  # Single File
            if not self.selected_paths['single']:
                raise ValueError("Please select an image file")
            if not self.single_output_path.text():
                raise ValueError("Please select output directory")
            self.ocr.output_base_dir = Path(self.single_output_path.text())
            self.ocr.output_formats = output_formats  # Set output formats
            return 'single', self.selected_paths['single']
            
        elif tab_index == 1:  # Folder
            if not self.selected_paths['folder']:
                raise ValueError("Please select a folder")
            if not self.folder_output_path.text():
                raise ValueError("Please select output directory")
            self.ocr.output_base_dir = Path(self.folder_output_path.text())
            self.ocr.output_formats = output_formats  # Set output formats
            path = self.selected_paths['folder']
            self.ocr.input_path = path
            return 'folder', path
            
        else:  # PDF
            if not self.selected_paths['pdf']:
                raise ValueError("Please select a PDF file")
            if not self.pdf_output_path.text():
                raise ValueError("Please select output directory")
            self.ocr.output_base_dir = Path(self.pdf_output_path.text())
            self.ocr.output_formats = output_formats  # Set output formats
            return 'pdf', self.selected_paths['pdf']

    def _get_total_files(self, path: Path, mode: str) -> int:
        """Get total number of files to process"""
        try:
            if mode == 'single':
                return 1
            elif mode == 'pdf':
                return 1
            elif mode == 'folder':
                counts = self._count_supported_files(str(path))
                return counts['images'] + counts['pdfs']
            return 0
        except Exception as e:
            logger.error(f"Error counting files: {e}")
            return 0

    def _on_cancelled(self):
        """Handle cancellation from worker"""
        logger.info("Processing cancelled")
        self._reset_processing_state()

    def _force_progress_update(self):
        """Force GUI update for overall progress"""
        self.overall_progress.repaint()
        self.overall_progress_label.repaint()
        QApplication.processEvents()

    def _update_current_file(self, filepath: str):
        """Update current file display"""
        filename = Path(filepath).name
        self.current_file_label.setText(f"Processing: {filename}")
        QApplication.processEvents()

    def _append_log(self, message):
        """No longer display logs in GUI"""
        pass  # Simply log to file, not to GUI

    def _update_overall_progress(self, current_file, total_files, file_progress):
        """Update progress with direct OCR sync"""
        try:
            # Get real progress from OCR
            real_count = len(getattr(self.ocr, '_processed_files', set()))
            self.processed_files = max(real_count, self.processed_files)
            
            # Calculate progress
            progress = int((self.processed_files / self.total_files) * 100)
            self.overall_progress.setValue(progress)
            self.overall_progress_label.setText(
                f"Files Processed: {self.processed_files}/{self.total_files}"
            )
            
            # Update file display
            if hasattr(self.ocr, 'current_file'):
                current = self.ocr.current_file
                if current:
                    self.current_file_label.setText(f"Processing: {Path(current).name}")
            
            logger.debug(f"Progress update from OCR: {self.processed_files}/{self.total_files}")
            
            # Force update
            self.overall_progress.repaint()
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error updating progress: {e}", exc_info=True)

    def _process_finished(self, success):
        """Handle process completion"""
        try:
            # Stop sync timer
            self.sync_timer.stop()
            
            # Stop progress monitoring
            self.progress_monitor.stop()
            
            # Force final progress update
            if success and self.total_files > 0:
                self.processed_files = self.total_files
                self.overall_progress.setValue(100)
                self.overall_progress_label.setText(
                    f"Files Processed: {self.total_files}/{self.total_files}"
                )
                QApplication.processEvents()
            
            # Stop timers first
            self.update_timer.stop()
            self.progress_timer.stop()
            
            # Show completion message before cleanup
            if success and not self.ocr.is_cancelled:
                QMessageBox.information(self, "Success", "Processing completed successfully!")
            
            # Reset state and cleanup
            self._reset_processing_state()
            
        except Exception as e:
            logger.error(f"Error during process completion: {e}")
            self._reset_processing_state()

    def _update_hardware_info(self):
        if hasattr(self, 'ocr') and self.ocr.device == "cuda":
            self.device_label.setText(f"Processing Device: GPU")
            
            try:
                if self.nvml_initialized:
                    import pynvml
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    util_rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    
                    gpu_util = util_rates.gpu if util_rates else 0
                    used_gb = mem_info.used / 1024**3
                    total_gb = mem_info.total / 1024**3
                    
                    self.cpu_label.setText(f"GPU Usage: {gpu_util}%")
                    self.memory_label.setText(f"GPU Memory Allocated: {used_gb:.1f}MB/{total_gb:.1f}MB")
                else:
                    # Try GPUtil as fallback
                    import GPUtil
                    gpu = GPUtil.getGPUs()[0]  # Get first GPU
                    
                    self.cpu_label.setText(f"GPU Usage: {gpu.load * 100:.1f}%")
                    self.memory_label.setText(f"GPU Memory Allocated: {gpu.memoryUsed:.1f}MB/{gpu.memoryTotal:.1f}MB")
                    
            except Exception as e:
                logger.error(f"Error getting GPU metrics: {e}")
                # Ultimate fallback to basic PyTorch info
                if torch.cuda.is_available():
                    used = torch.cuda.memory_allocated(0) / 1024**3
                    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    self.cpu_label.setText("GPU Usage: N/A")
                    self.memory_label.setText(f"GPU Memory Allocated: {used:.1f}MB/{total:.1f}MB")
        else:
            # CPU metrics (unchanged)
            self.device_label.setText("Processing Device: CPU")
            cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_label.setText(f"CPU Usage: {cpu_percent}%")
            memory = psutil.virtual_memory()
            self.memory_label.setText(f"Memory Usage: {memory.percent}%")

    def _handle_error(self, error_message: str):
        """Handle errors during processing"""
        try:
            logger.error(f"Processing error: {error_message}")
            logger.error(traceback.format_exc())
            
            # Stop any running timers
            for timer_attr in ['update_timer', 'progress_timer', 'sync_timer', 'progress_monitor']:
                if hasattr(self, timer_attr):
                    timer = getattr(self, timer_attr)
                    if timer.isActive():
                        timer.stop()
            
            # Show error to user
            QMessageBox.critical(self, "Error", str(error_message))
            
            # Reset processing state
            self._reset_processing_state()
            
        except Exception as e:
            logger.error(f"Error in error handler: {e}", exc_info=True)

    def _on_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Image Files (*.tif *.tiff *.jpg *.jpeg *.png);;PDF Files (*.pdf)"
        )
        if file_path:
            # Switch to appropriate tab based on file type
            if file_path.lower().endswith('.pdf'):
                self.tab_widget.setCurrentIndex(2)  # PDF tab
            else:
                self.tab_widget.setCurrentIndex(0)  # Single file tab
            self.selected_file_path = Path(file_path)
            self.file_path_label.setText(str(self.selected_file_path))

    def _save_settings(self):
        try:
            settings = {
                'dpi': self.dpi_combo.currentText(),
                'output_format': self.format_combo.currentText(),
                'last_directory': str(self.selected_file_path.parent if hasattr(self, 'selected_file_path') else ''),
            }
            settings_path = Path('settings.json')
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
            QMessageBox.information(self, "Success", "Settings saved successfully!")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings: {str(e)}")

    def _show_path_config(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Configure Paths")
        layout = QFormLayout(dialog)
        
        # Add path configuration widgets
        output_path = QLineEdit(str(self.ocr.output_base_dir))
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(lambda: self._browse_directory(output_path))
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(output_path)
        path_layout.addWidget(browse_button)
        
        layout.addRow("Output Directory:", path_layout)
        
        # Add OK/Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.ocr.output_base_dir = Path(output_path.text())
            QMessageBox.information(self, "Success", "Output path updated!")

    def _show_performance_options(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Performance Options")
        layout = QFormLayout(dialog)
        
        # Thread count setting 
        thread_count = QSpinBox()
        thread_count = QSpinBox()
        max_threads = psutil.cpu_count(logical=True)
        thread_count.setRange(1, max_threads)
        thread_count.setValue(max_threads) 
        thread_count.setEnabled(True) 
        layout.addRow("Thread Count:", thread_count) 
        
        # Add timeout settings
        operation_timeout = QSpinBox()
        operation_timeout.setRange(60, 3600)  # 1 minute to 1 hour
        operation_timeout.setValue(self.ocr.operation_timeout)
        operation_timeout.setSuffix(" seconds")
        layout.addRow("Operation Timeout:", operation_timeout)
        
        chunk_timeout = QSpinBox()
        chunk_timeout.setRange(30, 300)  # 30 seconds to 5 minutes
        chunk_timeout.setValue(self.ocr.chunk_timeout)
        chunk_timeout.setSuffix(" seconds")
        layout.addRow("Chunk Timeout:", chunk_timeout)
        
        # Add OK/Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.thread_pool.setMaxThreadCount(thread_count.value())
            self.ocr.operation_timeout = operation_timeout.value()
            self.ocr.chunk_timeout = chunk_timeout.value()
            QMessageBox.information(self, "Success", "Performance settings updated!")

    def _show_about(self):
        about_text = """
            <h3>VisionLane OCR</h3>
            <p><b>Version:</b> 1.0.0.0</p>
            <p>A powerful OCR engine built with <a href='https://github.com/mindee/doctr'>DocTR</a> for document processing.</p>
            <p><b>Features:</b></p>
            <ul>
                <li>Supports multiple image formats (JPG, PNG, TIFF, etc.)</li>
                <li>Exports searchable PDF and HOCR</li>
                <li>Batch processing for folders</li>
                <li>GPU acceleration when available</li>
            </ul>
            <p><b>Author:</b> <a href='https://github.com/NeoMatrix14241'>NeoMatrix14241</a></p>
            <p><i>Visit the <a href='https://github.com/NeoMatrix14241/VisionLane'>GitHub repository</a> for updates.</i></p>
            """
        QMessageBox.about(self, "About VisionLane OCR", about_text)

    def _browse_directory(self, line_edit):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Directory",
            line_edit.text()
        )
        if dir_path:
            line_edit.setText(dir_path)

    def __del__(self):
        """Cleanup when window is closed"""
        try:
            # Remove log handlers first
            if hasattr(self, 'log_handler'):
                logger.removeHandler(self.log_handler)
            
            # Stop timers
            if hasattr(self, 'hw_timer'):
                self.hw_timer.stop()
            
            # Clean up resources
            if hasattr(self, 'ocr'):
                self.ocr.cleanup_temp_files(force=True)
                
        except Exception as e:
            pass

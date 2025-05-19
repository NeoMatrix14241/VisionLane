from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, QPushButton, 
                           QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
                           QComboBox, QFileDialog, QMessageBox,
                           QLineEdit, QDialogButtonBox, QSpinBox, QCheckBox,
                           QFormLayout, QDialog, QProgressDialog, QSlider)
from PyQt6.QtCore import Qt, QTimer, QThreadPool
from PyQt6.QtGui import QIcon
import logging
import sys
import traceback
import psutil
from pathlib import Path
from datetime import datetime
import gc
import torch
import time
import configparser
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now import project modules
from ocr_processor import OCRProcessor
from .processing_thread import OCRWorker
from utils.process_manager import ProcessManager

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
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

            # Set window icon
            icon_path = str(Path(__file__).parent.parent / "icon.ico")
            self.setWindowIcon(QIcon(icon_path))
            
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
            self.current_worker = None
            self.process_manager = ProcessManager()
            self.thread_pool = QThreadPool()
            self.thread_pool.setMaxThreadCount(4)
            
            # Don't create output directories until needed
            self.project_root = Path(__file__).parent.parent.resolve()
            self.output_base_dir = self.project_root / "data" / "output"  # Default path
            self.pdf_dir = None
            self.hocr_dir = None
            self.temp_dir = None
            
            # Create data directory if it doesn't exist
            (self.project_root / "data").mkdir(exist_ok=True)
            
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
            
            # Add theme state
            self.theme_mode = "system"  # "system", "light", "dark", "night"
            
            # Initialize GUI
            self.setWindowTitle("VisionLane OCR (Can't fix GUI so slow I wanna cry, disappear, and become a potato)")
            self.setMinimumSize(800, 450)
            
            # Config parser for INI file
            self.config_path = self.project_root / "config.ini"
            self.config = configparser.ConfigParser()
            self._load_config()
            self._create_ui()
            # --- Ensure config.ini is created on first startup if missing ---
            if not self.config_path.exists():
                self._save_config()
            # Initialize OCR model
            QTimer.singleShot(0, lambda: self._delayed_init())
            
            # Add last update time tracking
            self.last_progress_update = time.time()
            self.progress_update_delay = 1.0  # 1 second delay
            
        except Exception as e:
            logger.error(f"Failed to initialize main window: {e}", exc_info=True)
            raise

    def _load_config(self):
        """Load settings from config.ini"""
        # Always use hardcoded defaults if config.ini is missing or does not contain the keys
        detection_model = "db_resnet50"
        recognition_model = "parseq"
        if self.config_path.exists():
            self.config.read(self.config_path, encoding="utf-8")
            detection_model = self.config.get("General", "detection_model", fallback=detection_model)
            recognition_model = self.config.get("General", "recognition_model", fallback=recognition_model)
        # DPI
        dpi = self.config.get("General", "dpi", fallback="Auto")
        if dpi not in ["Auto", "72", "96", "150", "200", "240", "250", "300", "350", "400", "450", "500", "600", "800", "900", "1200"]:
            dpi = "Auto"
        # Output format
        output_format = self.config.get("General", "output_format", fallback="PDF")
        # Theme
        theme_mode = self.config.get("General", "theme_mode", fallback="system")
        # Last directories
        last_single = self.config.get("Paths", "single", fallback="")
        last_folder = self.config.get("Paths", "folder", fallback="")
        last_pdf = self.config.get("Paths", "pdf", fallback="")
        last_output_single = self.config.get("Paths", "output_single", fallback="")
        last_output_folder = self.config.get("Paths", "output_folder", fallback="")
        last_output_pdf = self.config.get("Paths", "output_pdf", fallback="")
        # Performance
        thread_count = self.config.getint("Performance", "thread_count", fallback=psutil.cpu_count(logical=True))
        operation_timeout = self.config.getint("Performance", "operation_timeout", fallback=600)
        chunk_timeout = self.config.getint("Performance", "chunk_timeout", fallback=60)
        # Models: detection_model and recognition_model already set above

        # Compression settings
        compress_enabled = self.config.getboolean("General", "compress_enabled", fallback=False)
        compression_type = self.config.get("General", "compression_type", fallback="jpeg")
        compression_quality = self.config.getint("General", "compression_quality", fallback=100)
        # --- Archiving settings ---
        archive_enabled = self.config.getboolean("General", "archive_enabled", fallback=False)
        archive_single = self.config.get("Paths", "archive_single", fallback="")
        archive_folder = self.config.get("Paths", "archive_folder", fallback="")
        archive_pdf = self.config.get("Paths", "archive_pdf", fallback="")

        self._config_values = {
            "dpi": dpi,
            "output_format": output_format,
            "theme_mode": theme_mode,
            "last_single": last_single,
            "last_folder": last_folder,
            "last_pdf": last_pdf,
            "last_output_single": last_output_single,
            "last_output_folder": last_output_folder,
            "last_output_pdf": last_output_pdf,
            "thread_count": thread_count,
            "operation_timeout": operation_timeout,
            "chunk_timeout": chunk_timeout,
            "detection_model": detection_model,
            "recognition_model": recognition_model,
            "compress_enabled": compress_enabled,
            "compression_type": compression_type,
            "compression_quality": compression_quality,
            # --- Archiving ---
            "archive_enabled": archive_enabled,
            "archive_single": archive_single,
            "archive_folder": archive_folder,
            "archive_pdf": archive_pdf,
        }

    def _create_ui(self):
        """Create UI components"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        self._create_menu_bar()
        # Apply initial theme after menu bar is created
        self._apply_theme()
        self._create_input_section(layout)
        self._create_options_section(layout)
        self._create_status_section(layout)
        self._create_action_buttons(layout)
        # Restore config values to widgets after creation
        self._restore_config_to_widgets()

    def _restore_config_to_widgets(self):
        """Restore loaded config values to widgets"""
        v = self._config_values
        # DPI
        idx = self.dpi_combo.findText(v.get("dpi", "Auto"))
        if idx >= 0:
            self.dpi_combo.setCurrentIndex(idx)
        else:
            self.dpi_combo.setCurrentIndex(0)  # Always default to "Auto"
        # Output format
        idx = self.format_combo.findText(v["output_format"])
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        # Theme
        self._set_theme_mode(v["theme_mode"])
        # Last directories
        if v["last_single"]:
            self.selected_paths['single'] = Path(v["last_single"])
            self.single_file_label.setText(f"Selected: {Path(v['last_single']).name}")
        if v["last_folder"]:
            self.selected_paths['folder'] = Path(v["last_folder"])
            self.folder_label.setText(f"Selected: {Path(v['last_folder']).name}")
        if v["last_pdf"]:
            self.selected_paths['pdf'] = Path(v["last_pdf"])
            self.pdf_label.setText(f"Selected: {Path(v['last_pdf']).name}")
        if v["last_output_single"]:
            self.single_output_path.setText(v["last_output_single"])
        if v["last_output_folder"]:
            self.folder_output_path.setText(v["last_output_folder"])
        if v["last_output_pdf"]:
            self.pdf_output_path.setText(v["last_output_pdf"])
        # Performance
        self.thread_pool.setMaxThreadCount(v["thread_count"])
        # These will be set in _show_performance_options dialog as well
        # but also set as attributes for OCR
        if hasattr(self, "ocr"):
            self.ocr.operation_timeout = v["operation_timeout"]
            self.ocr.chunk_timeout = v["chunk_timeout"]
        # Detection/Recognition model dropdowns
        idx = self.det_model_combo.findData(v.get("detection_model", "db_resnet50"))
        if idx >= 0:
            self.det_model_combo.setCurrentIndex(idx)
        else:
            idx = self.det_model_combo.findData("db_resnet50")
            if idx >= 0:
                self.det_model_combo.setCurrentIndex(idx)
        idx = self.rec_model_combo.findData(v.get("recognition_model", "parseq"))
        if idx >= 0:
            self.rec_model_combo.setCurrentIndex(idx)
        else:
            idx = self.rec_model_combo.findData("parseq")
            if idx >= 0:
                self.rec_model_combo.setCurrentIndex(idx)
        # Compression settings
        self.compress_checkbox.setChecked(v.get("compress_enabled", False))
        idx = self.compression_type_combo.findText(v.get("compression_type", "JPEG").upper())
        if idx >= 0:
            self.compression_type_combo.setCurrentIndex(idx)
        self.quality_slider.setValue(v.get("compression_quality", 100))
        # --- Restore archiving settings ---
        self.single_archive_checkbox.setChecked(v.get("archive_enabled", False))
        self.folder_archive_checkbox.setChecked(v.get("archive_enabled", False))
        self.pdf_archive_checkbox.setChecked(v.get("archive_enabled", False))
        if v.get("archive_single"):
            self.single_archive_dir.setText(v["archive_single"])
        if v.get("archive_folder"):
            self.folder_archive_dir.setText(v["archive_folder"])
        if v.get("archive_pdf"):
            self.pdf_archive_dir.setText(v["archive_pdf"])
        # ...existing code...

    def _save_config(self):
        """Save all GUI settings to config.ini"""
        if not self.config.has_section("General"):
            self.config.add_section("General")
        if not self.config.has_section("Paths"):
            self.config.add_section("Paths")
        if not self.config.has_section("Performance"):
            self.config.add_section("Performance")
        # General
        self.config.set("General", "dpi", self.dpi_combo.currentText())
        self.config.set("General", "output_format", self.format_combo.currentText())
        self.config.set("General", "theme_mode", self.theme_mode)
        self.config.set("General", "detection_model", self.det_model_combo.currentData())
        self.config.set("General", "recognition_model", self.rec_model_combo.currentData())
        # Compression settings
        self.config.set("General", "compress_enabled", str(self.compress_checkbox.isChecked()))
        self.config.set("General", "compression_type", self.compression_type_combo.currentText().lower())
        self.config.set("General", "compression_quality", str(self.quality_slider.value()))
        # --- Archiving settings ---
        self.config.set("General", "archive_enabled", str(
            self.single_archive_checkbox.isChecked() or
            self.folder_archive_checkbox.isChecked() or
            self.pdf_archive_checkbox.isChecked()
        ))
        self.config.set("Paths", "archive_single", self.single_archive_dir.text())
        self.config.set("Paths", "archive_folder", self.folder_archive_dir.text())
        self.config.set("Paths", "archive_pdf", self.pdf_archive_dir.text())
        # Paths
        self.config.set("Paths", "single", str(self.selected_paths['single'] or ""))
        self.config.set("Paths", "folder", str(self.selected_paths['folder'] or ""))
        self.config.set("Paths", "pdf", str(self.selected_paths['pdf'] or ""))
        self.config.set("Paths", "output_single", self.single_output_path.text())
        self.config.set("Paths", "output_folder", self.folder_output_path.text())
        self.config.set("Paths", "output_pdf", self.pdf_output_path.text())
        # Performance
        self.config.set("Performance", "thread_count", str(self.thread_pool.maxThreadCount()))
        if hasattr(self, "ocr"):
            self.config.set("Performance", "operation_timeout", str(getattr(self.ocr, "operation_timeout", 600)))
            self.config.set("Performance", "chunk_timeout", str(getattr(self.ocr, "chunk_timeout", 60)))
        else:
            self.config.set("Performance", "operation_timeout", "600")
            self.config.set("Performance", "chunk_timeout", "60")
        # Write to file
        with open(self.config_path, "w", encoding="utf-8") as f:
            self.config.write(f)

    def show(self):
        """Override show to ensure window appears"""
        super().show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()  # Force window activation

    def closeEvent(self, event):
        """Handle window close"""
        try:
            self._save_config()
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

        # Theme menu
        theme_menu = menubar.addMenu("Theme")
        self.action_theme_system = theme_menu.addAction("System Default")
        self.action_theme_light = theme_menu.addAction("Light Mode")
        self.action_theme_dark = theme_menu.addAction("Dark Mode")
        self.action_theme_night = theme_menu.addAction("Night Mode")
        self.action_theme_system.setCheckable(True)
        self.action_theme_light.setCheckable(True)
        self.action_theme_dark.setCheckable(True)
        self.action_theme_night.setCheckable(True)
        self.action_theme_group = [
            self.action_theme_system,
            self.action_theme_light,
            self.action_theme_dark,
            self.action_theme_night
        ]
        self.action_theme_system.setChecked(True)

        self.action_theme_system.triggered.connect(lambda: self._set_theme_mode("system"))
        self.action_theme_light.triggered.connect(lambda: self._set_theme_mode("light"))
        self.action_theme_dark.triggered.connect(lambda: self._set_theme_mode("dark"))
        self.action_theme_night.triggered.connect(lambda: self._set_theme_mode("night"))

        # Help menu
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About").triggered.connect(self._show_about)

    def _set_theme_mode(self, mode):
        """Set theme mode: system, light, dark, or night"""
        self.theme_mode = mode
        # Update check states
        self.action_theme_system.setChecked(mode == "system")
        self.action_theme_light.setChecked(mode == "light")
        self.action_theme_dark.setChecked(mode == "dark")
        self.action_theme_night.setChecked(mode == "night")
        self._apply_theme()

    def _apply_theme(self):
        """Apply the current theme to the application (System, Light, Dark, or Night Mode)"""
        if self.theme_mode == "night":
            # Night mode stylesheet (custom, high-contrast)
            night_stylesheet = """
                QWidget {
                    background-color: #232629;
                    color: #F0F0F0;
                }
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
                    background-color: #31363b;
                    color: #F0F0F0;
                    border: 1px solid #555;
                }
                QPushButton {
                    background-color: #31363b;
                    color: #F0F0F0;
                    border: 1px solid #555;
                }
                QTabWidget::pane {
                    border: 1px solid #555;
                }
                QMenuBar, QMenu {
                    background-color: #232629;
                    color: #F0F0F0;
                }
                QProgressBar {
                    background-color: #31363b;
                    color: #F0F0F0;
                    border: 1px solid #555;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #0078d7;
                }
            """
            self.setStyleSheet(night_stylesheet)
        elif self.theme_mode == "dark":
            # Dark mode stylesheet (less contrast, more like system dark)
            dark_stylesheet = """
                QWidget {
                    background-color: #2d2d30;
                    color: #dddddd;
                }
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
                    background-color: #3c3c3c;
                    color: #dddddd;
                    border: 1px solid #444;
                }
                QPushButton {
                    background-color: #3c3c3c;
                    color: #dddddd;
                    border: 1px solid #444;
                }
                QTabWidget::pane {
                    border: 1px solid #444;
                }
                QMenuBar, QMenu {
                    background-color: #2d2d30;
                    color: #dddddd;
                }
                QProgressBar {
                    background-color: #3c3c3c;
                    color: #dddddd;
                    border: 1px solid #444;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #0078d7;
                }
            """
            self.setStyleSheet(dark_stylesheet)
        elif self.theme_mode == "light":
            # Force a light stylesheet regardless of system
            light_stylesheet = """
                QWidget {
                    background-color: #f6f6f6;
                    color: #222222;
                }
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
                    background-color: #ffffff;
                    color: #222222;
                    border: 1px solid #cccccc;
                }
                QPushButton {
                    background-color: #eaeaea;
                    color: #222222;
                    border: 1px solid #cccccc;
                }
                QTabWidget::pane {
                    border: 1px solid #cccccc;
                }
                QMenuBar, QMenu {
                    background-color: #f6f6f6;
                    color: #222222;
                }
                QProgressBar {
                    background-color: #eaeaea;
                    color: #222222;
                    border: 1px solid #cccccc;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #0078d7;
                }
            """
            self.setStyleSheet(light_stylesheet)
        else:
            # System default: clear stylesheet, let OS/PyQt6 decide
            self.setStyleSheet("")

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
            layout.setSpacing(5)
            layout.setContentsMargins(10, 10, 10, 10)

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
            browse_btn.setMinimumWidth(120)
            browse_btn.setMaximumWidth(120)
            out_layout.addWidget(output_path, stretch=4)
            out_layout.addWidget(browse_btn, stretch=1)
            layout.addWidget(select_btn)
            layout.addWidget(label)
            layout.addLayout(out_layout)

            # --- Archive row below output directory row ---
            archive_layout = QHBoxLayout()
            archive_checkbox = QCheckBox("Archiving?")
            archive_dir = QLineEdit()
            archive_dir.setPlaceholderText("Archive directory")
            archive_dir.setMinimumHeight(25)
            archive_browse_btn = QPushButton("Browse Archive")
            archive_browse_btn.setStyleSheet(btn_style)
            archive_browse_btn.setMinimumWidth(120)
            archive_browse_btn.setMaximumWidth(120)
            # Enable/disable archive_dir and browse button based on checkbox
            def on_archive_checked(state):
                enabled = state == 2  # 2 == Checked, 0 == Unchecked
                archive_dir.setEnabled(enabled)
                archive_browse_btn.setEnabled(enabled)
            archive_checkbox.stateChanged.connect(on_archive_checked)
            # Set initial state based on checkbox
            on_archive_checked(archive_checkbox.checkState())
            archive_layout.addWidget(archive_checkbox)
            archive_layout.addWidget(archive_dir, stretch=4)
            archive_layout.addWidget(archive_browse_btn, stretch=1)
            layout.addLayout(archive_layout)
            # Store references for later use
            widget._archive_checkbox = archive_checkbox
            widget._archive_dir = archive_dir
            widget._archive_browse_btn = archive_browse_btn

            layout.addStretch()
            return widget, select_btn, label, output_path, browse_btn, archive_checkbox, archive_dir, archive_browse_btn
        
        # Single File tab
        single_widget, select_file_btn, self.single_file_label, self.single_output_path, single_browse_btn, \
            self.single_archive_checkbox, self.single_archive_dir, self.single_archive_browse_btn = create_tab(
            "Single File", "Select Input File"
        )
        select_file_btn.clicked.connect(self._select_single_file)
        single_browse_btn.clicked.connect(lambda: self._browse_output(self.single_output_path))
        self.single_archive_browse_btn.clicked.connect(lambda: self._browse_output(self.single_archive_dir))
        self.tab_widget.addTab(single_widget, "Single File")
        
        # Folder tab
        folder_widget, select_folder_btn, self.folder_label, self.folder_output_path, folder_browse_btn, \
            self.folder_archive_checkbox, self.folder_archive_dir, self.folder_archive_browse_btn = create_tab(
            "Folder", "Select Input Folder"
        )
        select_folder_btn.clicked.connect(self._select_folder)
        folder_browse_btn.clicked.connect(lambda: self._browse_output(self.folder_output_path))
        self.folder_archive_browse_btn.clicked.connect(lambda: self._browse_output(self.folder_archive_dir))
        self.tab_widget.addTab(folder_widget, "Folder")
        
        # PDF tab
        pdf_widget, select_pdf_btn, self.pdf_label, self.pdf_output_path, pdf_browse_btn, \
            self.pdf_archive_checkbox, self.pdf_archive_dir, self.pdf_archive_browse_btn = create_tab(
            "PDF", "Select Input PDF"
        )
        select_pdf_btn.clicked.connect(self._select_pdf)
        pdf_browse_btn.clicked.connect(lambda: self._browse_output(self.pdf_output_path))
        self.pdf_archive_browse_btn.clicked.connect(lambda: self._browse_output(self.pdf_archive_dir))
        self.tab_widget.addTab(pdf_widget, "PDF")
        
        # Add tab widget to parent layout with reduced height
        parent_layout.addWidget(self.tab_widget)

        # Restore config values for input/output paths and update labels
        v = getattr(self, "_config_values", {})
        # Single file
        if v.get("last_single"):
            self.selected_paths['single'] = Path(v["last_single"])
            self.single_file_label.setText(f"Selected: {Path(v['last_single']).name}")
        if v.get("last_output_single"):
            self.single_output_path.setText(v["last_output_single"])
        # Folder
        if v.get("last_folder"):
            self.selected_paths['folder'] = Path(v["last_folder"])
            self.folder_label.setText(f"Selected: {Path(v['last_folder']).name}")
        if v.get("last_output_folder"):
            self.folder_output_path.setText(v["last_output_folder"])
        # PDF
        if v.get("last_pdf"):
            self.selected_paths['pdf'] = Path(v["last_pdf"])
            self.pdf_label.setText(f"Selected: {Path(v['last_pdf']).name}")
        if v.get("last_output_pdf"):
            self.pdf_output_path.setText(v["last_output_pdf"])

    def _browse_output(self, line_edit):
        """Handle output directory selection"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(self.project_root)  # Start from project root
        )
        if dir_path:
            # Update output path in UI
            line_edit.setText(dir_path)
            
            # Update OCR processor paths if it exists
            if hasattr(self, 'ocr'):
                self.ocr.output_base_dir = Path(dir_path)
                # Let OCR processor create directories when needed
                self.output_base_dir = self.ocr.output_base_dir
                self.pdf_dir = self.ocr.pdf_dir
                self.hocr_dir = self.ocr.hocr_dir
                self.temp_dir = self.ocr.temp_dir

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
        # DPI + Output Format row
        options_layout1 = QHBoxLayout()
        self.dpi_combo = QComboBox()
        # Add more DPI options and "Auto" as the first/default
        dpi_options = ["Auto", "72", "96", "150", "200", "240", "250", "300", "350", "400", "450", "500", "600", "800", "900", "1200"]
        self.dpi_combo.addItems(dpi_options)
        self.dpi_combo.setCurrentIndex(0)  # Always default to "Auto"
        options_layout1.addWidget(QLabel("DPI:"))
        options_layout1.addWidget(self.dpi_combo)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PDF", "HOCR", "PDF+HOCR"])
        options_layout1.addWidget(QLabel("Output Format:"))
        options_layout1.addWidget(self.format_combo)
        parent_layout.addLayout(options_layout1)

        # Detection Model + Recognition Model row
        options_layout2 = QHBoxLayout()
        self.det_model_combo = QComboBox()
        options_layout2.addWidget(QLabel("Detection Model:"))
        options_layout2.addWidget(self.det_model_combo)

        self.rec_model_combo = QComboBox()
        options_layout2.addWidget(QLabel("Recognition Model:"))
        options_layout2.addWidget(self.rec_model_combo)
        parent_layout.addLayout(options_layout2)

        # Only download the default models from config.ini at startup
        self._populate_model_dropdowns(download_missing="startup")
        self.det_model_combo.currentIndexChanged.connect(self._on_det_model_change)
        self.rec_model_combo.currentIndexChanged.connect(self._on_rec_model_change)

        # --- Compression Options (move below model selection) ---
        compression_layout = QHBoxLayout()
        self.compress_checkbox = QCheckBox("Compress with PyPDFCompressor")
        compression_layout.addWidget(self.compress_checkbox)

        self.compression_type_combo = QComboBox()
        self.compression_type_combo.addItems(["JPEG", "JPEG2000", "LZW", "PNG"])
        self.compression_type_combo.setEnabled(False)
        self.compression_type_combo.setCurrentIndex(0)  # Default to JPEG
        compression_layout.addWidget(QLabel("Type:"))
        compression_layout.addWidget(self.compression_type_combo)

        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setMinimum(0)
        self.quality_slider.setMaximum(100)
        self.quality_slider.setValue(100)  # Default to 100%
        self.quality_slider.setEnabled(False)
        self.quality_slider.setFixedWidth(120)
        compression_layout.addWidget(QLabel("Quality:"))
        compression_layout.addWidget(self.quality_slider)

        # Add dynamic label for quality percent
        self.quality_label = QLabel("100%")
        self.quality_label.setFixedWidth(40)
        compression_layout.addWidget(self.quality_label)

        # Add info button for Ghostscript status
        from PyQt6.QtWidgets import QPushButton  # Ensure QPushButton is imported

        self.compression_info_button = QPushButton("Unavailable: Learn More?")
        self.compression_info_button.setVisible(False)
        self.compression_info_button.setFixedHeight(24)
        self.compression_info_button.setStyleSheet("QPushButton { color: #0078d7; border: none; background: transparent; text-decoration: underline; }")
        compression_layout.addWidget(self.compression_info_button)

        # Remove the old info icon
        # self.compression_info_icon = QLabel()
        # info_pix = QPixmap(16, 16)
        # info_pix.fill(Qt.GlobalColor.transparent)
        # self.compression_info_icon.setPixmap(info_pix)
        # self.compression_info_icon.setVisible(False)
        # compression_layout.addWidget(self.compression_info_icon)

        parent_layout.addLayout(compression_layout)

        # --- Ghostscript check and UI update ---
        import re

        def check_ghostscript():
            # Windows: gswin64c.exe, Linux/Mac: gs
            if sys.platform.startswith("win"):
                exe_name = "gswin64c.exe"
                # 1. Check PATH
                gs_path = shutil.which(exe_name)
                if gs_path:
                    return True, gs_path
                # 2. Search in Program Files locations
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
                                    # Try to extract version from folder name
                                    m = re.search(r'(\d+(\.\d+)*)', sub.name)
                                    version = tuple(map(int, m.group(1).split('.'))) if m else (0,)
                                    found.append((version, exe))
                if found:
                    # Sort by version descending, pick highest
                    found.sort(reverse=True)
                    return True, str(found[0][1])
                return False, None
            else:
                exe_name = "gs"
                gs_path = shutil.which(exe_name)
                if gs_path:
                    return True, gs_path
                return False, None

        def show_ghostscript_dialog():
            msg = QMessageBox(self)
            msg.setWindowTitle("Ghostscript Required")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setText(
                "PDF compression requires Ghostscript (gswin64c.exe or gs) to be installed and available in your system PATH.<br><br>"
                "Please install Ghostscript and ensure it is accessible from the command line.<br><br>"
                "Download Ghostscript here:<br>"
                "<a href='https://www.ghostscript.com/releases/gsdnld.html'>https://www.ghostscript.com/releases/gsdnld.html</a>"
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            # Enable clickable links
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            msg.exec()

        self.compression_info_button.clicked.connect(show_ghostscript_dialog)

        def update_compression_controls():
            gs_found, gs_path = check_ghostscript()
            enabled = self.compress_checkbox.isChecked() and gs_found
            self.compression_type_combo.setEnabled(enabled)
            ctype = self.compression_type_combo.currentText().lower()
            self.quality_slider.setEnabled(enabled and ctype in ("jpeg", "jpeg2000"))
            self.quality_label.setText(f"{self.quality_slider.value()}%")
            self.quality_label.setEnabled(self.quality_slider.isEnabled())
            self.compress_checkbox.setEnabled(gs_found)
            # Button for Ghostscript info
            if not gs_found:
                self.compress_checkbox.setChecked(False)
                self.compress_checkbox.setEnabled(False)
                self.compression_type_combo.setEnabled(False)
                self.quality_slider.setEnabled(False)
                self.quality_label.setEnabled(False)
                self.compression_info_button.setVisible(True)
            else:
                self.compress_checkbox.setEnabled(True)
                self.compression_info_button.setVisible(False)
                # Optionally, store gs_path for use in compression logic
                self._gs_executable_path = gs_path

        self.compress_checkbox.stateChanged.connect(update_compression_controls)
        self.compression_type_combo.currentIndexChanged.connect(update_compression_controls)
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(f"{v}%"))
        self.quality_slider.valueChanged.connect(update_compression_controls)

        # --- Ensure controls are initialized correctly on startup ---
        update_compression_controls()

        # Only download the default models from config.ini at startup
        self._populate_model_dropdowns(download_missing="startup")
        self.det_model_combo.currentIndexChanged.connect(self._on_det_model_change)
        self.rec_model_combo.currentIndexChanged.connect(self._on_rec_model_change)

    def _populate_model_dropdowns(self, download_missing=False):
        """
        Populate detection/recognition model dropdowns with available models and download status.
        If download_missing == "startup", only download the default models from config.ini or hardcoded defaults.
        """
        det_models = [
            "db_resnet50",
            "linknet_resnet18",
            "linknet_resnet34",
            "linknet_resnet50",
            "db_mobilenet_v3_large",
            "fast_tiny",
            "fast_small",
            "fast_base",
        ]
        rec_models = [
            "parseq",
            "crnn_vgg16_bn",
            "crnn_mobilenet_v3_small",
            "crnn_mobilenet_v3_large",
            "sar_resnet31",
            "master",
            "vitstr_small",
            "vitstr_base",
        ]
        from pathlib import Path
        cache_dir = Path.home() / ".cache" / "doctr" / "models"
        def model_exists(name):
            # Only match the model name exactly (not startswith), to avoid duplicates
            return any(p.name.split('-')[0] == name for p in cache_dir.glob("*.pt"))

        # --- Only download the default models from config.ini or hardcoded defaults at startup ---
        if download_missing == "startup":
            det_model = self._config_values.get("detection_model") or "db_resnet50"
            rec_model = self._config_values.get("recognition_model") or "parseq"
            import doctr.models as doctr_models
            if not model_exists(det_model):
                try:
                    if hasattr(doctr_models.detection, det_model):
                        getattr(doctr_models.detection, det_model)(pretrained=True)
                except Exception:
                    pass
            if not model_exists(rec_model):
                try:
                    if hasattr(doctr_models.recognition, rec_model):
                        getattr(doctr_models.recognition, rec_model)(pretrained=True)
                except Exception:
                    pass
        # --- Download all models if download_missing is True ---
        elif download_missing is True:
            import doctr.models as doctr_models
            for key in det_models:
                if not model_exists(key):
                    try:
                        getattr(doctr_models.detection, key)(pretrained=True)
                    except Exception:
                        pass
            for key in rec_models:
                if not model_exists(key):
                    try:
                        getattr(doctr_models.recognition, key)(pretrained=True)
                    except Exception:
                        pass

        # --- Prevent duplicate items in dropdowns ---
        self.det_model_combo.clear()
        self.rec_model_combo.clear()

        self._det_model_needs_download = {}
        self._rec_model_needs_download = {}

        # Add detection models (no duplicates)
        added_det = set()
        for key in det_models:
            if key in added_det:
                continue
            added_det.add(key)
            exists = model_exists(key)
            self._det_model_needs_download[key] = not exists
            display = key + ("" if exists else " ⬇️")
            self.det_model_combo.addItem(display, key)

        # Add recognition models (no duplicates)
        added_rec = set()
        for key in rec_models:
            if key in added_rec:
                continue
            added_rec.add(key)
            exists = model_exists(key)
            self._rec_model_needs_download[key] = not exists
            display = key + ("" if exists else " ⬇️")
            self.rec_model_combo.addItem(display, key)

        # Remove any duplicate entries by checking all items after adding
        def remove_duplicates(combo):
            seen = set()
            indices_to_remove = []
            for i in range(combo.count()):
                data = combo.itemData(i)
                if data in seen:
                    indices_to_remove.append(i)
                else:
                    seen.add(data)
            # Remove from end to start to avoid shifting indices
            for i in reversed(indices_to_remove):
                combo.removeItem(i)
        remove_duplicates(self.det_model_combo)
        remove_duplicates(self.rec_model_combo)

        # Set default selection to db_resnet50 and parseq if present
        det_idx = self.det_model_combo.findData(self._config_values.get("detection_model", "db_resnet50"))
        if det_idx < 0:
            det_idx = self.det_model_combo.findData("db_resnet50")
        if det_idx >= 0:
            self.det_model_combo.setCurrentIndex(det_idx)
        rec_idx = self.rec_model_combo.findData(self._config_values.get("recognition_model", "parseq"))
        if rec_idx < 0:
            rec_idx = self.rec_model_combo.findData("parseq")
        if rec_idx >= 0:
            self.rec_model_combo.setCurrentIndex(rec_idx)

        # Connect to custom handler for download logic
        try:
            self.det_model_combo.currentIndexChanged.disconnect()
        except Exception:
            pass
        try:
            self.rec_model_combo.currentIndexChanged.disconnect()
        except Exception:
            pass
        self.det_model_combo.currentIndexChanged.connect(self._on_det_model_change)
        self.rec_model_combo.currentIndexChanged.connect(self._on_rec_model_change)

    def _on_det_model_change(self, idx):
        key = self.det_model_combo.itemData(idx)
        # Only prompt/download for the selected detection model, not all
        if self._det_model_needs_download.get(key, False):
            self._download_model_no_dialog(key, "detection")
            # After download, refresh dropdowns to update icon
            self._populate_model_dropdowns(download_missing=False)
            # Set selection back to the just-downloaded model
            idx_new = self.det_model_combo.findData(key)
            if idx_new >= 0:
                self.det_model_combo.blockSignals(True)
                self.det_model_combo.setCurrentIndex(idx_new)
                self.det_model_combo.blockSignals(False)
        self._on_model_change()

    def _on_rec_model_change(self, idx):
        key = self.rec_model_combo.itemData(idx)
        # Only prompt/download for the selected recognition model, not all
        if self._rec_model_needs_download.get(key, False):
            self._download_model_no_dialog(key, "recognition")
            # After download, refresh dropdowns to update icon
            self._populate_model_dropdowns(download_missing=False)
            # Set selection back to the just-downloaded model
            idx_new = self.rec_model_combo.findData(key)
            if idx_new >= 0:
                self.rec_model_combo.blockSignals(True)
                self.rec_model_combo.setCurrentIndex(idx_new)
                self.rec_model_combo.blockSignals(False)
        self._on_model_change()

    # Add this method for compatibility with model change handlers
    def _on_model_change(self, *args, **kwargs):
        """Update OCR processor with current model selections."""
        if hasattr(self, "ocr") and self.ocr:
            det_model = self.det_model_combo.currentData()
            rec_model = self.rec_model_combo.currentData()
            self.ocr.set_models(det_model, rec_model)

    def _download_model_no_dialog(self, model_key, model_type):
        """
        Download the specified model without any confirmation or completion dialogs.
        Show a progress dialog only while downloading.
        """
        progress = QProgressDialog(
            f"Downloading {model_key}...", None, 0, 0, self
        )
        progress.setWindowTitle("Downloading Model")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        try:
            import doctr.models as doctr_models
            if model_type == "detection":
                getattr(doctr_models.detection, model_key)(pretrained=True)
            else:
                getattr(doctr_models.recognition, model_key)(pretrained=True)
            progress.setValue(1)
            QApplication.processEvents()
        except Exception as e:
            QMessageBox.critical(self, "Download Failed", f"Failed to download model '{model_key}':\n{e}")
        finally:
            progress.close()

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
        """Reset UI state completely"""
        try:
            # Stop timers safely
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            if hasattr(self, 'progress_timer'):
                self.progress_timer.stop()
            if hasattr(self, 'progress_monitor'):
                self.progress_monitor.stop();
            
            # Reset progress counters
            self.processed_files = 0
            self.total_files = 0
            self.last_progress = 0
            
            # Reset UI labels to initial state
            self.current_file_label.setText("No file processing")
            self.overall_progress_label.setText("Total Progress: 0/0")
            self.overall_progress.setValue(0)
            
            # Reset file tracking
            self.file_tracking['current'] = None
            self.file_tracking['processed'].clear()
            
            # Reset buttons
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error in reset_processing_state: {e}")

    def _process_finished(self, success):
        """Handle process completion"""
        try:
            # Stop timers but keep current progress visible
            self.sync_timer.stop()
            self.progress_monitor.stop()
            self.update_timer.stop()
            self.progress_timer.stop()
            
            # Keep progress visible while showing completion message
            if success and not self.ocr.is_cancelled:
                # Show completion message and wait for user response
                QMessageBox.information(self, "Success", "Processing completed successfully!")
            
            # Only reset the state after user has seen completion message
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.current_file_label.setText("No file processing")
            self.overall_progress_label.setText("Total Progress: 0/0") 
            self.overall_progress.setValue(0)
            
            # Clear internal state
            self.processed_files = 0
            self.total_files = 0
            self.last_progress = 0
            self.file_tracking['current'] = None
            self.file_tracking['processed'].clear()
            
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error during process completion: {e}")
            self._reset_processing_state()

    def _update_gui(self):
        """Update GUI elements without blocking"""
        QApplication.processEvents()

    def _sync_progress(self):
        """Enhanced progress sync with real-time file counting"""
        try:
            if not self.current_worker or not self.current_worker.is_running:
                return

            # Update current file display first
            if hasattr(self.ocr, 'current_file') and self.ocr.current_file:
                current = Path(self.ocr.current_file)
                if current.name != getattr(self, '_last_displayed_file', None):
                    self.current_file_label.setText(f"Processing: {current.name}")
                    self._last_displayed_file = current.name
                    logger.debug(f"Showing current file: {current.name}")
                    QApplication.processEvents()

            # Only update progress when files are actually completed
            if hasattr(self.ocr, '_processed_files'):
                real_count = len(self.ocr._processed_files)
                if real_count != self.processed_files:
                    # Only update after both HOCR and PDF exist
                    if self._verify_file_completion(self.ocr.current_file):
                        self.processed_files = real_count
                        progress = int((real_count / self.total_files) * 100) if self.total_files > 0 else 0
                        self.overall_progress.setValue(progress)
                        self.overall_progress_label.setText(f"Files Processed: {real_count}/{self.total_files}")
                        logger.debug(f"Updated progress: {real_count}/{self.total_files}")
                        QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error in sync_progress: {e}")

    def _verify_file_completion(self, filepath):
        """Verify both HOCR and PDF exist for the file"""
        if not filepath:
            return False
        try:
            path = Path(filepath)
            # Check if both output files exist
            hocr_exists = any(self.ocr.hocr_dir.rglob(f"{path.stem}*.hocr"))
            pdf_exists = any(self.ocr.temp_dir.glob(f"*{path.stem}*.pdf"))
            return hocr_exists and pdf_exists
        except Exception as e:
            logger.error(f"Error verifying file completion: {e}")
            return False
        except Exception as e:
            logger.error(f"Error verifying file completion: {e}")
            return False

    def _start_processing(self):
        """Start processing with improved error handling and archiving support"""
        try:
            # --- Sync compression settings to OCRProcessor before processing ---
            if hasattr(self, 'ocr'):
                self.ocr.compress_images = self.compress_checkbox.isChecked()
                self.ocr.compression_type = self.compression_type_combo.currentText().lower()
                self.ocr.compression_quality = self.quality_slider.value()

            # Check if already processing
            if self.current_worker and self.current_worker.is_running:
                QMessageBox.warning(self, "Warning", "Processing already in progress")
                return

            # Get processing parameters and count files first
            current_tab = self.tab_widget.currentIndex()
            mode, path = self._get_processing_params(current_tab)
            self.total_files = self._get_total_files(path, mode)

            # Store the list of files to process for progress display
            if mode == 'folder':
                image_exts = ['.tif', '.tiff', '.jpg', '.jpeg', '.png']
                folder = Path(path)
                files = []
                for ext in image_exts:
                    files.extend(sorted(folder.rglob(f"*{ext}")))
                pdfs = sorted(folder.rglob("*.pdf"))
                self._files_to_process = files + pdfs
            else:
                self._files_to_process = [path]

            # --- Archiving logic ---
            archive_enabled = False
            archive_dir = None
            if current_tab == 0:  # Single File
                archive_enabled = self.single_archive_checkbox.isChecked()
                archive_dir = self.single_archive_dir.text().strip()
            elif current_tab == 1:  # Folder
                archive_enabled = self.folder_archive_checkbox.isChecked()
                archive_dir = self.folder_archive_dir.text().strip()
            elif current_tab == 2:  # PDF
                archive_enabled = self.pdf_archive_checkbox.isChecked()
                archive_dir = self.pdf_archive_dir.text().strip()

            # Validate archive path if archiving is enabled
            if archive_enabled:
                if not archive_dir:
                    logger.error("Archiving is enabled but no archive directory is specified.")
                    QMessageBox.critical(self, "Archiving Error", "Archiving is enabled but no archive directory is specified.")
                    return
                archive_dir = Path(archive_dir)
                if not archive_dir.exists():
                    try:
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Created archive directory: {archive_dir}")
                    except Exception as e:
                        logger.error(f"Failed to create archive directory: {e}")
                        QMessageBox.critical(self, "Archiving Error", f"Failed to create archive directory:\n{e}")
                        return

            # Reset state before starting
            self.processed_files = 0
            self.last_progress = 0
            self.max_processed = 0
            self._last_displayed_file = None

            self.current_file_label.setText("Starting processing...")
            self.overall_progress_label.setText(f"Files Processed: 0/{self.total_files}")
            self.overall_progress.setValue(0)
            QApplication.processEvents()

            if hasattr(self, 'ocr'):
                self.ocr.reset_state()
                self.ocr._processed_files.clear()

            self.current_worker = OCRWorker(self.ocr, mode, path)
            # ...existing signal connections...
            try:
                self.current_worker.signals.progress.connect(self._update_overall_progress)
                self.current_worker.signals.error.connect(self._handle_error)
                self.current_worker.signals.cancelled.connect(self._on_cancelled)
                self.current_worker.signals.finished.connect(self._process_finished)

                self.start_button.setEnabled(False)
                self.cancel_button.setEnabled(True)
                self.overall_progress.setValue(0)

                self.progress_monitor.start()
                self.sync_timer.start()

                logger.info(f"Starting processing: mode={mode}, path={path}")
                self.thread_pool.start(self.current_worker)
            except Exception as e:
                logger.error(f"Failed to connect worker signals: {e}")
                self._handle_error(f"Failed to start processing: {e}")
                self.current_worker = None

            # --- After processing, perform archiving if enabled ---
            if archive_enabled:
                try:
                    def do_archive():
                        try:
                            if mode == 'single':
                                src = Path(path)
                                rel_path = src.name
                                dst = archive_dir / rel_path
                                logger.info(f"Archiving single file: {src} -> {dst}")
                                shutil.move(str(src), str(dst))
                                logger.info(f"Archived single file: {src} -> {dst}")
                            elif mode == 'folder':
                                src_folder = Path(path)
                                for file in self._files_to_process:
                                    file = Path(file)
                                    rel_path = file.relative_to(src_folder)
                                    dst = archive_dir / rel_path
                                    dst.parent.mkdir(parents=True, exist_ok=True)
                                    logger.info(f"Archiving file: {file} -> {dst}")
                                    shutil.move(str(file), str(dst))
                                    logger.info(f"Archived file: {file} -> {dst}")
                            elif mode == 'pdf':
                                src = Path(path)
                                rel_path = src.name
                                dst = archive_dir / rel_path
                                logger.info(f"Archiving PDF: {src} -> {dst}")
                                shutil.move(str(src), str(dst))
                                logger.info(f"Archived PDF: {src} -> {dst}")
                        except Exception as e:
                            logger.error(f"Archiving error: {e}")
                            QMessageBox.critical(self, "Archiving Error", f"Failed to archive files:\n{e}")

                    def on_finished(success):
                        if success and not self.ocr.is_cancelled:
                            logger.info("Processing finished successfully, starting archiving.")
                            do_archive()
                        self._process_finished(success)
                    try:
                        self.current_worker.signals.finished.disconnect()
                    except Exception:
                        pass
                    self.current_worker.signals.finished.connect(on_finished)
                except Exception as e:
                    logger.error(f"Archiving setup error: {e}")
                    QMessageBox.critical(self, "Archiving Error", f"Failed to setup archiving:\n{e}")

        except Exception as e:
            logger.error(f"Error starting processing: {e}", exc_info=True)
            self._handle_error(str(e))

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
            # Use selected output directory
            output_dir = Path(self.single_output_path.text())
            self.ocr.set_output_directory(output_dir)
            self.ocr.output_formats = output_formats
            dpi_text = self.dpi_combo.currentText()
            if dpi_text == "Auto":
                dpi_value = None
            else:
                try:
                    dpi_value = int(dpi_text)
                except Exception:
                    dpi_value = None
            self.ocr.dpi = dpi_value  # Pass DPI to OCRProcessor
            return 'single', self.selected_paths['single']
            
        elif tab_index == 1:  # Folder
            if not self.selected_paths['folder']:
                raise ValueError("Please select a folder")
            if not self.folder_output_path.text():
                raise ValueError("Please select output directory")
            self.ocr.output_base_dir = Path(self.folder_output_path.text())
            self.ocr.output_formats = output_formats
            dpi_text = self.dpi_combo.currentText()
            if dpi_text == "Auto":
                dpi_value = None
            else:
                try:
                    dpi_value = int(dpi_text)
                except Exception:
                    dpi_value = None
            self.ocr.dpi = dpi_value
            path = self.selected_paths['folder']
            self.ocr.input_path = path
            return 'folder', path
            
        else:  # PDF
            if not self.selected_paths['pdf']:
                raise ValueError("Please select a PDF file")
            if not self.pdf_output_path.text():
                raise ValueError("Please select output directory")
            self.ocr.output_base_dir = Path(self.pdf_output_path.text())
            self.ocr.output_formats = output_formats
            dpi_text = self.dpi_combo.currentText()
            if dpi_text == "Auto":
                dpi_value = None
            else:
                try:
                    dpi_value = int(dpi_text)
                except Exception:
                    dpi_value = None
            self.ocr.dpi = dpi_value
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
        """Update progress with live file display"""
        try:
            # Show "Starting processing..." at the beginning
            if current_file == 0:
                self.current_file_label.setText("Starting processing...")
            else:
                # Show the correct file name based on progress
                if hasattr(self, '_files_to_process') and len(self._files_to_process) >= current_file:
                    file_idx = current_file - 1
                    if 0 <= file_idx < len(self._files_to_process):
                        filename = Path(self._files_to_process[file_idx]).name
                        self.current_file_label.setText(f"Processing: {filename}")
                    else:
                        self.current_file_label.setText("Processing...")
                else:
                    self.current_file_label.setText("Processing...")

            # Update progress counts
            self.processed_files = current_file
            self.total_files = total_files if total_files > 0 else self.total_files
            
            # Calculate and update progress
            if self.total_files > 0:
                progress = int((current_file / self.total_files) * 100)
                self.overall_progress.setValue(progress)
                self.overall_progress_label.setText(
                    f"Files Processed: {current_file}/{self.total_files}"
                )
            
            # Force GUI update
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error updating progress: {e}")

    def _process_finished(self, success):
        """Handle process completion"""
        try:
            # Stop timers but keep current progress visible
            self.sync_timer.stop()
            self.progress_monitor.stop()
            self.update_timer.stop()
            self.progress_timer.stop()
            
            # Keep progress visible while showing completion message
            if success and not self.ocr.is_cancelled:
                # Show completion message and wait for user response
                QMessageBox.information(self, "Success", "Processing completed successfully!")
            
            # Only reset the state after user has seen completion message
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.current_file_label.setText("No file processing")
            self.overall_progress_label.setText("Total Progress: 0/0") 
            self.overall_progress.setValue(0)
            
            # Clear internal state
            self.processed_files = 0
            self.total_files = 0
            self.last_progress = 0
            self.file_tracking['current'] = None
            self.file_tracking['processed'].clear()
            
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error during process completion: {e}")
            self._reset_processing_state()

    def _update_hardware_info(self):
        """Update hardware info display with better error handling and GPU memory tracking"""
        try:
            if hasattr(self, 'ocr'):
                device = getattr(self.ocr, 'device', 'cpu')  # Default to CPU if device not set
                
                # GPU Mode
                if device == "cuda" and torch.cuda.is_available():
                    self.device_label.setText("Processing Device: GPU")
                    
                    try:
                        # Try NVML first
                        if self.nvml_initialized:
                            import pynvml
                            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                            util_rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
                            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                            
                            gpu_util = util_rates.gpu if util_rates else 0
                            used_mb = mem_info.used / (1024*1024)
                            total_mb = mem_info.total / (1024*1024)
                            
                            self.cpu_label.setText(f"GPU Usage: {gpu_util}%")
                            self.memory_label.setText(f"GPU Memory: {used_mb:.0f}MB/{total_mb:.0f}MB")
                        
                        # Try GPUtil as fallback
                        else:
                            import GPUtil
                            gpus = GPUtil.getGPUs()
                            if gpus:
                                gpu = gpus[0]
                                self.cpu_label.setText(f"GPU Usage: {gpu.load * 100:.1f}%")
                                self.memory_label.setText(
                                    f"GPU Memory: {gpu.memoryUsed:.0f}MB/{gpu.memoryTotal:.0f}MB"
                                )
                            else:
                                raise RuntimeError("No GPU detected by GPUtil")
                                
                    except Exception:
                        # Fallback to basic PyTorch info
                        try:
                            allocated = torch.cuda.memory_allocated(0) / (1024*1024)
                            total = torch.cuda.get_device_properties(0).total_memory / (1024*1024)
                            self.cpu_label.setText("GPU Usage: N/A")
                            self.memory_label.setText(f"GPU Memory: {allocated:.0f}MB/{total:.0f}MB")
                        except Exception as e:
                            self.cpu_label.setText("GPU Usage: Error")
                            self.memory_label.setText("GPU Memory: Error")
                            logger.error(f"Failed to get GPU metrics: {e}")
                
                # CPU Mode
                else:
                    self.device_label.setText("Processing Device: CPU")
                    try:
                        cpu_percent = psutil.cpu_percent(interval=None)
                        memory = psutil.virtual_memory()
                        self.cpu_label.setText(f"CPU Usage: {cpu_percent}%")
                        self.memory_label.setText(f"Memory: {memory.percent}%")
                    except Exception as e:
                        logger.error(f"Failed to get CPU metrics: {e}")
                        self.cpu_label.setText("CPU Usage: Error")
                        self.memory_label.setText("Memory: Error")
                        
            else:
                self.device_label.setText("Processing Device: Initializing...")
                self.cpu_label.setText("Usage: N/A")
                self.memory_label.setText("Memory: N/A")
                
        except Exception as e:
            logger.error(f"Error in hardware monitoring: {e}")
            self.device_label.setText("Device: Error")
            self.cpu_label.setText("Usage: Error")
            self.memory_label.setText("Memory: Error")

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
        """Save settings to config.ini (replaces settings.json)"""
        try:
            self._save_config()
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
                <li>Supports multiple image formats (JPG, PNG, TIFF, PDF, etc.)</li>
                <li>Exports searchable PDF and HOCR</li>
                <li>Batch processing for folders</li>
                <li>GPU acceleration when available</li>
                <li>Dark, light, and night mode themes</li>
                <li>User-selectable DocTR detection and recognition models (auto-download if missing)</li>
                <li>Configurable DPI, output format, and PDF compression (JPEG, JPEG2000, LZW, PNG)</li>
                <li>Ghostscript auto-detection (PATH or Program Files, highest version used)</li>
                <li>Performance tuning: thread count and timeouts</li>
                <li>Remembers last used paths and settings</li>
                <li>Real-time progress and current file display</li>
                <li>Robust error handling and safe resource cleanup</li>
                               <li>Logging to file for troubleshooting</li>
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

    def _check_real_progress(self):
        """Monitor actual progress by checking processed files"""
        try:
            if not hasattr(self.ocr, '_processed_files'):
                return

            # Get actual count from OCR
            real_count = len(self.ocr._processed_files)
            
            # Update progress if count has changed
            if real_count != self.processed_files:
                self.processed_files = real_count
                self.max_processed = max(self.max_processed, real_count)
                
                # Update progress display
                if self.total_files > 0:
                    progress = int((real_count / self.total_files) * 100)
                    self.overall_progress.setValue(progress)
                    self.overall_progress_label.setText(
                        f"Files Processed: {real_count}/{self.total_files}"
                    )
                    
                    # Log progress change
                    logger.debug(f"Real progress update: {real_count}/{self.total_files}")
            
            # Update current file display
            if hasattr(self.ocr, 'current_file') and self.ocr.current_file:
                current = Path(self.ocr.current_file)
                if current.name != getattr(self, '_last_displayed_file', None):
                    self.current_file_label.setText(f"Processing: {current.name}")
                    self._last_displayed_file = current.name
            
            QApplication.processEvents()
            
        except Exception as e:
            logger.error(f"Error checking real progress: {e}")

    def _delayed_init(self):
        """Initialize heavy components after window is shown"""
        try:
            # Only download the default models from config.ini or hardcoded defaults at startup
            self._populate_model_dropdowns(download_missing="startup")
            # Initialize OCR processor with selected models from config.ini or hardcoded defaults
            det_model = self._config_values.get("detection_model") or "db_resnet50"
            rec_model = self._config_values.get("recognition_model") or "parseq"
            self.ocr = OCRProcessor(
                detection_model=det_model,
                recognition_model=rec_model
            )
            # Set compression defaults
            self.ocr.compress_images = self.compress_checkbox.isChecked()
            self.ocr.compression_type = self.compression_type_combo.currentText().lower()
            self.ocr.compression_quality = self.quality_slider.value()
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

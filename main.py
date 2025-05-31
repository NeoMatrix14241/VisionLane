# main.py

import sys
import os

# Note: DocTR setup will be done during splash screen loading for better user visibility

# Minimize imports at the top level to speed up initial loading
from PyQt6.QtWidgets import QApplication, QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QCoreApplication, QTimer, Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor
import traceback
# Import these critical modules at the top level
import logging
from multiprocessing import freeze_support

from utils.parallel_loader import StartupLoader
from utils.system_diagnostics import SystemDiagnostics


class FastSplashScreen(QSplashScreen):
    """A minimal splash screen that matches the design of the main SplashScreen"""
    def __init__(self, app):
        # Add window flags to prevent disappearing when clicked
        super().__init__(flags=Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        
        # Create a pixmap with the same design as splash_screen.py
        pixmap = QPixmap(QSize(400, 200))
        pixmap.fill(Qt.GlobalColor.white)
        self.setPixmap(pixmap)
        
        # Create widget to hold content
        self.content = QWidget(self)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(20, 20, 20, 20)  # Add margins for better appearance
        
        # Add title with the same styling
        title = QLabel("VisionLane OCR")
        title.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Add status label with the same styling
        self.status_label = QLabel("Starting application...")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #34495E;
                font-size: 12px;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Add progress bar with the same styling
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #BDC3C7;
                border-radius: 5px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #3498DB;
            }
        """)
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(5)  # Start with minimal progress
        layout.addWidget(self.progress)
        
        # Set fixed size for content and splash
        self.content.setFixedSize(400, 200)
        self.setFixedSize(400, 200)
        
        # Center on screen
        screen = app.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        
        # Force content to be visible
        self.content.show()
        self.content.raise_()
        
        # Update layout and process events
        layout.activate()
        self.content.updateGeometry()
        QCoreApplication.processEvents()
        
    def update_status(self, message, progress=None):
        """Update status message and progress bar"""
        self.status_label.setText(message)
        if progress is not None:
            self.progress.setValue(progress)
        self.content.updateGeometry()
        self.repaint()
        QCoreApplication.processEvents()
    
    def paintEvent(self, event):
        """Custom paint event to draw background and border"""
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap())
        painter.setPen(QColor("#BDC3C7"))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
    
    # Override mousePressEvent to prevent splash from disappearing when clicked
    def mousePressEvent(self, event):
        # Just consume the event without doing anything
        event.accept()


def initialize_app():
    """Initialize the application and return the splash screen immediately"""
    # Set up application first - minimal setup
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Create and show a fast splash screen immediately
    splash = FastSplashScreen(app)
    splash.show()
    
    # Force immediate update
    splash.update_status("Starting application...", 5)
    QCoreApplication.processEvents()
    
    return app, splash


def load_real_app(app, fast_splash):
    """Load the real application with enhanced startup system"""
    try:
        # Import enhanced startup system
        from pathlib import Path
        from gui.splash_screen import SplashScreen
        from utils.debug_helper import DebugLogger, CrashHandler
        from utils.startup_cache import startup_cache
        from utils.startup_config import StartupConfig
        from utils.logging_config import setup_logging
        
        # Load startup configuration
        startup_config = StartupConfig()
        
        # Setup logging with startup config
        logger = setup_logging(Path(__file__).parent, startup_config)
        
        # Replace fast splash with the real one
        real_splash = SplashScreen(app)
        real_splash.show()
        fast_splash.close()
        fast_splash.deleteLater()  # Ensure fast splash is properly cleaned up
        
        # Check if we should use parallel loading
        if startup_config.should_use_parallel_loading() and not startup_config.is_fast_startup_mode():
            real_splash.update_status("Initializing parallel loading system...", 5)
            QCoreApplication.processEvents()
            
            # Use parallel loading system
            loader = StartupLoader(
                progress_callback=lambda msg: real_splash.update_status(f"Parallel: {msg}", None)
            )
            
            # Setup tasks based on configuration
            config_path = Path(__file__).parent / "config.ini"
            loader.setup_loading_tasks(config_path)
            
            # Load with timeout
            timeout = startup_config.get_startup_timeout()
            results = loader.load_all(timeout=timeout)
            
            # Update progress based on results
            summary = loader.loader.get_loading_summary()
            if summary['success_rate'] > 0.8:  # 80% success rate
                real_splash.update_status("✓ Parallel loading completed successfully", 50)
            else:
                real_splash.update_status(f"⚠ Parallel loading completed ({summary['failed']} issues)", 50)
            
            QCoreApplication.processEvents()
            
        else:
            # Use traditional sequential loading
            real_splash.update_status("Starting sequential loading...", 5)
            QCoreApplication.processEvents()
            
            current_progress = 5
            
            # System diagnostics (if not skipped)
            if not startup_config.should_skip_system_diagnostics():
                real_splash.update_status("Running system diagnostics...", current_progress)
                QCoreApplication.processEvents()
                
                diagnostics = SystemDiagnostics(
                    progress_callback=lambda msg: real_splash.update_status(f"Diagnostics: {msg}", None)
                )
                
                # Use quick diagnostics if minimal mode
                diag_results = diagnostics.run_diagnostics(quick=startup_config.use_minimal_diagnostics())
                
                # Cache diagnostics if enabled
                if startup_config.should_cache_results():
                    startup_cache.cache_system_info(diag_results)
                
                current_progress = 10
                
                # Show diagnostics summary if detailed progress enabled
                if startup_config.should_show_detailed_progress():
                    summary = diagnostics.get_diagnostic_summary(diag_results)
                    real_splash.update_status(f"✓ System: {summary[:50]}...", current_progress)
                else:
                    real_splash.update_status("✓ System diagnostics complete", current_progress)
                
                QCoreApplication.processEvents()
            
            # DocTR setup (if not skipped)
            if not startup_config.should_skip_doctr_check():
                real_splash.update_status("Setting up DocTR...", current_progress)
                QCoreApplication.processEvents()
                
                try:
                    import doctr_torch_setup
                    
                    # Create progress callback
                    def doctr_progress_callback(message):
                        nonlocal current_progress
                        current_progress = min(current_progress + 0.5, 25)
                        real_splash.update_status(f"DocTR: {message}", int(current_progress))
                        QCoreApplication.processEvents()
                    
                    setup_success = doctr_torch_setup.setup_doctr_with_progress(
                        progress_callback=doctr_progress_callback,
                        use_cache=startup_config.should_cache_results(),
                        detailed_progress=startup_config.should_show_detailed_progress()
                    )
                    
                    current_progress = 25
                    
                    if setup_success:
                        real_splash.update_status("✓ DocTR setup completed", current_progress)
                    else:
                        real_splash.update_status("⚠ DocTR setup completed with warnings", current_progress)
                    
                    QCoreApplication.processEvents()
                    
                except ImportError as e:
                    real_splash.update_status("⚠ DocTR setup not found, continuing...", current_progress)
                    QCoreApplication.processEvents()
                    print(f"Warning: DocTR torch setup not found: {e}")
                except Exception as e:
                    real_splash.update_status(f"⚠ DocTR setup error: {str(e)[:30]}...", current_progress)
                    QCoreApplication.processEvents()
                    print(f"Error in DocTR setup: {e}")
            
            # Model handling
            if startup_config.should_auto_download_models() and not startup_config.should_skip_model_validation():
                real_splash.update_status("Checking models...", current_progress)
                QCoreApplication.processEvents()
                
                # Use enhanced model downloader
                from utils.model_downloader import EnhancedModelManager
                
                model_manager = EnhancedModelManager(
                    progress_callback=lambda msg: real_splash.update_status(f"Models: {msg}", None)
                )
                
                # Get model configuration
                models_config = startup_config.get_models_config()
                det_model = models_config['detection_model']
                rec_model = models_config['recognition_model']
                
                # Allocate progress for model downloads (current_progress to 70%)
                model_progress_start = current_progress
                model_progress_total = 70 - current_progress
                model_progress_per_model = model_progress_total // 2
                
                # Download detection model
                real_splash.update_status(f"Downloading {det_model} (detection)...", model_progress_start + 5)
                QCoreApplication.processEvents()
                
                det_success = model_manager.download_model_if_needed(det_model, "detection")
                current_progress = model_progress_start + model_progress_per_model
                
                if det_success:
                    real_splash.update_status(f"✓ {det_model} (detection) ready", current_progress)
                else:
                    real_splash.update_status(f"⚠ {det_model} download issue", current_progress)
                QCoreApplication.processEvents()
                
                # Download recognition model
                real_splash.update_status(f"Downloading {rec_model} (recognition)...", current_progress + 5)
                QCoreApplication.processEvents()
                
                rec_success = model_manager.download_model_if_needed(rec_model, "recognition")
                current_progress = 70
                
                if rec_success:
                    real_splash.update_status(f"✓ {rec_model} (recognition) ready", current_progress)
                else:
                    real_splash.update_status(f"⚠ {rec_model} download issue", current_progress)
                QCoreApplication.processEvents()
                
                if det_success and rec_success:
                    real_splash.update_status("✓ All models ready", current_progress)
                else:
                    real_splash.update_status("⚠ Some model issues detected", current_progress)
                
                QCoreApplication.processEvents()
        
        # Continue with the main application logic
        main(app, real_splash, startup_config)
        
    except Exception as e:
        print(f"Error during enhanced application loading: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to basic loading
        try:
            main(app, real_splash)
        except:
            # If even fallback fails, exit gracefully
            print("Critical startup failure, exiting...")
            sys.exit(1)


def main(app, splash, startup_config=None):
    debug_logger = None
    window = None
    try:
        from pathlib import Path
        from utils.debug_helper import DebugLogger, CrashHandler        # --- Enhanced Model Check and Download with Configuration ---
        # Skip model check if parallel loading already handled it
        if startup_config and startup_config.should_use_parallel_loading():
            splash.update_status("Models handled by parallel loader", 50)
            QCoreApplication.processEvents()
        elif startup_config and startup_config.should_skip_model_validation():
            splash.update_status("Model validation skipped by configuration", 50)
            QCoreApplication.processEvents()
        else:
            splash.update_status("Checking OCR models...", 20)
            QCoreApplication.processEvents()

            import doctr.models as doctr_models
            import configparser
            from pathlib import Path
            from utils.startup_cache import get_cached_models_status, cache_models_status

            # Get model configuration
            if startup_config:
                models_config = startup_config.get_models_config()
                det_model = models_config['detection_model']
                rec_model = models_config['recognition_model']
            else:
                # Fallback to reading config directly
                config_path = Path(__file__).parent / "config.ini"
                config = configparser.ConfigParser()
                config.read(config_path, encoding="utf-8")
                det_model = config.get("General", "detection_model", fallback="db_resnet50")
                rec_model = config.get("General", "recognition_model", fallback="parseq")

            cache_dir = Path.home() / ".cache" / "doctr" / "models"

            def model_exists(name):
                return any(p.name.split('-')[0] == name for p in cache_dir.glob("*.pt"))

            # Check cached model status first (if caching enabled)
            use_cache = not startup_config or startup_config.should_cache_results()
            cached_models = get_cached_models_status() if use_cache else None
            
            required_models = [
                (det_model, "Text Detection", "detection"),
                (rec_model, "Text Recognition", "recognition")
            ]
            
            # Verify cached results are still valid
            models_still_cached = False
            if cached_models and use_cache:
                models_still_cached = all(
                    cached_models.get(model_name, False) and model_exists(model_name)
                    for model_name, _, _ in required_models
                )
            
            if models_still_cached:
                splash.update_status("✓ All OCR models ready (cached)", 50)
                QCoreApplication.processEvents()
            else:
                # Use enhanced model downloader if available
                try:
                    from utils.model_downloader import EnhancedModelManager
                    
                    model_manager = EnhancedModelManager(
                        progress_callback=lambda msg: splash.update_status(f"Models: {msg}", None)
                    )
                    
                    progress = 20
                    progress_step = 15  # Each model gets 15% of progress
                    
                    for i, (model_name, model_desc, model_type) in enumerate(required_models):
                        progress_start = progress + (i * progress_step)
                        progress_end = progress_start + progress_step
                        
                        if not model_exists(model_name):
                            # Check if auto-download is enabled
                            if not startup_config or startup_config.should_auto_download_models():
                                success = model_manager.download_model_if_needed(model_name, model_type)
                                if success:
                                    splash.update_status(f"✓ {model_name} ({model_desc}) ready", progress_end)
                                else:
                                    splash.update_status(f"⚠ {model_name} download issue", progress_end)
                            else:
                                splash.update_status(f"⚠ {model_name} not found (auto-download disabled)", progress_end)
                        else:
                            splash.update_status(f"✓ {model_name} ({model_desc}) found", progress_end)
                        
                        QCoreApplication.processEvents()
                    
                    # Cache model status if enabled
                    if use_cache:
                        models_status = {model_name: model_exists(model_name) for model_name, _, _ in required_models}
                        cache_models_status(models_status)
                    
                except ImportError:
                    # Fallback to original download method with proper async handling
                    def download_model_with_progress(model_name, model_desc, model_type, progress_start, progress_end):
                        """Download model with detailed progress updates and async handling"""
                        try:
                            splash.update_status(f"Preparing {model_name} download...", progress_start)
                            QCoreApplication.processEvents()
                            
                            # Import required modules for async download
                            import threading
                            import time
                            from queue import Queue, Empty
                            
                            # Progress tracking
                            progress_queue = Queue()
                            download_complete = threading.Event()
                            download_success = threading.Event()
                            error_message = None
                            
                            def download_worker():
                                """Worker thread for downloading model"""
                                nonlocal error_message
                                try:
                                    progress_queue.put(("Initializing download...", 5))
                                    
                                    # Actually download the model
                                    if model_type == "detection":
                                        progress_queue.put((f"Loading {model_name} detection model...", 20))
                                        getattr(doctr_models.detection, model_name)(pretrained=True)
                                    else:
                                        progress_queue.put((f"Loading {model_name} recognition model...", 20))
                                        getattr(doctr_models.recognition, model_name)(pretrained=True)
                                    
                                    progress_queue.put((f"Model {model_name} loaded successfully", 95))
                                    download_success.set()
                                    
                                except Exception as e:
                                    error_message = str(e)
                                    progress_queue.put((f"Error downloading {model_name}: {str(e)[:30]}...", 0))
                                finally:
                                    download_complete.set()
                            
                            # Start download in background thread
                            download_thread = threading.Thread(target=download_worker, daemon=True)
                            download_thread.start()
                            
                            # Progress simulation with real updates
                            progress_steps = [
                                (f"Connecting to model repository...", 10),
                                (f"Downloading {model_name} metadata...", 15),
                                (f"Downloading {model_name} weights... (0%)", 20),
                                (f"Downloading {model_name} weights... (25%)", 35),
                                (f"Downloading {model_name} weights... (50%)", 50),
                                (f"Downloading {model_name} weights... (75%)", 70),
                                (f"Downloading {model_name} weights... (95%)", 85),
                                (f"Finalizing {model_name} installation...", 90),
                            ]
                            
                            current_step = 0
                            step_delay = 0.5  # 500ms between steps
                            max_wait_time = 300  # 5 minutes maximum wait
                            start_time = time.time()
                            
                            while not download_complete.is_set() and (time.time() - start_time) < max_wait_time:
                                # Check for real progress updates
                                try:
                                    msg, prog = progress_queue.get_nowait()
                                    current_progress = progress_start + ((progress_end - progress_start) * prog / 100)
                                    splash.update_status(msg, int(current_progress))
                                    QCoreApplication.processEvents()
                                except Empty:
                                    # No real update, use simulated progress
                                    if current_step < len(progress_steps):
                                        step_msg, step_prog = progress_steps[current_step]
                                        current_progress = progress_start + ((progress_end - progress_start) * step_prog / 100)
                                        splash.update_status(step_msg, int(current_progress))
                                        QCoreApplication.processEvents()
                                        current_step += 1
                                
                                time.sleep(step_delay)
                            
                            # Wait for download to complete with timeout
                            if download_complete.wait(timeout=10):
                                if download_success.is_set():
                                    splash.update_status(f"✓ {model_name} ({model_desc}) ready", progress_end)
                                    QCoreApplication.processEvents()
                                    return True
                                else:
                                    splash.update_status(f"✗ Failed to download {model_name}: {error_message[:30] if error_message else 'Unknown error'}...", progress_end)
                                    QCoreApplication.processEvents()
                                    return False
                            else:
                                # Timeout occurred
                                splash.update_status(f"⚠ {model_name} download timeout, but may continue in background", progress_end)
                                QCoreApplication.processEvents()
                                return False
                            

                        except Exception as e:
                            splash.update_status(f"✗ Failed to download {model_name}: {str(e)[:30]}...", progress_end)
                            QCoreApplication.processEvents()
                            return False
                    
                    # Better progress allocation for models (20-70%)
                    progress = 20
                    total_model_progress = 50  # 70 - 20 = 50% for models
                    progress_per_model = total_model_progress // len(required_models)

                    for i, (model_name, model_desc, model_type) in enumerate(required_models):
                        progress_start = progress + (i * progress_per_model)
                        progress_end = progress_start + progress_per_model
                        
                        splash.update_status(f"Checking {model_name} ({model_desc})...", progress_start)
                        QCoreApplication.processEvents()
                        
                        if not model_exists(model_name):
                            # Check if auto-download is enabled
                            if not startup_config or startup_config.should_auto_download_models():
                                splash.update_status(f"Model {model_name} not found, downloading...", progress_start + 2)
                                QCoreApplication.processEvents()
                                
                                success = download_model_with_progress(model_name, model_desc, model_type, progress_start, progress_end)
                                if not success:
                                    splash.update_status(f"⚠ {model_name} download had issues, continuing...", progress_end)
                                    QCoreApplication.processEvents()
                            else:
                                splash.update_status(f"⚠ {model_name} not found (auto-download disabled)", progress_end)
                                QCoreApplication.processEvents()
                        else:
                            splash.update_status(f"✓ {model_name} ({model_desc}) found", progress_end)
                            QCoreApplication.processEvents()
                
                splash.update_status("All OCR models processed", 70)
                QCoreApplication.processEvents()
        # --- End Enhanced Model Check ---

        splash.update_status("Loading core modules...", 75)
        QCoreApplication.processEvents()
        
        splash.update_status("Loading utilities...", 80)
        QCoreApplication.processEvents()
        
        splash.update_status("Initializing logging...", 85)
        QCoreApplication.processEvents()
        
        logger = logging.getLogger(__name__)
        debug_logger = DebugLogger()
        
        splash.update_status("Configuring system...", 90)
        QCoreApplication.processEvents()
        
        logger.info("Initializing application")
        logger.debug(f"Python executable: {sys.executable}")
        logger.debug(f"Working directory: {os.getcwd()}")
        
        base_dir = Path(__file__).parent.resolve()
        
        splash.update_status("Loading main window...", 95)
        QCoreApplication.processEvents()
        from gui.main_window import MainWindow
        window = MainWindow()
        
        app.window = window
        app._cleanup_done = False
        
        def cleanup_on_exit():
            if not app._cleanup_done:
                try:
                    logger.info("Application cleanup started")
                    if window:
                        # Stop all processing and timers
                        window._stop_all_timers()
                        if hasattr(window, 'current_worker') and window.current_worker:
                            window.current_worker.stop(force=True)
                        
                        # Clean up resources
                        window._cleanup_resources()
                        window.close()
                    
                    # Kill any child processes
                    import psutil
                    current_process = psutil.Process()
                    children = current_process.children(recursive=True)
                    for child in children:
                        try:
                            child.terminate()
                            child.wait(timeout=2)
                        except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                            try:
                                child.kill()
                            except psutil.NoSuchProcess:
                                pass
                        except Exception:
                            pass
                    
                    logger.info("Application cleanup completed")
                except Exception as e:
                    print(f"Error during cleanup: {e}")
                finally:
                    app._cleanup_done = True

        app.aboutToQuit.connect(cleanup_on_exit)
        
        splash.update_status("Finalizing interface...", 98)
        QCoreApplication.processEvents()
        
        # Don't hide window initially - let splash finish first
        splash.update_status("Ready!", 100)
        QCoreApplication.processEvents()
        
        # Small delay to show completion
        import time
        time.sleep(0.5)
        
        # Show window first, then close splash
        window.show()
        window.activateWindow()
        window.raise_()
        QCoreApplication.processEvents()
        
        # Use a longer delay to ensure window is fully rendered
        def close_splash():
            try:
                splash.close()
                splash.deleteLater()
            except:
                pass
        
        QTimer.singleShot(200, close_splash)
        
        if logger:
            logger.info("Starting Qt event loop")
        
        return None
        
    except Exception as e:
        if debug_logger and debug_logger.crash_handler:
            debug_logger.crash_handler.handle_exception(type(e), e, e.__traceback__)
        try:
            if 'logger' in locals():
                logger.error(f"Failed to start: {e}")
                logger.error("Stack trace:", exc_info=True)
        except:
            print(f"Failed to start: {e}")
            traceback.print_exc()


if __name__ == '__main__':
    freeze_support()
    try:
        # Initialize app and show splash
        app, fast_splash = initialize_app()
        
        # Use QTimer to defer loading rest of application
        QTimer.singleShot(0, lambda: load_real_app(app, fast_splash))
        
        # Start the event loop just once
        exit_code = app.exec()
        
        # Force exit with proper cleanup
        try:
            sys.exit(exit_code)
        except SystemExit:
            os._exit(exit_code)
        
    except Exception as e:
        print(f"Fatal error during startup: {e}")
        print(traceback.format_exc())
        try:
            sys.exit(1)
        except:
            os._exit(1)
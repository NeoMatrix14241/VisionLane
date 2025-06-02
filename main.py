# main.py
import sys
import os
# Set environment variables IMMEDIATELY
os.environ['USE_TORCH'] = '1'
os.environ['DOCTR_BACKEND'] = 'torch'
def show_instant_splash():
    """Show splash screen with ABSOLUTE minimal imports - appears instantly"""
    # Only import what's absolutely necessary for the splash
    from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QProgressBar
    from PyQt6.QtCore import Qt, QCoreApplication
    from PyQt6.QtGui import QFont
    # Create app immediately
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    # Create a simple splash screen widget immediately
    splash_widget = QWidget()
    splash_widget.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    # Enable translucent background to allow rounded corners
    splash_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    splash_widget.resize(450, 320)
    # Center the splash screen
    screen = app.primaryScreen().geometry()
    splash_widget.move(
        (screen.width() - splash_widget.width()) // 2,
        (screen.height() - splash_widget.height()) // 2
    )
    # Create inner container for rounded background
    container = QWidget(splash_widget)
    container.setGeometry(0, 0, 450, 320)
    container.setStyleSheet("""
        QWidget {
            background-color: white;
            border: 3px solid #2196F3;
            border-radius: 15px;
        }
    """)
    # Create layout for the container
    layout = QVBoxLayout(container)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(20)
    layout.setContentsMargins(40, 40, 40, 40)
    # Title with better styling
    title_label = QLabel("VisionLane OCR")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_font = QFont()
    title_font.setPointSize(26)
    title_font.setBold(True)
    title_label.setFont(title_font)
    title_label.setStyleSheet("""
        QLabel {
            color: #2196F3;
            background-color: transparent;
            padding: 15px;
            font-weight: bold;
        }
    """)
    # Status label with better contrast
    status_label = QLabel("Initializing...")
    status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status_font = QFont()
    status_font.setPointSize(13)
    status_label.setFont(status_font)
    status_label.setStyleSheet("""
        QLabel {
            color: #555555;
            background-color: transparent;
            padding: 10px;
            font-weight: normal;
        }
    """)
    # Progress bar with better contrast
    progress_bar = QProgressBar()
    progress_bar.setRange(0, 100)
    progress_bar.setValue(0)
    progress_bar.setTextVisible(True)
    progress_bar.setStyleSheet("""
        QProgressBar {
            border: 2px solid #DDDDDD;
            border-radius: 10px;
            text-align: center;
            font-weight: bold;
            color: #333333;
            background-color: #FFFFFF;
            height: 30px;
            font-size: 11px;
        }
        QProgressBar::chunk {
            background-color: #2196F3;
            border-radius: 8px;
            margin: 1px;
        }
    """)
    # Add widgets to layout
    layout.addWidget(title_label)
    layout.addWidget(status_label)
    layout.addWidget(progress_bar)
    # Make the main splash widget transparent (rounded corners will come from container)
    splash_widget.setStyleSheet("""
        QWidget {
            background-color: transparent;
        }
    """)
    # Show splash immediately
    splash_widget.show()
    splash_widget.raise_()
    splash_widget.activateWindow()
    # Force immediate rendering
    app.processEvents()
    QCoreApplication.processEvents()
    print("✓ Splash screen shown instantly!")
    # Create update function
    def update_splash_status(message, progress=0):
        status_label.setText(message)
        progress_bar.setValue(progress)
        progress_bar.setFormat(f"{progress}% - {message}")
        app.processEvents()
        QCoreApplication.processEvents()
    # Store references in app for later use
    app.splash_widget = splash_widget
    app.update_splash_status = update_splash_status
    return app
def load_modules_progressively(app):
    """Load all heavy modules one by one with progress updates"""
    import sys
    try:
        update_status = app.update_splash_status
        # Module loading progress tracking
        modules_to_load = [
            ("PyQt6 core modules", 5),
            ("doctr_patch", 15),
            ("doctr_torch_setup", 25),
            ("Debug utilities", 30),
            ("Startup configuration", 35),
            ("Logging system", 40),
            ("System diagnostics", 50),
            ("Model management", 60),
            ("Main application", 85),
            ("User interface", 95)
        ]
        current_step = 0        # 1. Load basic PyQt6 modules
        update_status("Loading PyQt6 core modules...", modules_to_load[current_step][1])
        import time
        time.sleep(0.1)  # Brief pause to show progress
        current_step += 1
        # 2. Load CUDA patches FIRST
        update_status("Loading CUDA compatibility patches...", modules_to_load[current_step][1])
        try:
            # Import for validation but don't use directly
            import core.cuda_patch_wrapper
            update_status("✓ CUDA patches loaded successfully", modules_to_load[current_step][1])
            time.sleep(0.1)
        except ImportError as e:
            update_status("⚠ CUDA patches not found", modules_to_load[current_step][1])
            print(f"CUDA patch import error: {e}")
            time.sleep(0.1)
        # 3. Load doctr_patch NEXT to ensure proper mocking
        update_status("Loading DocTR patch system...", modules_to_load[current_step][1])
        doctr_patch = None
        try:
            from core import doctr_patch
            update_status("✓ DocTR patch loaded successfully", modules_to_load[current_step][1])
            time.sleep(0.1)
        except ImportError as e:
            update_status("⚠ DocTR patch not found", modules_to_load[current_step][1])
            print(f"DocTR patch import error: {e}")
            time.sleep(0.1)
        current_step += 1
        # 4. Load doctr_torch_setup with enhanced mocking
        update_status("Loading DocTR torch setup...", modules_to_load[current_step][1])
        doctr_torch_setup = None
        try:
            from core import doctr_torch_setup
            # Ensure the mock has all required constants
            if 'doctr.file_utils' in sys.modules:
                file_utils = sys.modules['doctr.file_utils']
                if not hasattr(file_utils, 'ENV_VARS_TRUE_VALUES'):
                    file_utils.ENV_VARS_TRUE_VALUES = ['TRUE', 'True', 'true', '1', 'YES', 'Yes', 'yes']
                    print("DocTR Setup: Added missing ENV_VARS_TRUE_VALUES to mock")
            update_status("✓ DocTR torch setup loaded", modules_to_load[current_step][1])
            time.sleep(0.1)
        except ImportError as e:
            update_status("⚠ DocTR torch setup not found", modules_to_load[current_step][1])
            print(f"DocTR torch setup import error: {e}")
            time.sleep(0.1)
        current_step += 1        # 4. Load debug utilities
        update_status("Loading debug utilities...", modules_to_load[current_step][1])
        from pathlib import Path
        # Import for module loading but don't assign variables
        import utils.debug_helper
        time.sleep(0.1)
        current_step += 1        # 5. Load startup configuration
        update_status("Loading startup configuration...", modules_to_load[current_step][1])
        # Import for cache initialization
        import utils.startup_cache
        from utils.startup_config import StartupConfig
        startup_config = StartupConfig()
        time.sleep(0.1)
        current_step += 1
        # 6. Setup logging        update_status("Initializing logging system...", modules_to_load[current_step][1])
        from utils.logging_config import setup_logging
        logger = setup_logging(Path(__file__).parent, startup_config)
        logger.info("Progressive module loading started")
        time.sleep(0.1)
        current_step += 1
        # 7. System diagnostics (if needed)
        update_status("Running system diagnostics...", modules_to_load[current_step][1])
        if not startup_config.should_skip_system_diagnostics():
            from utils.system_diagnostics import SystemDiagnostics
            diagnostics = SystemDiagnostics()
            diag_results = diagnostics.run_diagnostics(quick=True)
            update_status("✓ System diagnostics complete", modules_to_load[current_step][1])
        else:
            update_status("System diagnostics skipped", modules_to_load[current_step][1])
        time.sleep(0.1)
        current_step += 1
        # 8. Model management
        update_status("Checking OCR models...", modules_to_load[current_step][1])
        if startup_config.should_auto_download_models():
            try:
                from utils.model_downloader import EnhancedModelManager
                model_manager = EnhancedModelManager()
                update_status("✓ Model system ready", modules_to_load[current_step][1])
            except ImportError:
                update_status("Model downloader not available", modules_to_load[current_step][1])
        else:
            update_status("Model validation skipped", modules_to_load[current_step][1])
        time.sleep(0.1)
        current_step += 1        # 9. Load main application
        update_status("Loading main application...", modules_to_load[current_step][1])
        # Import for module loading
        import gui.main_window
        time.sleep(0.1)
        current_step += 1
        # 10. Finalize UI
        update_status("Finalizing user interface...", modules_to_load[current_step][1])
        time.sleep(0.1)
        # Final status
        update_status("VisionLane OCR ready!", 100)
        time.sleep(0.3)
        # Now launch the main application
        launch_main_application(app, startup_config, logger)
    except Exception as e:
        print(f"Error during progressive loading: {e}")
        import traceback
        traceback.print_exc()
        # Create emergency mock before fallback
        try:
            import sys
            import types
            # Create comprehensive mock with all required constants
            if 'doctr.file_utils' not in sys.modules:
                print("Creating emergency DocTR file_utils mock...")
                file_utils_mock = types.ModuleType('doctr.file_utils')
                file_utils_mock.is_torch_available = lambda: True
                file_utils_mock.is_tf_available = lambda: False
                file_utils_mock._TORCH_AVAILABLE = True
                file_utils_mock._TF_AVAILABLE = False
                file_utils_mock.ENV_VARS_TRUE_VALUES = ['TRUE', 'True', 'true', '1', 'YES', 'Yes', 'yes']
                file_utils_mock.requires_package = lambda package_name, error_msg=None: lambda func: func
                file_utils_mock.CLASS_NAME = 'MockClassName'
                sys.modules['doctr.file_utils'] = file_utils_mock
                print("Emergency mock created successfully")
        except Exception as mock_error:
            print(f"Emergency mock creation failed: {mock_error}")
        # Try to launch anyway
        try:
            launch_main_application(app)
        except:
            print("Critical failure, exiting...")
            sys.exit(1)
def launch_main_application(app, startup_config=None, logger=None):
    """Launch the main application window"""
    try:
        update_status = app.update_splash_status
        update_status("Creating main window...", 98)
        # Import main window
        from gui.main_window import MainWindow
        from utils.debug_helper import DebugLogger
        # Create debug logger
        debug_logger = DebugLogger()
        # Create main window
        window = MainWindow()
        # Setup app references
        app.window = window
        app._cleanup_done = False
        # Setup cleanup
        def cleanup_on_exit():
            if not app._cleanup_done:
                try:
                    if logger:
                        logger.info("Application cleanup started")
                    if window:
                        window._stop_all_timers()
                        if hasattr(window, 'current_worker') and window.current_worker:
                            window.current_worker.stop(force=True)
                        window._cleanup_resources()
                        window.close()
                    # Kill child processes
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
                    if logger:
                        logger.info("Application cleanup completed")
                except Exception as e:
                    print(f"Error during cleanup: {e}")
                finally:
                    app._cleanup_done = True
        app.aboutToQuit.connect(cleanup_on_exit)
        update_status("Launching application...", 100)
        # Show main window
        window.show()
        window.activateWindow()
        window.raise_()
        # Process events to ensure window is rendered
        app.processEvents()
        # Close splash after a short delay
        def close_splash():
            try:
                if hasattr(app, 'splash_widget') and app.splash_widget:
                    app.splash_widget.close()
                    app.splash_widget.deleteLater()
                    delattr(app, 'splash_widget')
            except Exception as e:
                print(f"Error closing splash: {e}")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, close_splash)  # 0.5 second delay
        if logger:
            logger.info("Application launched successfully")
        print("✓ VisionLane OCR launched successfully!")
    except Exception as e:
        print(f"Error launching main application: {e}")
        import traceback
        traceback.print_exc()
        # Close splash and exit
        if hasattr(app, 'splash_widget'):
            try:
                app.splash_widget.close()
            except:
                pass
        sys.exit(1)
if __name__ == '__main__':
    try:
        print("Starting VisionLane OCR...")
        # Step 1: Show splash screen INSTANTLY
        app = show_instant_splash()
        # Step 2: Load modules progressively using QTimer (non-blocking)
        def start_progressive_loading():
            load_modules_progressively(app)
        # Use QTimer to start loading after splash is shown
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, start_progressive_loading)  # 100ms delay to ensure splash renders
        # Step 3: Start event loop
        print("Starting Qt event loop...")
        exit_code = app.exec()
        # Step 4: Clean exit
        try:
            sys.exit(exit_code)
        except SystemExit:
            os._exit(exit_code)
    except Exception as e:
        print(f"Fatal startup error: {e}")
        import traceback
        print(traceback.format_exc())
        try:
            sys.exit(1)
        except:
            os._exit(1)

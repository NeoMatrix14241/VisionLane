# main.py

import sys
import os
# Minimize imports at the top level to speed up initial loading
from PyQt6.QtWidgets import QApplication, QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QCoreApplication, QTimer, Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor
import traceback
# Import these critical modules at the top level
import logging
from multiprocessing import freeze_support


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
    """Load the real application with proper splash screen after showing the fast one"""
    try:
        # Now we can import the actual modules needed
        from pathlib import Path
        from gui.splash_screen import SplashScreen
        from utils.debug_helper import DebugLogger, CrashHandler
        
        # Replace fast splash with the real one
        real_splash = SplashScreen(app)
        real_splash.show()
        fast_splash.close()
        
        # Now proceed with the main application logic
        main(app, real_splash)
    except Exception as e:
        print(f"Error during application loading: {e}")
        traceback.print_exc()


def main(app, splash):
    debug_logger = None
    window = None
    try:
        from pathlib import Path
        from utils.debug_helper import DebugLogger, CrashHandler

        # --- DocTR Model Check and Download ---
        splash.update_status("Checking OCR models...", 10)
        QCoreApplication.processEvents()

        import doctr.models as doctr_models
        import configparser

        # Read config.ini for default models, fallback to hardcoded defaults if missing
        config_path = Path(__file__).parent / "config.ini"
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")
        det_model = config.get("General", "detection_model", fallback="db_resnet50")
        rec_model = config.get("General", "recognition_model", fallback="parseq")  # fallback to parseq

        # Enforce hardcoded defaults if config.ini is missing or empty
        if not det_model:
            det_model = "db_resnet50"
        if not rec_model:
            rec_model = "parseq"

        cache_dir = Path.home() / ".cache" / "doctr" / "models"

        def model_exists(name):
            return any(p.name.split('-')[0] == name for p in cache_dir.glob("*.pt"))

        # Only check/download the models specified in config.ini or hardcoded defaults
        required_models = [
            (det_model, "Text Detection", "detection"),
            (rec_model, "Text Recognition", "recognition")
        ]

        progress = 10
        progress_step = 20  # Only two models, so 20 each

        for model_name, model_desc, model_type in required_models:
            if not model_exists(model_name):
                splash.update_status(f"Downloading {model_name} ({model_desc})...", progress)
                QCoreApplication.processEvents()
                try:
                    if model_type == "detection":
                        getattr(doctr_models.detection, model_name)(pretrained=True)
                    else:
                        getattr(doctr_models.recognition, model_name)(pretrained=True)
                    progress += progress_step
                    splash.update_status(f"Downloaded {model_name} ({model_desc})", progress)
                    QCoreApplication.processEvents()
                except Exception as e:
                    splash.update_status(f"Failed to download {model_name}: {e}", 100)
                    QCoreApplication.processEvents()
                    raise RuntimeError(f"Failed to download {model_name}: {e}")
            else:
                splash.update_status(f"{model_name} ({model_desc}) found.", progress)
                QCoreApplication.processEvents()
                progress += progress_step
        splash.update_status("OCR models ready.", 50)
        QCoreApplication.processEvents()
        # --- End DocTR Model Check ---

        splash.update_status("Loading core modules...", 40)
        QCoreApplication.processEvents()
        
        splash.update_status("Loading utilities...", 50)
        QCoreApplication.processEvents()
        
        splash.update_status("Initializing logging...", 60)
        QCoreApplication.processEvents()
        
        logger = logging.getLogger(__name__)
        debug_logger = DebugLogger()
        
        splash.update_status("Configuring system...", 70)
        QCoreApplication.processEvents()
        
        logger.info("Initializing application")
        logger.debug(f"Python executable: {sys.executable}")
        logger.debug(f"Working directory: {os.getcwd()}")
        
        base_dir = Path(__file__).parent.resolve()
        
        splash.update_status("Loading main window...", 80)
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
        
        splash.update_status("Finalizing...", 95)
        QCoreApplication.processEvents()
        window.show()
        splash.finish(window)
        window.activateWindow()
        window.raise_()
        
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
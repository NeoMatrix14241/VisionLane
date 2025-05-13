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
    try:
        # Import necessary modules here rather than at the top
        from pathlib import Path
        from utils.debug_helper import DebugLogger, CrashHandler
        
        # Set up imports with progress updates
        splash.update_status("Loading core modules...", 10)
        QCoreApplication.processEvents()
        
        splash.update_status("Loading utilities...", 20)
        QCoreApplication.processEvents()
        
        # Initialize logging and debug
        splash.update_status("Initializing logging...", 30)
        QCoreApplication.processEvents()
        
        logger = logging.getLogger(__name__)
        debug_logger = DebugLogger()
        
        splash.update_status("Configuring system...", 40)
        QCoreApplication.processEvents()
        
        logger.info("Initializing application")
        logger.debug(f"Python executable: {sys.executable}")
        logger.debug(f"Working directory: {os.getcwd()}")
        
        # Import main window
        splash.update_status("Loading main window...", 60)
        QCoreApplication.processEvents()
        
        from gui.main_window import MainWindow
        window = MainWindow()
        
        # Complete initialization
        splash.update_status("Completing initialization...", 90)
        QCoreApplication.processEvents()
        
        # Show window and close splash more gracefully
        window.show()
        splash.finish(window)
        window.activateWindow()
        window.raise_()
        
        # Store window reference
        app.window = window
        if logger:
            logger.info("Starting Qt event loop")
        
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
    try:
        # Call freeze_support first thing - this is critical for multiprocessing
        freeze_support()
        
        # Initialize app and get basic splash screen with minimal imports
        app, fast_splash = initialize_app()
        
        # Use QTimer to defer the loading of the rest of the application
        # This ensures the splash appears immediately
        QTimer.singleShot(0, lambda: load_real_app(app, fast_splash))
        
        # Start event loop only once
        exit_code = app.exec()
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"Fatal error during startup: {e}")
        print(traceback.format_exc())
        sys.exit(1)
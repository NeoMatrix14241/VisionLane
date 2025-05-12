import sys
import os
from pathlib import Path
import logging
import traceback
from utils.debug_helper import DebugLogger, CrashHandler

# Set up logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure QApplication"""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    
    # Create application
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Log Qt version
    from PyQt6.QtCore import QT_VERSION_STR
    logger.debug(f"Qt Version: {QT_VERSION_STR}")
    
    return app

def main():
    debug_logger = None
    try:
        # Initialize debug logging first
        debug_logger = DebugLogger()
        
        logger.info("Initializing application")
        app = create_app()
        
        # Log startup details
        logger.debug(f"Python executable: {sys.executable}")
        logger.debug(f"Working directory: {os.getcwd()}")
        
        # Create and show main window
        from gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        window.activateWindow()
        window.raise_()
        
        # Store window reference and start event loop
        app.window = window
        logger.info("Starting Qt event loop")
        return app.exec()
        
    except Exception as e:
        if debug_logger and debug_logger.crash_handler:
            debug_logger.crash_handler.handle_exception(type(e), e, e.__traceback__)
        logger.error(f"Failed to start: {e}")
        logger.error("Stack trace:", exc_info=True)
        return 1

if __name__ == '__main__':
    try:
        exit_code = main()
        logger.debug(f"Application exited with code {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

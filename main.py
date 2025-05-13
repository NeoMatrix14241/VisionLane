import sys
import os
from pathlib import Path
import logging
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QCoreApplication
from gui.splash_screen import SplashScreen
from utils.debug_helper import DebugLogger, CrashHandler

# Create application first, before anything else
app = QApplication(sys.argv)
app.setStyle('Fusion')

def main():
    debug_logger = None
    try:
        # Show splash screen only during startup
        splash = SplashScreen(app)
        splash.show()
        splash.raise_()

        # Set up imports with progress updates
        splash.update_status("Loading core modules...", 10)
        QCoreApplication.processEvents()
        
        splash.update_status("Loading utilities...", 20)
        QCoreApplication.processEvents()

        # Initialize logging and debug
        splash.update_status("Initializing logging...", 30)
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
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
        
        # Store window reference and start event loop
        app.window = window
        logger.info("Starting Qt event loop")
        return app.exec()
        
    except Exception as e:
        if debug_logger and debug_logger.crash_handler:
            debug_logger.crash_handler.handle_exception(type(e), e, e.__traceback__)
        if 'logger' in locals():
            logger.error(f"Failed to start: {e}")
            logger.error("Stack trace:", exc_info=True)
        return 1

if __name__ == '__main__':
    try:
        exit_code = main()
        logging.getLogger(__name__).debug(f"Application exited with code {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

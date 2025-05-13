import sys
import os
import logging
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication
from gui.splash_screen import SplashScreen
from utils.debug_helper import DebugLogger, CrashHandler
from multiprocessing import freeze_support  # Import freeze_support

def main():
    debug_logger = None
    try:
        # Ensure freeze_support is called for multiprocessing
        freeze_support()

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
        # Initialize the QApplication
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # Ensure freeze_support is called when running as a frozen executable
        freeze_support()
        
        exit_code = main()
        logging.getLogger(__name__).debug(f"Application exited with code {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

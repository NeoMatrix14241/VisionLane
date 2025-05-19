import sys
from utils.debug_helper import DebugLogger
import logging

def run_with_debug():
    # Initialize debug logger
    debug = DebugLogger()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting application in debug mode")
        
        # Import and run main
        import main
        exit_code = main.main()
        
        logger.info(f"Application exited with code {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error("Stack trace:", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(run_with_debug())

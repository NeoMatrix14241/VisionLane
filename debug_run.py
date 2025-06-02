import sys
from utils.debug_helper import DebugLogger
import logging


def run_with_debug():
    """Run the application in debug mode."""
    # Initialize debug logger
    debug = DebugLogger()
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting application in debug mode")
        # Import and run main
        import main
        exit_code = main.main()
        logger.info("Application exited with code %s", exit_code)
        return exit_code
    except Exception as e:
        logger.error("Fatal error: %s", e)
        logger.error("Stack trace:", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(run_with_debug())

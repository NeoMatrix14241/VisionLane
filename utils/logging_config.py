import logging
from pathlib import Path
from datetime import datetime
import os

def setup_logging(base_dir: Path):
    try:
        # Create logs directory
        logs_dir = base_dir / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Create log filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = logs_dir / f"ocr_process_{timestamp}.log"

        # Create handlers with UTF-8 encoding
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        console_handler = logging.StreamHandler()

        # Create formatters with timezone
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Set formatters
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Set levels
        file_handler.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.INFO)

        # Get root logger and remove existing handlers
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        
        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger
        
    except Exception as e:
        print(f"Failed to setup logging: {e}")
        return None

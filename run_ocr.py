from core.ocr_processor import OCRProcessor
from utils.logging_config import setup_logging
import logging
import os
from datetime import datetime, UTC
from pathlib import Path
def setup_directories():
    # Get the directory where run_ocr.py is located
    base_dir = Path(__file__).parent
    # Create input and output directories in the same folder as run_ocr.py
    input_dirs = {
        'images': base_dir / 'input' / 'images',
        'pdfs': base_dir / 'input' / 'pdfs'
    }
    # Create directories if they don't exist
    for dir_path in input_dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    return base_dir
def find_files_recursive(directory: Path, extensions: list) -> list:
    """
    Recursively find files with specific extensions in a directory
    Args:
        directory (Path): Directory to search in
        extensions (list): List of file extensions to look for
    Returns:
        list: List of found files    """
    files = []
    try:
        # Walk through directory and all subdirectories
        for root, _, filenames in os.walk(directory):
            root_path = Path(root)
            for ext in extensions:
                # Find files with the current extension
                files.extend(root_path.glob(f"*.{ext}"))
        return sorted(files)  # Sort files for consistent processing order
    except Exception as e:
        logging.error("Error searching directory %s: %s", directory, e)
        return files


def main():
    # Get base directory and setup directories
    base_dir = setup_directories()
    # Setup enhanced logging
    logger = setup_logging(base_dir)
    # Print script information using timezone-aware datetime
    current_time = datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')
    logger.info("=" * 80)
    logger.info("OCR Processing Session Started at UTC: %s", current_time)
    logger.info("User: %s", "NeoMatrix14241")
    logger.info("Working directory: %s", base_dir)
    logger.info("=" * 80)
    # Initialize the OCR processor
    processor = OCRProcessor(
        output_base_dir=str(base_dir / "output")
    )
    # Define supported extensions
    image_extensions = ['jpg', 'jpeg', 'png', 'tif', 'tiff']
    pdf_extensions = ['pdf']
    # Process all images in the input/images directory and its subdirectories
    images_dir = base_dir / "input" / "images"
    pdfs_dir = base_dir / "input" / "pdfs"    # Process images
    if images_dir.exists():
        image_files = find_files_recursive(images_dir, image_extensions)
        if image_files:
            logger.info("Found %d images to process", len(image_files))
            for image_file in image_files:
                try:
                    # Create relative path structure in output directory
                    rel_path = image_file.relative_to(images_dir)
                    logger.info("Processing image: %s", rel_path)
                    # Create output subdirectories if needed
                    output_subdir = base_dir / "output" / "hocr" / rel_path.parent
                    output_subdir.mkdir(parents=True, exist_ok=True)
                    output_subdir = base_dir / "output" / "pdf" / rel_path.parent
                    output_subdir.mkdir(parents=True, exist_ok=True)
                    processor.process_image(str(image_file))
                except Exception as e:
                    logger.error("Failed to process image %s: %s", rel_path, e)
        else:
            logger.info("No image files found in input/images directory")    # Process PDFs
    if pdfs_dir.exists():
        pdf_files = find_files_recursive(pdfs_dir, pdf_extensions)
        if pdf_files:
            logger.info("Found %d PDFs to process", len(pdf_files))
            for pdf_file in pdf_files:
                try:
                    # Create relative path structure in output directory
                    rel_path = pdf_file.relative_to(pdfs_dir)
                    logger.info("Processing PDF: %s", rel_path)
                    # Create output subdirectories if needed
                    output_subdir = base_dir / "output" / "hocr" / rel_path.parent
                    output_subdir.mkdir(parents=True, exist_ok=True)
                    output_subdir = base_dir / "output" / "pdf" / rel_path.parent
                    output_subdir.mkdir(parents=True, exist_ok=True)
                    processor.process_pdf(str(pdf_file))
                except Exception as e:
                    logger.error("Failed to process PDF %s: %s", rel_path, e)
        else:
            logger.info("No PDF files found in input/pdfs directory")    # Enhanced summary logging
    logger.info("=" * 80)
    logger.info("Processing Summary:")
    logger.info("-" * 40)
    logger.info("Total images processed: %d", len(image_files) if 'image_files' in locals() else 0)
    logger.info("Total PDFs processed: %d", len(pdf_files) if 'pdf_files' in locals() else 0)
    logger.info("Output directory: %s", base_dir / 'output')
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

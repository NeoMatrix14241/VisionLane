import os
import sys
import logging
import threading
import multiprocessing as mp
import numpy as np
from pathlib import Path
import time
import traceback
from PIL import Image
import tempfile
logger = logging.getLogger(__name__)
class ImageProcessor(threading.Thread):
    """Process images in a separate thread/process"""
    def __init__(self, input_queue, output_queue):
        super().__init__(daemon=True)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self._stop_event = threading.Event()
    def run(self):
        """Main processing loop for the thread"""
        logger.debug("ImageProcessor thread started")
        try:
            while not self._stop_event.is_set():
                try:
                    # Get next task with timeout to allow checking stop_event
                    task = self.input_queue.get(timeout=0.5)
                    if task is None:  # Shutdown signal
                        break
                    # Process image
                    self._process_task(task)
                except mp.queues.Empty:
                    # No tasks in queue, just continue and check stop_event
                    continue
                except Exception as e:
                    logger.error(f"Error in image processor thread: {e}")
                    # Don't exit loop on error, continue with next task
        except Exception as e:
            logger.error(f"Fatal error in image processor thread: {e}")
        finally:
            logger.debug("ImageProcessor thread exiting")
    def _process_task(self, task):
        """Process a single image task"""
        try:
            img_path, shm_name, shape, dtype = task
            result = self._preprocess_image(img_path)
            self.output_queue.put(("success", result))
        except Exception as e:
            logger.error(f"Error processing image {img_path if 'img_path' in locals() else 'unknown'}: {e}")
            self.output_queue.put(("error", str(e)))
    def _preprocess_image(self, image_path):
        """Preprocess image for OCR compatibility"""
        try:
            # Load image
            img_path = Path(image_path)
            img = Image.open(img_path)
            # Convert image to RGB if needed for OCR compatibility
            result_img = img
            # Handle various image formats that might cause issues with OCR
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                # Create a white background image
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                # Paste using alpha channel as mask
                bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else img.split()[1])
                result_img = bg
            elif img.mode != 'RGB':
                # Convert other modes to RGB
                result_img = img.convert('RGB')
            # Get image DPI information
            dpi = img.info.get('dpi', (300, 300))
            if not isinstance(dpi, tuple) or len(dpi) != 2:
                dpi = (300, 300)
            # Get image dimensions
            width, height = img.size
            # Close original image to free memory
            if img is not result_img:
                img.close()
            # Check if we need to save the processed image
            try:
                # Create a unique temp filename
                temp_path = None
                if result_img.mode != 'RGB':
                    # This shouldn't happen since we convert to RGB above, but just to be safe
                    timestamp = int(time.time() * 1000)
                    filename = f"processed_{timestamp}_{Path(image_path).stem}.png"
                    temp_dir = Path(tempfile.gettempdir()) / "VisionLaneOCR_temp"
                    temp_dir.mkdir(exist_ok=True, parents=True)
                    temp_path = temp_dir / filename
                    result_img.convert('RGB').save(temp_path, "PNG", dpi=dpi)
            except Exception as e:
                logger.warning(f"Failed to save processed image: {e}")
            result_img.close()
            return {
                "dpi": dpi,
                "width": width,
                "height": height,
                "mode": "RGB",  # The image has been converted to RGB
                "processed_path": str(temp_path) if temp_path else None
            }
        except Exception as e:
            logger.error(f"Error in image preprocessing: {e}")
            traceback.print_exc()
            return None
    def stop(self):
        """Stop the processor thread"""
        self._stop_event.set()
        logger.debug("Stop event set for ImageProcessor")
    @staticmethod
    def ensure_rgb_format(image_path, output_dir=None):
        """
        Convert image to RGB format to avoid problems with OCR/HOCR.
        Returns the path to the converted image or original if already RGB.
        """
        try:
            if not output_dir:
                # Default: use system temp
                output_dir = Path(tempfile.gettempdir()) / "VisionLaneOCR_temp"
                output_dir.mkdir(exist_ok=True, parents=True)
            img_path = Path(image_path)
            img = Image.open(img_path)
            # Check if conversion needed
            if img.mode == 'RGB':
                img.close()
                return img_path
            # Get DPI
            dpi = img.info.get('dpi', (300, 300))
            # Convert to RGB
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                # Handle transparency
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                mask = img.split()[3] if img.mode == 'RGBA' else img.split()[1]
                bg.paste(img, mask=mask)
                rgb_img = bg
            else:
                # Simple conversion
                rgb_img = img.convert('RGB')
            # Save with timestamp to avoid conflicts
            timestamp = int(time.time() * 1000)
            out_path = output_dir / f"rgb_{timestamp}_{img_path.name}"
            # Save with original DPI if available
            rgb_img.save(out_path, format='PNG', dpi=dpi)
            # Cleanup
            img.close()
            rgb_img.close()
            return out_path
        except Exception as e:
            logger.error(f"Failed to convert image to RGB: {e}")
            return image_path

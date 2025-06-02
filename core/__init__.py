"""
Core modules for VisionLane OCR
"""

from .ocr_processor import OCRProcessor
from . import doctr_patch
from . import doctr_torch_setup

__all__ = ['OCRProcessor', 'doctr_patch', 'doctr_torch_setup']

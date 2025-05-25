#!/usr/bin/env python3
"""Simple test to verify compression attributes"""

import sys
from pathlib import Path

# Add the project root to the path  
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ocr_processor import OCRProcessor
    
    print("Creating OCRProcessor...")
    processor = OCRProcessor(output_base_dir="output/test", output_formats=["pdf"])
    
    print("Setting compression attributes...")
    processor.compress_enabled = True
    processor.compression_quality = 75
    processor.compression_type = "jpeg"
    
    print(f"compress_enabled: {hasattr(processor, 'compress_enabled')} = {getattr(processor, 'compress_enabled', 'NOT SET')}")
    print(f"compression_quality: {hasattr(processor, 'compression_quality')} = {getattr(processor, 'compression_quality', 'NOT SET')}")
    print(f"compression_type: {hasattr(processor, 'compression_type')} = {getattr(processor, 'compression_type', 'NOT SET')}")
    
    # Test the compression check condition
    compression_check = ("pdf" in processor.output_formats and 
                        hasattr(processor, "compress_enabled") and 
                        processor.compress_enabled)
    print(f"Compression check would pass: {compression_check}")
    
    print("✓ Test completed successfully!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

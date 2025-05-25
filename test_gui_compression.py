#!/usr/bin/env python3
"""Test script to verify GUI compression settings are properly passed to OCRProcessor"""

import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from ocr_processor import OCRProcessor

def test_compression_integration():
    """Test that compression attributes can be set and used by OCRProcessor"""
    
    # Create OCR processor instance
    output_dir = Path("output") / "test_compression"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    processor = OCRProcessor(
        output_base_dir=str(output_dir),
        output_formats=["pdf"]
    )
    
    # Simulate GUI setting compression attributes (as fixed)
    processor.compress_enabled = True
    processor.compression_quality = 75
    processor.compression_type = "jpeg"
    
    print(f"Compression enabled: {getattr(processor, 'compress_enabled', False)}")
    print(f"Compression quality: {getattr(processor, 'compression_quality', 'Not set')}")
    print(f"Compression type: {getattr(processor, 'compression_type', 'Not set')}")
    
    # Test with input image
    test_image = Path("input/images/test_image.png")
    if test_image.exists():
        print(f"\nProcessing test image: {test_image}")
        try:
            processor.process_single_image(str(test_image))
            print("✓ Processing completed successfully")
            
            # Check if output was created
            output_files = list(output_dir.glob("**/*.pdf"))
            if output_files:
                output_file = output_files[0]
                size_mb = output_file.stat().st_size / (1024 * 1024)
                print(f"✓ Output PDF created: {output_file}")
                print(f"✓ File size: {size_mb:.2f} MB")
            else:
                print("⚠ No PDF output found")
                
        except Exception as e:
            print(f"✗ Error during processing: {e}")
    else:
        print(f"⚠ Test image not found: {test_image}")
    
    # Cleanup
    processor.cleanup()

if __name__ == "__main__":
    test_compression_integration()

#!/usr/bin/env python3
import os
import argparse
import subprocess
from datetime import datetime, timezone
import time
from tqdm import tqdm
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import shutil

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s UTC [%(levelname)s] [%(threadName)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.user = os.getlogin()

    def get_max_threads(self):
        """Get the maximum number of threads available on the system"""
        return psutil.cpu_count(logical=True)

    def log_with_timestamp(
        self, message: str, level: str = "info", thread_name: str = None
    ):
        """Log message with current UTC timestamp using timezone-aware datetime"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        thread_info = f"[{thread_name}] " if thread_name else ""
        if level.lower() == "error":
            logger.error(f"{timestamp} - {thread_info}{message}")
        else:
            logger.info(f"{timestamp} - {thread_info}{message}")

    def compress_pdf(self, input_path: str, output_path: str, quality: int = 50, fast_mode: bool = True, compression_type: str = "jpeg") -> bool:
        """Compress a single PDF file using Ghostscript."""
        try:
            # Convert to absolute paths
            input_path = os.path.abspath(input_path)
            output_path = os.path.abspath(output_path)
            
            if not os.path.exists(input_path):
                self.log_with_timestamp(f"Input file not found: {input_path}", "error")
                return False
                
            start_time = time.time()
            thread_name = f"Thread-{threading.current_thread().ident}"
            
            self.log_with_timestamp(f"Processing file: {input_path}", thread_name=thread_name)
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # --- Find Ghostscript executable ---
            import sys
            if sys.platform.startswith("win"):
                exe_name = "gswin64c.exe"
                gs_path = None
                # 1. Check PATH
                gs_path = shutil.which(exe_name)
                if not gs_path:
                    # 2. Search in Program Files locations
                    import re
                    from pathlib import Path
                    search_dirs = [
                        Path("C:/Program Files/gs"),
                        Path("C:/Program Files (x86)/gs"),
                    ]
                    found = []
                    for base in search_dirs:
                        if base.exists():
                            for sub in base.iterdir():
                                if sub.is_dir():
                                    exe = sub / "bin" / exe_name
                                    if exe.exists():
                                        m = re.search(r'(\d+(\.\d+)*)', sub.name)
                                        version = tuple(map(int, m.group(1).split('.'))) if m else (0,)
                                        found.append((version, exe))
                    if found:
                        found.sort(reverse=True)
                        gs_path = str(found[0][1])
                if not gs_path:
                    self.log_with_timestamp("Ghostscript not found! PDF compression will not run.", "error")
                    return False
            else:
                exe_name = "gs"
                gs_path = shutil.which(exe_name)
                if not gs_path:
                    self.log_with_timestamp("Ghostscript not found! PDF compression will not run.", "error")
                    return False            # --- Check if compression is likely to be beneficial ---
            initial_size_mb = os.path.getsize(input_path) / (1024 * 1024)
            
            # For very small PDFs (< 1MB), be more conservative
            if initial_size_mb < 1.0:
                # Small PDFs - use gentler settings to avoid bloat
                compression_level = max(0, min(9, int((100 - quality) / 20)))  # Less aggressive
                resolution = 300 if quality > 50 else 150  # Keep reasonable resolution
                jpeg_quality = max(70, min(100, quality + 20))  # Higher JPEG quality
            else:
                # Larger PDFs - standard compression settings
                compression_level = max(0, min(9, int((100 - quality) / 11)))  # 0-9 compression level
                
                # Set downsampling resolution based on quality
                if quality <= 30:
                    resolution = 72  # Low quality - aggressive compression
                elif quality <= 60:
                    resolution = 150  # Medium quality
                elif quality <= 85:
                    resolution = 300  # High quality
                else:
                    resolution = 600  # Very high quality - minimal compression
                
                # Adjust JPEG quality based on input quality
                jpeg_quality = max(5, min(100, quality))  # Never go below 5% JPEG quality
            
            # --- IMPROVED: Set different parameters for each compression type ---            # Build GhostScript command with optimized parameters
            gs_cmd = [
                f'"{gs_path}"',
                '-sDEVICE=pdfwrite',
                '-dNOPAUSE',
                '-dQUIET',
                '-dBATCH',
                '-dSAFER',
            ]
            
            # For small PDFs, use more conservative settings
            if initial_size_mb < 1.0:
                gs_cmd.extend([
                    '-dPDFSETTINGS=/ebook',  # Conservative preset for small files
                    '-dCompatibilityLevel=1.4',
                    '-dCompressFonts=true',
                    '-dSubsetFonts=true',
                    '-dCompressStreams=false',  # Don't compress streams for small files
                    '-dAutoRotatePages=/None',
                    '-dPreserveStructure=true',
                ])
            else:
                gs_cmd.extend([
                    '-dCompatibilityLevel=1.5',  # Use PDF 1.5 compatibility for better compression
                    '-dPDFSETTINGS=/default',    # Base settings
                    '-dPrinted=false',           # Not for printing
                    '-dCompressFonts=true',
                    '-dCompressPages=true',
                    '-dCompressStreams=true',    # Force stream compression
                    '-dAutoRotatePages=/None',   # Preserve orientation
                    '-dPreserveStructure=true',  # Preserve document structure
                    '-dCompatibilityLevel=1.5',  # PDF 1.5 compatibility
                    '-dEmbedAllFonts=true',      # Keep all fonts
                    '-dSubsetFonts=true',        # But subset them to reduce size
                    f'-dCompressLevel={compression_level}',  # Compression level for non-image objects
                ])
              # --- IMPROVED: Set image sampling based on quality (only for larger PDFs) ---
            if initial_size_mb >= 1.0:  # Only apply aggressive image compression to larger files
                # Color image settings
                gs_cmd.extend([
                    f'-dColorImageDownsampleType=/Bicubic',
                    f'-dColorImageResolution={resolution}',
                    f'-dDownsampleColorImages=true',
                    f'-dColorImageDownsampleThreshold=1.0',  # Always downsample color images
                    f'-dEncodeColorImages=true',
                ])
                
                # Grayscale image settings
                gs_cmd.extend([
                    f'-dGrayImageDownsampleType=/Bicubic',
                    f'-dGrayImageResolution={resolution}',
                    f'-dDownsampleGrayImages=true',
                    f'-dGrayImageDownsampleThreshold=1.0',  # Always downsample grayscale images
                    f'-dEncodeGrayImages=true',
                ])
                
                # Monochrome image settings
                gs_cmd.extend([
                    f'-dMonoImageDownsampleType=/Bicubic',
                    f'-dMonoImageResolution={resolution}',
                    f'-dDownsampleMonoImages=true',
                    f'-dMonoImageDownsampleThreshold=1.0',  # Always downsample monochrome images
                ])
            else:            # For small PDFs, preserve image quality
                gs_cmd.extend([
                    f'-dDownsampleColorImages=false',
                    f'-dDownsampleGrayImages=false', 
                    f'-dDownsampleMonoImages=false',
                ])
              # --- IMPROVED: Handle specific compression type settings (only for larger PDFs) ---
            ctype = (compression_type or "jpeg").lower()
            
            if initial_size_mb >= 1.0:  # Only apply specific compression to larger files
                if ctype == "jpeg":
                    gs_cmd.extend([
                        f'-dAutoFilterColorImages=false',
                        f'-dColorImageFilter=/DCTEncode',
                        f'-dAutoFilterGrayImages=false',
                        f'-dGrayImageFilter=/DCTEncode',
                        f'-dJPEGQ={jpeg_quality}',
                        # Color bit depth based on quality
                        f'-dColorConversionStrategy=/LeaveColorUnchanged',
                        f'-dColorImageDepth={8 if quality < 85 else 24}',
                    ])
                elif ctype == "jpeg2000":
                    gs_cmd.extend([
                        f'-dAutoFilterColorImages=false',
                        f'-dColorImageFilter=/JPXEncode',
                        f'-dAutoFilterGrayImages=false',
                        f'-dGrayImageFilter=/JPXEncode',
                        # Quality parameters specific to JPEG2000
                        f'-dJPEGQ={jpeg_quality}',
                        # Set color depth based on quality
                        f'-dColorConversionStrategy=/LeaveColorUnchanged',
                        f'-dColorImageDepth={8 if quality < 85 else 24}',
                    ])
                elif ctype == "lzw":
                    gs_cmd.extend([
                        f'-dAutoFilterColorImages=false',
                        f'-dColorImageFilter=/LZWEncode',
                        f'-dAutoFilterGrayImages=false',
                        f'-dGrayImageFilter=/LZWEncode',
                        # LZW predictor to improve compression
                        f'-dLZWPredictor=2',
                        f'-dColorConversionStrategy=/LeaveColorUnchanged',
                    ])
                elif ctype == "png" or ctype == "flate":
                    gs_cmd.extend([
                        f'-dAutoFilterColorImages=false',
                        f'-dColorImageFilter=/FlateEncode',
                        f'-dAutoFilterGrayImages=false',
                        f'-dGrayImageFilter=/FlateEncode',
                        # Set flate predictor for better lossless compression
                        f'-dFlatePrediction=2',
                        f'-dColorConversionStrategy=/LeaveColorUnchanged',
                    ])
                else:
                    # Default to JPEG
                    gs_cmd.extend([
                        f'-dAutoFilterColorImages=false',
                        f'-dColorImageFilter=/DCTEncode',
                        f'-dAutoFilterGrayImages=false',
                        f'-dGrayImageFilter=/DCTEncode',
                        f'-dJPEGQ={jpeg_quality}',
                    ])
            
            # --- IMPROVED: Add PDFSETTINGS presets for better compression ---
            # Override default settings with quality-based presets if quality is at extremes
            if quality < 30:
                # Low quality: aggressive compression
                gs_cmd.append('-dPDFSETTINGS=/ebook')
            elif quality > 90:
                # Very high quality: minimal compression
                gs_cmd.append('-dPDFSETTINGS=/prepress')
                
            # Quote the file paths and add to command
            gs_cmd.extend([
                f'-sOutputFile="{output_path}"',
                f'"{input_path}"'
            ])

            # Execute compression
            self.log_with_timestamp(f"Starting compression with command: {' '.join(gs_cmd)}", thread_name=thread_name)
            run_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                shell=True
            )
            if sys.platform.startswith("win"):
                run_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            process = subprocess.run(
                ' '.join(gs_cmd),
                **run_kwargs
            )
            # --- Print Ghostscript output for debugging ---
            self.log_with_timestamp(f"Ghostscript stdout: {process.stdout}", thread_name=thread_name)
            if process.stderr:
                self.log_with_timestamp(f"Ghostscript stderr: {process.stderr}", thread_name=thread_name)

            if process.returncode == 0 and os.path.exists(output_path):
                initial_size = os.path.getsize(input_path) / (1024 * 1024)  # Convert to MB
                final_size = os.path.getsize(output_path) / (1024 * 1024)  # Convert to MB
                compression_ratio = (1 - final_size/initial_size) * 100
                elapsed_time = time.time() - start_time
                
                self.log_with_timestamp(
                    f"\nCompression Results for {os.path.basename(input_path)}:", 
                    thread_name=thread_name
                )
                self.log_with_timestamp(
                    f"- Initial size: {initial_size:.2f}MB", 
                    thread_name=thread_name
                )
                self.log_with_timestamp(
                    f"- Final size: {final_size:.2f}MB", 
                    thread_name=thread_name
                )
                self.log_with_timestamp(
                    f"- Compression ratio: {compression_ratio:.2f}%", 
                    thread_name=thread_name
                )
                self.log_with_timestamp(
                    f"- Processing time: {elapsed_time:.2f}s", 
                    thread_name=thread_name
                )
                  # If compression actually made the file larger, use the original
                # But be more lenient for small files (< 5% increase is acceptable)
                size_increase_threshold = 0.05 if initial_size_mb < 2.0 else 0.0
                
                if final_size > initial_size * (1 + size_increase_threshold):
                    self.log_with_timestamp(
                        f"Compression increased file size significantly, reverting to original.", 
                        thread_name=thread_name
                    )
                    os.remove(output_path)
                    shutil.copy2(input_path, output_path)
                    return True
                elif final_size > initial_size:
                    self.log_with_timestamp(
                        f"Compression slightly increased file size but within acceptable threshold.", 
                        thread_name=thread_name
                    )
                    
                return True
            else:
                self.log_with_timestamp(
                    f"Failed to compress {input_path}\nError: {process.stderr}", 
                    "error", 
                    thread_name=thread_name
                )
                return False
                
        except Exception as e:
            self.log_with_timestamp(
                f"Error compressing {input_path}: {str(e)}", 
                "error", 
                thread_name=thread_name
            )
            return False

    def process_directory(self, input_folder: str, output_folder: str, quality: int, fast_mode: bool = True) -> None:
        """Process all PDFs in a directory recursively using multithreading"""
        try:
            # Convert to absolute paths
            input_folder = os.path.abspath(input_folder)
            output_folder = os.path.abspath(output_folder)
            
            # Get list of PDF files
            pdf_files = []
            for root, _, files in os.walk(input_folder):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        input_path = os.path.abspath(os.path.join(root, file))
                        rel_path = os.path.relpath(os.path.dirname(input_path), input_folder)
                        output_subdir = os.path.join(output_folder, rel_path)
                        os.makedirs(output_subdir, exist_ok=True)
                        output_path = os.path.abspath(os.path.join(output_subdir, f"{os.path.basename(file)}"))
                        pdf_files.append((input_path, output_path, quality))

            if not pdf_files:
                self.log_with_timestamp("No PDF files found in the input directory")
                return

            # Get maximum number of threads
            max_threads = min(len(pdf_files), self.get_max_threads())
            self.log_with_timestamp(f"Processing {len(pdf_files)} files using {max_threads} threads")

            # Process files using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = []
                for args in pdf_files:
                    input_path, output_path, quality = args
                    self.log_with_timestamp(f"Queueing file: {input_path}")
                    futures.append(
                        executor.submit(
                            self.compress_pdf, 
                            input_path, 
                            output_path, 
                            quality,
                            fast_mode
                        )
                    )
                
                # Process results with progress bar
                successful = 0
                failed = 0
                with tqdm(total=len(pdf_files), desc="Processing PDFs", unit="file") as pbar:
                    for future in as_completed(futures):
                        try:
                            if future.result():
                                successful += 1
                            else:
                                failed += 1
                        except Exception as e:
                            self.log_with_timestamp(f"Error in thread: {str(e)}", "error")
                            failed += 1
                        pbar.update(1)

            # Log final statistics
            self.log_with_timestamp(
                f"\nCompression Statistics:"
                f"\n- Total files processed: {len(pdf_files)}"
                f"\n- Successfully compressed: {successful}"
                f"\n- Failed: {failed}"
                f"\n- Success rate: {(successful/len(pdf_files)*100):.2f}%"
            )

        except Exception as e:
            self.log_with_timestamp(f"Error processing directory: {str(e)}", "error")
            raise


# Export compress_pdf for import in ocr_processor.py
def compress_pdf(input_path, output_path, quality=50, fast_mode=True, compression_type="jpeg"):
    """
    Compress a PDF file using Ghostscript.
    """
    processor = PDFProcessor()
    return processor.compress_pdf(input_path, output_path, quality, fast_mode, compression_type=compression_type)

def main():
    parser = argparse.ArgumentParser(
        description="Recursively compress PDF files while preserving DPI and OCR layers"
    )

    parser.add_argument(
        "input", type=str, help="Input PDF file or directory containing PDF files"
    )

    parser.add_argument(
        "output", type=str, help="Output directory for compressed PDF files"
    )

    parser.add_argument(
        "--quality",
        type=int,
        choices=range(0, 101),
        default=50,
        metavar="0-100",
        help="Compression quality (0-100, higher = better quality but larger file size, default: 50)",
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        help="Enable fast mode (skip detailed page analysis)",
    )

    args = parser.parse_args()
    processor = PDFProcessor()

    # Log start of processing
    processor.log_with_timestamp("=== PDF Compression Task Started ===")
    processor.log_with_timestamp(
        f"Mode: {'Fast' if args.fast else 'Detailed analysis'}"
    )
    processor.log_with_timestamp(
        f"Available CPU threads: {processor.get_max_threads()}"
    )
    processor.log_with_timestamp(f"Input path: {args.input}")
    processor.log_with_timestamp(f"Output path: {args.output}")
    processor.log_with_timestamp(f"Quality setting: {args.quality}")

    try:
        if os.path.isfile(args.input):
            processor.log_with_timestamp("Processing single file mode")
            os.makedirs(args.output, exist_ok=True)
            output_path = os.path.join(
                args.output, f"{os.path.basename(args.input)}"
            )
            processor.compress_pdf(args.input, output_path, args.quality, args.fast)
        elif os.path.isdir(args.input):
            processor.log_with_timestamp("Processing directory mode")
            processor.process_directory(
                args.input, args.output, args.quality, args.fast
            )
        else:
            processor.log_with_timestamp(
                f"Error: {args.input} is not a valid file or directory", "error"
            )
            return

        processor.log_with_timestamp("=== PDF Compression Task Completed ===")

    except Exception as e:
        processor.log_with_timestamp(f"Task failed: {str(e)}", "error")
        processor.log_with_timestamp("=== PDF Compression Task Failed ===")


if __name__ == "__main__":
    main()
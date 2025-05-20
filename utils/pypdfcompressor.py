#!/usr/bin/env python3
import os
import argparse
import subprocess
from typing import Optional, Dict
import fitz  # PyMuPDF
from datetime import datetime, timezone
import time
from tqdm import tqdm
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import shutil

# --- Simple image compression utility for OCR pipeline ---
def compress_image(input_path, output_path, quality=80, compression_type="jpeg"):
    """
    Compress an image using PyMuPDF and save to output_path.
    Supports 'jpeg', 'jpeg2000', 'png' for compression_type.
    Only the first page is used for multi-page TIFFs.
    """
    try:
        orig_size = os.path.getsize(input_path) if os.path.exists(input_path) else None
        logger.info(f"[PyPDFCompressor] Compressing: {input_path} -> {output_path} | type={compression_type} | quality={quality}")
        if orig_size:
            logger.info(f"[PyPDFCompressor] Original size: {orig_size/1024:.1f} KB")
        doc = fitz.open(input_path)
        page = doc[0]
        pix = page.get_pixmap()
        fmt = compression_type.lower()
        if fmt == "jpeg":
            ext = "jpg"
            # PyMuPDF's tobytes("jpg") does NOT support quality in recent versions.
            # Use PIL for JPEG compression with quality.
            from PIL import Image
            import io
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.save(output_path, "JPEG", quality=int(quality))
        elif fmt == "jpeg2000":
            ext = "jp2"
            img_bytes = pix.tobytes("jp2")
            with open(output_path, "wb") as f:
                f.write(img_bytes)
        elif fmt == "png":
            ext = "png"
            img_bytes = pix.tobytes("png")
            with open(output_path, "wb") as f:
                f.write(img_bytes)
        elif fmt == "lzw":
            ext = "tif"
            pix.save(output_path)  # TIFF, no quality option
        else:
            pix.save(output_path)
        doc.close()
        # Double check file was written and is not empty
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(f"Compression failed, output not created: {output_path}")
        out_size = os.path.getsize(output_path)
        logger.info(f"[PyPDFCompressor] Compressed size: {out_size/1024:.1f} KB")
        if orig_size:
            ratio = (out_size/orig_size)*100 if orig_size else 0
            logger.info(f"[PyPDFCompressor] Compression ratio: {ratio:.1f}%")
    except Exception as e:
        logger.error(f"[PyPDFCompressor] ERROR: {e}")
        raise RuntimeError(f"PyMuPDF compression failed: {e}")


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

    def get_quick_pdf_info(
        self, pdf_path: str, thread_name: str = None
    ) -> Optional[int]:
        """Quick PDF analysis - just gets basic info without page-by-page analysis"""
        try:
            doc = fitz.open(pdf_path)
            file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)

            self.log_with_timestamp(
                f"\nQuick Analysis of: {os.path.basename(pdf_path)}",
                thread_name=thread_name,
            )
            self.log_with_timestamp(
                f"- Total Pages: {len(doc)}", thread_name=thread_name
            )
            self.log_with_timestamp(
                f"- File Size: {file_size_mb:.2f} MB", thread_name=thread_name
            )

            # Quick check of first page only for DPI
            if len(doc) > 0:
                first_page = doc[0]
                image_list = first_page.get_images()
                max_dpi = 0
                for img in image_list:
                    xref = img[0]
                    image = doc.extract_image(xref)
                    if image and "dpi" in image:
                        max_dpi = max(max_dpi, max(image.get("dpi", (0, 0))))

                if max_dpi > 0:
                    self.log_with_timestamp(
                        f"- Sample DPI (first page): {max_dpi}", thread_name=thread_name
                    )

            doc.close()
            return max_dpi if max_dpi > 0 else None

        except Exception as e:
            self.log_with_timestamp(
                f"Error in quick analysis of {pdf_path}: {str(e)}", "error", thread_name
            )
            return None

    def analyze_pdf_page(
        self, page: fitz.Page, page_num: int, thread_name: str = None
    ) -> Dict:
        """Analyze a single PDF page for detailed information"""
        result = {
            "page_number": page_num,
            "images": [],
            "max_dpi": 0,
            "total_images": 0,
            "page_size": f"{page.rect.width:.2f}x{page.rect.height:.2f} points",
        }

        image_list = page.get_images()
        result["total_images"] = len(image_list)

        for img_idx, img in enumerate(image_list, 1):
            xref = img[0]
            try:
                image = page.parent.extract_image(xref)
                if image:
                    img_info = {
                        "index": img_idx,
                        "width": image.get("width", 0),
                        "height": image.get("height", 0),
                        "dpi": max(image.get("dpi", (0, 0))),
                        "colorspace": image.get("colorspace", "Unknown"),
                        "size_kb": len(image.get("image", b"")) / 1024,
                    }
                    result["images"].append(img_info)
                    result["max_dpi"] = max(result["max_dpi"], img_info["dpi"])
            except Exception as e:
                self.log_with_timestamp(
                    f"Error analyzing image {img_idx} on page {page_num}: {str(e)}",
                    "error",
                    thread_name,
                )

        return result

    def get_pdf_dpi(self, pdf_path: str, thread_name: str = None) -> Optional[int]:
        """Extract detailed DPI and page information from a PDF file"""
        try:
            self.log_with_timestamp(f"\n{'='*50}", thread_name=thread_name)
            self.log_with_timestamp(
                f"Starting detailed analysis of: {os.path.basename(pdf_path)}",
                thread_name=thread_name,
            )
            self.log_with_timestamp(f"{'='*50}", thread_name=thread_name)

            doc = fitz.open(pdf_path)
            max_dpi = 0
            total_images = 0
            file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)

            self.log_with_timestamp(f"Document Properties:", thread_name=thread_name)
            self.log_with_timestamp(
                f"- Total Pages: {len(doc)}", thread_name=thread_name
            )
            self.log_with_timestamp(
                f"- File Size: {file_size_mb:.2f} MB", thread_name=thread_name
            )
            self.log_with_timestamp(
                f"- PDF Version: {doc.metadata.get('format', 'Unknown')}",
                thread_name=thread_name,
            )
            self.log_with_timestamp(
                f"- Title: {doc.metadata.get('title', 'Untitled')}",
                thread_name=thread_name,
            )
            self.log_with_timestamp(
                f"\nStarting page-by-page analysis:", thread_name=thread_name
            )

            for page_num, page in enumerate(doc, 1):
                self.log_with_timestamp(
                    f"\nAnalyzing Page {page_num}/{len(doc)}:", thread_name=thread_name
                )
                page_info = self.analyze_pdf_page(page, page_num, thread_name)

                # Log page details
                self.log_with_timestamp(
                    f"  Page Size: {page_info['page_size']}", thread_name=thread_name
                )
                self.log_with_timestamp(
                    f"  Images Found: {page_info['total_images']}",
                    thread_name=thread_name,
                )

                if page_info["images"]:
                    self.log_with_timestamp("  Image Details:", thread_name=thread_name)
                    for img in page_info["images"]:
                        self.log_with_timestamp(
                            f"    - Image {img['index']}: "
                            f"{img['width']}x{img['height']} pixels, "
                            f"DPI: {img['dpi']}, "
                            f"ColorSpace: {img['colorspace']}, "
                            f"Size: {img['size_kb']:.2f}KB",
                            thread_name=thread_name,
                        )

                max_dpi = max(max_dpi, page_info["max_dpi"])
                total_images += page_info["total_images"]

            doc.close()

            self.log_with_timestamp(f"\nAnalysis Summary:", thread_name=thread_name)
            self.log_with_timestamp(
                f"- Maximum DPI found: {max_dpi}", thread_name=thread_name
            )
            self.log_with_timestamp(
                f"- Total images: {total_images}", thread_name=thread_name
            )
            self.log_with_timestamp(f"{'='*50}\n", thread_name=thread_name)

            return max_dpi if max_dpi > 0 else None

        except Exception as e:
            self.log_with_timestamp(
                f"Error analyzing PDF {pdf_path}: {str(e)}", "error", thread_name
            )
            return None

    def compress_single_pdf(self, args):
        """Wrapper function for compressing a single PDF (used with ThreadPoolExecutor)"""
        input_path, output_path, quality = args
        try:
            return self.compress_pdf(input_path, output_path, quality)
        except Exception as e:
            self.log_with_timestamp(f"Error processing {input_path}: {str(e)}", "error")
            return False

    def compress_pdf(self, input_path: str, output_path: str, quality: int = 50, fast_mode: bool = True, compression_type: str = "jpeg") -> bool:
        """Compress a single PDF file while preserving DPI and OCR layers."""
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
            
            # Use quick analysis in fast mode, detailed analysis otherwise
            if fast_mode:
                original_dpi = self.get_quick_pdf_info(input_path, thread_name)
            else:
                original_dpi = self.get_pdf_dpi(input_path, thread_name)
            
            # Calculate compression settings
            compression_level = max(0, min(9, int((100 - quality) / 11)))
            
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
                    return False

            # Prepare Ghostscript command with quoted paths
            gs_call = [
                f'"{gs_path}"',
                '-sDEVICE=pdfwrite',
                '-dCompatibilityLevel=1.5',
                '-dNOPAUSE',
                '-dBATCH',
                '-dSAFER',
                '-dPrinted=false',
                '-dPreserveAnnots=true',
                '-dAutoRotatePages=/None',
                '-dPreserveStructure=true',
                f'-dCompressFonts=true',
                f'-dCompressPages=true',
                f'-dCompressLevel={compression_level}',
                f'-dJPEGQ={quality}',
                '-dColorImageDownsampleType=/Bicubic',
                '-dGrayImageDownsampleType=/Bicubic',
                '-dMonoImageDownsampleType=/Bicubic',
                f'-dColorImageDepth={8 if quality < 50 else 16 if quality < 85 else 24}',
                # --- Force recompression ---
                '-dEncodeColorImages=true',
                '-dEncodeGrayImages=true',
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
            ]

            # --- Add compression type logic ---
            # See: https://ghostscript.com/doc/current/VectorDevices.htm#PDFWRITE
            ctype = (compression_type or "jpeg").lower()
            if ctype == "jpeg":
                gs_call += [
                    '-dColorImageFilter=/DCTEncode',
                    '-dGrayImageFilter=/DCTEncode',
                ]
            elif ctype == "jpeg2000":
                gs_call += [
                    '-dColorImageFilter=/JPXEncode',
                    '-dGrayImageFilter=/JPXEncode',
                ]
            elif ctype == "lzw":
                gs_call += [
                    '-dColorImageFilter=/LZWEncode',
                    '-dGrayImageFilter=/LZWEncode',
                ]
            elif ctype == "png":
                gs_call += [
                    '-dColorImageFilter=/FlateEncode',
                    '-dGrayImageFilter=/FlateEncode',
                ]
            # else: default to JPEG

            if original_dpi:
                gs_call.extend([
                    f'-dColorImageResolution={original_dpi}',
                    f'-dGrayImageResolution={original_dpi}',
                    f'-dMonoImageResolution={original_dpi}'
                ])

            # Quote the file paths
            gs_call.extend([
                f'-sOutputFile="{output_path}"',
                f'"{input_path}"'
            ])

            # Execute compression
            self.log_with_timestamp(f"Starting compression with command: {' '.join(gs_call)}", thread_name=thread_name)
            run_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                shell=True
            )
            if sys.platform.startswith("win"):
                run_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            process = subprocess.run(
                ' '.join(gs_call),
                **run_kwargs
            )
            # --- Print Ghostscript output for debugging ---
            self.log_with_timestamp(f"Ghostscript stdout: {process.stdout}", thread_name=thread_name)
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
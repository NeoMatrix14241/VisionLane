"""
Custom HOCR to PDF conversion utility that doesn't rely on ocrmypdf's HocrTransform
This is a fallback implementation when the ocrmypdf.hocrtransform module has API changes
"""

import re
import logging
from pathlib import Path
from typing import Optional, Tuple
from lxml import etree, html
from PIL import Image
import io
import reportlab
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch
import reportlab.lib.pagesizes as pagesizes

logger = logging.getLogger(__name__)

class CustomHOCRTransform:
    """
    Custom implementation to convert HOCR files to searchable PDF
    without relying on ocrmypdf's specific implementation
    """
    
    def __init__(self, hocr_file: str, image_file: str, dpi: int = 300):
        """Initialize with hocr file and corresponding image"""
        self.hocr_path = hocr_file
        self.image_path = image_file
        self.dpi = dpi
        self._pages = []
        self._parse_hocr()
        
    def _parse_hocr(self):
        """Parse HOCR file and extract text positions"""
        try:
            with open(self.hocr_path, 'rb') as f:
                self.hocr_data = f.read()
                
            parser = etree.HTMLParser()
            self.hocr = html.fromstring(self.hocr_data, parser=parser)
            
            # Extract pages
            pages = self.hocr.xpath('//*[@class="ocr_page"]')
            if not pages:
                raise ValueError(f"No pages found in HOCR file: {self.hocr_path}")
                
            self._pages = pages
            logger.debug(f"Found {len(self._pages)} pages in HOCR file")
            
        except Exception as e:
            logger.error(f"Error parsing HOCR file: {e}")
            raise
            
    def _parse_title(self, node):
        """Parse properties from a node's title attribute"""
        props = {}
        if 'title' in node.attrib:
            title = node.attrib['title']
            
            # Extract bbox coordinates
            bbox_match = re.search(r'bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', title)
            if bbox_match:
                props['bbox'] = tuple(int(x) for x in bbox_match.groups())
                
            # Extract image dimensions if available
            image_match = re.search(r'image\s+(\d+)\s+(\d+)', title)
            if image_match:
                props['image'] = tuple(int(x) for x in image_match.groups())
                
            # Extract baseline info if available
            baseline_match = re.search(r'baseline\s+([\d.-]+)\s+([\d.-]+)', title)
            if baseline_match:
                props['baseline'] = (float(baseline_match.group(1)), float(baseline_match.group(2)))
                
            # Extract x_wconf if available
            conf_match = re.search(r'x_wconf\s+(\d+)', title)
            if conf_match:
                props['confidence'] = int(conf_match.group(1))
                
        return props
        
    def to_pdf(self, pdf_file: str) -> bool:
        """Convert HOCR to searchable PDF"""
        try:
            # Get image for dimensions
            img = Image.open(self.image_path)
            width_px, height_px = img.size
            
            # Calculate page size in points (1/72 inch)
            dpi = self.dpi or 300
            width_pt = width_px * 72.0 / dpi
            height_pt = height_px * 72.0 / dpi
            
            # Create PDF canvas with proper dimensions
            canvas = Canvas(pdf_file, pagesize=(width_pt, height_pt))
            
            # Add image as background (full page size)
            canvas.setPageSize((width_pt, height_pt))
            canvas.drawImage(
                self.image_path, 
                0, 0, 
                width=width_pt, 
                height=height_pt, 
                preserveAspectRatio=True
            )
            
            # Process text elements
            for page in self._pages:
                page_props = self._parse_title(page)
                
                # Get words from the page
                for word in page.xpath('.//*[@class="ocrx_word"]'):
                    props = self._parse_title(word)
                    if 'bbox' not in props:
                        continue
                        
                    # Get word bbox and text
                    x1, y1, x2, y2 = props['bbox']
                    text = ''.join(word.xpath('.//text()'))
                    
                    if not text.strip():
                        continue
                        
                    # Convert from pixels to points and flip y-coordinate (PDF origin is bottom-left)
                    x1_pt = x1 * 72.0 / dpi
                    y1_pt = height_pt - (y2 * 72.0 / dpi)  # Flip y-coordinate
                    x2_pt = x2 * 72.0 / dpi
                    y2_pt = height_pt - (y1 * 72.0 / dpi)  # Flip y-coordinate
                    
                    # Calculate suitable font size
                    font_height = y2_pt - y1_pt
                    font_size = max(1, min(font_height, 20))  # Limit to reasonable size
                    
                    # Set font properties
                    canvas.setFont('Helvetica', font_size)
                    
                    # Add transparent text for searchability
                    canvas.saveState()
                    canvas.setFillColorRGB(0, 0, 0, 0)  # Transparent
                    canvas.rect(x1_pt, y1_pt, x2_pt - x1_pt, y2_pt - y1_pt, fill=True, stroke=False)
                    canvas.restoreState()
                    
                    # Add invisible text for searchability
                    canvas.saveState()
                    canvas.setFillColorRGB(0, 0, 0, 0.01)  # Almost transparent
                    canvas.drawString(x1_pt, y1_pt, text)
                    canvas.restoreState()
                    
            # Finalize PDF
            canvas.save()
            
            img.close()
            logger.info(f"Successfully created searchable PDF: {pdf_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating PDF from HOCR: {e}")
            return False


# Fallback function to use if the ocrmypdf.hocrtransform isn't working
def convert_hocr_to_pdf(hocr_path: str, image_path: str, pdf_path: str, dpi: Optional[int] = None) -> bool:
    """
    Convert HOCR to PDF using custom implementation
    
    Args:
        hocr_path: Path to HOCR file
        image_path: Path to original image
        pdf_path: Output PDF path
        dpi: Resolution in DPI (dots per inch)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Use our custom implementation
        transformer = CustomHOCRTransform(hocr_path, image_path, dpi or 300)
        return transformer.to_pdf(pdf_path)
    except Exception as e:
        logger.error(f"Error in custom HOCR to PDF conversion: {e}")
        return False


# Function to try multiple conversion methods
def hocr_to_pdf(hocr_path: str, image_path: str, pdf_path: str, dpi: Optional[int] = None) -> bool:
    """
    Try multiple methods to convert HOCR to PDF
    
    Args:
        hocr_path: Path to HOCR file
        image_path: Path to original image
        pdf_path: Output PDF path
        dpi: Resolution in DPI (dots per inch)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Try ocrmypdf's implementation first (multiple approaches)
    try:
        # Try the newest HocrTransform API
        from ocrmypdf.hocrtransform import HocrTransform
        try:
            # Method 1: modern HocrTransform with properties
            transformer = HocrTransform(hocr_filename=hocr_path, dpi=dpi or 300)
            transformer.image_filename = image_path
            transformer.to_pdf(pdf_path)
            logger.debug("Successfully converted using latest HocrTransform API")
            return True
        except TypeError:
            # Method 2: try positional arguments if keyword fails
            try:
                transformer = HocrTransform(hocr_path, image_path, dpi or 300)
                transformer.to_pdf(pdf_path)
                logger.debug("Successfully converted using HocrTransform with positional args")
                return True
            except Exception:
                pass
    except (ImportError, AttributeError) as e:
        logger.debug(f"ocrmypdf.hocrtransform.HocrTransform not available: {e}")
    
    # Try direct make_hocr_to_pdf function if available
    try:
        from ocrmypdf.hocrtransform import make_hocr_to_pdf
        try:
            make_hocr_to_pdf(hocr_path, image_path, pdf_path, dpi=dpi or 300)
            logger.debug("Successfully converted using make_hocr_to_pdf")
            return True
        except Exception as e:
            logger.debug(f"make_hocr_to_pdf failed: {e}")
    except ImportError:
        logger.debug("ocrmypdf.hocrtransform.make_hocr_to_pdf not available")
    
    # Fall back to our custom implementation
    logger.info("Falling back to custom HOCR to PDF conversion")
    return convert_hocr_to_pdf(hocr_path, image_path, pdf_path, dpi)

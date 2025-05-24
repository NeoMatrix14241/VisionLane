"""
Custom HOCR to PDF conversion utility that doesn't rely on ocrmypdf's HocrTransform
This is a fallback implementation when the ocrmypdf.hocrtransform module has API changes
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple
from lxml import etree, html
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import Color

logger = logging.getLogger(__name__)

class CustomHOCRTransform:
    """
    Custom implementation to convert HOCR files to searchable PDF
    without relying on ocrmypdf's specific implementation
    """
    
    def __init__(self, hocr_file: str, image_file: str, dpi: int = 300):
        self.hocr_file = Path(hocr_file)
        self.image_file = Path(image_file)
        self.dpi = dpi
        self.words = []
        self.page_width = 0
        self.page_height = 0
        
        # Load image to get dimensions
        try:
            with Image.open(self.image_file) as img:
                self.image_width, self.image_height = img.size
        except Exception as e:
            logger.error(f"Failed to load image {self.image_file}: {e}")
            self.image_width = self.image_height = 0
            
    def _parse_hocr(self):
        """Parse HOCR file and extract word positions and text"""
        try:
            with open(self.hocr_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse HTML content
            doc = html.fromstring(content)
            
            # Find page dimensions
            page_elem = doc.xpath('.//div[@class="ocr_page"]')[0]
            bbox = self._parse_title(page_elem)
            if bbox:
                self.page_width = bbox[2] - bbox[0]
                self.page_height = bbox[3] - bbox[1]
            else:
                # Fallback to image dimensions
                self.page_width = self.image_width
                self.page_height = self.image_height
            
            # Extract all words
            word_elements = doc.xpath('.//span[@class="ocrx_word"]')
            
            for word_elem in word_elements:
                bbox = self._parse_title(word_elem)
                text = word_elem.text_content().strip()
                
                if bbox and text:
                    # Convert coordinates to PDF space
                    x1, y1, x2, y2 = bbox
                    
                    # HOCR uses top-left origin, PDF uses bottom-left
                    pdf_x1 = x1
                    pdf_y1 = self.page_height - y2
                    pdf_x2 = x2
                    pdf_y2 = self.page_height - y1
                    
                    self.words.append({
                        'text': text,
                        'bbox': (pdf_x1, pdf_y1, pdf_x2, pdf_y2),
                        'width': pdf_x2 - pdf_x1,
                        'height': pdf_y2 - pdf_y1
                    })
            
            logger.info(f"Parsed {len(self.words)} words from HOCR")
            return True
            
        except Exception as e:
            logger.error(f"Failed to parse HOCR file: {e}")
            return False
        
    def _parse_title(self, node):
        """Parse bbox coordinates from title attribute"""
        if node is None:
            return None
            
        title = node.get('title', '')
        if not title:
            return None
        
        # Look for bbox pattern
        bbox_match = re.search(r'bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', title)
        if bbox_match:
            return tuple(map(int, bbox_match.groups()))
        
        return None
        
    def to_pdf(self, pdf_file: str) -> bool:
        """Convert HOCR to searchable PDF with invisible text layer"""
        try:
            if not self._parse_hocr():
                return False
            
            # Calculate PDF page size based on DPI
            pdf_width = (self.page_width / self.dpi) * inch
            pdf_height = (self.page_height / self.dpi) * inch
            
            # Create PDF canvas
            c = Canvas(pdf_file, pagesize=(pdf_width, pdf_height))
            
            # Draw the image as background
            try:
                c.drawImage(str(self.image_file), 0, 0, 
                           width=pdf_width, height=pdf_height)
            except Exception as e:
                logger.warning(f"Failed to embed image: {e}")
            
            # Add invisible text layer
            for word in self.words:
                text = word['text']
                bbox = word['bbox']
                
                # Convert HOCR coordinates to PDF coordinates
                x = (bbox[0] / self.dpi) * inch
                y = (bbox[1] / self.dpi) * inch
                width = (bbox[2] - bbox[0]) / self.dpi * inch
                height = (bbox[3] - bbox[1]) / self.dpi * inch
                
                # Calculate font size to fit the bbox
                font_size = max(1, height * 0.8)  # 80% of bbox height
                
                # Set text rendering mode to invisible (mode 3)
                c.setFillColor(Color(0, 0, 0, alpha=0))  # Transparent
                c.setFont("Helvetica", font_size)
                
                # Add the text at the correct position
                text_obj = c.beginText(x, y)
                text_obj.setTextRenderMode(3)  # Invisible text
                text_obj.textLine(text)
                c.drawText(text_obj)
            
            # Save the PDF
            c.save()
            logger.info(f"Successfully created searchable PDF: {pdf_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create PDF: {e}")
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
        if dpi is None:
            dpi = 300  # Default DPI
            
        transformer = CustomHOCRTransform(hocr_path, image_path, dpi)
        return transformer.to_pdf(pdf_path)
        
    except Exception as e:
        logger.error(f"HOCR to PDF conversion failed: {e}")
        return False


# Function to try multiple conversion methods
def hocr_to_pdf(hocr_path: str, image_path: str, pdf_path: str, dpi: Optional[int] = None) -> bool:
    """
    Try only the custom fallback method for debugging.
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.info(f"[DEBUG] hocr_to_pdf called: hocr_path={hocr_path}, image_path={image_path}, pdf_path={pdf_path}, dpi={dpi}")
    try:
        # First try ocrmypdf's HocrTransform if available
        try:
            from ocrmypdf.hocrtransform import HocrTransform
            
            # Create output directory if it doesn't exist
            Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Use ocrmypdf's HocrTransform
            with open(hocr_path, 'rb') as hocr_file:
                hocr_transform = HocrTransform(hocr_file, dpi or 300)
                with open(pdf_path, 'wb') as pdf_file:
                    hocr_transform.to_pdf(pdf_file, image_filename=image_path)
            
            logger.info(f"Successfully converted using ocrmypdf HocrTransform: {pdf_path}")
            return True
            
        except (ImportError, AttributeError, Exception) as e:
            logger.warning(f"ocrmypdf HocrTransform failed, using fallback: {e}")
            
            # Fallback to custom implementation
            return convert_hocr_to_pdf(hocr_path, image_path, pdf_path, dpi)
            
    except Exception as e:
        logger.error(f"All HOCR to PDF conversion methods failed: {e}")
        return False

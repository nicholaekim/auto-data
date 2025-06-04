"""
OCR-based text extraction as a fallback when direct text extraction fails.
"""
import logging
from typing import Optional
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

# Configure logging
logger = logging.getLogger(__name__)

def ocr_page(pdf_path: str, dpi: int = 200, lang: str = "eng") -> str:
    """
    Render page 1 of the PDF at the specified DPI and perform OCR.
    
    Args:
        pdf_path: Path to the PDF file
        dpi: Dots per inch for rendering the PDF (default: 200)
        lang: Language code for Tesseract (default: "eng")
        
    Returns:
        Extracted text as a single string, or empty string on failure
    """
    try:
        # Open the PDF and get the first page
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        
        # Render the page as a high-resolution image
        pix = page.get_pixmap(dpi=dpi)
        
        # Convert to a PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Convert to grayscale for better OCR
        img = img.convert('L')
        
        # Perform OCR
        text = pytesseract.image_to_string(img, lang=lang)
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"OCR failed for {pdf_path}: {str(e)}")
        return ""

def extract_text_with_ocr(pdf_path: str, dpi: int = 200, lang: str = "eng+spa") -> str:
    """
    Extract text from a PDF using OCR (compatibility wrapper for ocr_page).
    
    Args:
        pdf_path: Path to the PDF file
        dpi: Dots per inch for rendering the PDF (default: 200)
        lang: Language code for Tesseract (default: "eng+spa")
        
    Returns:
        Extracted text as a single string, or empty string on failure
    """
    return ocr_page(pdf_path, dpi=dpi, lang=lang)

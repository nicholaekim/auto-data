"""
Text extraction utilities for PDF documents.
Handles both searchable text and fallback to OCR when needed.
"""
import fitz  # PyMuPDF

def get_selectable_text(pdf_path: str) -> str:
    """
    Open the PDF at pdf_path, return text of page 1 as a single string.
    If the extracted text is < 80 characters (likely scanned), return an empty string.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text from the first page if it has enough content, otherwise empty string
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)  # Get the first page (0-indexed)
        raw_text = page.get_text("text").strip()
        
        # Return text only if it has at least 80 characters
        return raw_text if len(raw_text) >= 80 else ""
        
    except Exception as e:
        # If there's any error, return empty string
        return ""

def extract_text(pdf_path: str) -> tuple[str, bool]:
    """
    Extract text from a PDF, falling back to OCR if needed.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Tuple of (extracted_text, used_ocr) where used_ocr is True if OCR was used
    """
    # First try to get selectable text from the first page
    text = get_selectable_text(pdf_path)
    
    # If we got enough selectable text, return it
    if text:
        return text, False
        
    # Otherwise, fall back to OCR for the entire document
    from .ocr_fallback import extract_text_with_ocr
    return extract_text_with_ocr(pdf_path), True

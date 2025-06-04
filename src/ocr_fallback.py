"""
OCR-based text extraction as a fallback when direct text extraction fails.
"""
import logging
import os
import sys
from typing import Optional, Tuple
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import cv2
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

def preprocess_image(image, debug=False):
    """
    Preprocess image to improve OCR accuracy with multiple enhancement techniques.
    
    Args:
        image: Input image in BGR format (OpenCV format)
        debug: If True, save intermediate processing steps
        
    Returns:
        Preprocessed image in grayscale
    """
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply histogram equalization to improve contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        equalized = clahe.apply(gray)
        
        # Apply bilateral filter to reduce noise while keeping edges sharp
        denoised = cv2.bilateralFilter(equalized, 9, 75, 75)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            denoised, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 7
        )
        
        # Apply morphological operations to clean up the image
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # Invert the image (black text on white background)
        inverted = cv2.bitwise_not(opened)
        
        # Save intermediate steps if debugging
        if debug:
            debug_dir = "debug_processing"
            os.makedirs(debug_dir, exist_ok=True)
            cv2.imwrite(f"{debug_dir}/1_original.png", gray)
            cv2.imwrite(f"{debug_dir}/2_equalized.png", equalized)
            cv2.imwrite(f"{debug_dir}/3_denoised.png", denoised)
            cv2.imwrite(f"{debug_dir}/4_threshold.png", thresh)
            cv2.imwrite(f"{debug_dir}/5_opened.png", opened)
            cv2.imwrite(f"{debug_dir}/6_final.png", inverted)
            logger.info(f"Saved debug images to {debug_dir}/")
        
        return inverted
        
    except Exception as e:
        logger.error(f"Error in image preprocessing: {e}", exc_info=True)
        return gray if 'gray' in locals() else image  # Return best available

def ocr_page(pdf_path: str, dpi: int = 300, lang: str = "eng", debug: bool = True) -> tuple[str, float]:
    """
    Render page 1 of the PDF at the specified DPI and perform OCR.
    
    Args:
        pdf_path: Path to the PDF file
        dpi: Dots per inch for rendering the PDF (default: 300)
        lang: Language code for Tesseract (default: "eng")
        debug: If True, save debug images and additional info
        
    Returns:
        tuple: (extracted_text, confidence_score)
    """
    try:
        # Verify file exists and is accessible
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        # Open PDF and render first page
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                raise ValueError("PDF appears to be empty or corrupted")
                
            page = doc.load_page(0)
            
            # Render at higher DPI for better quality
            pix = page.get_pixmap(dpi=dpi)
            
            # Convert to OpenCV format
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            # Preprocess image with debug mode
            processed_img = preprocess_image(img_cv, debug=debug)
            
            # Save processed image for debugging
            if debug:
                debug_img_path = os.path.splitext(pdf_path)[0] + "_debug.png"
                cv2.imwrite(debug_img_path, processed_img)
                logger.info(f"Saved processed image to {debug_img_path}")
            
            # Configure Tesseract with optimized settings
            custom_config = (
                r'--oem 3 '  # LSTM engine
                r'--psm 6 '  # Assume a single uniform block of text
                r'-c preserve_interword_spaces=1 '
                r'-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?()[]{}:;\'"\/\-+*=@#$%^&_|<>\n\t\r\x0b\x0c '  # Common characters
            )
            
            # Try multiple page segmentation modes if needed
            for psm in [6, 3, 4, 11]:
                current_config = f'--oem 3 --psm {psm} -c preserve_interword_spaces=1'
                try:
                    text_data = pytesseract.image_to_data(
                        processed_img,
                        lang=lang,
                        config=current_config,
                        output_type=pytesseract.Output.DICT
                    )
                    
                    # Calculate average confidence
                    confidences = [int(c) for c in text_data['conf'] if int(c) > 0]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                    
                    # Combine text
                    text = ' '.join([t.strip() for t in text_data['text'] if t.strip()])
                    
                    if text.strip():
                        if debug:
                            logger.info(f"Successfully extracted text with PSM {psm}, confidence: {avg_confidence:.1f}%")
                        return text.strip(), avg_confidence
                        
                except Exception as e:
                    logger.warning(f"PSM {psm} failed: {str(e)}")
                    continue
            
            # If we get here, all PSMs failed
            logger.warning("All page segmentation modes failed to extract text")
            return "", 0.0
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error in ocr_page: {str(e)}", exc_info=True)
        return "", 0.0

def extract_text_with_ocr(pdf_path: str, dpi: int = 300, lang: str = "spa+eng") -> tuple[str, float]:
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

import os
import re
import logging
import pdfplumber
import PyPDF2
import pandas as pd
from datetime import datetime
from dateutil import parser as dateparser
from typing import Dict, List, Optional, Tuple
import openai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logger.warning("OPENAI_API_KEY environment variable is not set")

def extract_metadata(pdf_path: str) -> Tuple[str, str]:
    """
    Extract title and date from PDF metadata or first page content.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Tuple of (title, date) as strings
    """
    try:
        # Try to extract from PDF metadata first
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            meta = reader.metadata or {}
            
            # Get title from metadata or use filename as fallback
            title = meta.get('/Title', '') or os.path.splitext(os.path.basename(pdf_path))[0]
            
            # Try to extract creation date from metadata
            raw_date = meta.get('/CreationDate', '')
            date = ''
            
            if raw_date:
                try:
                    # Handle PDF date format (D:YYYYMMDDHHmmSS...)
                    if raw_date.startswith('D:'):
                        date_str = raw_date[2:10]  # Get YYYYMMDD
                        date_obj = datetime.strptime(date_str, '%Y%m%d')
                        date = date_obj.date().isoformat()
                except Exception as e:
                    logger.debug(f"Could not parse PDF date: {e}")
        
        # Fallback: extract from first page text
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.pages:
                first_page = pdf.pages[0].extract_text() or ""
                
                # If no title from metadata, use first line of text
                if not title.strip():
                    title = first_page.split('\n')[0].strip()
                
                # If no date from metadata, try to find date in text
                if not date:
                    # Look for common date patterns
                    date_patterns = [
                        r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',  # YYYY-MM-DD
                        r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b',  # DD-MM-YYYY
                        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'  # Month Day, Year
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, first_page)
                        if match:
                            try:
                                date_obj = dateparser.parse(match.group(0))
                                if date_obj:
                                    date = date_obj.date().isoformat()
                                    break
                            except Exception as e:
                                logger.debug(f"Could not parse date {match.group(0)}: {e}")
        
        return title, date
    
    except Exception as e:
        logger.error(f"Error extracting metadata from {pdf_path}: {e}")
        # Return filename as title and current date if extraction fails
        return os.path.basename(pdf_path), datetime.now().date().isoformat()

def summarize_pdf(pdf_path: str, max_chars: int = 3000) -> str:
    """
    Generate a summary of the PDF using OpenAI's API.
    
    Args:
        pdf_path: Path to the PDF file
        max_chars: Maximum number of characters to process
        
    Returns:
        String containing the generated summary
    """
    if not openai.api_key:
        logger.error("OpenAI API key not found")
        return "Summary unavailable: OpenAI API key not configured"
    
    try:
        # Extract text from first 3 pages or first 3000 chars
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:3]:  # First 3 pages max
                page_text = page.extract_text() or ""
                if len(text) + len(page_text) > max_chars:
                    text += page_text[:max_chars - len(text)]
                    break
                text += page_text + "\n"
        
        if not text.strip():
            return "No text content found in the document"
        
        # Prepare the prompt for OpenAI
        prompt = (
            "Provide a concise 2-sentence summary of the document below. "
            "Focus on the main topic, purpose, and key points.\n\n"
            f"{text[:max_chars]}"
        )
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Using gpt-3.5-turbo as gpt-4o-mini might not be available
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        logger.error(f"Error summarizing PDF {pdf_path}: {e}")
        return f"Error generating summary: {str(e)}"

def process_file(pdf_path: str) -> Dict[str, str]:
    """
    Process a single PDF file to extract metadata and generate a summary.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary containing file information
    """
    if not os.path.exists(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        return {
            "error": f"File not found: {os.path.basename(pdf_path)}",
            "path": pdf_path,
            "name": os.path.basename(pdf_path),
            "title": "",
            "date": "",
            "description": "Error: File not found"
        }
    
    try:
        # Extract metadata and generate summary
        title, date = extract_metadata(pdf_path)
        description = summarize_pdf(pdf_path)
        
        return {
            "path": pdf_path,
            "name": os.path.basename(pdf_path),
            "title": title[:255] if title else "No title",  # Limit title length
            "date": date or "",
            "description": description[:1000] if description else "No description generated"  # Limit description length
        }
    except Exception as e:
        logger.error(f"Error processing file {pdf_path}: {e}")
        return {
            "error": str(e),
            "path": pdf_path,
            "name": os.path.basename(pdf_path),
            "title": "",
            "date": "",
            "description": f"Error processing file: {str(e)}"
        }

def write_to_excel(records: List[Dict], excel_path: str) -> None:
    """
    Write records to an Excel file.
    
    Args:
        records: List of dictionaries containing document information
        excel_path: Path where the Excel file should be saved
        
    Raises:
        ValueError: If records is empty or invalid
        IOError: If there's an error writing the file
    """
    if not records:
        raise ValueError("No records to write to Excel")
    
    try:
        # Create a DataFrame from the records
        df = pd.DataFrame(records)
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        
        # Write to Excel with formatting
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Documents')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Documents']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(str(col))
                )
                # Add a little extra space
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
                
        logger.info(f"Successfully wrote {len(records)} records to {excel_path}")
        
    except Exception as e:
        logger.error(f"Error writing to Excel file {excel_path}: {e}")
        raise IOError(f"Failed to create Excel file: {str(e)}")

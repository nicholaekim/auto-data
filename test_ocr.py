import os
import sys
import re
import openai
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Initialize OpenAI client with API key from environment
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    print("Warning: OPENAI_API_KEY not found in environment variables.")

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent))

from src.ocr_fallback import ocr_page
from src.parse_metadata import extract_metadata

def generate_ai_description(text, max_length=200):
    """
    Generate a concise description using OpenAI's API (v1.0.0+).
    
    Args:
        text: The text to summarize
        max_length: Maximum length of the description
        
    Returns:
        Generated description or None if API call fails
    """
    try:
        # Initialize the client
        client = openai.OpenAI()
        
        # Truncate text to fit within token limits
        truncated_text = text[:4000]  # Leave room for the prompt
        
        # Make the API call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates concise document descriptions."},
                {"role": "user", "content": f"Generate a brief 1-2 sentence description of this document in English. Focus on the main topic and purpose. Document content:\n\n{truncated_text}"}
            ],
            max_tokens=100,
            temperature=0.3
        )
        
        # Extract the response content
        description = response.choices[0].message.content.strip()
        return description[:max_length]
    except Exception as e:
        print(f"Error generating AI description: {str(e)}")
        return None

def clean_document_title(text, extracted_text):
    """Clean and format the document title."""
    # First, look for a newspaper header pattern
    header_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+[A-Za-z]+\s+\d{1,2},\s*\d{4}', text)
    if header_match:
        return header_match.group(0).strip()
    
    # Look for a line that looks like a title in the first few lines
    first_lines = [line.strip() for line in extracted_text.split('\n') if line.strip()][:5]
    for line in first_lines:
        # Skip lines that are too short or too long
        if 20 <= len(line) <= 200:
            # Skip lines that are all uppercase or contain many special characters
            if (line.upper() != line and 
                sum(c.isalpha() or c.isspace() for c in line) / len(line) > 0.7):
                return line.strip()
    
    # If no good line found, clean up the filename
    clean_text = re.sub(r'[^\w\s-]', ' ', text)  # Remove special chars
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()  # Normalize whitespace
    
    # If still no good title, use first 5 words of first line
    if not clean_text or len(clean_text) < 10:
        first_line = next((line.strip() for line in extracted_text.split('\n') if line.strip()), text)
        clean_text = ' '.join(first_line.split()[:5])
    
    return clean_text if clean_text else "Untitled Document"

def extract_document_date(text, title):
    """Extract date from text with various formats."""
    # First, look for a date in the first few lines
    first_few_lines = '\n'.join(line.strip() for line in text.split('\n')[:10] if line.strip())
    
    # Try to find dates in various formats
    date_patterns = [
        # Month Day, Year (e.g., December 18, 1984)
        (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*(\d{4})\b', 
         lambda m: (m.group(2), m.group(1), m.group(1))),  # year, month, day
        # MM/DD/YYYY or MM-DD-YYYY
        (r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b',
         lambda m: (m.group(3) if len(m.group(3)) == 4 else f"20{m.group(3)}", m.group(1), m.group(2))),
        # YYYY/MM/DD or YYYY-MM-DD
        (r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b',
         lambda m: (m.group(1), m.group(2), m.group(3))),
        # Month Year (e.g., December 1984)
        (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b',
         lambda m: (m.group(2), m.group(1), "01")),  # Default to first day of month
        # Just the year (19xx or 20xx)
        (r'\b(19\d{2}|20[0-2]\d)\b',
         lambda m: (m.group(1), "01", "01"))  # Default to Jan 1st
    ]
    
    for pattern, processor in date_patterns:
        match = re.search(pattern, first_few_lines, re.IGNORECASE)
        if match:
            try:
                year, month, day = processor(match)
                # Convert month name to number if needed
                if month.isalpha():
                    from datetime import datetime
                    month_num = datetime.strptime(month[:3], "%b").month
                    month = f"{month_num:02d}"
                # Ensure day is 2 digits
                day = f"{int(day):02d}" if day else "01"
                # Ensure year is 4 digits
                if len(year) == 2:
                    year = f"20{year}"
                return f"{year}/{month}/{day}"
            except (ValueError, IndexError):
                continue
                
    # If no date found, try to find just a year
    year_match = re.search(r'\b(19\d{2}|20[0-2]\d)\b', first_few_lines)
    if year_match:
        return f"{year_match.group(1)}/01/01"
    
    # If still no date, try the filename
    if 'Document' in title and any(c.isdigit() for c in title):
        year_match = re.search(r'\b(19\d{2}|20[0-2]\d)\b', title)
        if year_match:
            return f"{year_match.group(1)}/01/01"
    
    return "Date not found"

def main():
    # Create pdfs directory if it doesn't exist
    pdfs_dir = Path("pdfs")
    pdfs_dir.mkdir(exist_ok=True)
    
    # Check if there are PDFs in the directory
    pdf_files = list(pdfs_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {pdfs_dir}/")
        print(f"Please place your PDF files in the {pdfs_dir}/ directory and try again.")
        return
    
    # Process each PDF
    for pdf_path in pdf_files:
        print(f"\nProcessing: {pdf_path}")
        print("-" * 80)
        
        try:
            # Extract text using OCR
            extracted_text, confidence = ocr_page(str(pdf_path), dpi=200, lang="eng")
            print(f"OCR Confidence: {confidence:.1f}%")
            
            # Extract metadata
            metadata = extract_metadata(extracted_text, str(pdf_path.name))
            
            # Generate AI description if we have enough text
            if len(extracted_text) > 50:  # Only generate if we have substantial text
                print("\nGenerating AI description...")
                ai_description = generate_ai_description(extracted_text)
                if ai_description:
                    metadata['description'] = ai_description
            
            # Format and print the document information
            print("\n" + "="*80)
            print(f"DOCUMENT: {pdf_path.name}".center(80))
            print("="*80)
            
            # Extract title from the first few lines
            title = ""
            if extracted_text:
                # Split into lines and clean them up
                lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]
                
                # Look for the first line that looks like a title
                for line in lines[:10]:  # Only check first 10 lines
                    line = line.strip()
                    
                    # Skip lines that are too short or too long
                    if len(line) < 15 or len(line) > 200:
                        continue
                        
                    # Skip lines that are mostly numbers or special chars
                    if sum(1 for c in line if c.isalpha()) < len(line) * 0.5:  # Less than 50% letters
                        continue
                        
                    # Calculate a score for the line based on its length and letter density
                    score = len(line) * sum(1 for c in line if c.isalpha()) / len(line)
                    if score > best_score:
                        best_score = score
                        best_line = line
                
                # Extract title from the first few lines
                title = ""
                for line in lines[:5]:  # Check first 5 lines for title
                    line = line.strip()
                    if 20 <= len(line) <= 200 and not line.isupper() and sum(c.isalpha() for c in line) > len(line) * 0.6:
                        title = line
                        break
                
                # If no good title found, use the first line or filename
                if not title:
                    title = lines[0].strip() if lines else pdf_path.stem
                
                # Clean the title
                clean_title_text = clean_document_title(title, extracted_text)
                
                # If title is still not good, use the filename
                if not clean_title_text or len(clean_title_text) < 10 or not any(c.isalpha() for c in clean_title_text):
                    clean_title_text = pdf_path.stem.replace('_', ' ').title()
                
                # Extract date from the text
                date_str = extract_document_date(extracted_text, clean_title_text)
            
            # Try to find date patterns in the title or extracted text
            date_patterns = [
                # Format: 1983 (year only in title)
                (r'\b(19\d{2})\b', 
                 lambda m: (m.group(1), '01', '01', m.group(1), '12', '31')),
                # Format: NOV. 21-22-23 DE 1984
                (r'(?P<month>JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\.?\s*(?P<day1>\d{1,2})[-–](?P<day2>\d{1,2})[-–](?P<day3>\d{1,2})\s+DE\s+(?P<year>\d{4})', 
                 lambda m: (m.group('year'), m.group('month'), m.group('day1'), 
                           m.group('year'), m.group('month'), m.group('day3'))),
                # Format: NOV. 21-23, 1984
                (r'(?P<month>JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\.?\s*(?P<day1>\d{1,2})[-–](?P<day2>\d{1,2})[,\s]+(?P<year>\d{4})',
                 lambda m: (m.group('year'), m.group('month'), m.group('day1'),
                          m.group('year'), m.group('month'), m.group('day2'))),
                # Format: 15th of October 1984
                (r'(?P<day>\d{1,2})(?:st|nd|rd|th)\s+of\s+(?P<month>JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[a-z]*\s+(?P<year>\d{4})',
                 lambda m: (m.group('year'), m.group('month'), m.group('day'),
                          m.group('year'), m.group('month'), m.group('day')))
            ]
            
            months = {'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04', 'MAY': '05', 'JUN': '06',
                     'JUL': '07', 'AUG': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'}
            
            # Search in both title and first 500 chars of text for more context
            search_texts = [title]
            if extracted_text:
                search_texts.append(extracted_text[:500])  # Increased from 200 to 500 for more context
                
                # Also try to find specific date mentions in the text (e.g., "On 15th of October 1983")
                specific_date_match = re.search(
                    r'(?:on\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[a-z]*[\s,]+(\d{4})',
                    extracted_text,
                    re.IGNORECASE
                )
                
                if specific_date_match:
                    day = specific_date_match.group(1)
                    month = specific_date_match.group(2)
                    year = specific_date_match.group(3)
                    month_num = months.get(month.upper()[:3], '10')  # Default to October if not found
                    date_str = f"{year}/{month_num}/{day.zfill(2)}"
                    
                    # If we found a specific date, don't override it with the year range
                    date_found_in_text = True
                else:
                    date_found_in_text = False
            
            for text in search_texts:
                for pattern, processor in date_patterns:
                    date_match = re.search(pattern, text, re.IGNORECASE)
                    if date_match:
                        try:
                            year1, month1, day1, year2, month2, day2 = processor(date_match)
                            month_num1 = months.get(month1.upper()[:3], '01')
                            month_num2 = months.get(month2.upper()[:3], '12')
                            
                            # Format the date range
                            if year1 == year2 and month_num1 == month_num2 and day1 == day2:
                                date_str = f"{year1}/{month_num1}/{day1.zfill(2)}"
                            else:
                                date_str = f"{year1}/{month_num1}/{day1.zfill(2)} to {year2}/{month_num2}/{day2.zfill(2)}"
                            break
                        except (IndexError, AttributeError) as e:
                            continue
                    
                    if date_str != 'Date not found':
                        break
                
                if date_str != 'Date not found':
                    break
            
            # Clean up the title by removing document numbers, organization names, and extra text
            clean_title = title
            
            # Remove document numbers and other common prefixes (e.g., "No. 12", "Document 12", "RS 12")
            clean_title = re.sub(r'(?:^|\s)(?:(?:NO\.?|DOCUMENT|RS|RO|VOL\.?|ISSUE)\s*\d+\s*|\[?\d+\]?\s*[-:]?\s*)', ' ', clean_title, flags=re.IGNORECASE)
            
            # Remove organization names and other common prefixes/suffixes
            org_phrases = [
                'international association for the establishment of peace in el salvador',
                'el salvador',
                'on 15th of october this year',
                'this year',
                '^[^a-zA-Z0-9]*',  # Remove any remaining non-alphanumeric chars at start
                '[^a-zA-Z0-9]*$'    # Remove any remaining non-alphanumeric chars at end
            ]
            
            for phrase in org_phrases:
                clean_title = re.sub(phrase, '', clean_title, flags=re.IGNORECASE)
            
            # Clean up any remaining special characters and normalize whitespace
            clean_title = re.sub(r'[^\w\s.,-]', ' ', clean_title)  # Keep basic punctuation
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()
            clean_title = clean_title.strip(' ,.-')
            
            # If title is empty after cleaning, use a fallback
            if not clean_title or len(clean_title) < 10:
                clean_title = title[:100].strip()  # Fall back to original title if cleaned version is too short
            
            # Print formatted output in a clean vertical layout
            print("\n" + "-"*80)
            print(f"TITLE:       {clean_title}")
            print(f"DATE:        {date_str}")
            
            # Print organization if found in title
            org_match = re.search(r'\b(Mi VETS|PRIMER CONGRESO|DEDERECHOSHUMANOS|EL SALVADOR)\b', title, re.IGNORECASE)
            if org_match:
                print(f"ORGANIZATION: {org_match.group(0)}")
            
            print("\n" + "DESCRIPTION:".ljust(80, '-'))
            print(metadata.get('description', 'No description available'))
            
            # Clean and format text preview
            def clean_text(text):
                # Remove common OCR artifacts and normalize text
                text = re.sub(r'[\x00-\x1F\x7F-\x9F]', ' ', text)  # Remove control characters
                text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
                return text
                
            # Get first few paragraphs for preview
            paragraphs = [p.strip() for p in extracted_text.split('\n\n') if p.strip()]
            preview_text = []
            char_count = 0
            
            for para in paragraphs:
                clean_para = clean_text(para)
                if char_count + len(clean_para) > 500:  # Limit preview length
                    preview_text.append(clean_para[:500-char_count] + '...')
                    break
                preview_text.append(clean_para)
                char_count += len(clean_para)
            
            # Clean up the title for display
            display_title = clean_document_title(extracted_text[:200], extracted_text)  # Use first 200 chars for title
            if len(display_title) > 100:  # Truncate very long titles
                display_title = display_title[:97] + '...'
            
            # Print minimal metadata
            print("\n" + "="*80)
            print(f"{'DOCUMENT:':<12} {pdf_path.name}")
            print(f"{'TITLE:':<12} {display_title}")
            print(f"{'DATE:':<12} {date_str}")
            
            # Print AI description if available
            if ai_description:
                print("\n" + "DESCRIPTION:" + "-"*(80-12))
                print(ai_description)
            
            # Create output directory if it doesn't exist
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            # Save the extracted text to a file
            output_path = output_dir / f"{pdf_path.stem}.txt"
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(extracted_text)
                print(f"\n{'Saved to:':<12} {output_path}")
            except Exception as e:
                print(f"\n{'Error saving file:'} {str(e)}")
            
            print("="*80 + "\n")
            
        except Exception as e:
            print(f"Error processing {pdf_path}: {str(e)}")

if __name__ == "__main__":
    main()

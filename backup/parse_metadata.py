"""
Metadata extraction using regex patterns and heuristics.
"""
import re
from datetime import datetime
from typing import Dict, List, Pattern, Optional, Tuple

# Precompile regex patterns for better performance
DATE_PATTERNS: List[Pattern] = [
    # English formats
    re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}\b"),
    re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"),
    re.compile(r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b"),
    re.compile(r"\b\d{4}\.\d{2}\.\d{2}\b"),
    # Spanish formats
    re.compile(r"\b\d{1,2}\s+(?:de\s+)?(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\s+de)?\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{1,2},\s*\d{4}\b", re.IGNORECASE),
    # Year only (fallback)
    re.compile(r"\b(19|20)\d{2}\b"),
]

VOL_ISSUE_PATTERNS: List[Pattern] = [
    re.compile(r"\bVolume\s+[IVXLC\d]+(?:\s*,\s*No\.?\s*\d+)\b", re.IGNORECASE),
    re.compile(r"\bVol\.?\s*\d+\s*,\s*No\.?\s*\d+\b", re.IGNORECASE),
    # Additional volume/issue formats
    re.compile(r"\bVol\.?\s*\d+\s*\(\s*No\.?\s*\d+\s*\)\b", re.IGNORECASE),
    re.compile(r"\bTomo\s+[IVXLC\d]+(?:\s*,\s*Núm\.?\s*\d+)\b", re.IGNORECASE),
]

def parse_and_format_date(date_str: str) -> Optional[str]:
    """
    Parse a date string and format it as YYYY/MM/DD.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Formatted date string (YYYY/MM/DD) or None if parsing fails
    """
    if not date_str:
        return None
        
    # Dictionary for month names in different languages
    month_map = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12',
        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
    }
    
    try:
        # Try to parse as YYYY (year only)
        if re.match(r'^\d{4}$', date_str):
            return f"{date_str}/NA/NA"  # Use NA for missing month and day
            
        # Try to parse various date formats
        for fmt in [
            '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',  # YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
            '%d %B %Y', '%d %B, %Y', '%B %d, %Y',  # 01 January 2020, 01 January, 2020, January 01, 2020
            '%d %b %Y', '%d %b, %Y', '%b %d, %Y',  # 01 Jan 2020, 01 Jan, 2020, Jan 01, 2020
            '%d/%m/%Y', '%m/%d/%Y',  # DD/MM/YYYY or MM/DD/YYYY
            '%d-%m-%Y', '%m-%d-%Y'   # DD-MM-YYYY or MM-DD-YYYY
        ]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y/%m/%d')
            except ValueError:
                continue
                
        # Try to parse month names in different languages
        for month_name, month_num in month_map.items():
            if month_name in date_str.lower():
                # Extract year (4 digits)
                year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
                if not year_match:
                    return None  # Can't determine year
                year = year_match.group(0)
                
                # Extract day (1-31)
                day_match = re.search(r'\b(0?[1-9]|[12]\d|3[01])\b', date_str)
                day = day_match.group(0).zfill(2) if day_match else 'NA'
                
                return f"{year}/{month_num}/{day}"
                
    except Exception as e:
        print(f"Error parsing date '{date_str}': {str(e)}")
    
    return None

# Common mastheads to ignore when finding titles
MASTHEADS = [
    r"Newsweek",
    r"Time",
    r"The Economist",
    r"The International Newsmagazine",
    # Add Spanish/other language mastheads
    r"El Diario de Hoy",
    r"La Prensa Gráfica",
    r"Diario El Mundo"
]

def extract_metadata(text: str, filename: str) -> Dict[str, str]:
    """
    Extract metadata from text (selectable or OCR'd).
    
    Args:
        text: Extracted text from the PDF
        filename: Name of the PDF file
        
    Returns:
        Dictionary containing extracted metadata with keys: title, date, volume_issue, description, filename
    """
    # Initialize metadata with empty values
    metadata = {
        'title': '',
        'date': '',
        'volume_issue': '',
        'description': '',
        'filename': filename
    }
    
    if not text or not text.strip():
        return metadata
    
    # Remove any null bytes that might be present in OCR'd text
    clean_text = text.replace('\x00', ' ').strip()
    
    # Split into non-blank lines for title extraction
    lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
    
    # Join lines for full-text searches
    joined_text = ' '.join(lines)

    # 1) Extract and format DATE
    for pattern in DATE_PATTERNS:
        match = pattern.search(joined_text)
        if match:
            date_str = match.group(0)
            formatted_date = parse_and_format_date(date_str)
            if formatted_date:
                metadata['date'] = formatted_date
            else:
                metadata['date'] = date_str  # Fallback to original if parsing fails
            break

    # 2) Extract VOLUME/ISSUE
    for pattern in VOL_ISSUE_PATTERNS:
        match = pattern.search(joined_text)
        if match:
            metadata['volume_issue'] = match.group(0)
            break

    # 3) Extract TITLE/HEADLINE
    # Look for multi-line titles and clean them up
    potential_title_lines = []
    
    # Check the first 10 non-empty lines
    for line in lines[:10]:
        line = line.strip()
        if not line:
            continue
            
        # Skip lines that are too short/long or are obviously not titles
        if len(line) < 5 or len(line) > 200:
            continue
            
        # Skip lines that are just numbers or special characters
        if re.match(r'^[\s\d\W]+$', line):
            continue
            
        # Skip lines that match date or volume/issue patterns
        if any(pattern.search(line) for pattern in DATE_PATTERNS + VOL_ISSUE_PATTERNS):
            continue
            
        # Skip common mastheads and headers
        if any(re.search(masthead, line, re.IGNORECASE) for masthead in MASTHEADS):
            continue
            
        potential_title_lines.append(line)
    
    # Join consecutive lines that appear to be part of the same title
    if potential_title_lines:
        # Look for the most title-like line (longest line with uppercase words)
        def title_score(line):
            # Score based on length and percentage of uppercase letters
            words = line.split()
            if not words:
                return 0
            uppercase_words = sum(1 for word in words if word.isupper())
            return len(line) * (uppercase_words / len(words))
            
        # Find the line that looks most like a title
        best_title = max(potential_title_lines, key=title_score)
        
        # If the best title is followed by another line, consider combining them
        if len(potential_title_lines) > 1:
            idx = potential_title_lines.index(best_title)
            if idx < len(potential_title_lines) - 1:
                next_line = potential_title_lines[idx + 1]
                if (len(next_line) > 5 and 
                    not any(pattern.search(next_line) for pattern in DATE_PATTERNS + VOL_ISSUE_PATTERNS)):
                    best_title = f"{best_title} {next_line}"
        
        # Clean up the title
        best_title = re.sub(r'\s+', ' ', best_title).strip()
        # Convert to title case if it's all uppercase
        if best_title.isupper():
            best_title = ' '.join(word.capitalize() for word in best_title.split())
            
        metadata['title'] = best_title
    
    return metadata

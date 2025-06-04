"""
Metadata extraction using regex patterns and heuristics.
"""
import re
import logging
import unicodedata
from datetime import datetime
from typing import Dict, Optional, List, Tuple, Pattern, Match
from dataclasses import dataclass
from collections import namedtuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants for metadata extraction
DEFAULT_LANGUAGE = 'en'
MIN_TITLE_LENGTH = 5
MAX_TITLE_LENGTH = 200

# Define a simple confidence score
ConfidenceScore = namedtuple('ConfidenceScore', ['value', 'reason'])

# Enhanced date patterns with language support
class DatePattern:
    """Container for date patterns with language support and parsing logic."""
    def __init__(self, pattern, format_str='', language='en', confidence=0.9):
        self.pattern = re.compile(pattern, re.IGNORECASE) if isinstance(pattern, str) else pattern
        self.format_str = format_str
        self.language = language
        self.confidence = confidence

DATE_PATTERNS = [
    # ISO 8601 formats (YYYY-MM-DD, YYYY/MM/DD)
    DatePattern(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b', '%Y-%m-%d'),
    
    # English dates (Month Day, Year)
    DatePattern(
        r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b',
        '%B %d, %Y', 'en'
    ),
    
    # Spanish dates (DD de MES de YYYY)
    DatePattern(
        r'\b(\d{1,2})\s+de\s+'
        r'(Ene(?:ro)?|Feb(?:rero)?|Mar(?:zo)?|Abr(?:il)?|May(?:o)?|Jun(?:io)?|'
        r'Jul(?:io)?|Ago(?:sto)?|Sep(?:tiembre)?|Oct(?:ubre)?|Nov(?:iembre)?|Dic(?:iembre)?)'
        r'\s+de\s+(\d{4})\b',
        '%d de %B de %Y', 'es'
    ),
    
    # Year only (lowest confidence)
    DatePattern(r'\b(19|20\d{2})\b', '%Y', confidence=0.7)
]

# List of (pattern, confidence) tuples for volume/issue extraction
VOL_ISSUE_PATTERNS = [
    (re.compile(r"\bVolume\s+[IVXLC\d]+(?:\s*,\s*No\.?\s*\d+)\b", re.IGNORECASE), 0.9),
    (re.compile(r"\bVol\.?\s*\d+\s*,\s*No\.?\s*\d+\b", re.IGNORECASE), 0.9),
    # Additional volume/issue formats
    (re.compile(r"\bVol\.?\s*\d+\s*\(\s*No\.?\s*\d+\s*\)\b", re.IGNORECASE), 0.9),
    (re.compile(r"\bTomo\s+[IVXLC\d]+(?:\s*,\s*Núm\.?\s*\d+)\b", re.IGNORECASE), 0.85),
    # More patterns with different formats and confidences
    (re.compile(r"\bV\.?\s*\d+\s*[,-]?\s*N[o°]?\s*\d+\b", re.IGNORECASE), 0.8),
    (re.compile(r"\bVolume\s+\d+\s*[,-]?\s*Issue\s+\d+\b", re.IGNORECASE), 0.9),
    (re.compile(r"\bVol\.?\s*\d+\s*[,-]?\s*Iss?\.?\s*\d+\b", re.IGNORECASE), 0.85),
]

def parse_and_format_date(date_str: str) -> Optional[str]:
    """
    Parse a date string and format it as YYYY/MM/DD.
    If month or day is missing, they will be set to 'NA'.
    Returns a tuple of (formatted_date, confidence_score)
    """
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip()
    best_match = None
    highest_confidence = 0.0
    
    # Try each date pattern
    for date_pattern in DATE_PATTERNS:
        match = date_pattern.pattern.search(date_str)
        if not match:
            continue
            
        try:
            # For patterns with capture groups
            if date_pattern.format_str:
                # Handle different date formats
                if '%B' in date_pattern.format_str or '%b' in date_pattern.format_str:
                    # Handle month names
                    dt = datetime.strptime(match.group(0), date_pattern.format_str)
                else:
                    # Handle numeric dates
                    parts = [int(g) for g in match.groups() if g]
                    if len(parts) == 3:
                        dt = datetime(parts[0], parts[1], parts[2])
                    elif len(parts) == 2:
                        dt = datetime(parts[0], parts[1], 1)  # Default to 1st of month
                    else:
                        dt = datetime(parts[0], 1, 1)  # Default to Jan 1st for year only
                        
                # Calculate confidence
                confidence = date_pattern.confidence
                
                # Higher confidence for complete dates
                if dt.month != 1 or dt.day != 1:
                    confidence = min(1.0, confidence + 0.1)
                
                if confidence > highest_confidence:
                    highest_confidence = confidence
                    best_match = dt
                    
        except (ValueError, IndexError) as e:
            logger.debug(f"Date parsing failed for '{date_str}': {e}")
            continue
    
    # Format the best match
    if best_match:
        # If we only have year, format with NA for month/day
        if highest_confidence < 0.8:
            return f"{best_match.year}/NA/NA"
        # If we have year and month but not day
        elif highest_confidence < 0.9:
            return f"{best_match.year}/{best_match.month:02d}/NA"
        # Full date
        else:
            return best_match.strftime('%Y/%m/%d')
    
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

def extract_metadata(text: str, filename: str, language: str = 'en') -> Dict[str, str]:
    """
    Extract metadata from the given text with improved accuracy and confidence scoring.
    
    Args:
        text: The text to extract metadata from
        filename: The name of the file being processed
        language: Language code for metadata extraction (default: 'en')
        
    Returns:
        Dictionary containing extracted metadata with confidence scores
    """
    metadata = {
        'title': {'value': '', 'confidence': 0.0, 'source': 'none'},
        'date': {'value': '', 'confidence': 0.0, 'source': 'none'},
        'volume_issue': {'value': '', 'confidence': 0.0, 'source': 'none'},
        'document_name': filename,
        'language': language,
        'extraction_confidence': 0.0
    }
    
    if not text or not text.strip():
        return metadata
    
    try:
        # Normalize text and split into lines
        text = unicodedata.normalize('NFKC', text)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return metadata
            
        # Join lines for full-text searches
        joined_text = ' '.join(lines)
        
        # 1) Extract and format DATE with confidence scoring
        best_date = None
        best_date_confidence = 0.0
        
        for date_pattern in DATE_PATTERNS:
            # Skip patterns not in the document's language if specified
            if language != 'any' and date_pattern.language != language and date_pattern.language != 'en':
                continue
                
            for match in date_pattern.pattern.finditer(joined_text):
                date_str = match.group(0)
                formatted_date = parse_and_format_date(date_str)
                
                if formatted_date:
                    # Calculate confidence based on pattern and position
                    confidence = date_pattern.confidence
                    
                    # Higher confidence for dates in the first few lines
                    if any(date_str in line for line in lines[:5]):
                        confidence = min(1.0, confidence + 0.1)
                        
                    if confidence > best_date_confidence:
                        best_date_confidence = confidence
                        best_date = {
                            'value': formatted_date,
                            'confidence': confidence,
                            'source': 'date_pattern',
                            'raw': date_str
                        }
        
        if best_date:
            metadata['date'] = best_date
        
        # 2) Extract VOLUME/ISSUE with confidence scoring
        for pattern, confidence in VOL_ISSUE_PATTERNS:
            match = pattern.search(joined_text)
            if match:
                metadata['volume_issue'] = {
                    'value': match.group(0),
                    'confidence': confidence,
                    'source': 'pattern_matching'
                }
                break
        
        # 3) Extract TITLE with improved heuristics
        title_candidates = []
        masthead_pattern = re.compile('|'.join(MASTHEADS), re.IGNORECASE)
        
        # Check first 15 lines for potential titles
        for i, line in enumerate(lines[:15]):
            line = line.strip()
            if not line:
                continue
                
            # Calculate confidence based on various factors
            confidence = 0.5
            line_length = len(line)
            
            # Skip lines that are too short or too long
            if line_length < 10 or line_length > 200:
                continue
                
            # Position-based confidence
            position_boost = max(0, (15 - i) * 0.05)  # Higher confidence for earlier lines
            confidence += position_boost
            
            # Format-based confidence
            if line.istitle() or (line[0].isupper() and any(c.islower() for c in line)):
                confidence += 0.2
                
            # Length-based confidence
            if 20 <= line_length <= 100:  # Ideal title length
                confidence += 0.1
                
            # Penalize lines that look like dates, numbers, or mastheads
            if (any(p.search(line) for p, _ in VOL_ISSUE_PATTERNS) or
                masthead_pattern.search(line)):
                confidence -= 0.3
                
            # Skip if confidence is too low
            if confidence < 0.6:
                continue
                
            title_candidates.append({
                'text': line,
                'confidence': min(1.0, confidence),
                'position': i
            })
        
        # Select best title candidate
        if title_candidates:
            # Sort by confidence (descending) and position (ascending)
            best_title = max(
                title_candidates,
                key=lambda x: (x['confidence'], -x['position'])
            )
            
            metadata['title'] = {
                'value': best_title['text'],
                'confidence': best_title['confidence'],
                'source': 'heuristic',
                'position': best_title['position']
            }
        
        # Fallback: Use first non-empty line if no good title found
        if not metadata['title']['value']:
            first_line = next((line for line in lines if line.strip()), '').strip()
            if first_line:
                metadata['title'] = {
                    'value': first_line,
                    'confidence': 0.3,
                    'source': 'first_line_fallback'
                }
        
        # Calculate overall extraction confidence
        confidences = [
            metadata['title']['confidence'],
            metadata['date']['confidence'],
            metadata['volume_issue']['confidence'] * 0.5  # Lower weight for volume/issue
        ]
        metadata['extraction_confidence'] = sum(confidences) / len(confidences)
        
    except Exception as e:
        logger.error(f"Error extracting metadata: {str(e)}", exc_info=True)
        metadata['error'] = str(e)
    
    # Convert to simple dict for backward compatibility
    return {
        'title': metadata['title']['value'],
        'date': metadata['date']['value'],
        'volume_issue': metadata['volume_issue']['value'],
        'document_name': metadata['document_name'],
        '_confidence': {
            'title': metadata['title']['confidence'],
            'date': metadata['date']['confidence'],
            'volume_issue': metadata['volume_issue']['confidence'],
            'overall': metadata.get('extraction_confidence', 0.0)
        },
        '_sources': {
            'title': metadata['title']['source'],
            'date': metadata['date']['source'],
            'volume_issue': metadata['volume_issue']['source']
        }
    }

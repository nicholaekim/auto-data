"""
Generate descriptions for PDF pages using a combination of heuristics and LLM summarization.
"""
import re
from typing import List, Dict, Any
from .llm_fallback import extract_metadata_with_llm

def generate_description(text: str, filename: str) -> str:
    """
    Generate a description for the document using heuristics and LLM fallback.
    
    Args:
        text: Extracted text from the PDF
        filename: Name of the PDF file
        
    Returns:
        Generated description as a string
    """
    # First try to extract key sections using heuristics
    description = extract_key_sections(text)
    
    # If heuristics didn't find enough content, use LLM fallback
    if len(description.split()) < 20:  # If description is too short
        llm_metadata = extract_metadata_with_llm(text, filename)
        description = llm_metadata.get('description', '')
    
    return description

def extract_key_sections(text: str) -> str:
    """
    Extract key sections from the text using heuristics.
    
    Args:
        text: Extracted text from the PDF
        
    Returns:
        Extracted key sections as a single string
    """
    # Look for common section headers
    sections = []
    
    # Try to find introduction/conclusion
    intro_match = re.search(
        r'(?i)(?:introducci[oó]n|introduction|resumen|summary)[\s\:]+(.+?)(?=\n\n[A-Z]|$)',
        text, re.DOTALL
    )
    if intro_match:
        sections.append(intro_match.group(1).strip())
    
    # Try to find conclusions
    concl_match = re.search(
        r'(?i)(?:conclusiones|conclusion|recomendaciones|recomendations)[\s\:]+(.+?)(?=\n\n[A-Z]|$)',
        text, re.DOTALL
    )
    if concl_match:
        sections.append(concl_match.group(1).strip())
    
    # If no sections found, take first 3 non-empty paragraphs
    if not sections:
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        sections = paragraphs[:3]
    
    return ' '.join(sections)

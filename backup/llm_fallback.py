"""
LLM-based metadata extraction as a fallback when heuristics fail.
"""
import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_metadata_with_llm(text: str, filename: str) -> Dict[str, str]:
    """
    Extract metadata using LLM when heuristics fail.
    
    Args:
        text: Extracted text from the PDF
        filename: Name of the PDF file
        
    Returns:
        Dictionary containing extracted metadata
    """
    prompt = f"""Extract the following metadata from the text below:
    - Title
    - Date (in YYYY-MM-DD format, use 1900-01-01 if only year is known)
    - Volume/Issue (if any)
    - A 2-3 sentence description
    
    Return as a JSON object with these keys: title, date, volume_issue, description
    
    Text:
    {text[:8000]}  # Limit to first 8000 chars to avoid context window issues
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts metadata from documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        result['filename'] = filename
        return result
        
    except Exception as e:
        print(f"Error during LLM extraction: {str(e)}")
        return {
            'title': '',
            'date': '',
            'volume_issue': '',
            'description': f'Error during extraction: {str(e)}',
            'filename': filename
        }

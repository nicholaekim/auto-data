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
            extracted_text = ocr_page(str(pdf_path), dpi=200, lang="eng")
            
            # Extract metadata
            metadata = extract_metadata(extracted_text, str(pdf_path.name))
            
            # Generate AI description if we have enough text
            if len(extracted_text) > 50:  # Only generate if we have substantial text
                print("\nGenerating AI description...")
                ai_description = generate_ai_description(extracted_text)
                if ai_description:
                    metadata['description'] = ai_description
            
            # Print formatted metadata in the requested format
            print("\n" + "="*80)
            print(f"Document name: {pdf_path.name}")
            print("-"*80)
            print(f"Title: {metadata.get('title', 'N/A')}")
            print(f"Description: {metadata.get('description', 'No description available')}")
            print(f"Date: {metadata.get('date', 'N/A')}")
            if metadata.get('volume_issue'):
                print(f"Volume / Issue Number: {metadata['volume_issue']}")
            print("="*80)
            
            # Print a preview of the extracted text
            preview = extracted_text[:500]
            if len(extracted_text) > 500:
                preview += "..."
            
            print("\nTEXT PREVIEW:" + "-"*40)
            print(preview)
            print(f"\nTotal characters extracted: {len(extracted_text)}")
            
            # Save full text to a file
            output_file = pdf_path.with_suffix(".txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            print(f"\nFull text saved to: {output_file}")
            
        except Exception as e:
            print(f"Error processing {pdf_path}: {str(e)}")

if __name__ == "__main__":
    main()

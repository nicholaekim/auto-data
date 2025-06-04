"""
Main module for the PDF metadata extraction pipeline.
Orchestrates the entire process from file input to metadata extraction.
"""
import os
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .extract_text import extract_text
from .parse_metadata import extract_metadata
from .describe_page import generate_description
from .llm_fallback import extract_metadata_with_llm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def process_pdf(pdf_path: str, use_llm_fallback: bool = True) -> Dict[str, Any]:
    """
    Process a single PDF file to extract metadata.
    
    Args:
        pdf_path: Path to the PDF file
        use_llm_fallback: Whether to use LLM fallback for metadata extraction
        
    Returns:
        Dictionary containing extracted metadata and processing info
    """
    try:
        filename = os.path.basename(pdf_path)
        logger.info(f"Processing: {filename}")
        
        # Extract text from PDF
        text, used_ocr = extract_text(pdf_path)
        
        # Extract metadata using heuristics
        metadata = extract_metadata(text, filename)
        
        # If heuristics didn't find enough info, use LLM fallback
        if use_llm_fallback and (not metadata.get('title') or not metadata.get('date')):
            logger.info("Using LLM fallback for metadata extraction")
            llm_metadata = extract_metadata_with_llm(text, filename)
            
            # Only update empty fields
            for key in ['title', 'date', 'volume_issue', 'description']:
                if not metadata.get(key) and llm_metadata.get(key):
                    metadata[key] = llm_metadata[key]
        
        # Generate description if not already extracted
        if not metadata.get('description'):
            metadata['description'] = generate_description(text, filename)
        
        # Add processing metadata
        metadata.update({
            'processing': {
                'used_ocr': used_ocr,
                'success': True,
                'error': None
            }
        })
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {str(e)}")
        return {
            'filename': os.path.basename(pdf_path),
            'processing': {
                'success': False,
                'error': str(e)
            }
        }

def process_directory(input_dir: str, output_file: Optional[str] = None, 
                    max_workers: int = 4) -> List[Dict[str, Any]]:
    """
    Process all PDFs in a directory.
    
    Args:
        input_dir: Directory containing PDFs
        output_file: Optional path to save results (JSONL format)
        max_workers: Maximum number of parallel workers
        
    Returns:
        List of metadata dictionaries for all processed PDFs
    """
    # Create output directory if it doesn't exist
    if output_file:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # Find all PDFs in the directory
    pdf_files = list(Path(input_dir).glob('*.pdf'))
    if not pdf_files:
        logger.warning(f"No PDF files found in {input_dir}")
        return []
    
    logger.info(f"Found {len(pdf_files)} PDFs to process")
    
    # Process PDFs in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pdf = {
            executor.submit(process_pdf, str(pdf)): pdf 
            for pdf in pdf_files
        }
        
        for future in as_completed(future_to_pdf):
            pdf = future_to_pdf[future]
            try:
                result = future.result()
                results.append(result)
                
                # Save results after each successful processing
                if output_file:
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(result, ensure_ascii=False) + '\n')
                
                logger.info(f"Processed: {pdf.name}")
                
            except Exception as e:
                logger.error(f"Error processing {pdf}: {str(e)}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Extract metadata from PDFs')
    parser.add_argument('input', help='Input PDF file or directory')
    parser.add_argument('-o', '--output', help='Output JSON file for results')
    parser.add_argument('-w', '--workers', type=int, default=4,
                      help='Number of worker processes (default: 4)')
    
    args = parser.parse_args()
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    if os.path.isfile(args.input) and args.input.lower().endswith('.pdf'):
        # Process single file
        result = process_pdf(args.input)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
    else:
        # Process directory
        results = process_directory(
            args.input, 
            output_file=args.output,
            max_workers=args.workers
        )
        print(f"Processed {len(results)} files")

if __name__ == '__main__':
    main()

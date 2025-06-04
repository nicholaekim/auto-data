# PDF Metadata Extractor

A robust Python tool for extracting metadata from PDF documents, with support for both searchable text and OCR fallback.

## Features

- Extracts title, date, volume/issue, and descriptions from PDFs
- Handles both searchable and scanned PDFs with OCR fallback
- Uses heuristics first, with LLM fallback for better accuracy
- Parallel processing for batch operations
- Comprehensive logging and error handling

## Project Structure

```
auto-data/
├── .gitignore
├── README.md
├── requirements.txt
├── secrets.example           # Template for environment variables
├── metadata_cache.json       # Optional, auto-generated
├── logs/                     # Log files
├── pdfs/                     # Place your PDFs here
├── src/                      # Source code
│   ├── __init__.py
│   ├── extract_text.py       # Text extraction with OCR fallback
│   ├── parse_metadata.py     # Regex-based metadata extraction
│   ├── ocr_fallback.py       # OCR logic
│   ├── llm_fallback.py       # LLM-based extraction
│   ├── describe_page.py      # Description generation
│   └── main.py               # Main orchestrator
└── tests/                    # Unit tests
    ├── __init__.py
    ├── test_parse_metadata.py
    ├── test_ocr_fallback.py
    └── test_describe_page.py
```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/nicholaekim/auto-data.git
   cd auto-data
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Tesseract OCR:
   - **macOS**: `brew install tesseract`
   - **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`
   - **Windows**: Download installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)

5. Set up environment variables:
   ```bash
   cp secrets.example .env
   # Edit .env with your actual API keys
   ```

## Usage

### Process a single PDF

```bash
python -m src.main path/to/your/document.pdf -o output.json
```

### Process all PDFs in a directory

```bash
python -m src.main ./pdfs -o results.jsonl
```

### Command-line Options

- `-o, --output`: Output file for results (JSON or JSONL format)
- `-w, --workers`: Number of worker processes (default: 4)

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Adding New Features

1. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and write tests

3. Run tests and linting:
   ```bash
   pytest
   flake8 src/
   ```

4. Commit and push your changes:
   ```bash
   git add .
   git commit -m "Add your feature"
   git push origin feature/your-feature-name
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

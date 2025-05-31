import os
import re
import sys
import pdfplumber
import PyPDF2
import openai
from dateutil import parser as dateparser

# Initialize OpenAI from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    sys.exit("ERROR: OPENAI_API_KEY not set. Run 'export OPENAI_API_KEY=…' first.")

def extract_metadata(pdf_path):
    """
    Try to pull title + date from PDF metadata.
    If missing, fallback to first-page text.
    """
    reader = PyPDF2.PdfReader(pdf_path)
    meta = reader.metadata or {}

    title = meta.title or ""
    raw_date = meta.get("/CreationDate", "")

    # Normalize raw_date if present
    date = ""
    if raw_date:
        try:
            date = dateparser.parse(raw_date).date().isoformat()
        except Exception:
            date = ""

    # Fallback: first-page text
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text() or ""

    if not title:
        title = first_page_text.strip().split("\n")[0]

    if not date:
        m = re.search(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b", first_page_text)
        if m:
            date = m.group(1)

    return title, date, first_page_text

def extract_volume_issue(first_page_text):
    """
    Simple regex to catch "Vol. 12, No. 3" or "Volume 12 Issue 3".
    """
    patterns = [
        r"(Vol\.?\s*\d+\s*,\s*No\.?\s*\d+)",
        r"(Volume\s*\d+\s*Issue\s*\d+)",
        r"(Volume\s*\d+\s*,\s*No\.?\s*\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, first_page_text, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return ""

def summarize_pdf(pdf_path, max_chars=3000):
    """
    Read up to the first 3 pages of text and ask OpenAI for a 2‑sentence summary.
    """
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:3]:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
            if len(text) > max_chars:
                break

    prompt = "Provide a 2-sentence description of this document:\n\n" + text[:max_chars]
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error getting summary: {e}]"

def process_pdf_file(pdf_path):
    """
    Main driver: extract metadata, summary, volume/issue, then print to terminal.
    """
    if not os.path.isfile(pdf_path):
        print(f"  ✖ File not found: {pdf_path}")
        return

    print(f"\nProcessing: {os.path.basename(pdf_path)}")
    title, date, first_page_text = extract_metadata(pdf_path)
    volume_issue = extract_volume_issue(first_page_text)
    description = summarize_pdf(pdf_path)

    print(f"  • File name:    {os.path.basename(pdf_path)}")
    print(f"  • Title:        {title}")
    print(f"  • Date:         {date}")
    print(f"  • Volume/Issue: {volume_issue or 'N/A'}")
    print(f"  • Description:\n{description}\n")

if __name__ == "__main__":
    # Expect one or more PDF paths: python process_pdfs.py file1.pdf file2.pdf
    if len(sys.argv) < 2:
        print("Usage: python process_pdfs.py <file1.pdf> [file2.pdf ...]")
        sys.exit(1)

    for pdf in sys.argv[1:]:
        process_pdf_file(pdf)

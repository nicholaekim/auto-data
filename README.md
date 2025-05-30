// Copilot prompt:
You’re a senior Python engineer. Generate a standalone GUI app (no web server) called `gui_labeler.py` that:

1. Uses PySimpleGUI to open a window where the user can drag‑and‑drop one or more PDF files.
2. Copies each dropped PDF into an `uploads/` folder.
3. Loads the existing Excel file `ES Archives Summer '24 Metadata.xlsx` with pandas/openpyxl.
4. Promotes the real header row (e.g. where “Name” appears) and finds the column matching each PDF’s filename.
5. For each PDF:
   • Extracts metadata (title + creation date) with PyPDF2, falling back to first‑page text via pdfplumber and regex/dateutil.
   • Reads the first 3 pages’ text (up to 3000 chars) and sends it to OpenAI’s ChatCompletion API (`gpt-4o-mini`, temp=0.3) to produce a 2‑sentence summary, reading the key from `OPENAI_API_KEY`.
   • Writes “Extracted Title”, “Extracted Date”, and “Extracted Description” into new columns in the DataFrame.
6. Saves the DataFrame back to the same Excel file (overwrite) preserving all other columns.
7. Shows success or error popups as needed.

Include imports, environment‑variable key loading, inline comments, and a `main()` entrypoint. Make it production‑ready (error handling, folder creation).


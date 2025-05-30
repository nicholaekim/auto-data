import os
from flask import Flask, request, send_file, jsonify
from processing import process_file, write_to_excel

# Initialize Flask app
app = Flask(__name__)

# Configuration
UPLOAD_DIR = "uploads"
OUTPUT_FILE = "output/labels.xlsx"
ALLOWED_EXTENSIONS = {'pdf'}

# Ensure required directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET", "POST"])
def index():
    """Handle file upload and processing."""
    if request.method == "POST":
        # Check if the post request has the file part
        if 'pdfs' not in request.files:
            return jsonify({"error": "No file part"}), 400
            
        files = request.files.getlist("pdfs")
        if not files or not files[0].filename:
            return jsonify({"error": "No selected files"}), 400
            
        records = []
        for f in files:
            if not allowed_file(f.filename):
                continue
                
            save_path = os.path.join(UPLOAD_DIR, f.filename)
            try:
                f.save(save_path)
                records.append(process_file(save_path))
            except Exception as e:
                app.logger.error(f"Error processing {f.filename}: {str(e)}")
                continue
                
        if not records:
            return jsonify({"error": "No valid PDFs processed"}), 400
            
        try:
            write_to_excel(records, OUTPUT_FILE)
            return send_file(
                OUTPUT_FILE,
                as_attachment=True,
                download_name="document_labels.xlsx"
            )
        except Exception as e:
            app.logger.error(f"Error generating Excel: {str(e)}")
            return jsonify({"error": "Failed to generate Excel file"}), 500
    
    # Return HTML form for GET request
    return """
    <!doctype html>
    <html>
    <head>
        <title>PDF Labeler</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .container { border: 2px dashed #ccc; padding: 20px; text-align: center; border-radius: 5px; }
            h2 { color: #333; }
            .btn { 
                background-color: #4CAF50; 
                color: white; 
                padding: 10px 20px; 
                border: none; 
                border-radius: 4px; 
                cursor: pointer; 
                font-size: 16px;
                margin-top: 15px;
            }
            .btn:hover { background-color: #45a049; }
            .info { margin-top: 20px; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>PDF Labeler</h2>
            <p>Upload one or more PDF files to generate labeled Excel output</p>
            <form method="post" enctype="multipart/form-data">
                <input type="file" name="pdfs" multiple accept="application/pdf">
                <div>
                    <button type="submit" class="btn">Upload & Generate Labels</button>
                </div>
            </form>
            <div class="info">
                <p>Note: The first 3 pages of each PDF will be analyzed to generate a summary.</p>
                <p>Make sure your OPENAI_API_KEY environment variable is set.</p>
            </div>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    # Check for required environment variable
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY environment variable is not set")
    
    # Run the application
    app.run(debug=True, port=5000)
    
    # For production use:
    # app.run(host='0.0.0.0', port=5000, debug=False)

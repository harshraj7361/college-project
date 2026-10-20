# 📚 PDF Notes Generator (College Minor Project)

A clean, beginner-friendly web application that allows users to upload any PDF document (lecture notes, textbook chapters, research papers) and automatically generate short, structured, and easy-to-understand study notes.

---

## 🌟 Project Overview

- **Frontend**: Clean and responsive UI built using **HTML5, Modern CSS (Glassmorphism & Gradients), and Vanilla JavaScript**.
- **Backend**: High-performance REST API built using **Python and FastAPI**.
- **PDF Extraction**: Fast in-memory text parsing powered by **PyMuPDF (`pymupdf`)**.
- **AI Engine**: Summarization powered by **Google Gemini 2.5 Flash** (via `google-genai`), with an automatic built-in offline summarizer fallback so the project **always works during evaluations and presentations** even without an API key!
- **Zero Database / Zero Auth**: Kept strictly simple, lightweight, and suitable for academic submission.

---

## 📁 Beginner-Friendly Project Structure

```
mini -project/
├── backend/
│   ├── __init__.py           # Package marker
│   ├── main.py               # FastAPI server, endpoints, and static file serving
│   ├── pdf_utils.py          # PyMuPDF text extraction & PDF validations
│   └── ai_service.py         # Google Gemini AI integration & fallback summarizer
├── frontend/
│   ├── index.html            # User interface structure (Drag & Drop zone, Notes viewer)
│   ├── style.css             # Modern responsive styling, glassmorphism, animations
│   └── app.js                # Frontend logic (file selection, API calls, download, copy)
├── sample_pdfs/
│   ├── generate_sample.py    # Script that generated the test PDF
│   └── operating_systems_notes.pdf # Multi-page academic study material for testing
├── .env.example              # Sample environment configuration template
├── .env                      # Active environment configuration
├── requirements.txt          # Python dependencies
├── run.py                    # One-click launcher script (opens browser automatically)
├── test_app.py               # Automated verification test suite
└── README.md                 # Complete project documentation
```

---

## 🚀 How to Run Locally (Step-by-Step)

### Step 1: Open Terminal in the Project Folder
Open PowerShell or your command prompt in the project root directory:
```powershell
cd "c:\Users\harsh\OneDrive\Desktop\mini -project"
```

### Step 2: (Recommended) Create & Activate a Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows (PowerShell)
.\venv\Scripts\Activate.ps1
```
*(If you encounter a PowerShell execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

### Step 3: Install Required Packages
```powershell
pip install -r requirements.txt
```

### Step 4: Configure Gemini API Key (Optional)
The project works immediately out of the box using its built-in engine. To enable **Google Gemini 2.5 Flash AI**:
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Open the `.env` file in the project folder and paste your key:
   ```env
   GEMINI_API_KEY=AIzaSyYourActualKeyHere
   ```
*(You can also paste the API key directly into the web UI via the "API Key" button on the top right).*

### Step 5: Start the Application
Run the launcher script:
```powershell
python run.py
```
Or run directly with Uvicorn:
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Your browser will automatically open to:
👉 **http://127.0.0.1:8000**

Interactive API documentation (Swagger UI) is available at:
👉 **http://127.0.0.1:8000/docs**

---

## 🧪 Testing the Project

We have included an automated test suite that tests extraction, endpoint validations, and note generation:
```powershell
python test_app.py
```
All 6/6 tests verify:
- ✅ PyMuPDF text extraction accuracy.
- ✅ AI notes formatting & section generation.
- ✅ FastAPI healthcheck endpoint.
- ✅ Full PDF file upload and processing.
- ✅ Rejection of non-PDF files (e.g. `.txt`).
- ✅ Rejection of empty (0-byte) files.

---

## 🎯 Key Features

1. **Drag-and-Drop & File Picker**:
   - Easily drop any PDF or click to browse.
   - Shows real-time file name and formatted size badge (KB/MB).
   - Instant validation for `.pdf` extension and 15 MB size limit.

2. **One-Click Bundled Sample PDF**:
   - Includes an embedded academic document (`operating_systems_notes.pdf`) covering OS Concepts, CPU Scheduling, and Virtual Memory.
   - Allows instant demonstration with zero manual file search.

3. **PyMuPDF Text Extraction**:
   - Reads PDFs page by page directly in memory (`stream=file_bytes`).
   - Detects image-only or scanned PDFs that lack digital text and shows friendly, helpful error messages.

4. **Multi-Style Note Generation**:
   - **Standard Revision Notes** (Balanced with definitions and key takeaways).
   - **Quick Summary** (Bullet points only, rapid scanning).
   - **In-Depth Study Notes** (Detailed concepts with explanations).

5. **Structured Notes Display**:
   - 📌 **Quick Summary**
   - 🔑 **Key Concepts & Highlights**
   - 📖 **Important Definitions & Terms**
   - 💡 **Quick Exam / Revision Takeaways**

6. **Export & Utility Tools**:
   - **💾 Download as .txt**: Automatically generates and downloads `Notes_<filename>.txt`.
   - **📋 Copy to Clipboard**: Copies the full formatted study notes with instant feedback.
   - **🔄 New PDF**: Resets the workspace with a single click.

---

## 🎓 College Viva / Project Presentation Guide

### Q1: Why did you choose PyMuPDF over other PDF libraries like PyPDF2 or pdfminer?
> **Answer**: PyMuPDF (`pymupdf`) is written in C/C++ (MuPDF engine) with Python bindings. It is up to 10x faster than pure-Python libraries like PyPDF2, handles complex multi-column layouts gracefully, supports in-memory byte stream extraction without creating temporary files on disk, and has clean page-by-page text methods.

### Q2: Why did you use FastAPI instead of Flask or Django?
> **Answer**: 
> - **Speed & Asynchronous Support**: FastAPI is built on Starlette and ASGI (`uvicorn`), offering async/await support for non-blocking I/O.
> - **Automatic Validation**: Uses Python type hints and Pydantic for request and response validation.
> - **Built-in Interactive Documentation**: Automatically generates interactive Swagger UI documentation at `/docs`.
> - **Lightweight**: Flask requires several external extensions for CORS, OpenAPI, and validation, whereas FastAPI provides them natively while remaining much lighter than Django.

### Q3: What happens if a user uploads a scanned image PDF?
> **Answer**: `pdf_utils.py` inspects the extracted text from all pages. If no selectable digital text is found (or fewer than 10 words), the backend catches this and returns a clear `422 Unprocessable Entity` error informing the user that the PDF is scanned or image-based, rather than crashing the system.

### Q4: How is the separation of concerns maintained?
> **Answer**:
> - `frontend/`: Responsible only for UI rendering, drag-and-drop file capture, Markdown visualization, and trigger downloads.
> - `backend/pdf_utils.py`: Dedicated purely to reading PDF byte streams and returning clean text.
> - `backend/ai_service.py`: Dedicated purely to formatting prompts, communicating with the AI model, and executing fallback heuristics.
> - `backend/main.py`: Coordinates API routing, CORS, input validation, and file serving.

---

## 📄 License
This project was developed for educational purposes and is free to use for college projects, assignments, and study demonstrations.

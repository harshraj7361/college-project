"""
main.py - FastAPI Backend for PDF Notes Generator
--------------------------------------------------
Serves API endpoints for:
1. PDF upload, validation, and text extraction using PyMuPDF.
2. Topic-wise AI note generation (separate notes per chapter/heading).
3. Static file serving for the frontend and sample PDFs.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.pdf_utils import extract_text_from_pdf
from backend.ai_service import generate_notes, answer_question

# Directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
SAMPLE_DIR = BASE_DIR / "sample_pdfs"

# FastAPI app
app = FastAPI(
    title="PDF Notes Generator API",
    description="Generates topic-wise study notes from uploaded PDFs using PyMuPDF and Gemini AI",
    version="2.0.0"
)

# CORS – allow all origins so the frontend can always talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Max upload: 15 MB
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024


@app.get("/api/health")
async def health_check():
    """Health check – also reports whether a Gemini API key is configured."""
    has_api_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "status": "online",
        "has_gemini_api_key": has_api_key,
        "message": "PDF Notes Generator API is running smoothly.",
        "version": "2.0.0"
    }


@app.post("/api/generate-notes")
async def handle_generate_notes(
    file: UploadFile = File(..., description="PDF file to summarize"),
    custom_api_key: Optional[str] = Form(None, description="Optional per-request Gemini API key"),
    note_style: Optional[str] = Form("standard", description="concise | standard | detailed"),
):
    """
    Main endpoint:
    1. Validates the uploaded file (type, size, not empty).
    2. Extracts text and topic segments using PyMuPDF.
    3. Generates separate AI notes for each topic.
    4. Returns structured JSON including per-topic notes and an overall summary.
    """
    # ── 1. Validate file ──────────────────────────────────────────────────────
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded. Please select a valid PDF file."
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.filename}'. Only .pdf files are supported."
        )

    # ── 2. Read bytes ─────────────────────────────────────────────────────────
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read the uploaded file: {str(e)}"
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is empty (0 bytes). Please upload a valid document."
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of {max_mb} MB."
        )

    # ── 3. Extract text & topic segments using PyMuPDF ────────────────────────
    try:
        extraction = extract_text_from_pdf(file_bytes)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF extraction error: {str(e)}"
        )

    # ── 4. Generate topic-wise notes via AI service ───────────────────────────
    try:
        ai_result = generate_notes(
            text=extraction["text"],
            topics=extraction.get("topics"),         # NEW: pass topic list
            custom_api_key=custom_api_key,
            note_style=note_style or "standard",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Note generation error: {str(e)}"
        )

    # ── 5. Return structured response ─────────────────────────────────────────
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "filename": file.filename,
            "pages": extraction["pages"],
            "word_count": extraction["word_count"],
            "character_count": extraction["character_count"],
            "note_style": note_style,
            # Combined full text (for download/copy)
            "notes": ai_result["notes"],
            # Per-topic list: [{"title": str, "notes": str}, ...]
            "topics": ai_result["topics"],
            # Short overall document summary
            "overall_summary": ai_result["overall_summary"],
            "engine": ai_result["engine"],
            "used_api": ai_result["used_api"],
            "message": ai_result.get("message", "Notes generated successfully!"),
            "topic_count": len(ai_result["topics"]),
            # Extracted plain text used as context for the Q&A feature
            "extracted_text": extraction["text"],
        }
    )


# ─── Ask Questions About PDF Endpoint ─────────────────────────────────────────

class AskQuestionRequest(BaseModel):
    question: str = Field(..., description="User's question about the PDF")
    pdf_text: str = Field(..., description="Extracted text from the uploaded PDF")
    custom_api_key: Optional[str] = Field(None, description="Optional per-request Gemini API key")


@app.post("/api/ask-question")
async def handle_ask_question(payload: AskQuestionRequest):
    """
    Answers questions about the uploaded PDF:
    1. Uses the extracted PDF text as context.
    2. For long PDFs, retrieves the most relevant text sections.
    3. Provides beginner-friendly answers.
    4. If not available in the PDF, returns:
       'This information was not found in the uploaded PDF.'
    """
    q = (payload.question or "").strip()
    if not q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a question to ask about the PDF."
        )

    text = (payload.pdf_text or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PDF text context provided. Please upload and process a PDF first."
        )

    try:
        result = answer_question(
            question=q,
            pdf_text=text,
            custom_api_key=payload.custom_api_key,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "question": q,
                "answer": result["answer"],
                "engine": result["engine"],
                "used_api": result["used_api"],
                "context_chunks_used": result.get("context_chunks_used", 1),
                "found": result.get("found", True),
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Question answering error: {str(e)}"
        )


# ── Static file mounts ────────────────────────────────────────────────────────
if SAMPLE_DIR.exists():
    app.mount("/sample_pdfs", StaticFiles(directory=str(SAMPLE_DIR)), name="sample_pdfs")

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

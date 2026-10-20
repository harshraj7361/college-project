"""
test_app.py - Automated Verification Test Suite (v2 - Topic-wise)
------------------------------------------------------------------
Tests:
  1. PyMuPDF text extraction and topic segmentation.
  2. AI notes generation for multiple topics (fallback engine).
  3. FastAPI health endpoint.
  4. Full PDF upload → per-topic notes generation endpoint.
  5. Invalid file type rejection.
  6. Empty file rejection.
  7. Topic count in response matches extracted topics.
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.main import app
from backend.pdf_utils import extract_text_from_pdf
from backend.ai_service import generate_notes

client = TestClient(app)
SAMPLE_PDF = Path(__file__).resolve().parent / "sample_pdfs" / "operating_systems_notes.pdf"


def test_pdf_extraction_and_topic_segmentation():
    print("Testing PyMuPDF extraction + topic segmentation...")
    assert SAMPLE_PDF.exists(), "Sample PDF must exist. Run: python sample_pdfs/generate_sample.py"

    with open(SAMPLE_PDF, "rb") as f:
        file_bytes = f.read()

    result = extract_text_from_pdf(file_bytes)

    assert result["success"] is True
    assert result["pages"] >= 2, "Should have at least 2 pages"
    assert result["word_count"] > 100
    assert "topics" in result, "Result must contain a 'topics' key"
    assert len(result["topics"]) >= 3, (
        f"Expected at least 3 topics, got {len(result['topics'])}: "
        f"{[t['title'] for t in result['topics']]}"
    )
    for t in result["topics"]:
        assert "title" in t and t["title"], "Each topic must have a non-empty title"
        assert "content" in t and len(t["content"].split()) > 5, (
            f"Topic '{t['title']}' has too little content"
        )

    print(f"Extraction passed: {result['pages']} pages, {result['word_count']} words, "
          f"{len(result['topics'])} topics detected.")
    for t in result["topics"]:
        print(f"   - {t['title']} ({len(t['content'].split())} words)")


def test_per_topic_notes_generation():
    print("Testing per-topic notes generation (fallback engine)...")
    topics = [
        {"title": "Process Management", "content":
            "A process is a program in execution. The OS manages processes using a Process Control Block (PCB). "
            "Processes move through states: New, Ready, Running, Waiting, Terminated. "
            "CPU scheduling determines which process runs next."},
        {"title": "Memory Management", "content":
            "Memory management tracks RAM allocation. Paging divides memory into fixed-size pages and frames. "
            "Virtual memory extends RAM using disk storage. Page faults occur when a page is not in memory. "
            "Thrashing is excessive swapping that degrades performance."},
    ]
    sample_text = " ".join(t["content"] for t in topics)
    result = generate_notes(text=sample_text, topics=topics, note_style="standard")

    assert "notes" in result, "Result must contain 'notes'"
    assert "topics" in result, "Result must contain per-topic 'topics' list"
    assert "overall_summary" in result, "Result must contain 'overall_summary'"
    assert len(result["topics"]) == 2, (
        f"Expected 2 topic results, got {len(result['topics'])}"
    )

    for t in result["topics"]:
        assert "title" in t and t["title"], "Each topic result must have a title"
        assert "notes" in t and len(t["notes"]) > 30, (
            f"Topic '{t['title']}' notes are too short"
        )
        # Check for expected sections in notes
        assert "Simple Explanation" in t["notes"] or "Important Points" in t["notes"], (
            f"Topic '{t['title']}' notes missing expected sections"
        )

    print(f"Per-topic notes test passed! Engine: {result['engine']}")
    for t in result["topics"]:
        print(f"   - {t['title']}: {len(t['notes'])} chars")


def test_health_endpoint():
    print("Testing /api/health endpoint...")
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "has_gemini_api_key" in data
    print("Health endpoint test passed!")


def test_upload_and_generate_topic_notes_endpoint():
    print("Testing /api/generate-notes endpoint (topic-wise response)...")
    with open(SAMPLE_PDF, "rb") as f:
        response = client.post(
            "/api/generate-notes",
            files={"file": ("operating_systems_notes.pdf", f, "application/pdf")},
            data={"note_style": "standard"}
        )

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    data = response.json()

    # Core fields
    assert data["success"] is True
    assert data["pages"] >= 2
    assert data["word_count"] > 100

    # Topic-wise fields (NEW in v2)
    assert "topics" in data, "Response must include 'topics' list"
    assert "overall_summary" in data, "Response must include 'overall_summary'"
    assert "topic_count" in data, "Response must include 'topic_count'"
    assert data["topic_count"] >= 3, (
        f"Expected at least 3 topics, got {data['topic_count']}"
    )
    assert len(data["topics"]) == data["topic_count"], (
        "topics list length should match topic_count"
    )

    # Each topic has title and notes
    for t in data["topics"]:
        assert t.get("title"), "Each topic must have a title"
        assert len(t.get("notes", "")) > 20, f"Topic '{t['title']}' has too little notes"

    # Combined notes exist
    assert data["notes"] and len(data["notes"]) > 100, "Combined notes should be non-empty"

    print(f"Endpoint test passed! {data['topic_count']} topics, engine: {data['engine']}")
    for t in data["topics"]:
        print(f"   - {t['title']}")


def test_invalid_file_type():
    print("Testing upload rejection for non-PDF file...")
    response = client.post(
        "/api/generate-notes",
        files={"file": ("notes.txt", b"Hello world this is not a PDF.", "text/plain")},
        data={"note_style": "standard"}
    )
    assert response.status_code == 400
    assert "Only .pdf files" in response.json()["detail"]
    print("Invalid file type rejection test passed!")


def test_empty_file_rejection():
    print("Testing upload rejection for empty (0-byte) file...")
    response = client.post(
        "/api/generate-notes",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"note_style": "standard"}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
    print("Empty file rejection test passed!")


def test_ask_question_relevant_content():
    print("Testing /api/ask-question with relevant question...")
    pdf_text = (
        "Operating systems provide memory management and process scheduling. "
        "A Process Control Block (PCB) is a data structure used by the OS to manage information about a process. "
        "It stores the process ID, program counter, and CPU registers. "
        "Virtual memory uses paging to allow programs larger than physical RAM to execute."
    )
    response = client.post(
        "/api/ask-question",
        json={
            "question": "What is a Process Control Block?",
            "pdf_text": pdf_text,
        }
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["success"] is True
    assert "answer" in data
    assert "Process Control Block" in data["answer"] or "data structure" in data["answer"]
    assert "This information was not found in the uploaded PDF." not in data["answer"]
    print("Relevant QA test passed! Answer snippet:", data["answer"][:70].replace("\n", " "))


def test_ask_question_not_found():
    print("Testing /api/ask-question when information is NOT in PDF...")
    pdf_text = (
        "Operating systems provide memory management and process scheduling. "
        "CPU scheduling determines which process in the ready queue is allocated CPU time."
    )
    response = client.post(
        "/api/ask-question",
        json={
            "question": "How do you bake a sourdough bread?",
            "pdf_text": pdf_text,
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["answer"] == "This information was not found in the uploaded PDF."
    print("Not found QA test passed! Output exactly matched requirement.")


def test_ask_question_long_pdf_retrieval():
    print("Testing long PDF chunking and relevant section retrieval...")
    chunk1 = "Section 1: Basics of Computer Hardware. CPU, RAM, and Motherboard. " * 30
    chunk2 = "Section 2: Database Management Systems. SQL, Relational tables, and ACID properties. " * 30
    chunk3 = "Section 3: Deadlock conditions in Operating Systems. Mutual exclusion, Hold and wait, No preemption, Circular wait. " * 30
    long_text = chunk1 + "\n\n" + chunk2 + "\n\n" + chunk3

    response = client.post(
        "/api/ask-question",
        json={
            "question": "What are the four deadlock conditions?",
            "pdf_text": long_text,
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "Circular wait" in data["answer"] or "Mutual exclusion" in data["answer"] or "Deadlock" in data["answer"]
    assert data["context_chunks_used"] >= 1
    print(f"Long PDF retrieval test passed! Chunks used: {data['context_chunks_used']}")


def test_ask_question_validation_errors():
    print("Testing /api/ask-question validation (empty input)...")
    # Empty question
    res1 = client.post("/api/ask-question", json={"question": "   ", "pdf_text": "Sample text"})
    assert res1.status_code == 400

    # Empty context
    res2 = client.post("/api/ask-question", json={"question": "What is this?", "pdf_text": "   "})
    assert res2.status_code == 400
    print("Validation error tests passed!")


def test_generate_notes_returns_extracted_text():
    print("Testing that /api/generate-notes includes 'extracted_text'...")
    with open(SAMPLE_PDF, "rb") as f:
        response = client.post(
            "/api/generate-notes",
            files={"file": ("operating_systems_notes.pdf", f, "application/pdf")},
            data={"note_style": "standard"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "extracted_text" in data
    assert len(data["extracted_text"]) > 100
    print("extracted_text is present in notes generation response!")


if __name__ == "__main__":
    print("\n" + "-" * 52)
    print(" PDF Notes Generator v2.5 - Full Test Suite")
    print("-" * 52 + "\n")

    test_pdf_extraction_and_topic_segmentation()
    test_per_topic_notes_generation()
    test_health_endpoint()
    test_upload_and_generate_topic_notes_endpoint()
    test_invalid_file_type()
    test_empty_file_rejection()
    test_generate_notes_returns_extracted_text()
    test_ask_question_relevant_content()
    test_ask_question_not_found()
    test_ask_question_long_pdf_retrieval()
    test_ask_question_validation_errors()

    print("\n" + "=" * 52)
    print("  ALL 11 TESTS PASSED SUCCESSFULLY!")
    print("=" * 52 + "\n")


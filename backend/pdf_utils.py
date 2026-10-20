"""
pdf_utils.py - PDF Processing Utilities using PyMuPDF
------------------------------------------------------
Extracts text from PDF files AND identifies topics/chapters/headings
so the AI can generate separate notes per topic instead of one big summary.
"""

import re
import unicodedata
from typing import Dict, Any, List
import pymupdf  # Official PyMuPDF library


# ─── Text Sanitization ───────────────────────────────────────────────────────

# Map common PDF ligature characters to their ASCII equivalents.
# These appear when PyMuPDF extracts text from PDFs with Type1/OpenType fonts.
_LIGATURE_MAP = {
    "\uFB00": "ff",   # ﬀ
    "\uFB01": "fi",   # ﬁ
    "\uFB02": "fl",   # ﬂ
    "\uFB03": "ffi",  # ﬃ
    "\uFB04": "ffl",  # ﬄ
    "\uFB05": "st",   # ﬅ
    "\uFB06": "st",   # ﬆ
    "\u2019": "'",    # right single quotation mark
    "\u2018": "'",    # left single quotation mark
    "\u201C": '"',   # left double quotation mark
    "\u201D": '"',   # right double quotation mark
    "\u2013": "-",   # en dash
    "\u2014": "--",  # em dash
    "\u00A0": " ",   # non-breaking space
    "\u2022": "-",   # bullet
    "\u2023": "-",   # triangular bullet
    "\u25CF": "-",   # black circle bullet
}

# Unicode category prefixes that are typically garbage from PDF font encoding.
# 'Co' = Private Use Area, 'Cs' = Surrogate, 'Cn' = Unassigned
_BAD_CATEGORIES = {"Co", "Cs", "Cn"}


def sanitize_text(text: str) -> str:
    """
    Cleans raw text extracted by PyMuPDF:
    1. Replaces known PDF ligature Unicode characters with ASCII equivalents.
    2. Removes Private-Use Area codepoints (U+E000..U+F8FF, U+F0000+) that
       appear as replacement characters or boxes in browsers.
    3. Strips null bytes and non-printable ASCII control characters
       (except newlines and tabs).
    4. Normalises multiple spaces/lines.
    """
    if not text:
        return ""

    # 1. Replace known ligatures / typographic quotes
    for orig, replacement in _LIGATURE_MAP.items():
        text = text.replace(orig, replacement)

    # 2. Remove Private-Use Area and other garbage codepoints
    cleaned_chars = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat in _BAD_CATEGORIES:
            continue  # drop the character entirely
        # Keep printable chars, newlines, tabs; drop other control chars
        if cat.startswith("C") and ch not in ("\n", "\t", "\r"):
            continue
        cleaned_chars.append(ch)
    text = "".join(cleaned_chars)

    # 3. Collapse multiple consecutive spaces (but keep newlines)
    text = re.sub(r"[^\S\n]+", " ", text)
    # 4. Collapse 3+ consecutive blank lines into two
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ─── Heading Detection Helpers ───────────────────────────────────────────────

def _is_heading_font(size: float, avg_size: float) -> bool:
    """Heuristic: text is a heading if its font size is notably larger than average."""
    return size >= avg_size * 1.20


def _clean_line(text: str) -> str:
    """Remove excess whitespace from a text line and sanitize encoding artifacts."""
    return sanitize_text(" ".join(text.split()))


def _looks_like_heading(text: str) -> bool:
    """
    Extra heuristics to detect headings from content, even without font-size data.
    Returns True if the text looks like a chapter/section heading.
    """
    t = text.strip()
    if not t or len(t) > 150:
        return False

    # Numbered headings: "1.", "1.1", "Chapter 1", "Section 2", "Unit 3", etc.
    numbered = re.match(
        r'^(\d+[\.\d]*\.?\s+\S|chapter\s+\d|section\s+\d|unit\s+\d|topic\s+\d|part\s+\d)',
        t, re.IGNORECASE
    )
    if numbered:
        return True

    # Short ALL-CAPS lines that are not sentences
    if t == t.upper() and len(t) >= 4 and not t.endswith('.'):
        return True

    # Title-cased short phrases (≤ 8 words, no trailing period)
    words = t.split()
    if (2 <= len(words) <= 10
            and t[0].isupper()
            and not t.endswith('.')
            and not t.endswith(',')
            and sum(1 for w in words if w and w[0].isupper()) >= len(words) * 0.6):
        return True

    return False


# ─── Topic Segmentation ───────────────────────────────────────────────────────

def segment_into_topics(pages_data: List[Dict]) -> List[Dict[str, str]]:
    """
    Splits the full document text into named topic segments.

    Each segment is a dict:
        { "title": str, "content": str }

    Strategy:
    1. Use PyMuPDF block-level data (with font sizes) to detect headings.
    2. Fall back to line-by-line heuristics for PDFs without clear font metadata.
    3. If no headings are found at all, split the document into ~500-word chunks
       and label them as "Part 1", "Part 2", etc. so every chunk gets its own notes.
    """
    heading_blocks: List[Dict] = []  # {"level": int, "title": str, "content_lines": [str]}

    # ── Pass 1: collect all text blocks with font sizes ──────────────────────
    all_spans = []
    for pd in pages_data:
        all_spans.extend(pd.get("spans", []))

    # Compute the average body-text font size across the document
    if all_spans:
        sizes = [s["size"] for s in all_spans if s["size"] > 0]
        avg_size = sum(sizes) / len(sizes) if sizes else 11.0
    else:
        avg_size = 11.0

    # ── Pass 2: build a stream of {is_heading, text} items ────────────────────
    stream = []
    for pd in pages_data:
        for span in pd.get("spans", []):
            txt = _clean_line(span["text"])
            if not txt:
                continue
            is_h = _is_heading_font(span["size"], avg_size) or _looks_like_heading(txt)
            stream.append({"is_heading": is_h, "text": txt, "size": span["size"]})

    # ── Pass 3: group stream into topic segments ──────────────────────────────
    topics = []
    current_title = None
    current_lines = []

    for item in stream:
        if item["is_heading"]:
            # Save previous topic
            if current_lines:
                content = " ".join(current_lines).strip()
                if content:
                    topics.append({
                        "title": current_title or "Introduction",
                        "content": content
                    })
            current_title = item["text"]
            current_lines = []
        else:
            current_lines.append(item["text"])

    # Don't forget the last topic
    if current_lines:
        content = " ".join(current_lines).strip()
        if content:
            topics.append({
                "title": current_title or "Main Content",
                "content": content
            })

    # ── Merge very short topics with their neighbour ──────────────────────────
    MIN_WORDS = 30
    merged = []
    for t in topics:
        wc = len(t["content"].split())
        if merged and wc < MIN_WORDS:
            # Merge into previous
            merged[-1]["content"] += " " + t["content"]
        else:
            merged.append(t)

    # ── Fallback: no headings found → split by word chunks ────────────────────
    if not merged or (len(merged) == 1 and merged[0]["title"] in ("Introduction", "Main Content")):
        # No structural headings detected; chunk the full text by ~400 words
        all_text = " ".join(
            " ".join(s["text"] for s in pd.get("spans", []))
            for pd in pages_data
        ).split()

        chunk_size = 400
        merged = []
        for i in range(0, len(all_text), chunk_size):
            chunk_words = all_text[i: i + chunk_size]
            merged.append({
                "title": f"Part {i // chunk_size + 1}",
                "content": " ".join(chunk_words)
            })

    # ── Split very long topics into sub-chunks (avoid AI token limit) ─────────
    MAX_WORDS_PER_TOPIC = 800
    final_topics = []
    for t in merged:
        words = t["content"].split()
        if len(words) <= MAX_WORDS_PER_TOPIC:
            final_topics.append(t)
        else:
            # Split into smaller sub-chunks, labelled "Topic Title (Part N)"
            for part_idx, start in enumerate(range(0, len(words), MAX_WORDS_PER_TOPIC), 1):
                chunk = " ".join(words[start: start + MAX_WORDS_PER_TOPIC])
                final_topics.append({
                    "title": f"{t['title']} (Part {part_idx})",
                    "content": chunk
                })

    return final_topics


# ─── Main Extraction Function ─────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> Dict[str, Any]:
    """
    Extracts text and structural metadata from a PDF file (provided as bytes).

    Returns a dict with:
        - success (bool)
        - text (str)          : full extracted text (for backwards compatibility)
        - pages (int)         : total page count
        - word_count (int)
        - character_count (int)
        - page_snippets (list): per-page preview snippets
        - topics (list)       : list of {"title": str, "content": str} dicts
    """
    if not file_bytes:
        raise ValueError("The uploaded file is empty (0 bytes).")

    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(
            f"Failed to read PDF. The file may be corrupted or not a valid PDF. Error: {str(e)}"
        )

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        raise ValueError("The PDF document contains 0 pages.")

    all_page_texts = []
    page_snippets = []
    pages_data = []   # Rich block/span data for heading detection

    for page_num in range(page_count):
        page = doc[page_num]

        # ── Plain text (for full_text field) ──────────────────────────────────
        page_text = sanitize_text(page.get_text("text").strip())
        if page_text:
            all_page_texts.append(f"--- Page {page_num + 1} ---\n{page_text}")
            snippet = page_text[:120].replace("\n", " ") + ("..." if len(page_text) > 120 else "")
            page_snippets.append({"page": page_num + 1, "preview": snippet})
        else:
            page_snippets.append({"page": page_num + 1, "preview": "(Empty or Scanned Image Page)"})

        # ── Span-level data (text + font size) for heading detection ──────────
        page_spans = []
        try:
            blocks = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]
            for block in blocks:
                if block.get("type") != 0:  # type 0 = text block
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        raw = sanitize_text(span.get("text", "").strip())
                        if raw:
                            page_spans.append({
                                "text": raw,
                                "size": round(span.get("size", 11.0), 1),
                                "flags": span.get("flags", 0),
                            })
        except Exception:
            # If span extraction fails, fall back to line-based heuristics
            for line in page_text.splitlines():
                clean = _clean_line(line)
                if clean:
                    page_spans.append({"text": clean, "size": 11.0, "flags": 0})

        pages_data.append({"page": page_num + 1, "spans": page_spans})

    doc.close()

    full_text = "\n\n".join(all_page_texts).strip()

    if not full_text:
        raise ValueError(
            "No readable text could be found in this PDF. "
            "It appears to be a scanned document or image-only PDF. "
            "Please upload a PDF with selectable digital text."
        )

    words = full_text.split()
    word_count = len(words)

    if word_count < 10:
        raise ValueError(
            "The PDF contains too little text (fewer than 10 words) to generate meaningful notes."
        )

    # Segment document into topics
    topics = segment_into_topics(pages_data)

    return {
        "success": True,
        "text": full_text,
        "pages": page_count,
        "word_count": word_count,
        "character_count": len(full_text),
        "page_snippets": page_snippets,
        "topics": topics,          # NEW: list of {title, content}
    }

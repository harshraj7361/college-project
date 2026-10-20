"""
ai_service.py - AI Summarization Service (Topic-wise Notes Generation)
-----------------------------------------------------------------------
Generates SEPARATE, detailed notes for EACH topic/chapter found in the PDF.
Every topic gets its own explanation, bullet points, definitions, and examples.

Also produces an overall quick summary at the end.

Works with Google Gemini 2.5 Flash (AI) or the built-in offline engine.
"""

import math
import os
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from backend.pdf_utils import sanitize_text  # reuse the same cleaner

load_dotenv()

# Standard not-found response required when information is absent from the PDF
NOT_FOUND_MESSAGE = "This information was not found in the uploaded PDF."

# Common English stopwords to filter out when scoring keyword relevance
_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "tell", "explain", "describe", "give", "please", "summary"
}


# ─── Per-Topic Prompt Builder ────────────────────────────────────────────────

def build_topic_prompt(topic_title: str, topic_content: str, note_style: str = "standard") -> str:
    """
    Builds a prompt that instructs Gemini to generate DETAILED notes
    for a SINGLE specific topic extracted from the PDF.
    """
    style_instruction = {
        "concise": "Be concise — use compact bullet points, max 180 words total.",
        "detailed": "Be very thorough — include detailed explanations, real-world examples, and sub-points.",
        "standard": "Be balanced — clear explanations with concrete bullet points suitable for college revision.",
    }.get(note_style, "Be balanced and clear.")

    prompt = f"""You are an expert college tutor creating topic-specific study notes.

TOPIC: "{topic_title}"
Style: {style_instruction}

Generate focused, high-quality notes ONLY for this specific topic.
Do NOT repeat content from other topics. Do NOT write a generic summary.

Format your response EXACTLY like this (use Markdown):

## {topic_title}

### Simple Explanation
(2-3 sentences that clearly explain what this topic is about, in simple language)

### Important Points
- **Point 1**: Clear, specific explanation
- **Point 2**: Clear, specific explanation
- **Point 3**: Clear, specific explanation
(Add 3-6 bullet points based on the content)

### Definitions & Key Terms
- **Term**: Definition and brief example if relevant
(Only include terms actually mentioned in the content below)

### Quick Revision Takeaways
- One-liner must-know fact 1
- One-liner must-know fact 2
- One-liner must-know fact 3

---

TOPIC CONTENT:
\"\"\"
{topic_content[:5000]}
\"\"\"

IMPORTANT:
- Base your notes strictly on the content provided above.
- Do NOT add information not present in the content.
- If the content is short, keep notes proportionally short.
- Use plain English. Avoid jargon unless it is defined.
"""
    return prompt


def build_overall_summary_prompt(topic_titles: List[str], full_text_snippet: str) -> str:
    """
    Builds a prompt for a short overall document summary that links all topics.
    """
    topics_list = "\n".join(f"- {t}" for t in topic_titles)
    return f"""You are a college tutor. The following document covers these topics:
{topics_list}

Write a SHORT overall summary (3-5 sentences max) that:
1. States what subject/domain the document covers.
2. Lists the main topics briefly.
3. Explains the overall purpose or learning goal of the document.

Do NOT repeat individual topic notes. Keep it under 120 words.

Document excerpt for context:
\"\"\"
{full_text_snippet[:3000]}
\"\"\"
"""


# ─── Gemini API Calls ────────────────────────────────────────────────────────

def call_gemini(prompt: str, api_key: str, max_tokens: int = 1200) -> str:
    """
    Makes a single call to Gemini 2.5 Flash and returns the text response.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.25,
            max_output_tokens=max_tokens,
        )
    )
    if not response.text:
        raise ValueError("Gemini API returned an empty response.")
    return response.text.strip()


def generate_topic_notes_with_gemini(
    topics: List[Dict[str, str]],
    full_text: str,
    api_key: str,
    note_style: str = "standard"
) -> List[Dict[str, str]]:
    """
    Calls Gemini once per topic to generate detailed, individual topic notes.
    Also generates an overall document summary.

    Returns a list of dicts: [{"title": str, "notes": str}, ...]
    The last item is always {"title": "__overall_summary__", "notes": str}.
    """
    results = []

    for i, topic in enumerate(topics):
        print(f"  Generating notes for topic {i+1}/{len(topics)}: {topic['title']}")
        prompt = build_topic_prompt(topic["title"], topic["content"], note_style)
        notes = call_gemini(prompt, api_key, max_tokens=1200)
        results.append({"title": topic["title"], "notes": notes})

    # Generate overall summary
    topic_titles = [t["title"] for t in topics]
    summary_prompt = build_overall_summary_prompt(topic_titles, full_text)
    overall_summary = call_gemini(summary_prompt, api_key, max_tokens=300)
    results.append({"title": "__overall_summary__", "notes": overall_summary})

    return results


# ─── Fallback Offline Engine (per-topic) ─────────────────────────────────────

def _extract_definitions(sentences: List[str]) -> List[str]:
    """Extract definition-like sentences from a list of sentences."""
    pattern = re.compile(
        r'\b(is defined as|refers to|is called|is known as|is an?|means|are defined|denotes)\b',
        re.IGNORECASE
    )
    return [s for s in sentences if pattern.search(s) and len(s) < 200]


def _split_sentences(text: str) -> List[str]:
    """Split text into individual sentences."""
    raw = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in raw if 15 <= len(s.strip()) <= 300]


def generate_topic_notes_fallback(
    topics: List[Dict[str, str]],
    full_text: str,
    note_style: str = "standard"
) -> List[Dict[str, str]]:
    """
    Built-in offline engine that generates per-topic notes without any API.
    Uses sentence scoring, keyword extraction, and structured markdown formatting.
    """
    results = []

    for topic in topics:
        title = topic["title"]
        content = topic["content"]

        sentences = _split_sentences(content)

        # Deduplicate sentences (preserve order)
        seen = set()
        unique_sentences = []
        for s in sentences:
            low = s.lower()
            if low not in seen:
                seen.add(low)
                unique_sentences.append(s)

        definitions = _extract_definitions(unique_sentences)

        # Build explanation (first 2-3 sentences)
        explanation_sents = unique_sentences[:3] if len(unique_sentences) >= 3 else unique_sentences

        # Key points: next 3-6 sentences
        if note_style == "concise":
            key_points = unique_sentences[3:6]
        elif note_style == "detailed":
            key_points = unique_sentences[3:10]
        else:
            key_points = unique_sentences[3:7]

        # Quick takeaways: later sentences
        takeaways = unique_sentences[10:13] if len(unique_sentences) > 13 else unique_sentences[-3:]

        md = [f"## {sanitize_text(title)}"]

        md.append("\n### Simple Explanation")
        if explanation_sents:
            md.append(" ".join(explanation_sents))
        else:
            # Fallback: use the first 30 words of raw content instead of a generic message
            raw_preview = " ".join(content.split()[:30])
            md.append(raw_preview if raw_preview else "See the source document for details on this topic.")

        md.append("\n### Important Points")
        if key_points:
            for pt in key_points:
                words = pt.split()
                if len(words) >= 4:
                    head = " ".join(words[:3])
                    rest = " ".join(words[3:])
                    md.append(f"- **{head}**: {rest}")
                else:
                    md.append(f"- {pt}")
        else:
            md.append(f"- Refer to the source material for detailed points on {title}.")

        md.append("\n### Definitions & Key Terms")
        if definitions:
            for defn in definitions[:4]:
                md.append(f"- **Definition**: {defn}")
        else:
            md.append("- No explicit definitions found in this section.")

        md.append("\n### Quick Revision Takeaways")
        if takeaways:
            for tk in takeaways:
                md.append(f"- {tk}")
        elif key_points:
            for pt in key_points[:3]:
                md.append(f"- {pt}")
        else:
            md.append(f"- Review the main points of {title} from the source document.")

        results.append({"title": title, "notes": "\n".join(md)})

    # Overall summary for fallback
    all_titles = [t["title"] for t in topics]
    summary_lines = [
        "# Document Overview",
        f"This document covers **{len(all_titles)} topic(s)**: "
        + ", ".join(f"*{t}*" for t in all_titles) + ".",
        "\nUse the topic navigation on the left to jump to each section's notes.",
        "\n*Generated by the built-in offline engine. "
        "Set `GEMINI_API_KEY` in `.env` for Gemini 2.5 Flash AI.*"
    ]
    results.append({"title": "__overall_summary__", "notes": "\n".join(summary_lines)})

    return results


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def generate_notes(
    text: str,
    topics: Optional[List[Dict[str, str]]] = None,
    custom_api_key: Optional[str] = None,
    note_style: str = "standard"
) -> Dict[str, Any]:
    """
    Main entry point for note generation.

    Parameters:
        text (str): The full extracted document text.
        topics (list): List of {"title": str, "content": str} dicts from pdf_utils.
        custom_api_key (str): Optional per-request Gemini API key.
        note_style (str): "concise", "standard", or "detailed".

    Returns:
        dict:
            "notes" (str)            - Combined markdown of ALL topic notes (for download/copy).
            "topics" (list)          - List of {"title": str, "notes": str} per-topic dicts.
            "overall_summary" (str)  - Short document-level overview.
            "engine" (str)           - Which engine was used.
            "used_api" (bool)
            "message" (str)
    """
    # If no topic segmentation was provided, treat the whole text as one chunk
    if not topics:
        topics = [{"title": "Document Content", "content": text[:8000]}]

    api_key = (custom_api_key or "").strip() or os.getenv("GEMINI_API_KEY", "").strip()

    topic_results: List[Dict[str, str]] = []
    engine = "Local Smart Engine"
    used_api = False
    message = ""

    if api_key:
        try:
            topic_results = generate_topic_notes_with_gemini(topics, text, api_key, note_style)
            engine = "Gemini 2.5 Flash AI"
            used_api = True
            message = f"Notes generated for {len(topics)} topic(s) using Google Gemini 2.5 Flash!"
        except Exception as e:
            # Fall back gracefully if API fails
            topic_results = generate_topic_notes_fallback(topics, text, note_style)
            engine = "Local Smart Engine (API Fallback)"
            used_api = False
            message = f"Gemini API error ({str(e)}). Used built-in engine instead."
    else:
        topic_results = generate_topic_notes_fallback(topics, text, note_style)
        engine = "Local Smart Engine"
        used_api = False
        message = f"Notes generated for {len(topics)} topic(s) via built-in engine. Add GEMINI_API_KEY in .env for Gemini AI."

    # Separate overall summary from per-topic notes
    overall_summary = ""
    per_topic_notes = []
    for item in topic_results:
        if item["title"] == "__overall_summary__":
            overall_summary = item["notes"]
        else:
            per_topic_notes.append(item)

    # Build combined full-text notes for copy/download
    sections = []
    for t in per_topic_notes:
        sections.append(t["notes"])
    if overall_summary:
        sections.append("\n---\n" + overall_summary)
    combined_notes = "\n\n".join(sections)

    return {
        "notes": combined_notes,           # Full combined markdown (copy/download)
        "topics": per_topic_notes,         # Per-topic list for UI navigation
        "overall_summary": overall_summary,
        "engine": engine,
        "used_api": used_api,
        "message": message,
    }


# ─── QA Retrieval & Question Answering ───────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Extract lowercase alphanumeric tokens."""
    return re.findall(r'\b[a-zA-Z0-9_-]+\b', text.lower())


def chunk_pdf_text(text: str, chunk_words: int = 350, overlap_words: int = 60) -> List[Dict[str, Any]]:
    """
    Splits long PDF text into overlapping word chunks to retrieve the most
    relevant sections for a question without sending the entire document every time.
    """
    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_words:
        return [{"id": 0, "text": text, "word_count": len(words)}]

    chunks = []
    start = 0
    chunk_id = 0
    step = max(chunk_words - overlap_words, 50)

    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunk_words_slice = words[start:end]
        chunks.append({
            "id": chunk_id,
            "text": " ".join(chunk_words_slice),
            "word_count": len(chunk_words_slice),
        })
        chunk_id += 1
        if end >= len(words):
            break
        start += step

    return chunks


def retrieve_relevant_sections(
    text: str,
    question: str,
    max_chunks: int = 3,
    chunk_words: int = 350
) -> Dict[str, Any]:
    """
    Retrieves the most relevant text sections from a long PDF for a given question.
    Uses BM25-style term frequency + inverse document frequency scoring,
    along with exact phrase and bigram matching bonuses.
    """
    words = text.split()
    total_words = len(words)

    # For short documents, the full text fits easily in the prompt
    if total_words <= 800:
        q_tokens = [w for w in _tokenize(question) if w not in _STOP_WORDS and len(w) > 1]
        text_lower = text.lower()
        matches = [w for w in q_tokens if w in text_lower]
        is_relevant = len(matches) > 0 or len(q_tokens) == 0
        return {
            "context": text,
            "chunks_used": 1,
            "is_relevant": is_relevant,
            "max_score": float(len(matches)),
            "total_chunks": 1,
        }

    chunks = chunk_pdf_text(text, chunk_words=chunk_words)
    total_chunks = len(chunks)

    # Extract non-stopword query tokens
    q_tokens = [w for w in _tokenize(question) if w not in _STOP_WORDS and len(w) > 1]
    q_lower = question.lower().strip()

    # Create bigrams from query for phrase bonuses
    q_bigrams = []
    raw_tokens = _tokenize(question)
    for i in range(len(raw_tokens) - 1):
        q_bigrams.append(f"{raw_tokens[i]} {raw_tokens[i+1]}")

    # Compute document frequency (how many chunks contain each query token)
    doc_freq: Dict[str, int] = {}
    chunk_token_sets = []
    for chunk in chunks:
        tokens_set = set(_tokenize(chunk["text"]))
        chunk_token_sets.append(tokens_set)
        for w in q_tokens:
            if w in tokens_set:
                doc_freq[w] = doc_freq.get(w, 0) + 1

    avg_chunk_len = sum(c["word_count"] for c in chunks) / max(total_chunks, 1)

    # Score each chunk
    scored_chunks = []
    for i, chunk in enumerate(chunks):
        c_text = chunk["text"]
        c_lower = c_text.lower()
        c_words = c_text.split()
        score = 0.0

        # Exact phrase match bonus
        if len(q_lower) >= 8 and q_lower in c_lower:
            score += 10.0

        # Bigram match bonus
        for bg in q_bigrams:
            if bg in c_lower:
                score += 3.5

        # BM25-like keyword scoring
        for w in q_tokens:
            cnt = c_lower.count(w)
            if cnt > 0:
                df = doc_freq.get(w, 1)
                idf = math.log(1.0 + (total_chunks - df + 0.5) / (df + 0.5))
                k1 = 1.2
                b = 0.75
                tf = (cnt * (k1 + 1.0)) / (cnt + k1 * (1.0 - b + b * (len(c_words) / max(avg_chunk_len, 1))))
                score += tf * max(idf, 0.2)

        scored_chunks.append({
            "chunk": chunk,
            "score": score,
        })

    # Sort chunks by score descending
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    max_score = scored_chunks[0]["score"] if scored_chunks else 0.0

    is_relevant = max_score >= 1.0

    # Pick top scoring chunks
    if is_relevant:
        top_items = [sc for sc in scored_chunks if sc["score"] > 0][:max_chunks]
        if not top_items:
            top_items = scored_chunks[:1]
    else:
        # Keep first chunk as fallback context so AI / validator can inspect
        top_items = scored_chunks[:1]

    # Re-order selected chunks back to original document order
    top_items.sort(key=lambda x: x["chunk"]["id"])
    selected_chunks_text = [item["chunk"]["text"] for item in top_items]
    combined_context = "\n\n[...]\n\n".join(selected_chunks_text)

    return {
        "context": combined_context,
        "chunks_used": len(top_items),
        "is_relevant": is_relevant,
        "max_score": max_score,
        "total_chunks": total_chunks,
    }


def build_qa_prompt(question: str, context: str) -> str:
    """
    Builds the Gemini prompt for beginner-friendly, strictly grounded Q&A.
    """
    return f"""You are a helpful, clear, and beginner-friendly college tutor.
Answer the user's question based ONLY on the provided PDF context excerpts below.

CRITICAL INSTRUCTIONS:
1. Base your answer strictly on the provided PDF excerpts. Do NOT extrapolate or assume facts not present in the excerpts.
2. Give clear, simple, beginner-friendly explanations in plain English. Use short bullet points where appropriate for clarity.
3. If the answer cannot be found in or deduced from the provided PDF excerpts, you MUST respond EXACTLY with this phrase:
   "{NOT_FOUND_MESSAGE}"
4. Do NOT make up any facts, names, dates, or specifications that are not explicitly stated in the context.

PDF CONTEXT EXCERPTS:
\"\"\"
{context[:8000]}
\"\"\"

USER QUESTION:
{question}
"""


def answer_question_fallback(
    question: str,
    context: str,
    is_relevant: bool,
    max_score: float
) -> str:
    """
    Offline QA fallback that extracts and formats relevant statements from matching PDF context.
    If the question is unrelated or not found in the PDF, returns NOT_FOUND_MESSAGE.
    """
    if not is_relevant or max_score < 0.8 or not context.strip():
        return NOT_FOUND_MESSAGE

    sentences = _split_sentences(context)
    if not sentences:
        return NOT_FOUND_MESSAGE

    q_tokens = [w for w in _tokenize(question) if w not in _STOP_WORDS and len(w) > 1]
    if not q_tokens:
        return NOT_FOUND_MESSAGE

    q_lower = question.lower()
    scored_sentences = []

    for sent in sentences:
        s_lower = sent.lower()
        score = 0.0

        # Exact phrase bonus
        if len(q_lower) >= 8 and q_lower in s_lower:
            score += 8.0

        # Word overlap
        sent_words = set(_tokenize(sent))
        matches = [w for w in q_tokens if w in sent_words]
        if matches:
            score += len(matches) * 2.0
            # Definition or explanation keywords bonus
            if any(term in s_lower for term in ["is defined as", "refers to", "is a", "is an", "is called", "means", "are"]):
                score += 2.0
            scored_sentences.append((score, sent))

    if not scored_sentences:
        return NOT_FOUND_MESSAGE

    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    best_score, best_sent = scored_sentences[0]

    if best_score < 1.5:
        return NOT_FOUND_MESSAGE

    # Pick top 2-3 distinct sentences
    top_sents = []
    seen = set()
    for s, sent in scored_sentences:
        s_clean = sent.strip()
        if s_clean.lower() not in seen and s >= 1.5:
            seen.add(s_clean.lower())
            top_sents.append(s_clean)
        if len(top_sents) >= 3:
            break

    if not top_sents:
        return NOT_FOUND_MESSAGE

    # Format beginner-friendly answer
    lines = [
        f"**Based on the uploaded PDF:**",
        "",
        top_sents[0],
    ]
    if len(top_sents) > 1:
        lines.append("")
        lines.append("**Key Details from Document:**")
        for st in top_sents[1:]:
            lines.append(f"- {st}")

    return "\n".join(lines)


def answer_question(
    question: str,
    pdf_text: str,
    custom_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Answers a question about an uploaded PDF:
    1. Retrieves the most relevant text sections using keyword & BM25 scoring.
    2. Answers with Gemini AI (if key is provided) or built-in offline QA engine.
    3. Strictly outputs NOT_FOUND_MESSAGE if the content is not in the PDF.
    """
    clean_q = sanitize_text(question.strip())
    clean_text = sanitize_text(pdf_text.strip())

    if not clean_q or not clean_text:
        return {
            "answer": NOT_FOUND_MESSAGE,
            "engine": "Local Smart QA",
            "used_api": False,
            "context_chunks_used": 0,
            "found": False,
        }

    # Retrieve relevant sections (chunking long PDFs)
    retrieval = retrieve_relevant_sections(clean_text, clean_q, max_chunks=3)
    context = retrieval["context"]
    is_relevant = retrieval["is_relevant"]
    max_score = retrieval["max_score"]
    chunks_used = retrieval["chunks_used"]

    api_key = (custom_api_key or "").strip() or os.getenv("GEMINI_API_KEY", "").strip()

    if api_key:
        try:
            # If completely irrelevant keywords (e.g. 0 score across entire document),
            # we can fast-path or let Gemini confirm with context
            prompt = build_qa_prompt(clean_q, context)
            ai_answer = call_gemini(prompt, api_key, max_tokens=600)

            # Check if answer indicates not found
            is_not_found = (
                NOT_FOUND_MESSAGE.lower() in ai_answer.lower()
                or "not found in the uploaded pdf" in ai_answer.lower()
            )

            return {
                "answer": NOT_FOUND_MESSAGE if is_not_found else ai_answer,
                "engine": "Gemini 2.5 Flash AI",
                "used_api": True,
                "context_chunks_used": chunks_used,
                "found": not is_not_found,
            }
        except Exception:
            # Fall back gracefully to built-in QA engine
            fb_answer = answer_question_fallback(clean_q, context, is_relevant, max_score)
            return {
                "answer": fb_answer,
                "engine": "Local Smart QA (API Fallback)",
                "used_api": False,
                "context_chunks_used": chunks_used,
                "found": fb_answer != NOT_FOUND_MESSAGE,
            }
    else:
        # Use built-in offline QA engine
        fb_answer = answer_question_fallback(clean_q, context, is_relevant, max_score)
        return {
            "answer": fb_answer,
            "engine": "Local Smart QA",
            "used_api": False,
            "context_chunks_used": chunks_used,
            "found": fb_answer != NOT_FOUND_MESSAGE,
        }


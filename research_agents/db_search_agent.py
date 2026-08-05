# db_search_agent.py
import sqlite3
import os
import re
from agents import Agent, Runner

DB_PATH = "research.db"


def find_books_for_topic(topic: str) -> list[dict]:

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Split topic into individual keywords and match any of them
    keywords = topic.lower().strip().split()
    conditions = " OR ".join(["topic LIKE ?" for _ in keywords])
    params = [f"%{kw}%" for kw in keywords]

    cursor.execute(
        f"SELECT id, topic, book_name, file_path FROM books WHERE {conditions}",
        params
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {"id": row[0], "topic": row[1], "book_name": row[2], "file_path": row[3]}
        for row in rows
    ]


def extract_relevant_text_from_pdf(file_path: str, topic: str, max_chars: int = 4000) -> str:

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "PyMuPDF not installed. Run: pip install pymupdf"

    if not os.path.exists(file_path):
        return f"PDF not found at path: {file_path}"

    keywords = topic.lower().split()
    doc = fitz.open(file_path)
    relevant_chunks = []
    total_chars = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        # Check if page is relevant to topic
        text_lower = text.lower()
        if any(kw in text_lower for kw in keywords):
            chunk = f"[Page {page_num + 1}]\n{text.strip()}"
            relevant_chunks.append(chunk)
            total_chars += len(chunk)

        if total_chars >= max_chars:
            break

    doc.close()

    if not relevant_chunks:
        return f"No relevant content found for '{topic}' in this book."

    combined = "\n\n---\n\n".join(relevant_chunks)
    return combined[:max_chars]


async def search_db_for_topic(topic: str) -> list[dict]:
    books = find_books_for_topic(topic)
    results = []

    for book in books:
        extracted_text = extract_relevant_text_from_pdf(book["file_path"], topic)

        if extracted_text.startswith("PyMuPDF not installed") or extracted_text.startswith("PDF not found") or extracted_text.startswith("No relevant content found"):
            summary = extracted_text
        else:
            input_text = (
                f"Book title: {book['book_name']}\n"
                f"Topic: {topic}\n\n"
                f"Extracted text:\n{extracted_text}"
            )
            summary_result = await Runner.run(book_summary_agent, input=input_text)
            summary = summary_result.final_output

        results.append({
            "title": book["book_name"],
            "url": f"local://{book['file_path']}",
            "summary": summary,
            "source": "book"
        })

    return results


BOOK_SUMMARY_PROMPT = """
You are a research assistant. You will receive extracted text from a book PDF
that is relevant to a research topic. Summarize the core ideas, main points,
and useful details from the extracted text.

Write a concise 2-3 paragraph summary. Focus on the most important
information related to the topic, avoid fluff, and do not add extra commentary.
"""

book_summary_agent = Agent(
    name="Book Summary Agent",
    instructions=BOOK_SUMMARY_PROMPT,
)
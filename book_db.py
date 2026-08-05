import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "research.db")
BOOKS_DIR = os.path.join(BASE_DIR, "books")

os.makedirs(BOOKS_DIR, exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            book_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _connect():
    return sqlite3.connect(DB_PATH)


def get_all_books():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, topic, book_name, file_path, added_on FROM books ORDER BY added_on DESC")
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "topic": row[1],
            "book_name": row[2],
            "file_path": row[3],
            "added_on": row[4],
        }
        for row in rows
    ]


def get_book(book_id):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, topic, book_name, file_path, added_on FROM books WHERE id = ?", (book_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "topic": row[1],
        "book_name": row[2],
        "file_path": row[3],
        "added_on": row[4],
    }


def add_book(topic, book_name, file_path):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO books (topic, book_name, file_path) VALUES (?, ?, ?)",
        (topic.strip().lower(), book_name.strip(), file_path),
    )
    conn.commit()
    conn.close()


def update_book(book_id, topic, book_name, file_path=None):
    conn = _connect()
    cursor = conn.cursor()
    if file_path:
        cursor.execute(
            "UPDATE books SET topic = ?, book_name = ?, file_path = ? WHERE id = ?",
            (topic.strip().lower(), book_name.strip(), file_path, book_id),
        )
    else:
        cursor.execute(
            "UPDATE books SET topic = ?, book_name = ? WHERE id = ?",
            (topic.strip().lower(), book_name.strip(), book_id),
        )
    conn.commit()
    conn.close()


def delete_book(book_id):
    book = get_book(book_id)
    if not book:
        return
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    try:
        if os.path.exists(book["file_path"]):
            os.remove(book["file_path"])
    except OSError:
        pass
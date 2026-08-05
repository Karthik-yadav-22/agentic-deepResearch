import os
import asyncio
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for, flash, render_template_string
from werkzeug.utils import secure_filename

from coordinator import ResearchCoordinator
from book_db import BOOKS_DIR, init_db, get_all_books, get_book, add_book, update_book, delete_book

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found. Set it in .env or Vercel environment variables.")

UPLOAD_FOLDER = BOOKS_DIR
ALLOWED_EXTENSIONS = {"pdf"}

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-for-prod")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

init_db()
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Agentic Research</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" />
    <style>
      body { padding-top: 4rem; }
      .report { white-space: pre-wrap; background: #f8f9fa; border: 1px solid #dee2e6; padding: 1rem; border-radius: .5rem; }
      .nav-link.active { font-weight: 600; }
      .small-note { font-size: .9rem; color: #6c757d; }
    </style>
  </head>
  <body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary fixed-top">
      <div class="container">
        <a class="navbar-brand" href="{{ url_for('index') }}">Agentic Research</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navMenu">
          <ul class="navbar-nav ms-auto">
            <li class="nav-item"><a class="nav-link {% if active=='research' %}active{% endif %}" href="{{ url_for('index') }}">Research</a></li>
            <li class="nav-item"><a class="nav-link {% if active=='books' %}active{% endif %}" href="{{ url_for('books') }}">Books</a></li>
          </ul>
        </div>
      </div>
    </nav>

    <main class="container">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          <div class="mt-3">
            {% for category, message in messages %}
              <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                {{ message }}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
              </div>
            {% endfor %}
          </div>
        {% endif %}
      {% endwith %}
      {{ body|safe }}
    </main>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  </body>
</html>
"""


def render_page(body, active="research"):
    return render_template_string(BASE_TEMPLATE, body=body, active=active)


@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    report = None
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if not query:
            flash("Please enter a research topic.", "warning")
        else:
            coordinator = ResearchCoordinator(query)
            try:
                report = asyncio.run(coordinator.research())
            except Exception as exc:
                flash(f"Research failed: {exc}", "danger")
    body = f"""
    <div class="row">
      <div class="col-lg-8 mx-auto">
        <div class="card shadow-sm mb-4">
          <div class="card-body">
            <h2 class="card-title">Research Topic</h2>
            <p class="small-note">Enter the topic you want to research and the system will synthesize a report from web and local books.</p>
            <form method="post">
              <div class="mb-3">
                <label for="query" class="form-label">Topic</label>
                <input name="query" id="query" class="form-control" value="{query}" placeholder="e.g. k-means clustering algorithm" required />
              </div>
              <button class="btn btn-primary">Run Research</button>
            </form>
          </div>
        </div>
        {f'<div class="card shadow-sm mb-4"><div class="card-body"><h3 class="card-title">Research Report</h3><div class="report">{report}</div></div></div>' if report else ''}
      </div>
    </div>
    """
    return render_page(body, active="research")


@app.route("/books", methods=["GET"])
def books():
    books = get_all_books()
    rows = ""
    for book in books:
        rows += f"""
        <tr>
          <td>{book['id']}</td>
          <td>{book['topic']}</td>
          <td>{book['book_name']}</td>
          <td>{os.path.basename(book['file_path'])}</td>
          <td>{book['added_on']}</td>
          <td>
            <a class="btn btn-sm btn-outline-primary" href="{url_for('edit_book', book_id=book['id'])}">Edit</a>
            <form method="post" action="{url_for('delete_book', book_id=book['id'])}" class="d-inline">
              <button class="btn btn-sm btn-outline-danger" type="submit" onclick="return confirm('Delete this book?')">Delete</button>
            </form>
          </td>
        </tr>
        """
    body = f"""
    <div class="row">
      <div class="col-lg-10 mx-auto">
        <div class="card shadow-sm mb-4">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <div>
                <h2 class="card-title">Books</h2>
                <p class="small-note">Manage your local PDF books and topics.</p>
              </div>
              <a class="btn btn-success" href="{url_for('add_book_view')}">Add Book</a>
            </div>
            <div class="table-responsive">
              <table class="table table-striped">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Topic</th>
                    <th>Book</th>
                    <th>File</th>
                    <th>Added</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
    """
    return render_page(body, active="books")


@app.route("/books/add", methods=["GET", "POST"])
def add_book_view():
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        book_name = request.form.get("book_name", "").strip()
        file = request.files.get("file")
        if not topic or not book_name or not file or file.filename == "":
            flash("Topic, book name, and PDF file are required.", "warning")
            return redirect(url_for("add_book_view"))
        if not allowed_file(file.filename):
            flash("Only PDF files are allowed.", "warning")
            return redirect(url_for("add_book_view"))
        filename = secure_filename(file.filename)
        target_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(target_path)
        add_book(topic, book_name, target_path)
        flash("Book added successfully.", "success")
        return redirect(url_for("books"))
    body = f"""
    <div class="row">
      <div class="col-lg-8 mx-auto">
        <div class="card shadow-sm">
          <div class="card-body">
            <h2 class="card-title">Add Book</h2>
            <form method="post" enctype="multipart/form-data">
              <div class="mb-3">
                <label class="form-label">Topic</label>
                <input name="topic" class="form-control" required />
              </div>
              <div class="mb-3">
                <label class="form-label">Book Name</label>
                <input name="book_name" class="form-control" required />
              </div>
              <div class="mb-3">
                <label class="form-label">PDF File</label>
                <input type="file" name="file" class="form-control" accept=".pdf" required />
              </div>
              <button class="btn btn-primary">Save Book</button>
              <a class="btn btn-secondary" href="{url_for('books')}">Cancel</a>
            </form>
          </div>
        </div>
      </div>
    </div>
    """
    return render_page(body, active="books")


@app.route("/books/edit/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    book = get_book(book_id)
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("books"))
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        book_name = request.form.get("book_name", "").strip()
        file = request.files.get("file")
        if not topic or not book_name:
            flash("Topic and book name are required.", "warning")
            return redirect(url_for("edit_book", book_id=book_id))
        file_path = None
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Only PDF files are allowed.", "warning")
                return redirect(url_for("edit_book", book_id=book_id))
            filename = secure_filename(file.filename)
            target_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(target_path)
            file_path = target_path
        update_book(book_id, topic, book_name, file_path)
        flash("Book updated successfully.", "success")
        return redirect(url_for("books"))
    body = f"""
    <div class="row">
      <div class="col-lg-8 mx-auto">
        <div class="card shadow-sm">
          <div class="card-body">
            <h2 class="card-title">Edit Book</h2>
            <form method="post" enctype="multipart/form-data">
              <div class="mb-3">
                <label class="form-label">Topic</label>
                <input name="topic" class="form-control" value="{book['topic']}" required />
              </div>
              <div class="mb-3">
                <label class="form-label">Book Name</label>
                <input name="book_name" class="form-control" value="{book['book_name']}" required />
              </div>
              <div class="mb-3">
                <label class="form-label">Replace PDF (optional)</label>
                <input type="file" name="file" class="form-control" accept=".pdf" />
                <div class="small-note mt-1">Current file: {os.path.basename(book['file_path'])}</div>
              </div>
              <button class="btn btn-primary">Save Changes</button>
              <a class="btn btn-secondary" href="{url_for('books')}">Cancel</a>
            </form>
          </div>
        </div>
      </div>
    </div>
    """
    return render_page(body, active="books")


@app.route("/books/delete/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    delete_book(book_id)
    flash("Book deleted successfully.", "success")
    return redirect(url_for("books"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
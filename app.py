import os
import asyncio
import json
from uuid import uuid4
from urllib.parse import urlparse
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for, flash, render_template_string, jsonify
from werkzeug.utils import secure_filename

from coordinator import ResearchCoordinator
from book_db import (
    init_db,
    get_all_books,
    get_book,
    add_book as add_book_to_db,
    update_book as update_book_in_db,
    delete_book as delete_book_from_db,
)
from s3_utils import is_s3_enabled, generate_presigned_post, generate_presigned_url, is_s3_path

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found. Set it in .env or Vercel environment variables.")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-for-prod")

CAN_USE_S3 = is_s3_enabled()
ALLOWED_EXTENSIONS = {"pdf"}


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
    {% if upload_script %}
      {{ upload_script|safe }}
    {% endif %}
  </body>
</html>
"""


def render_page(body, active="research", upload_script=""):
    return render_template_string(BASE_TEMPLATE, body=body, active=active, upload_script=upload_script)


@app.route("/books/presign", methods=["GET"])
def presign_upload():
    if not CAN_USE_S3:
        return jsonify({"error": "S3 is not configured."}), 500

    filename = request.args.get("filename", "").strip()
    content_type = request.args.get("content_type", "application/pdf").strip()
    if not filename:
        return jsonify({"error": "filename is required"}), 400

    key = f"books/{uuid4().hex}_{secure_filename(filename)}"
    presign_data = generate_presigned_post(key, content_type)
    file_url = f"s3://{os.getenv('S3_BUCKET_NAME')}/{key}"

    return jsonify({"url": presign_data["url"], "fields": presign_data["fields"], "file_url": file_url})


@app.route("/", methods=["GET", "POST"])
def index():
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
        file_display = os.path.basename(book["file_path"])
        if is_s3_path(book["file_path"]):
            try:
                url = generate_presigned_url(book["file_path"])
                file_display = f'<a href="{url}" target="_blank">{file_display}</a>'
            except Exception:
                file_display = os.path.basename(book["file_path"])
        rows += f"""
        <tr>
          <td>{book['id']}</td>
          <td>{book['topic']}</td>
          <td>{book['book_name']}</td>
          <td>{file_display}</td>
          <td>{book['added_on']}</td>
          <td>
            <a class="btn btn-sm btn-outline-primary" href="{url_for('edit_book', book_id=book['id'])}">Edit</a>
            <form method="post" action="{url_for('remove_book', book_id=book['id'])}" class="d-inline">
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
                <p class="small-note">Manage your local and S3-backed book collection.</p>
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


def upload_script():
    if not CAN_USE_S3:
        return ""
    return """
    <script>
      async function presignAndUpload(form) {
        const fileInput = form.querySelector('input[name="file"]');
        const fileUrlInput = form.querySelector('input[name="file_url"]');
        if (!fileInput || fileInput.files.length === 0) {
          return true;
        }
        const file = fileInput.files[0];
        const response = await fetch('/books/presign?filename=' + encodeURIComponent(file.name) + '&content_type=' + encodeURIComponent(file.type || 'application/pdf'));
        const data = await response.json();
        if (!response.ok) {
          alert(data.error || 'Failed to generate upload URL.');
          return false;
        }
        const uploadData = new FormData();
        Object.entries(data.fields).forEach(([key, value]) => {
          uploadData.append(key, value);
        });
        uploadData.append('file', file);
        const uploadResp = await fetch(data.url, {
          method: 'POST',
          body: uploadData
        });
        if (!uploadResp.ok) {
          alert('Upload failed.');
          return false;
        }
        fileUrlInput.value = data.file_url;
        return true;
      }
      async function handleBookForm(event) {
        event.preventDefault();
        const form = event.target;
        const ok = await presignAndUpload(form);
        if (ok) {
          form.submit();
        }
      }
    </script>
    """


@app.route("/books/add", methods=["GET", "POST"])
def add_book_view():
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        book_name = request.form.get("book_name", "").strip()
        file_url = request.form.get("file_url", "").strip()
        file = request.files.get("file")

        if not topic or not book_name:
            flash("Topic and book name are required.", "warning")
            return redirect(url_for("add_book_view"))

        if CAN_USE_S3 and file_url:
            path = file_url
        else:
            if not file or file.filename == "":
                flash("PDF file is required.", "warning")
                return redirect(url_for("add_book_view"))
            if not allowed_file(file.filename):
                flash("Only PDF files are allowed.", "warning")
                return redirect(url_for("add_book_view"))
            filename = secure_filename(file.filename)
            local_path = os.path.join(app.root_path, "books", filename)
            file.save(local_path)
            path = local_path

        add_book_to_db(topic, book_name, path)
        flash("Book added successfully.", "success")
        return redirect(url_for("books"))

    body = f"""
    <div class="row">
      <div class="col-lg-8 mx-auto">
        <div class="card shadow-sm">
          <div class="card-body">
            <h2 class="card-title">Add Book</h2>
            <form method="post" enctype="multipart/form-data" onsubmit="return handleBookForm(event);">
              <input type="hidden" name="file_url" value="" />
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
    return render_page(body, active="books", upload_script=upload_script())


@app.route("/books/edit/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    book = get_book(book_id)
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("books"))

    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        book_name = request.form.get("book_name", "").strip()
        file_url = request.form.get("file_url", "").strip()
        file = request.files.get("file")

        if not topic or not book_name:
            flash("Topic and book name are required.", "warning")
            return redirect(url_for("edit_book", book_id=book_id))

        new_path = book["file_path"]

        if CAN_USE_S3 and file_url:
            new_path = file_url
        elif file and file.filename != "":
            if not allowed_file(file.filename):
                flash("Only PDF files are allowed.", "warning")
                return redirect(url_for("edit_book", book_id=book_id))
            filename = secure_filename(file.filename)
            local_path = os.path.join(app.root_path, "books", filename)
            file.save(local_path)
            new_path = local_path
            if not is_s3_path(book["file_path"]) and os.path.exists(book["file_path"]):
                try:
                    os.remove(book["file_path"])
                except OSError:
                    pass

        update_book_in_db(book_id, topic, book_name, new_path)
        flash("Book updated successfully.", "success")
        return redirect(url_for("books"))

    body = f"""
    <div class="row">
      <div class="col-lg-8 mx-auto">
        <div class="card shadow-sm">
          <div class="card-body">
            <h2 class="card-title">Edit Book</h2>
            <form method="post" enctype="multipart/form-data" onsubmit="return handleBookForm(event);">
              <input type="hidden" name="file_url" value="" />
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
    return render_page(body, active="books", upload_script=upload_script())


@app.route("/books/delete/<int:book_id>", methods=["POST"])
def remove_book(book_id):
    delete_book_from_db(book_id)
    flash("Book deleted successfully.", "success")
    return redirect(url_for("books"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
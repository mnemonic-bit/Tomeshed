"""Document catalog, import jobs, and authenticated source delivery."""

from __future__ import annotations

import json
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Response, abort, g, jsonify, render_template, request, send_file, stream_with_context


class DocumentLibrary:
    def __init__(self, app, db):
        self.app = app
        self.db = db
        self.root = Path(app.config["LIBRARY_DIR"] or Path(app.config["DATABASE"]).parent / "library").resolve()
        for folder in ("sources", "artifacts", "thumbnails", "staging"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=max(1, int(app.config["CONVERSION_WORKERS"])))
        self.subscribers = set()
        self.subscriber_lock = threading.Lock()
        self._init_schema()
        from file_workflows import FileWorkflows
        self.files = FileWorkflows(self)
        from organization_service import OrganizationService
        self.organization = OrganizationService(self)
        from bookshelf_service import BookshelfService
        self.bookshelves = BookshelfService(self)
        self._install_routes()
        from reader_service import install_reader
        install_reader(self)
        from preview_service import install_preview
        install_preview(self)
        self.reconcile()
        self.files.start_watcher()

    def _init_schema(self):
        with self.db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, original_filename TEXT NOT NULL,
                    source_path TEXT NOT NULL, source_type TEXT NOT NULL,
                    title TEXT NOT NULL, author TEXT NOT NULL, byte_size INTEGER NOT NULL,
                    search_key TEXT NOT NULL,
                    text_content TEXT NOT NULL DEFAULT '', page_count INTEGER,
                    count_kind TEXT NOT NULL CHECK (count_kind IN ('exact','estimated','unknown')),
                    thumbnail_path TEXT, artifact_path TEXT,
                    state TEXT NOT NULL CHECK (state IN ('ready','ready_with_warning')),
                    error TEXT, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS import_jobs (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
                    original_filename TEXT NOT NULL, source_path TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('pending','processing','ready','ready_with_warning','failed')),
                    error TEXT, retry INTEGER NOT NULL DEFAULT 0,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS documents_created ON documents(created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS import_jobs_created ON import_jobs(created_at DESC);
            """)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(import_jobs)")}
            for name, definition in (("origin", "TEXT NOT NULL DEFAULT 'browser'"),
                                     ("source_url", "TEXT"), ("bytes_received", "INTEGER NOT NULL DEFAULT 0"),
                                     ("expected_bytes", "INTEGER"),
                                     ("cancel_requested", "INTEGER NOT NULL DEFAULT 0"),
                                     ("transfer_complete", "INTEGER NOT NULL DEFAULT 0")):
                if name not in columns:
                    conn.execute(f"ALTER TABLE import_jobs ADD COLUMN {name} {definition}")
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
            if "source_url" not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN source_url TEXT")
            if "owner_user_id" not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
            if "visibility" not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','private'))")
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(import_jobs)")}
            if "owner_user_id" not in columns:
                conn.execute("ALTER TABLE import_jobs ADD COLUMN owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")

    def safe_path(self, stored):
        if not stored:
            abort(404)
        target = (self.root / stored).resolve()
        if not target.is_relative_to(self.root) or not target.is_file():
            abort(404)
        return target

    def publish(self):
        with self.subscriber_lock:
            subscribers = tuple(self.subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait("change")
            except queue.Full:
                try:
                    subscriber.get_nowait()
                    subscriber.put_nowait("change")
                except queue.Empty:
                    pass

    def reconcile(self):
        with self.db() as conn:
            rows = conn.execute("SELECT id, document_id, source_path, origin, retry, expected_bytes, bytes_received, transfer_complete, cancel_requested FROM import_jobs WHERE state IN ('pending','processing')").fetchall()
            for row in rows:
                if row["cancel_requested"]:
                    conn.execute("UPDATE import_jobs SET state='failed', error='Cancelled by user', updated_at=? WHERE id=?", (time.time(), row["id"]))
                    try:
                        self.files.remove_owned_source(row)
                    except (OSError, ValueError):
                        pass
                    continue
                legacy_upload_path = row["source_path"] == f"sources/{row['document_id']}.source"
                needs_marker = not row["retry"] and (row["origin"] in ("url", "watch") or
                    (row["origin"] == "browser" and not legacy_upload_path))
                if needs_marker and not row["transfer_complete"]:
                    conn.execute("UPDATE import_jobs SET state='failed', error='Transfer interrupted by restart', updated_at=? WHERE id=?", (time.time(), row["id"]))
                    try:
                        self.files.remove_owned_source(row)
                    except (OSError, ValueError):
                        pass
                    continue
                if row["origin"] == "browser" and row["expected_bytes"] is not None:
                    try:
                        complete_size = self.files.owned_path(row["source_path"]).stat().st_size == row["expected_bytes"] == row["bytes_received"]
                    except (OSError, ValueError):
                        complete_size = False
                    if not complete_size:
                        conn.execute("UPDATE import_jobs SET state='failed', error='Transfer interrupted by restart', updated_at=? WHERE id=?", (time.time(), row["id"]))
                        try:
                            self.files.remove_owned_source(row)
                        except (OSError, ValueError):
                            pass
                        continue
                try:
                    source_present = self.files.owned_path(row["source_path"]).is_file()
                except ValueError:
                    source_present = False
                if row["origin"] in ("browser", "url") and not source_present:
                    conn.execute("UPDATE import_jobs SET state='failed', error='Transfer interrupted by restart', updated_at=? WHERE id=?", (time.time(), row["id"]))
                    continue
                try:
                    self.safe_path(row["source_path"])
                except Exception:
                    conn.execute("UPDATE import_jobs SET state='failed', error='Stored source is missing or outside library storage', updated_at=? WHERE id=?", (time.time(), row["id"]))
                else:
                    conn.execute("UPDATE import_jobs SET state='pending', updated_at=? WHERE id=?", (time.time(), row["id"]))
                    self.pool.submit(self._process_job, row["id"])
            failed_rows = conn.execute("SELECT id,document_id,source_path FROM import_jobs WHERE state='failed' AND retry=0").fetchall()
            for row in failed_rows:
                try:
                    self.files.remove_owned_source(row)
                except (OSError, ValueError):
                    pass

    def _run_conversion(self, source, filename, staging):
        command = [sys.executable, str(Path(__file__).with_name("document_processing.py")), str(source), filename, str(staging)]
        subprocess.run(command, check=True, timeout=max(1, int(self.app.config["CONVERSION_TIMEOUT"])), capture_output=True)
        return json.loads((staging / "result.json").read_text(encoding="utf-8"))

    def _process_job(self, job_id):
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM import_jobs WHERE id=? AND state='pending' AND cancel_requested=0", (job_id,)).fetchone()
            if not row:
                return
            attempt = row["attempt"] + 1
            conn.execute("UPDATE import_jobs SET state='processing', attempt=?, updated_at=? WHERE id=?", (attempt, time.time(), job_id))
            job = dict(row)
        self.publish()
        staging = self.root / "staging" / f"{job_id}-{attempt}"
        staging.mkdir(parents=True, exist_ok=True)
        try:
            source = self.safe_path(job["source_path"])
            result = self._run_conversion(source, job["original_filename"], staging)
        except subprocess.TimeoutExpired:
            result = {"state": "failed", "error": f"Conversion exceeded the {self.app.config['CONVERSION_TIMEOUT']} second time limit"}
        except Exception as exc:
            result = {"state": "failed", "error": f"Import failed: {exc}"}
        try:
            self._finish_job(job, attempt, result, staging)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            self.publish()

    def _finish_job(self, job, attempt, result, staging):
        state = result.get("state")
        if state not in ("ready", "ready_with_warning"):
            message = str(result.get("error") or "Document validation failed")[:1000]
            with self.db() as conn:
                changed = conn.execute("UPDATE import_jobs SET state='failed', error=CASE WHEN cancel_requested=1 THEN 'Cancelled by user' ELSE ? END, updated_at=? WHERE id=? AND attempt=? AND state='processing'", (message, time.time(), job["id"], attempt)).rowcount
                if changed and job["retry"]:
                    conn.execute("UPDATE documents SET state='ready_with_warning', error=? WHERE id=? AND state='ready_with_warning'",
                                 (f"Indexing warning: {message}", job["document_id"]))
            if changed and job.get("origin") == "watch":
                self.files.watched_failed(job["id"], message)
            if changed and not job["retry"]:
                try:
                    self.files.remove_owned_source(job)
                except (OSError, ValueError):
                    pass
            return
        document_id = job["document_id"]
        with self.db() as conn:
            current = conn.execute("SELECT state,attempt,cancel_requested FROM import_jobs WHERE id=?", (job["id"],)).fetchone()
        if not current or current["state"] != "processing" or current["attempt"] != attempt or current["cancel_requested"]:
            return
        artifact_path = None
        thumbnail_path = None
        if result.get("artifact") and (staging / result["artifact"]).is_file():
            artifact_path = f"artifacts/{document_id}-{job['id']}-{attempt}.json"
            shutil.copyfile(staging / result["artifact"], self.root / artifact_path)
        if result.get("thumbnail") and (staging / result["thumbnail"]).is_file():
            thumbnail_path = f"thumbnails/{document_id}-{job['id']}-{attempt}.png"
            shutil.copyfile(staging / result["thumbnail"], self.root / thumbnail_path)
        with self.db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT state,attempt,cancel_requested FROM import_jobs WHERE id=?", (job["id"],)).fetchone()
            if not current or current["state"] != "processing" or current["attempt"] != attempt or current["cancel_requested"]:
                for stored in (artifact_path, thumbnail_path):
                    if stored:
                        (self.root / stored).unlink(missing_ok=True)
                return
            if job["retry"]:
                old = conn.execute("SELECT thumbnail_path, artifact_path FROM documents WHERE id=?", (document_id,)).fetchone()
                if not old:
                    conn.execute("UPDATE import_jobs SET state='failed',error='Document no longer exists',updated_at=? WHERE id=?", (time.time(), job["id"]))
                    return
                conn.execute("""UPDATE documents SET title=?, author=?, source_type=?, byte_size=?,search_key=?,
                    text_content=?,page_count=?,count_kind=?,thumbnail_path=?,artifact_path=?,state=?,error=?
                    WHERE id=? AND state='ready_with_warning'""",
                    (result["title"], result["author"], result["source_type"], result["byte_size"],
                     f"{result['title']} {result['author']} {job['original_filename']}".casefold(), result.get("text", ""),
                     result.get("page_count"), result["count_kind"], thumbnail_path or old["thumbnail_path"],
                     artifact_path or old["artifact_path"], state, result.get("error"), document_id))
            else:
                conn.execute("""INSERT INTO documents(id,original_filename,source_path,source_type,title,author,byte_size,search_key,
                    text_content,page_count,count_kind,thumbnail_path,artifact_path,state,error,created_at,
                    source_url,owner_user_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (document_id, job["original_filename"], job["source_path"], result["source_type"], result["title"],
                     result["author"], result["byte_size"],
                     f"{result['title']} {result['author']} {job['original_filename']}".casefold(),
                     result.get("text", ""), result.get("page_count"),
                     result["count_kind"], thumbnail_path, artifact_path, state, result.get("error"), job["created_at"], job.get("source_url"), job.get("owner_user_id")))
            conn.execute("UPDATE import_jobs SET state=?,error=?,updated_at=? WHERE id=?", (state, result.get("error"), time.time(), job["id"]))
            if job["origin"] == "watch":
                self.files.record_receipt(job["id"], document_id, conn)

    def public_document(self, row):
        return self.organization.public_document(row, g.current_user["id"])

    def can_access_document(self, row, user_id):
        if row["visibility"] == "public" or row["owner_user_id"] == user_id:
            return True
        with self.db() as conn:
            role = conn.execute("SELECT r.name FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=?", (user_id,)).fetchone()
        return bool(role and role["name"] == "admin")

    def can_manage_document(self, row, user_id):
        if row["owner_user_id"] == user_id:
            return True
        with self.db() as conn:
            role = conn.execute("SELECT r.name FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=?", (user_id,)).fetchone()
        return bool(role and role["name"] == "admin")

    def can_access_job(self, row, user_id):
        if row["owner_user_id"] == user_id:
            return True
        with self.db() as conn:
            role = conn.execute("SELECT r.name FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=?", (user_id,)).fetchone()
        return bool(role and role["name"] == "admin")

    def _install_routes(self):
        app = self.app

        @app.post("/api/imports")
        def import_document():
            upload = request.files.get("file")
            if upload is None or not upload.filename:
                return jsonify(error="Choose a PDF, EPUB, or DoclingDocument JSON file"), 400
            filename = upload.filename.replace("\\", "/").split("/")[-1][:255]
            limit = max(1, int(app.config["MAX_UPLOAD_BYTES"]))
            if request.content_length and request.content_length > limit + 65536:
                return jsonify(error=f"Upload exceeds the {limit} byte size limit"), 413
            job_id, document_id = uuid.uuid4().hex, uuid.uuid4().hex
            path = f"sources/{document_id}.source"
            now = time.time()
            with self.db() as conn:
                conn.execute("INSERT INTO import_jobs(id,document_id,original_filename,source_path,state,created_at,updated_at,owner_user_id) VALUES (?,?,?,?,?,?,?,?)",
                             (job_id, document_id, filename, path, "pending", now, now,g.current_user["id"]))
            try:
                size = 0
                with (self.root / path).open("xb") as output:
                    while chunk := upload.stream.read(1024 * 1024):
                        size += len(chunk)
                        if size > limit:
                            raise ValueError(f"Upload exceeds the {limit} byte size limit")
                        output.write(chunk)
                if not size:
                    raise ValueError("Uploaded file is empty")
            except Exception as exc:
                (self.root / path).unlink(missing_ok=True)
                with self.db() as conn:
                    conn.execute("UPDATE import_jobs SET state='failed',error=?,updated_at=? WHERE id=?", (str(exc), time.time(), job_id))
                self.publish()
                return jsonify(error=str(exc), job_id=job_id), 413 if "size limit" in str(exc) else 400
            with self.db() as conn:
                conn.execute("UPDATE import_jobs SET bytes_received=?,expected_bytes=?,transfer_complete=1,updated_at=? WHERE id=?", (size, size, time.time(), job_id))
            self.pool.submit(self._process_job, job_id)
            self.publish()
            return jsonify(id=job_id, document_id=document_id, state="pending"), 202

        @app.get("/api/imports")
        def import_jobs():
            with self.db() as conn:
                scope = "" if g.current_user["role"] == "admin" else "WHERE owner_user_id=?"
                parameters = () if g.current_user["role"] == "admin" else (g.current_user["id"],)
                rows = conn.execute(f"SELECT id,document_id,original_filename,state,error,retry,origin,bytes_received,expected_bytes,created_at FROM import_jobs {scope} ORDER BY created_at DESC,id DESC LIMIT 100", parameters).fetchall()
            return jsonify(jobs=[dict(row) for row in rows])

        def get_document(document_id):
            with self.db() as conn:
                row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if row is None or not self.can_access_document(row, g.current_user["id"]):
                abort(404)
            return row

        @app.get("/api/documents/<document_id>")
        def document_detail_api(document_id):
            return jsonify(self.public_document(get_document(document_id)))

        @app.get("/documents/<document_id>")
        def document_detail(document_id):
            return render_template("document.html", document=self.public_document(get_document(document_id)), version=app.config.get("VERSION", ""))

        @app.get("/api/documents/<document_id>/source")
        def document_source(document_id):
            row = get_document(document_id)
            mimetype = {"pdf": "application/pdf", "epub": "application/epub+zip", "docling": "application/json"}[row["source_type"]]
            source = self.safe_path(row["source_path"])
            return send_file(source, mimetype=mimetype, conditional=True,
                             as_attachment=request.args.get("download") == "1",
                             download_name=source.name if source.suffix != ".source" else row["original_filename"])

        @app.get("/api/documents/<document_id>/thumbnail")
        def document_thumbnail(document_id):
            return send_file(self.safe_path(get_document(document_id)["thumbnail_path"]), mimetype="image/png", conditional=True)

        @app.post("/api/documents/<document_id>/retry")
        def retry_document(document_id):
            job_id, now = uuid.uuid4().hex, time.time()
            with self.db() as conn:
                # Reserve the writer before checking the document and active
                # retries so two simultaneous requests cannot both queue work.
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
                if row is None or not self.can_access_document(row, g.current_user["id"]):
                    return jsonify(error="Unknown document"), 404
                if row["state"] != "ready_with_warning":
                    return jsonify(error="Document has no indexing warning"), 409
                active = conn.execute("""SELECT id FROM import_jobs WHERE document_id=? AND retry=1
                    AND state IN ('pending','processing') LIMIT 1""", (document_id,)).fetchone()
                if active:
                    return jsonify(error="Indexing retry already in progress", id=active["id"]), 409
                conn.execute("INSERT INTO import_jobs(id,document_id,original_filename,source_path,state,retry,created_at,updated_at,owner_user_id) VALUES (?,?,?,?,?,?,?,?,?)",
                             (job_id, document_id, row["original_filename"], row["source_path"], "pending", 1, now, now,g.current_user["id"]))
            self.pool.submit(self._process_job, job_id)
            self.publish()
            return jsonify(id=job_id, document_id=document_id, state="pending"), 202

        @app.get("/api/events")
        def events():
            subscriber = queue.Queue(maxsize=32)

            def stream():
                with self.subscriber_lock:
                    self.subscribers.add(subscriber)
                try:
                    yield "retry: 1000\nevent: ready\ndata: {}\n\n"
                    while True:
                        try:
                            subscriber.get(timeout=15)
                            yield "event: change\ndata: {}\n\n"
                        except queue.Empty:
                            yield ": keepalive\n\n"
                finally:
                    with self.subscriber_lock:
                        self.subscribers.discard(subscriber)

            response = Response(stream_with_context(stream()), mimetype="text/event-stream")
            response.headers["Cache-Control"] = "no-cache, no-transform"
            response.headers["X-Accel-Buffering"] = "no"
            return response

import importlib
import io
import json
import subprocess
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from docling_core.types.doc import DoclingDocument
from pypdf import PdfWriter

import document_processing


@pytest.fixture
def module(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMESHED_DB", str(tmp_path / "library.db"))
    monkeypatch.setenv("TOMESHED_LIBRARY_DIR", str(tmp_path / "library"))
    import tomeshed
    current = importlib.reload(tomeshed)
    current.app.config.update(TESTING=True, CATALOG_PAGE_SIZE=2)
    return current


def signed_in(module):
    client = module.app.test_client()
    response = client.post("/login", data={"username": "admin", "password": "secret-password", "password_confirmation": "secret-password"})
    assert response.status_code == 302
    return client


def wait_job(client, job_id, state=None):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        jobs = client.get("/api/imports").json["jobs"]
        job = next(row for row in jobs if row["id"] == job_id)
        if job["state"] in ("ready", "ready_with_warning", "failed") and (state is None or job["state"] == state):
            return job
        time.sleep(0.03)
    raise AssertionError(f"Job {job_id} did not finish: {job}")


def pdf_bytes(pages=12):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=400)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def epub_bytes(words=1):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        archive.writestr("OEBPS/content.opf", '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>ÉPÚB Book</dc:title><dc:creator>Áuthor</dc:creator></metadata><manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="chapter"/></spine></package>')
        archive.writestr("OEBPS/chapter.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>' + ("word " * words) + '</p></body></html>')
    return stream.getvalue()


def json_bytes(name="Structured Notes"):
    document = DoclingDocument(name=name)
    document.add_title("A structured heading")
    return json.dumps(document.export_to_dict()).encode()


def upload(client, content, filename):
    return client.post("/api/imports", data={"file": (io.BytesIO(content), filename)}, content_type="multipart/form-data")


def fake_result(source, filename, staging):
    source_type, title, author, page_count = document_processing.detect_source(source)
    if source_type == "docling":
        return document_processing.process_document(source, filename, staging)
    title = title or document_processing.cleaned_title(filename)
    document_processing.make_thumbnail(source, source_type, title, staging / "thumbnail.png")
    text = "word " * 601 if source_type == "epub" else ""
    (staging / "structured.json").write_text(json.dumps({"test": "structured"}))
    return {"state": "ready", "source_type": source_type, "title": title, "author": author or "Unknown author",
            "byte_size": source.stat().st_size, "text": text, "page_count": page_count if source_type == "pdf" else 3,
            "count_kind": "exact" if source_type == "pdf" else "estimated", "thumbnail": "thumbnail.png", "artifact": "structured.json"}


def test_pdf_epub_json_import_source_detail_and_pagination(module, monkeypatch):
    monkeypatch.setattr(module.document_library, "_run_conversion", fake_result)
    client = signed_in(module)
    fixtures = [(pdf_bytes(), "Plain_File.pdf", "pdf"), (epub_bytes(), "sample.epub", "epub"), (json_bytes(), "notes.json", "docling")]
    ids = []
    for content, filename, source_type in fixtures:
        response = upload(client, content, filename)
        assert response.status_code == 202
        assert len(response.json["document_id"]) == 32
        wait_job(client, response.json["id"], "ready")
        document_id = response.json["document_id"]
        ids.append(document_id)
        detail = client.get(f"/api/documents/{document_id}").json
        assert detail["source_type"] == source_type
        assert client.get(f"/documents/{document_id}").status_code == 200
        assert client.get(f"/api/documents/{document_id}/source").data == content
    first = client.get("/api/documents?limit=99").json
    assert first["total"] == first["library_total"] == 3
    assert len(first["documents"]) == 2
    assert len(client.get("/api/documents?offset=2").json["documents"]) == 1
    pdf = client.get(f"/api/documents/{ids[0]}").json
    epub = client.get(f"/api/documents/{ids[1]}").json
    structured = client.get(f"/api/documents/{ids[2]}").json
    assert (pdf["page_count"], pdf["count_kind"], pdf["title"], pdf["author"]) == (12, "exact", "Plain File", "Unknown author")
    assert (epub["page_count"], epub["count_kind"], epub["author"]) == (3, "estimated", "Áuthor")
    assert (structured["page_count"], structured["count_kind"]) == (None, "unknown")
    for document_id in ids[:2]:
        assert client.get(f"/api/documents/{document_id}/thumbnail").status_code == 200
    assert client.get("/api/documents?q=Épúb").json["total"] == 1
    assert client.get("/api/documents?q=áUTHOR").json["total"] == 1
    assert client.get("/api/documents?q=PLAIN_file").json["total"] == 1
    assert client.get("/api/documents?q=missing").json["total"] == 0


def test_invalid_uploads_jobs_and_auth_path_boundary(module, monkeypatch, tmp_path):
    monkeypatch.setattr(module.document_library, "_run_conversion", fake_result)
    anonymous = module.app.test_client()
    for path in ("/api/documents", "/api/documents?q=secret", "/api/imports", "/api/documents/abc/source", "/api/documents/abc/thumbnail"):
        assert anonymous.get(path).status_code == 401
    client = signed_in(module)
    for content, filename in ((b"not a book", "bad.pdf"), (b"%PDF-broken", "bad.epub")):
        response = upload(client, content, filename)
        assert response.status_code == 202
        job = wait_job(client, response.json["id"], "failed")
        assert job["error"]
    assert client.get("/api/documents").json["total"] == 0
    response = upload(client, json_bytes(), "valid.json")
    wait_job(client, response.json["id"], "ready")
    external = tmp_path / "secret.txt"; external.write_text("private")
    with module.db() as conn:
        conn.execute("UPDATE documents SET source_path=? WHERE id=?", (str(external), response.json["document_id"]))
    assert client.get(f"/api/documents/{response.json['document_id']}/source").status_code == 404
    assert client.get("/api/documents/../../secret.txt/source").status_code in (404, 308)


def test_warning_retry_and_thumbnail_fallback(module, monkeypatch):
    client = signed_in(module)
    attempts = 0

    def converter(source, filename, staging):
        nonlocal attempts
        attempts += 1
        result = fake_result(source, filename, staging)
        if attempts < 3:
            result.update(state="ready_with_warning", error=f"Indexing warning: extraction failed {attempts}", text="", artifact=None)
        if attempts == 1:
            result["thumbnail"] = None
        return result

    monkeypatch.setattr(module.document_library, "_run_conversion", converter)
    content = pdf_bytes(1)
    response = upload(client, content, "No_Title.pdf")
    wait_job(client, response.json["id"], "ready_with_warning")
    document_id = response.json["document_id"]
    detail = client.get(f"/api/documents/{document_id}").json
    assert detail["state"] == "ready_with_warning" and detail["error"].startswith("Indexing warning")
    assert detail["thumbnail_available"] is False and detail["author"] == "Unknown author"
    assert client.get(f"/api/documents/{document_id}/source").data == content
    retry = client.post(f"/api/documents/{document_id}/retry")
    wait_job(client, retry.json["id"], "ready_with_warning")
    assert client.get(f"/api/documents/{document_id}").json["error"].endswith("2")
    retry = client.post(f"/api/documents/{document_id}/retry")
    wait_job(client, retry.json["id"], "ready")
    assert client.get(f"/api/documents/{document_id}").json["error"] is None
    assert client.get(f"/api/documents/{document_id}/source").data == content


def test_concurrent_retry_is_deduplicated_and_late_failure_keeps_success(module, monkeypatch):
    client = signed_in(module)
    source = pdf_bytes(1)

    def first_conversion(path, filename, staging):
        result = fake_result(path, filename, staging)
        result.update(state="ready_with_warning", error="Indexing warning: initial extraction failed", text="", artifact=None)
        return result

    monkeypatch.setattr(module.document_library, "_run_conversion", first_conversion)
    imported = upload(client, source, "retry.pdf")
    wait_job(client, imported.json["id"], "ready_with_warning")
    document_id = imported.json["document_id"]
    started = threading.Event()
    release = threading.Event()

    def retry_conversion(path, filename, staging):
        started.set()
        assert release.wait(timeout=5)
        result = fake_result(path, filename, staging)
        result["text"] = "indexed words"
        return result

    monkeypatch.setattr(module.document_library, "_run_conversion", retry_conversion)
    other = module.app.test_client()
    assert other.post("/login", data={"username": "admin", "password": "secret-password"}).status_code == 302
    gate = threading.Barrier(2)

    def request_retry(request_client):
        gate.wait(timeout=5)
        return request_client.post(f"/api/documents/{document_id}/retry")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(request_retry, client)
        second = pool.submit(request_retry, other)
        responses = [first.result(timeout=5), second.result(timeout=5)]
    assert sorted(response.status_code for response in responses) == [202, 409]
    assert next(response for response in responses if response.status_code == 409).json["error"] == "Indexing retry already in progress"
    assert started.wait(timeout=5)
    release.set()
    accepted = next(response for response in responses if response.status_code == 202)
    wait_job(client, accepted.json["id"], "ready")
    with module.db() as conn:
        successful = conn.execute("SELECT state,error,text_content,artifact_path FROM documents WHERE id=?", (document_id,)).fetchone()
        assert successful["state"] == "ready" and successful["error"] is None
        assert successful["text_content"] == "indexed words"
        stale_id = uuid.uuid4().hex
        now = time.time()
        conn.execute("""INSERT INTO import_jobs(id,document_id,original_filename,source_path,state,retry,attempt,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""", (stale_id, document_id, "retry.pdf", f"sources/{document_id}.source",
                                   "processing", 1, 1, now, now))
    module.document_library._finish_job({"id": stale_id, "document_id": document_id, "retry": 1}, 1,
                                        {"state": "failed", "error": "late extraction failure"}, module.document_library.root / "staging")
    with module.db() as conn:
        after = conn.execute("SELECT state,error,text_content,artifact_path FROM documents WHERE id=?", (document_id,)).fetchone()
    assert dict(after) == dict(successful)
    assert client.get(f"/api/documents/{document_id}/source").data == source


def test_size_timeout_late_completion_and_existing_document(module, monkeypatch):
    client = signed_in(module)
    monkeypatch.setattr(module.document_library, "_run_conversion", fake_result)
    existing = upload(client, json_bytes(), "existing.json")
    wait_job(client, existing.json["id"], "ready")
    module.app.config["MAX_UPLOAD_BYTES"] = 12
    oversized = upload(client, b"x" * 100, "too-big.pdf")
    assert oversized.status_code == 413 and "size limit" in oversized.json["error"]
    module.app.config["MAX_UPLOAD_BYTES"] = 100000

    def timeout(source, filename, staging):
        raise subprocess.TimeoutExpired(["docling"], 1)

    monkeypatch.setattr(module.document_library, "_run_conversion", timeout)
    failed = upload(client, pdf_bytes(1), "slow.pdf")
    wait_job(client, failed.json["id"], "failed")
    assert "time limit" in next(row for row in client.get("/api/imports").json["jobs"] if row["id"] == failed.json["id"])["error"]
    assert client.get("/api/documents").json["total"] == 1
    assert client.get(f"/api/documents/{existing.json['document_id']}/source").data == json_bytes()
    # A worker result arriving after failure cannot create a card or replace an artifact.
    module.document_library._finish_job({"id": failed.json["id"], "document_id": failed.json["document_id"],
        "source_path": f"sources/{failed.json['document_id']}.source", "original_filename": "slow.pdf", "retry": 0,
        "created_at": time.time()}, 1, {"state": "ready", "source_type": "pdf", "title": "late", "author": "Unknown author",
        "byte_size": 10, "count_kind": "exact", "page_count": 1}, module.document_library.root / "staging")
    assert client.get("/api/documents").json["total"] == 1


def test_source_storage_failure_records_failed_job(module, monkeypatch):
    client = signed_in(module)
    original_open = Path.open

    def fail_source_open(path, *args, **kwargs):
        if path.parent == module.document_library.root / "sources":
            raise OSError("Storage unavailable")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_source_open)
    response = upload(client, pdf_bytes(1), "storage.pdf")
    assert response.status_code == 400
    assert "Storage unavailable" in response.json["error"]
    job = wait_job(client, response.json["job_id"], "failed")
    assert job["error"] == "Storage unavailable"
    assert client.get("/api/documents").json["total"] == 0


def test_configured_conversion_concurrency(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMESHED_DB", str(tmp_path / "library.db"))
    monkeypatch.setenv("TOMESHED_LIBRARY_DIR", str(tmp_path / "library"))
    monkeypatch.setenv("TOMESHED_CONVERSION_WORKERS", "1")
    import tomeshed
    module = importlib.reload(tomeshed)
    client = signed_in(module)
    entered = threading.Event()
    release = threading.Event()
    active = 0
    maximum = 0
    lock = threading.Lock()

    def blocked(source, filename, staging):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        entered.set()
        assert release.wait(timeout=5)
        result = fake_result(source, filename, staging)
        with lock:
            active -= 1
        return result

    monkeypatch.setattr(module.document_library, "_run_conversion", blocked)
    first = upload(client, json_bytes("First"), "first.json")
    assert entered.wait(timeout=5)
    second = upload(client, json_bytes("Second"), "second.json")
    assert second.status_code == 202
    time.sleep(.1)
    assert maximum == 1
    release.set()
    wait_job(client, first.json["id"], "ready")
    wait_job(client, second.json["id"], "ready")
    assert maximum == 1


def test_restart_reconciles_jobs_and_sse(module, monkeypatch):
    client = signed_in(module)
    source = json_bytes()
    present = uuid.uuid4().hex
    processing_present = uuid.uuid4().hex
    missing = uuid.uuid4().hex
    (module.document_library.root / "sources" / f"{present}.source").write_bytes(source)
    (module.document_library.root / "sources" / f"{processing_present}.source").write_bytes(source)
    now = time.time()
    with module.db() as conn:
        for job_id, state, document_id in (("pending-job", "pending", present),
                                           ("processing-job", "processing", processing_present),
                                           ("missing-job", "processing", missing)):
            conn.execute("INSERT INTO import_jobs(id,document_id,original_filename,source_path,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (job_id, document_id, "notes.json", f"sources/{document_id}.source", state, now, now))
    monkeypatch.setattr(type(module.document_library), "_run_conversion", lambda self, source, filename, staging: fake_result(source, filename, staging))
    module = importlib.reload(module)
    client = module.app.test_client()
    assert client.post("/login", data={"username": "admin", "password": "secret-password"}).status_code == 302
    assert wait_job(client, "pending-job", "ready")["document_id"] == present
    assert wait_job(client, "processing-job", "ready")["document_id"] == processing_present
    assert wait_job(client, "missing-job", "failed")["error"]
    assert client.get(f"/api/documents/{present}/source").data == source
    assert client.get(f"/api/documents/{processing_present}/source").data == source
    stream = client.get("/api/events", buffered=False)
    first = next(stream.response).decode()
    assert "event: ready" in first
    module.document_library.publish()
    second = next(stream.response).decode()
    assert "event: change" in second
    stream.close()


def test_real_docling_json_pdf_and_epub_pagination(tmp_path):
    source = tmp_path / "document.source"
    source.write_bytes(json_bytes())
    stage = tmp_path / "stage"; stage.mkdir()
    result = document_processing.process_document(source, "notes.json", stage)
    assert result["state"] == "ready" and result["source_type"] == "docling"
    assert (stage / "structured.json").is_file()
    assert result["count_kind"] == "unknown"
    source.write_bytes(pdf_bytes(12))
    result = document_processing.process_document(source, "book.pdf", stage)
    assert (result["state"], result["page_count"], result["count_kind"], result["thumbnail"]) == ("ready", 12, "exact", "thumbnail.png")
    source.write_bytes(epub_bytes(601))
    result = document_processing.process_document(source, "book.epub", stage)
    assert (result["page_count"], result["count_kind"], result["thumbnail"]) == (3, "estimated", "thumbnail.png")
    source.write_bytes(epub_bytes(0))
    result = document_processing.process_document(source, "book.epub", stage)
    assert (result["page_count"], result["count_kind"]) == (None, "unknown")


def test_epub_missing_spine_content_is_invalid(tmp_path):
    content = epub_bytes()
    source = tmp_path / "broken.epub"
    with zipfile.ZipFile(io.BytesIO(content)) as original, zipfile.ZipFile(source, "w") as changed:
        for name in original.namelist():
            if name != "OEBPS/chapter.xhtml":
                changed.writestr(name, original.read(name))
    with pytest.raises(ValueError, match="missing content"):
        document_processing.detect_source(source)

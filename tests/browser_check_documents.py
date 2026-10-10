"""Feature 0002 browser checks with real PDF, EPUB, and Docling JSON imports."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ARTIFACTS = Path("/tmp/tomeshed-feature-0002-browser")
ARTIFACTS.mkdir(exist_ok=True)


def fixture_files(folder):
    from test_documents import pdf_bytes, epub_bytes, json_bytes
    paths = []
    for name, data in (("Twelve_Page.pdf", pdf_bytes(12)), ("Book_601.epub", epub_bytes(601)),
                       ("Structured_Notes.json", json_bytes())):
        path = folder / name
        path.write_bytes(data)
        paths.append(path)
    return paths


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        database = folder / "library.db"
        files = fixture_files(folder)
        corrupt = folder / "Corrupt.pdf"
        corrupt.write_bytes(b"not a PDF")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, TOMESHED_DB=str(database), TOMESHED_LIBRARY_DIR=str(folder / "storage"),
                   TOMESHED_CATALOG_PAGE_SIZE="2", HOST="127.0.0.1", PORT=str(port))
        server = subprocess.Popen([sys.executable, "tomeshed.py"], cwd=ROOT, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    with urlopen(base + "/api/health", timeout=.2):
                        break
                except Exception:
                    time.sleep(.1)
            else:
                raise AssertionError("Tomeshed did not start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 390, "height": 800})
                page = context.new_page()
                event_requests = []
                page.on("request", lambda request: event_requests.append(request.url) if request.url.endswith("/api/events") else None)
                page.goto(base + "/login")
                page.locator("#password").fill("browser-password")
                page.locator("#password_confirmation").fill("browser-password")
                page.get_by_role("button", name="Set password and open library").click()
                page.wait_for_url(base + "/")
                page.locator("#uploadFile").set_input_files([str(path) for path in files])
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '3 documents'", timeout=60000)
                assert 2 <= page.locator(".document-card").count() <= 3
                if page.locator(".document-card").count() < 3:
                    page.get_by_role("button", name="Load more documents").click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                assert page.locator("#libraryCount").inner_text() == "3 documents"
                assert page.locator(".document-art").count() >= 2
                assert page.get_by_text("PDF · 12 pages").is_visible()
                assert page.get_by_text("EPUB · ~3 pages").is_visible()
                assert "estimated" in page.get_by_text("EPUB · ~3 pages").get_attribute("aria-label")
                pdf = page.locator(".document-card").filter(has_text="Twelve Page")
                pdf.get_by_role("button", name="Info for Twelve Page").click()
                panel = pdf.locator(".document-info")
                assert panel.is_visible()
                geometry = panel.evaluate("el => {const r=el.getBoundingClientRect();return {left:r.left,right:r.right,width:innerWidth}}")
                assert geometry["left"] >= 0 and geometry["right"] <= geometry["width"], geometry
                assert "Import state: ready" in panel.inner_text()
                page.screenshot(path=str(ARTIFACTS / "library-390.png"), full_page=True)

                # A corrupt upload records a failed job; seeded pending and
                # processing rows let the drawer show each active state.
                page.locator("#uploadFile").set_input_files(str(corrupt))
                with sqlite3.connect(database) as conn:
                    now = time.time()
                    for job_id, state in (("drawer-pending", "pending"), ("drawer-processing", "processing")):
                        conn.execute("INSERT INTO import_jobs(id,document_id,original_filename,source_path,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                                     (job_id, uuid.uuid4().hex, f"{state}.pdf", "sources/missing.source", state, now, now))
                page.locator("#importsButton").click()
                page.wait_for_function("async () => (await (await fetch('/api/imports')).json()).jobs.some(job => job.original_filename === 'Corrupt.pdf' && job.state === 'failed')")
                page.evaluate("() => loadImportJobs()")
                drawer = page.locator("#importsDrawer")
                assert "pending.pdf" in drawer.inner_text() and "processing.pdf" in drawer.inner_text()
                page.wait_for_function("() => [...document.querySelectorAll('.import-job')].some(row => row.textContent.includes('Corrupt.pdf') && row.textContent.includes('failed'))")
                page.screenshot(path=str(ARTIFACTS / "imports-390.png"), full_page=True)
                page.locator("#closeImports").click()
                with sqlite3.connect(database) as conn:
                    conn.execute("DELETE FROM import_jobs WHERE id IN ('drawer-pending','drawer-processing')")

                # A warning stays on the card until retry completes.
                with sqlite3.connect(database) as conn:
                    pdf_id = conn.execute("SELECT id FROM documents WHERE source_type='pdf'").fetchone()[0]
                    conn.execute("UPDATE documents SET state='ready_with_warning',error='Indexing warning: controlled failure',text_content='' WHERE id=?", (pdf_id,))
                page.locator("#librarySearch").fill("Twelve")
                page.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                page.evaluate("() => refreshLibrary()")
                warning_card = page.locator(".document-card")
                assert warning_card.locator(".document-copy .index-warning").is_visible()
                warning_card.get_by_role("button", name="Info for Twelve Page").click()
                assert "controlled failure" in warning_card.locator(".document-info").inner_text()
                warning_card.get_by_role("button", name="Retry indexing").click()
                page.wait_for_function("async id => (await (await fetch('/api/documents/'+id)).json()).state === 'ready'", arg=pdf_id, timeout=30000)
                page.wait_for_function("document.querySelector('.document-card .index-warning') === null")
                page.locator("#librarySearch").fill("áUTHOR")
                page.wait_for_function("document.querySelector('.document-card h3')?.textContent === 'ÉPÚB Book'")
                assert "ÉPÚB Book" in page.locator(".document-card").first.inner_text()
                page.locator("#librarySearch").fill("not in the catalog")
                page.get_by_text("No matching documents").wait_for()
                page.locator("#librarySearch").fill("")
                page.wait_for_function("document.querySelectorAll('.document-card').length >= 2")
                if page.locator(".document-card").count() < 3:
                    page.get_by_role("button", name="Load more documents").click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                pdf = page.locator(".document-card").filter(has_text="Twelve Page")
                pdf.get_by_role("button", name="Open Twelve Page").focus()
                page.keyboard.press("Enter")
                page.locator("#reader").wait_for(state="visible")
                page.locator("#readerClose").click()
                page.goto(base + f"/documents/{pdf_id}")
                assert page.get_by_role("link", name="Open source").is_visible()
                assert page.get_by_role("link", name="Download source").is_visible()
                page.goto(base + "/")
                page.set_viewport_size({"width": 1280, "height": 800})
                page.wait_for_function("document.querySelectorAll('.document-card').length >= 2")
                if page.locator(".document-card").count() < 3:
                    page.get_by_role("button", name="Load more documents").click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                page.screenshot(path=str(ARTIFACTS / "library-1280.png"), full_page=True)
                assert page.locator(".document-card").first.bounding_box()["width"] > 150

                first_event_requests = len(event_requests)
                assert first_event_requests >= 1
                server.terminate()
                server.wait(timeout=5)
                with sqlite3.connect(database) as conn:
                    original = conn.execute("SELECT * FROM documents LIMIT 1").fetchone()
                    columns = [column[1] for column in conn.execute("PRAGMA table_info(documents)")]
                    clone = dict(zip(columns, original))
                    clone.update(id=uuid.uuid4().hex, title="Reconnected document", search_key="reconnected document", created_at=time.time())
                    conn.execute(f"INSERT INTO documents({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", tuple(clone[column] for column in columns))
                server = subprocess.Popen([sys.executable, "tomeshed.py"], cwd=ROOT, env=env,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for _ in range(100):
                    try:
                        with urlopen(base + "/api/health", timeout=.2):
                            break
                    except Exception:
                        time.sleep(.1)
                else:
                    raise AssertionError("Tomeshed did not restart")
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '4 documents'", timeout=20000)
                assert len(event_requests) > first_event_requests, "EventSource did not reconnect"
                if page.locator(".document-card").count() < 4:
                    page.get_by_role("button", name="Load more documents").click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 4")
                assert page.locator("#libraryCount").inner_text() == "4 documents"
                browser.close()
            (ARTIFACTS / "report.json").write_text(json.dumps({"result": "passed", "checks": [
                "real imports", "cards and badges", "mobile Info geometry", "import drawer states",
                "indexing warning and retry", "search and keyboard", "authenticated detail",
                "responsive widths", "catalog pagination", "SSE reconnect"]}, indent=2))
            print(f"passed: {ARTIFACTS / 'report.json'}")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    main()

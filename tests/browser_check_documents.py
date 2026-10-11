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
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '3 results'", timeout=60000)
                assert 2 <= page.locator(".document-card").count() <= 3
                assert page.evaluate("""async () => (await fetch('/api/preferences', {method:'PATCH',
                    headers:{'Content-Type':'application/json'}, body:JSON.stringify({page_size:'endless'})})).ok""")
                page.reload()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                assert page.locator("#libraryCount").inner_text() == "3 results"
                assert page.locator(".document-art").count() >= 2
                assert page.locator(".document-card .document-copy h3").count() == 3
                assert page.locator(".document-card .document-copy p, .document-card .document-tags, .document-page-badge").count() == 0
                assert page.locator(".document-card .document-fallback").count() == 3
                assert page.locator(".document-card").filter(has_text="Structured Notes").locator(".document-fallback").is_visible()
                page.screenshot(path=str(ARTIFACTS / "library-390-light.png"), full_page=True)
                page.evaluate("document.documentElement.dataset.theme = 'dark'")
                page.screenshot(path=str(ARTIFACTS / "library-390-dark.png"), full_page=True)
                page.evaluate("document.documentElement.dataset.theme = 'light'")
                touch_context = browser.new_context(viewport={"width": 390, "height": 800}, has_touch=True,
                                                    is_mobile=True, storage_state=context.storage_state())
                touch_page = touch_context.new_page()
                touch_page.goto(base + "/")
                touch_page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                touch_card = touch_page.locator('.document-card').first
                touch_card.locator('.document-open').tap()
                assert touch_card.get_attribute('class').find('document-selected') >= 0
                assert touch_card.locator('.document-copy button, .document-preview .document-open-action').count() == 0
                touch_page.locator('#openSelected').tap()
                touch_page.locator('#reader').wait_for(state='visible')
                touch_context.close()
                pdf = page.locator(".document-card").filter(has_text="Twelve Page")
                pdf.locator(".document-open").dblclick()
                panel = page.locator("#readerDocumentPanel")
                assert panel.is_visible()
                assert "Page count: 12 (exact)" in panel.inner_text()
                geometry = panel.evaluate("el => {const r=el.getBoundingClientRect();return {left:r.left,right:r.right,width:innerWidth}}")
                assert geometry["left"] >= 0 and geometry["right"] <= geometry["width"], geometry
                assert "Import state: ready" in panel.inner_text()
                page.screenshot(path=str(ARTIFACTS / "reader-panel-390.png"), full_page=True)
                page.locator("#readerClose").click()
                page.locator(".document-card").filter(has_text="ÉPÚB Book").locator(".document-open").dblclick()
                assert "Page count: 3 (estimated)" in panel.inner_text()
                page.locator("#readerClose").click()

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
                for width in (390, 320):
                    page.set_viewport_size({"width": width, "height": 800})
                    for theme in ("light", "dark"):
                        page.evaluate("theme => { document.documentElement.dataset.theme = theme; }", theme)
                        page.wait_for_function("""() => {
                          const header = document.querySelector('.app-header').getBoundingClientRect();
                          const drawer = document.querySelector('#importsDrawer').getBoundingClientRect();
                          const footer = document.querySelector('#versionFooter').getBoundingClientRect();
                          return drawer.top >= header.bottom && drawer.bottom <= footer.top;
                        }""")
                        geometry = page.evaluate("""() => {
                          const header = document.querySelector('.app-header').getBoundingClientRect();
                          const search = document.querySelector('.library-search').getBoundingClientRect();
                          const drawer = document.querySelector('#importsDrawer').getBoundingClientRect();
                          const close = document.querySelector('#closeImports').getBoundingClientRect();
                          const footer = document.querySelector('#versionFooter').getBoundingClientRect();
                          return {header: header.toJSON(), search: search.toJSON(),
                            drawer: drawer.toJSON(), close: close.toJSON(), footer: footer.toJSON(),
                            target: document.elementFromPoint(close.x + close.width / 2, close.y + close.height / 2)?.id};
                        }""")
                        assert geometry["search"]["bottom"] <= geometry["header"]["bottom"], geometry
                        assert geometry["close"]["top"] >= geometry["drawer"]["top"], geometry
                        assert geometry["close"]["bottom"] <= geometry["drawer"]["bottom"], geometry
                        assert geometry["target"] == "closeImports", geometry
                        page.locator("#closeImports").click()
                        assert drawer.is_hidden()
                        assert page.locator("#importsButton").evaluate("el => el === document.activeElement")
                        page.locator("#importsButton").focus()
                        page.keyboard.press("Enter")
                        assert drawer.is_visible()
                        assert page.locator("#closeImports").evaluate("el => el === document.activeElement")
                        page.keyboard.press("Enter")
                        assert drawer.is_hidden()
                        assert page.locator("#importsButton").evaluate("el => el === document.activeElement")
                        page.locator("#importsButton").click()
                footer_height = page.locator("#versionFooter").evaluate("el => el.getBoundingClientRect().height")
                page.evaluate("""() => {
                  document.querySelector('#versionWarningText').textContent = 'A newer version is available.';
                  document.querySelector('#versionWarning').hidden = false;
                }""")
                assert page.locator("#versionFooter").evaluate("el => el.getBoundingClientRect().height") > footer_height
                page.wait_for_function("""() => document.querySelector('#importsDrawer').getBoundingClientRect().bottom <=
                  document.querySelector('#versionFooter').getBoundingClientRect().top""")
                page.evaluate("() => { document.querySelector('#versionWarning').hidden = true; }")
                page.locator("#closeImports").click()
                page.set_viewport_size({"width": 390, "height": 800})
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
                assert warning_card.get_by_role("img", name="Indexing warning; details in reader document panel").is_visible()
                warning_card.locator(".document-open").dblclick()
                assert "controlled failure" in page.locator("#readerDocumentPanel").inner_text()
                page.locator("#readerDocumentPanel").get_by_role("button", name="Retry indexing").click()
                page.wait_for_function("async id => (await (await fetch('/api/documents/'+id)).json()).state === 'ready'", arg=pdf_id, timeout=30000)
                page.wait_for_function("document.querySelector('.document-card .document-warning-badge') === null")
                page.locator("#readerClose").click()
                page.locator("#librarySearch").fill("áUTHOR")
                page.wait_for_function("document.querySelector('.document-card h3')?.textContent === 'ÉPÚB Book'")
                assert "ÉPÚB Book" in page.locator(".document-card").first.inner_text()
                page.locator("#librarySearch").fill("not in the catalog")
                page.get_by_text("No matching documents").wait_for()
                page.locator("#librarySearch").fill("")
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                pdf = page.locator(".document-card").filter(has_text="Twelve Page")
                pdf.get_by_role("button", name="Select Twelve Page").focus()
                page.keyboard.press("Enter")
                page.locator("#reader").wait_for(state="visible")
                page.locator("#readerClose").click()
                page.goto(base + f"/documents/{pdf_id}")
                assert page.get_by_role("link", name="Open source").is_visible()
                assert page.get_by_role("link", name="Download source").is_visible()
                page.goto(base + "/")
                page.set_viewport_size({"width": 1280, "height": 800})
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                page.screenshot(path=str(ARTIFACTS / "library-1280.png"), full_page=True)
                page.evaluate("document.documentElement.dataset.theme = 'dark'")
                page.screenshot(path=str(ARTIFACTS / "library-1280-dark.png"), full_page=True)
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
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '4 results'", timeout=20000)
                assert len(event_requests) > first_event_requests, "EventSource did not reconnect"
                page.wait_for_function("document.querySelectorAll('.document-card').length === 4")
                assert page.locator("#libraryCount").inner_text() == "4 results"
                browser.close()
            (ARTIFACTS / "report.json").write_text(json.dumps({"result": "passed", "checks": [
                "real imports", "cover tiles and reader counts", "mobile reader panel geometry", "import drawer states and geometry",
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

"""Feature 0005 browser and existing-database migration checks."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from test_documents import pdf_bytes
from test_reader import epub_fixture, docling_fixture


ARTIFACTS = Path("/tmp/tomeshed-feature-0005-browser")
ARTIFACTS.mkdir(exist_ok=True)


def seed_legacy_database(folder):
    storage = folder / "storage" / "sources"
    storage.mkdir(parents=True)
    database = folder / "legacy.db"
    with sqlite3.connect(database) as conn:
        conn.execute("""CREATE TABLE documents (
            id TEXT PRIMARY KEY, original_filename TEXT NOT NULL, source_path TEXT NOT NULL,
            source_type TEXT NOT NULL, title TEXT NOT NULL, author TEXT NOT NULL,
            byte_size INTEGER NOT NULL, search_key TEXT NOT NULL, text_content TEXT NOT NULL DEFAULT '',
            page_count INTEGER, count_kind TEXT NOT NULL, thumbnail_path TEXT, artifact_path TEXT,
            state TEXT NOT NULL, error TEXT, created_at REAL NOT NULL)""")
        for index in range(7):
            document_id = f"book{index:02d}"
            source = pdf_bytes(index + 1)
            (storage / f"{document_id}.source").write_bytes(source)
            conn.execute("""INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                document_id, f"Source_{index}.pdf", f"sources/{document_id}.source", "pdf", f"Book {index}",
                "Ada" if index % 2 == 0 else "Bob", len(source), f"book {index} ada", "indexed moon" if index == 2 else "",
                index + 1, "exact", None, None, "ready_with_warning" if index == 6 else "ready",
                "Indexing warning: test" if index == 6 else None, 100 + index))
        for document_id, kind, content, count, basis in (
            ("older-epub", "epub", epub_fixture(), 3, "estimated"),
            ("older-docling", "docling", docling_fixture(extra=0), None, "unknown"),
        ):
            (storage / f"{document_id}.source").write_bytes(content)
            conn.execute("""INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                document_id, f"{document_id}.{kind}", f"sources/{document_id}.source", kind,
                f"Older {kind}", "Older author", len(content), f"older {kind}", "", count, basis,
                None, None, "ready", None, 50))
        assert "favorite" not in [row[1] for row in conn.execute("PRAGMA table_info(documents)")]
    return database


def ids(page):
    return page.locator(".document-card").evaluate_all("cards => cards.map(card => card.dataset.documentId)")


def card(page, title):
    return page.locator(".document-card").filter(has=page.locator("h3", has_text=title))


def set_sort(page, field, direction=None):
    page.locator("#sortToggle").click()
    page.locator("#sortField").select_option(field)
    if direction is not None:
        page.locator("#sortDirection").select_option(direction)
    page.keyboard.press("Escape")
    assert page.locator("#catalogSort").is_hidden()
    assert page.locator("#sortToggle").get_attribute("aria-expanded") == "false"


def load_all(page):
    """Scroll the endless sentinel until every authorized result is rendered."""
    page.wait_for_function("catalogSignature === catalogParams(0).toString() && !catalogLoading && pendingCatalogMutation === 0")
    for _ in range(20):
        loaded, total = page.evaluate("[catalogLoaded, catalogTotal]")
        if loaded >= total:
            assert page.locator("#documentGrid > *").count() == total
            return
        page.evaluate("document.querySelector('#catalogSentinel').scrollIntoView()")
        page.wait_for_function("before => (catalogLoaded > before || catalogLoaded >= catalogTotal) && !catalogLoading", arg=loaded)
    raise AssertionError("Endless scrolling did not reach the final result")


def submit_tag(page, document_id, value):
    """Submit the current reader form after live updates settle."""
    page.wait_for_function("pendingCatalogMutation === 0 && !catalogLoading")
    page.evaluate("""({id, tag}) => {
        if (!window.tomeshedReader.isOpenFor(id)) throw new Error('Wrong document is open');
        const form = document.querySelector('#readerDocumentPanel form.document-tag-editor');
        form.querySelector('input').value = tag;
        form.requestSubmit();
    }""", {"id": document_id, "tag": value})


def open_info(page, item):
    if page.locator('#reader').is_visible():
        page.locator('#readerClose').click()
    item.locator('.document-open').dblclick()
    return page.locator('#readerDocumentPanel')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        database = seed_legacy_database(folder)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, TOMESHED_DB=str(database), TOMESHED_LIBRARY_DIR=str(folder / "storage"),
                   TOMESHED_CATALOG_PAGE_SIZE="2", HOST="127.0.0.1", PORT=str(port), PYTHONDONTWRITEBYTECODE="1")
        server = subprocess.Popen([sys.executable, "tomeshed.py"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        checks = {}
        try:
            for _ in range(100):
                try:
                    with urlopen(base + "/api/health", timeout=.2): break
                except Exception: time.sleep(.1)
            else: raise AssertionError("Server did not start")
            with sqlite3.connect(database) as conn:
                assert {"favorite", "corrected_title", "corrected_author"} <= {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
                assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 9
            checks["migration"] = "passed"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 850})
                page = context.new_page()
                page.on("console", lambda message: print("BROWSER", message.type, message.text))
                page.on("pageerror", lambda error: print("PAGE ERROR", error))
                page.goto(base + "/login")
                page.locator("#password").fill("browser-password")
                page.locator("#password_confirmation").fill("browser-password")
                page.get_by_role("button", name="Set password and open library").click()
                page.wait_for_url(base + "/")
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2", timeout=10000)
                page.wait_for_function("document.querySelectorAll('.document-new-badge').length === 2")
                first_card = page.locator('.document-card').first
                assert first_card.locator('.document-copy h3').is_visible()
                assert first_card.locator('.document-copy p, .document-copy .document-tags').count() == 0
                checks["unread_badges"] = "passed"
                assert page.locator("#sortToggle").get_attribute("aria-label") == "Sort: Date added, Descending"
                page.locator("#sortToggle").focus()
                page.keyboard.press("Enter")
                assert page.locator("#catalogSort").is_visible()
                assert page.evaluate("document.activeElement.id") == "sortField"
                page.keyboard.press("Tab")
                assert page.evaluate("document.activeElement.id") == "sortDirection"
                page.keyboard.press("Escape")
                assert page.evaluate("document.activeElement.id") == "sortToggle"
                page.locator("#accountMenuButton").click()
                page.locator("#settingsMenuItem").click()
                page.locator("#prefPageSize").select_option("endless")
                page.get_by_text("Items per page saved.").wait_for()
                page.locator("#settingsBack").click()
                load_all(page)
                assert page.locator(".document-card").count() == 9
                set_sort(page, "title", "asc")
                load_all(page)
                page.wait_for_function("document.querySelector('.document-card')?.dataset.documentId === 'book00' && document.querySelectorAll('.document-card').length === 9")
                assert page.locator("#sortToggle").get_attribute("aria-label") == "Sort: Title, Ascending"
                set_sort(page, "title", "desc")
                page.wait_for_function("document.querySelector('.document-card')?.dataset.documentId === 'older-epub'")
                set_sort(page, "favorite", "desc")
                assert page.locator("#sortDirection option:checked").inner_text() == "Favorites first"
                assert page.locator("#sortToggle").get_attribute("aria-label") == "Sort: Favorite, Favorites first"
                set_sort(page, "date_added", "desc")
                page.wait_for_function("document.querySelector('.document-card')?.dataset.documentId === 'book06'")
                load_all(page)
                checks["sort_popover_keyboard_direction"] = "passed"
                # Tag spelling, reuse, suggestions, and final association cleanup.
                book6 = card(page, "Book 6")
                info = open_info(page, book6)
                info_text = info.inner_text()
                for field in ("Original filename: Source_6.pdf", "Source type: PDF", "Size:", "Page count: 7 (exact)", "Imported:", "Import state: ready_with_warning", "Indexing warning: test", "Last read: Never"):
                    assert field in info_text
                info.get_by_role("textbox", name="Add tag").fill("  History   ")
                info.get_by_role("button", name="Add tag", exact=True).click()
                page.wait_for_function("document.querySelector('#readerDocumentPanel .document-tags').textContent.includes('History')")
                load_all(page)
                book5 = card(page, "Book 5")
                info = open_info(page, book5)
                assert info.locator(".document-tag-suggestions").get_by_role("button", name="History").count() == 1
                submit_tag(page, "book05", "history")
                page.wait_for_function("document.querySelector('#readerDocumentPanel .document-tags').textContent.includes('History')")
                assert page.evaluate("async () => (await (await fetch('/api/tags')).json()).tags") == ["History"]
                for document_id in ("book06", "book05"):
                    item = page.locator(f'.document-card[data-document-id="{document_id}"]')
                    info = open_info(page, item)
                    info.locator(".document-tag-editor").last.get_by_role("button", name="History ×").click()
                    page.wait_for_function("id => !document.querySelector('#readerDocumentPanel .document-tags').textContent.includes('History')", arg=document_id)
                assert page.evaluate("async () => (await (await fetch('/api/tags')).json()).tags") == []
                book5 = card(page, "Book 5")
                open_info(page, book5)
                submit_tag(page, "book05", "History")
                page.wait_for_function("document.querySelector('#readerDocumentPanel .document-tags').textContent.includes('History')")
                checks["tag_reuse_suggestion"] = "passed"
                page.locator("#readerClose").click()
                for query, expected in (("Older epub", "Page count: 3 (estimated)"), ("Older docling", "Page count: Unknown (unknown)")):
                    page.locator("#librarySearch").fill(query)
                    page.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                    item = card(page, query)
                    assert expected in open_info(page, item).inner_text()
                    page.locator("#readerClose").click()
                page.locator("#librarySearch").fill("")
                load_all(page)
                assert page.locator(".document-card").count() == 9
                checks["reader_panel_count_basis"] = "passed"
                # Correct metadata and search; failed mutation leaves confirmed text.
                book5 = card(page, "Book 5")
                info = open_info(page, book5)
                info.get_by_label("Title").fill("Corrected Atlas")
                info.get_by_label("Author").fill("Revised Ada")
                info.get_by_role("button", name="Save metadata").click()
                page.wait_for_function("document.querySelector('.document-card[data-document-id=book05] h3').textContent === 'Corrected Atlas'")
                assert page.evaluate("async () => (await (await fetch('/api/documents/book05')).json()).original_filename") == "Source_5.pdf"
                page.locator("#readerClose").click()
                page.locator("#librarySearch").fill("REVISED ADA")
                page.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                assert ids(page) == ["book05"]
                page.locator("#librarySearch").fill("")
                load_all(page)
                assert page.locator(".document-card").count() == 9
                checks["metadata_search"] = "passed"
                page.route("**/api/documents/book05/metadata", lambda route: route.fulfill(status=503, content_type="application/json", body='{"error":"controlled metadata rejection"}'))
                book5 = card(page, "Corrected Atlas")
                info = open_info(page, book5)
                info.get_by_label("Title").fill("Unconfirmed title")
                info.get_by_label("Author").fill("Unconfirmed author")
                info.get_by_role("button", name="Save metadata").click()
                info.get_by_text("Change was not saved: controlled metadata rejection").wait_for()
                book5 = card(page, "Corrected Atlas")
                assert info.is_visible()
                assert info.get_by_label("Title").input_value() == "Unconfirmed title"
                assert info.get_by_label("Author").input_value() == "Unconfirmed author"
                page.unroute("**/api/documents/book05/metadata")
                checks["metadata_failure_keeps_input"] = "passed"
                page.locator("#readerClose").click()
                page.locator("#filtersToggle").click()
                page.locator("#filterType").select_option("pdf")
                page.locator("#filterAuthor").fill("REVISED")
                page.locator("#filterFavorite").select_option("false")
                page.locator("#filterReading").select_option("in_progress")
                page.locator("#filterTags input[value=History]").check()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                assert ids(page) == ["book05"]
                page.wait_for_function("document.querySelector('#activeFilters').textContent.includes('Tags (ALL): History')")
                assert "Tags (ALL): History" in page.locator("#activeFilters").inner_text()
                page.locator("#librarySearch").fill("no document has this exact phrase")
                page.get_by_text("No matching documents").wait_for()
                if page.locator("#catalogFilters").is_hidden(): page.locator("#filtersToggle").click()
                page.locator("#clearFilters").click()
                assert page.locator("#librarySearch").input_value() == "no document has this exact phrase"
                assert page.locator("#activeFilters").inner_text() == "Search: no document has this exact phrase"
                page.locator("#librarySearch").fill("")
                load_all(page)
                assert page.locator(".document-card").count() == 9
                assert page.locator("#activeFilters").inner_text() == "No active filters"
                checks["combined_filter_clear_empty"] = "passed"
                # Favorite-first ordering, keyboard activation, and confirmed failure rollback.
                set_sort(page, "favorite", "desc")
                load_all(page)
                assert page.locator(".document-card").count() == 9
                before = ids(page)
                target = page.locator('.document-card[data-document-id="book04"] .document-star')
                page.keyboard.press("Tab"); target.focus()
                assert target.evaluate("button => getComputedStyle(button).outlineStyle !== 'none'")
                page.keyboard.press("Enter")
                page.wait_for_function("document.querySelector('.document-card[data-document-id=book04] .document-star').getAttribute('aria-pressed') === 'true'")
                assert ids(page) == before
                assert page.locator("#reader").is_hidden()
                load_all(page)
                assert page.locator(".document-card").count() == 9
                assert len(ids(page)) == len(set(ids(page)))
                assert set(ids(page)) >= set(before)
                page.route("**/api/documents/book04/favorite", lambda route: route.fulfill(status=503, content_type="application/json", body='{"error":"controlled rejection"}'))
                page.locator('.document-card[data-document-id="book04"] .document-star').click()
                page.get_by_text("Change was not saved: controlled rejection").wait_for()
                assert page.locator('.document-card[data-document-id="book04"] .document-star').get_attribute("aria-pressed") == "true"
                page.unroute("**/api/documents/book04/favorite")
                set_sort(page, "date_added", "desc")
                set_sort(page, "favorite", "desc")
                page.wait_for_function("document.querySelector('.document-card')?.dataset.documentId === 'book04'")
                checks["favorite_order_rollback_pagination"] = "passed"
                # A concurrent server event cannot reorder cards during a delayed star save.
                cookie = next(item["value"] for item in context.cookies() if item["name"] == "session")
                concurrent = []
                def publish_favorite():
                    request = Request(base + "/api/documents/book03/favorite", method="PATCH",
                                      data=b'{"favorite":true}', headers={"Cookie": f"session={cookie}", "Content-Type": "application/json"})
                    with urlopen(request, timeout=5) as response:
                        concurrent.append(response.status)
                def delay_favorite(route):
                    worker = threading.Thread(target=publish_favorite); worker.start()
                    time.sleep(.35); worker.join(timeout=5)
                    route.continue_()
                page.route("**/api/documents/book04/favorite", delay_favorite)
                before = ids(page)
                page.locator('.document-card[data-document-id="book04"] .document-star').click()
                page.wait_for_function("document.querySelector('.document-card[data-document-id=book04] .document-star').getAttribute('aria-pressed') === 'false'")
                page.wait_for_function("document.querySelector('.document-card[data-document-id=book03] .document-star')?.getAttribute('aria-pressed') === 'true'")
                assert concurrent == [200] and ids(page)[:len(before)] == before
                page.unroute("**/api/documents/book04/favorite")
                set_sort(page, "date_added", "desc")
                page.wait_for_function("document.querySelector('.document-card')?.dataset.documentId === 'book06'")
                set_sort(page, "favorite", "desc")
                page.wait_for_function("document.querySelector('.document-card')?.dataset.documentId === 'book03'")
                checks["delayed_favorite_sse_stable_order"] = "passed"
                for document_id in ("book05", "book02"):
                    assert page.evaluate("async id => (await fetch(`/api/documents/${id}/favorite`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({favorite:true})})).ok", document_id)
                page.locator("#filtersToggle").click()
                page.locator("#filterFavorite").select_option("true")
                load_all(page)
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                assert ids(page) == ["book05", "book03", "book02"]
                page.locator('.document-card[data-document-id="book03"] .document-star').click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                assert ids(page) == ["book05", "book02"]
                if page.locator("#catalogFilters").is_hidden(): page.locator("#filtersToggle").click()
                page.locator("#clearFilters").click()
                checks["filter_removal_stable_order"] = "passed"
                page.screenshot(path=str(ARTIFACTS / "catalog-1280.png"), full_page=True)
                # Reader-open state belongs to the first account; preview leaves it untouched.
                page.locator("#librarySearch").fill("Book 6")
                page.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                book6 = card(page, "Book 6")
                book6.locator(".document-open").scroll_into_view_if_needed()
                state_before_preview = page.evaluate("async () => (await (await fetch('/api/documents/book06')).json()).reading_state")
                page.evaluate("""() => {const card = document.querySelector('.document-card[data-document-id="book06"]');
                    window.tomeshedPreview.open('book06', card, card.querySelector('.document-preview'), card.querySelector('.document-open'));} """)
                page.locator("#previewBubble").wait_for(state="visible")
                page.locator("#previewClose").click()
                assert page.evaluate("async () => (await (await fetch('/api/documents/book06')).json()).reading_state") == state_before_preview
                assert page.evaluate("async () => (await fetch('/api/documents/book06/source?download=1')).ok")
                book6.locator(".document-open").dblclick()
                page.locator("#reader").wait_for(state="visible")
                page.wait_for_function("async () => (await (await fetch('/api/documents/book06')).json()).reading_state === 'in_progress'")
                page.locator("#readerFinished").click()
                page.wait_for_function("async () => (await (await fetch('/api/documents/book06')).json()).reading_state === 'finished'")
                page.locator("#readerStartOver").click()
                page.wait_for_function("async () => (await (await fetch('/api/documents/book06')).json()).reading_state === 'in_progress'")
                page.locator("#readerClose").click()
                assert "Last read: Never" not in open_info(page, card(page, "Book 6")).inner_text()
                page.locator("#readerClose").click()
                assert card(page, "Book 6").locator(".document-new-badge").count() == 0
                checks["reader_state_preview_isolation"] = "passed"
                page.screenshot(path=str(ARTIFACTS / "reader-state-1280.png"), full_page=True)
                # Two accounts have separate reader-open state.
                created = page.evaluate("async () => await (await fetch('/api/users', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'second',password:'second-password',role:'normal'})})).json()")
                second = browser.new_context(viewport={"width": 390, "height": 800})
                other = second.new_page(); other.goto(base + "/login")
                other.locator("#username").fill("second"); other.locator("#password").fill("second-password")
                other.get_by_role("button", name="Sign in").click(); other.wait_for_url(base + "/")
                other.locator("#librarySearch").fill("Book 6")
                other.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                assert card(other, "Book 6").get_by_text("new", exact=True).is_visible()
                assert "Last read: Never" in open_info(other, card(other, "Book 6")).inner_text()
                other.screenshot(path=str(ARTIFACTS / "second-user-390.png"), full_page=True)
                other.locator("#readerClose").click()
                checks["two_accounts"] = "passed"
                # A source failure in the normal reader flow cannot create an open.
                (folder / "storage" / "sources" / "book00.source").unlink()
                other.locator("#librarySearch").fill("Book 0")
                other.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                card(other, "Book 0").locator(".document-open").dblclick()
                other.locator("#readerError").wait_for(state="visible")
                assert "Source missing" in other.locator("#readerError").inner_text()
                assert other.evaluate("async () => (await (await fetch('/api/documents/book00')).json()).reading_state") == "unread"
                with sqlite3.connect(database) as conn:
                    assert conn.execute("SELECT COUNT(*) FROM reader_opens WHERE document_id='book00'").fetchone()[0] == 0
                checks["failed_reader_no_open"] = "passed"
                browser.close()
            # Restart the application against the migrated database.
            server.terminate(); server.wait(timeout=5)
            server = subprocess.Popen([sys.executable, "tomeshed.py"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                try:
                    with urlopen(base + "/api/health", timeout=.2): break
                except Exception: time.sleep(.1)
            else: raise AssertionError("Server did not restart")
            with sqlite3.connect(database) as conn:
                assert conn.execute("SELECT favorite FROM documents WHERE id='book04'").fetchone()[0] == 0
                assert conn.execute("SELECT corrected_title,corrected_author FROM documents WHERE id='book05'").fetchone() == ("Corrected Atlas", "Revised Ada")
                assert conn.execute("SELECT name FROM tags").fetchone()[0] == "History"
            checks["restart_persistence"] = "passed"
        finally:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill()
        (ARTIFACTS / "report.json").write_text(json.dumps(checks, indent=2))
        print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()

"""Browser checks for Bug 0014 across desktop, mobile, users, and restart.

Usage: .venv/bin/python tests/browser_check_pagination.py
"""

import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

from browser_check import free_port
from browser_check_organization import seed_legacy_database


ROOT = Path(__file__).resolve().parents[1]


def login(page, base, name, password):
    page.goto(base + "/login")
    page.locator("#username").fill(name)
    page.locator("#password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(base + "/")


def wait_server(base):
    for _ in range(100):
        try:
            with urlopen(base + "/api/health", timeout=.2):
                return
        except Exception:
            time.sleep(.1)
    raise AssertionError("Server did not start")


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        database = seed_legacy_database(folder)
        with sqlite3.connect(database) as conn:
            source = conn.execute("SELECT * FROM documents LIMIT 1").fetchone()
            for index in range(9, 55):
                conn.execute("""INSERT INTO documents(id,original_filename,source_path,source_type,title,author,
                    byte_size,search_key,text_content,page_count,count_kind,thumbnail_path,artifact_path,state,error,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (f"book{index:02d}", source[1], source[2], "pdf", f"Book {index}", "Ada",
                     source[6], f"book {index}", "", 1, "exact", None, None, "ready", None, 100 + index))
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, TOMESHED_DB=str(database), TOMESHED_LIBRARY_DIR=str(folder / "storage"),
                   HOST="127.0.0.1", PORT=str(port), PYTHONDONTWRITEBYTECODE="1")

        def start():
            process = subprocess.Popen([sys.executable, "tomeshed.py"], cwd=ROOT, env=env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wait_server(base)
            return process

        server = start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 850})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/login")
                page.locator("#password").fill("browser-password")
                page.locator("#password_confirmation").fill("browser-password")
                page.get_by_role("button", name="Set password and open library").click()
                page.wait_for_url(base + "/")
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.includes('of 6')")
                assert page.locator("#documentGrid").locator("> *").count() == 10
                assert page.locator("#pagerFirst").is_disabled() and page.locator("#pagerPrev").is_disabled()
                assert page.locator("#pagerNext").is_enabled() and page.locator("#pagerLast").is_enabled()
                assert page.evaluate("async () => (await (await fetch('/api/documents?limit=50')).json()).items.length") == 50

                # A bookshelf takes one slot in the same authorized result list.
                assert page.evaluate("""async () => (await fetch('/api/bookshelves', {
                  method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:'Reading circle'})
                })).ok""")
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.includes('56 results')")
                page.locator("#pagerLast").click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 6')")
                assert page.locator("#documentGrid").locator("> *").count() == 6
                assert page.locator("#pagerNext").is_disabled() and page.locator("#pagerLast").is_disabled()
                assert page.locator("#pagerFirst").is_enabled() and page.locator("#pagerPrev").is_enabled()

                page.locator("#accountMenuButton").click()
                page.locator("#settingsMenuItem").click()
                page.locator("#prefPageSize").select_option("20")
                page.get_by_text("Items per page saved.").wait_for()
                page.locator("#settingsBack").click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 1 of 3')")
                assert page.locator("#documentGrid").locator("> *").count() == 20
                page.locator("#accountMenuButton").click()
                page.locator("#settingsMenuItem").click()
                page.locator("#prefPageSize").select_option("50")
                page.locator("#settingsBack").click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 1 of 2')")
                assert page.locator("#documentGrid").locator("> *").count() == 50

                # Remove the only final-page item after choosing five items per page.
                page.locator("#accountMenuButton").click()
                page.locator("#settingsMenuItem").click()
                page.locator("#prefPageSize").select_option("5")
                page.get_by_text("Items per page saved.").wait_for()
                page.locator("#settingsBack").click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 1 of 12')")
                page.locator("#pagerLast").click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 12')")
                last_document = page.locator(".document-card").first.get_attribute("data-document-id")
                assert last_document
                with sqlite3.connect(database) as conn:
                    conn.execute("DELETE FROM documents WHERE id=?", (last_document,))
                page.evaluate("() => loadCatalog(false, true)")
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 11 of 11')")
                assert page.locator("#documentGrid").locator("> *").count() == 5

                assert page.locator("#pagerNext").is_disabled()
                page.locator("#librarySearch").fill("Book 1")
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.includes('11 results')")
                assert page.locator("#pagerInfo").inner_text().startswith("Page 1")
                page.locator("#librarySearch").fill("")
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.includes('55 results')")
                page.locator("#pagerLast").click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 11')")
                page.locator("#filtersToggle").click()
                page.locator("#filterScope").select_option("bookshelves")
                page.wait_for_function("document.querySelector('#pagerInfo').textContent === 'Page 1 of 1 · 1 result'")
                page.locator("#filterScope").select_option("all")
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 1 of 11')")
                page.locator("#filtersToggle").click()
                page.locator("#pagerLast").click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 11')")
                page.locator("#sortToggle").click()
                page.locator("#sortField").select_option("title")
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 1 of 11')")
                page.locator("#sortToggle").click()
                page.locator("#accountMenuButton").click()
                page.locator("#settingsMenuItem").click()
                page.locator("#prefPageSize").select_option("endless")
                page.get_by_text("Items per page saved.").wait_for()
                page.locator("#settingsBack").click()
                page.locator("#catalogSentinel").scroll_into_view_if_needed()
                page.wait_for_function("document.querySelector('#catalogEndlessStatus').textContent.includes('All')")
                assert page.locator("#documentGrid").locator("> *").count() == 55
                page.locator("#accountMenuButton").click()
                page.locator("#settingsMenuItem").click()
                page.locator("#prefPageSize").select_option("5")
                page.get_by_text("Items per page saved.").wait_for()
                page.locator("#settingsBack").click()
                page.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 1 of 11')")

                # Page size remains per user after a process restart.
                admin_user = page.evaluate("""async () => (await (await fetch('/api/users', {
                  method:'POST', headers:{'Content-Type':'application/json'},
                  body:JSON.stringify({username:'reader',name:'Reader',password:'reader-password',role:'normal'})
                })).json()).id""")
                assert admin_user
                reader = browser.new_page(viewport={"width": 390, "height": 780})
                login(reader, base, "reader", "reader-password")
                reader.wait_for_function("document.querySelector('#pagerInfo').textContent.startsWith('Page 1')")
                assert reader.locator("#documentGrid").locator("> *").count() == 10
                reader.locator("#accountMenuButton").click()
                reader.locator("#settingsMenuItem").click()
                reader.locator("#prefPageSize").select_option("endless")
                reader.get_by_text("Items per page saved.").wait_for()
                reader.locator("#settingsBack").click()
                reader.locator("#catalogSentinel").scroll_into_view_if_needed()
                reader.wait_for_function("document.querySelector('#catalogEndlessStatus').textContent.includes('All')")
                assert reader.locator("#catalogPager").is_hidden()
                reader_total = reader.evaluate("async () => (await (await fetch('/api/documents')).json()).total")
                assert reader.locator("#documentGrid").locator("> *").count() == reader_total
                assert reader.locator(".bookshelf-card").count() == 0
                assert reader.locator("#catalogEndlessStatus").is_visible()
                assert not errors, errors
                browser.close()
            server.terminate()
            server.wait(timeout=5)
            server = start()
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                login(page, base, "admin", "browser-password")
                page.locator("#accountMenuButton").click()
                page.locator("#settingsMenuItem").click()
                assert page.locator("#prefPageSize").input_value() == "5"
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=5)
    print("Bug 0014 browser pagination checks passed")


if __name__ == "__main__":
    main()

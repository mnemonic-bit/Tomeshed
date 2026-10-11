"""Check that Clear filters resets only catalog filters inside the Filters popover.

Usage: .venv/bin/python tests/browser_check_clear_filters.py
Evidence: /tmp/tomeshed-bug-0011-browser/checks.json
"""

import json
import os
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
ARTIFACTS = Path("/tmp/tomeshed-bug-0011-browser")
ARTIFACTS.mkdir(exist_ok=True)


def main():
    checks = {}
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        database = seed_legacy_database(folder)
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, TOMESHED_DB=str(database), TOMESHED_LIBRARY_DIR=str(folder / "storage"),
                   TOMESHED_CATALOG_PAGE_SIZE="2", HOST="127.0.0.1", PORT=str(port),
                   PYTHONDONTWRITEBYTECODE="1")
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
                raise AssertionError("Server did not start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 850})
                page.goto(base + "/login")
                page.locator("#password").fill("browser-password")
                page.locator("#password_confirmation").fill("browser-password")
                page.get_by_role("button", name="Set password and open library").click()
                page.wait_for_url(base + "/")
                page.locator(".document-card").first.wait_for()
                assert page.evaluate("async () => (await fetch('/api/documents/book00/tags', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tag:'History'})})).ok")
                page.reload()
                page.locator("#filterTags input[value=History]").wait_for(state="attached")
                page.locator("#librarySearch").fill("Book")
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '7 results'")
                assert page.locator("#activeFilters").count() == 0
                page.locator("#filtersToggle").click()
                clear = page.locator("#clearFilters")
                assert page.get_by_role("button", name="Clear filters", exact=True).count() == 1
                assert clear.evaluate("button => button.closest('#catalogFilters') !== null")
                assert clear.inner_text() == ""
                assert clear.is_disabled()
                assert page.get_by_role("button", name="Filters", exact=True).count() == 1
                assert not page.locator("#filtersToggle").evaluate("button => button.classList.contains('has-active-filters')")
                checks["placement_and_search_only"] = "passed"

                page.locator("#sortToggle").click()
                page.locator("#sortField").select_option("title")
                page.locator("#sortDirection").select_option("asc")
                page.keyboard.press("Escape")
                page.locator("#filtersToggle").click()
                page.locator("#filterScope").select_option("documents")
                page.locator("#filterType").select_option("pdf")
                page.locator("#filterAuthor").fill("Ada")
                page.locator("#filterFavorite").select_option("false")
                page.locator("#filterReading").select_option("unread")
                page.locator("#filterTags input[value=History]").check()
                page.locator("#filterTagMode").select_option("ANY")
                page.wait_for_function("document.querySelector('#filtersToggle').getAttribute('aria-label') === 'Filters active'")
                assert clear.is_enabled()
                assert page.locator("#filtersToggle").evaluate("button => button.classList.contains('has-active-filters')")
                clear.click()
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '7 results'")
                assert page.locator("#librarySearch").input_value() == "Book"
                assert page.locator("#sortField").input_value() == "title"
                assert page.locator("#sortDirection").input_value() == "asc"
                for selector, expected in (("#filterScope", "all"), ("#filterType", ""),
                                           ("#filterAuthor", ""), ("#filterFavorite", ""),
                                           ("#filterReading", ""), ("#filterTagMode", "ALL")):
                    assert page.locator(selector).input_value() == expected
                assert page.locator("#filterTags input:checked").count() == 0
                assert page.locator(".document-card").evaluate_all("cards => cards.map(card => card.dataset.documentId)") == ["book00", "book01"]
                assert page.locator("#catalogPager").is_visible()
                assert page.locator("#pagerNext").is_enabled()
                assert page.get_by_role("button", name="Filters", exact=True).count() == 1
                assert not page.locator("#filtersToggle").evaluate("button => button.classList.contains('has-active-filters')")
                assert clear.is_disabled()
                assert page.locator("#catalogFilters").is_hidden()
                assert page.locator("#filtersToggle").evaluate("button => document.activeElement === button")
                checks["clear_preserves_search_sort_and_first_page"] = "passed"
                page.locator("#filtersToggle").click()
                page.locator("#filterTagMode").select_option("ANY")
                assert clear.is_enabled()
                assert page.get_by_role("button", name="Filters", exact=True).count() == 1
                clear.click()
                assert page.locator("#filterTagMode").input_value() == "ALL"
                assert page.get_by_role("button", name="Filters", exact=True).count() == 1
                checks["tag_mode_only"] = "passed"
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=5)
    (ARTIFACTS / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()

"""Check that library filters belong to search at desktop and narrow widths.

Usage: .venv/bin/python tests/browser_check_filters_popover.py
Evidence: /tmp/tomeshed-bug-0009-browser
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
ARTIFACTS = Path("/tmp/tomeshed-bug-0009-browser")
ARTIFACTS.mkdir(exist_ok=True)


def check_geometry(page):
    geometry = page.evaluate("""() => {
      const search = document.querySelector('.library-search').getBoundingClientRect();
      const button = document.querySelector('#filtersToggle').getBoundingClientRect();
      const panel = document.querySelector('#catalogFilters').getBoundingClientRect();
      return {search: search.toJSON(), button: button.toJSON(), panel: panel.toJSON(), width: innerWidth, height: innerHeight};
    }""")
    assert geometry["button"]["left"] >= geometry["search"]["left"]
    assert geometry["button"]["right"] <= geometry["search"]["right"]
    assert 0 <= geometry["panel"]["left"] < geometry["panel"]["right"] <= geometry["width"]
    assert 0 <= geometry["panel"]["top"] - geometry["search"]["bottom"] <= 12
    assert geometry["panel"]["bottom"] <= geometry["height"]
    assert geometry["panel"]["width"] <= 420
    assert page.evaluate("""() => document.querySelector('.library-heading').getBoundingClientRect().top >=
      document.querySelector('.app-header').getBoundingClientRect().bottom""")


def check_sort_geometry(page):
    geometry = page.evaluate("""() => {
      const search = document.querySelector('.library-search').getBoundingClientRect();
      const filters = document.querySelector('#filtersToggle').getBoundingClientRect();
      const button = document.querySelector('#sortToggle').getBoundingClientRect();
      const panel = document.querySelector('#catalogSort').getBoundingClientRect();
      return {search: search.toJSON(), filters: filters.toJSON(), button: button.toJSON(), panel: panel.toJSON(), width: innerWidth, height: innerHeight};
    }""")
    assert geometry["filters"]["right"] <= geometry["button"]["left"]
    assert geometry["button"]["right"] <= geometry["search"]["right"]
    assert 0 <= geometry["panel"]["left"] < geometry["panel"]["right"] <= geometry["width"]
    assert 0 <= geometry["panel"]["top"] - geometry["search"]["bottom"] <= 12
    assert geometry["panel"]["bottom"] <= geometry["height"]
    assert geometry["panel"]["width"] <= 260


def main():
    checks = {}
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        database = seed_legacy_database(folder)
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, TOMESHED_DB=str(database), TOMESHED_LIBRARY_DIR=str(folder / "storage"),
                   HOST="127.0.0.1", PORT=str(port), PYTHONDONTWRITEBYTECODE="1")
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
                toggle = page.get_by_role("button", name="Filters", exact=True)
                assert toggle.inner_text() == ""
                assert toggle.get_attribute("aria-controls") == "catalogFilters"
                for width in (390, 1280):
                    page.set_viewport_size({"width": width, "height": 568 if width == 390 else 850})
                    toggle.focus()
                    page.keyboard.press("Enter")
                    assert toggle.get_attribute("aria-expanded") == "true"
                    assert page.locator("#catalogFilters").is_visible()
                    check_geometry(page)
                    for field in ("#filterType", "#filterAuthor", "#filterFavorite", "#filterReading", "#filterTagMode", "#filterTags"):
                        assert page.locator(field).is_visible()
                    page.screenshot(path=str(ARTIFACTS / f"filters-{width}.png"))
                    page.locator("#filterType").focus()
                    page.keyboard.press("Escape")
                    assert page.locator("#catalogFilters").is_hidden()
                    assert toggle.evaluate("button => document.activeElement === button")
                    toggle.click()
                    page.locator("#filterType").focus()
                    page.locator(".app-title").click()
                    assert page.locator("#catalogFilters").is_hidden()
                    assert toggle.evaluate("button => document.activeElement === button")
                    toggle.click()
                    page.locator("#librarySearch").click()
                    assert page.locator("#catalogFilters").is_hidden()
                    assert page.locator("#librarySearch").evaluate("input => document.activeElement === input")
                    sort_toggle = page.locator("#sortToggle")
                    assert sort_toggle.inner_text() == ""
                    sort_toggle.focus()
                    page.keyboard.press("Enter")
                    assert page.locator("#catalogSort").is_visible()
                    check_sort_geometry(page)
                    page.keyboard.press("Escape")
                    assert page.locator("#catalogSort").is_hidden()
                    checks[f"geometry_access_dismiss_{width}"] = "passed"
                toggle.click()
                page.locator("#filterType").select_option("pdf")
                page.locator("#filterAuthor").fill("Ada")
                page.locator("#filterFavorite").select_option("false")
                page.locator("#filterReading").select_option("unread")
                page.locator("#librarySearch").fill("Book 2")
                page.wait_for_function("document.querySelectorAll('.document-card').length === 1")
                assert page.locator(".document-card h3").inner_text() == "Book 2"
                assert "Type: PDF" in page.locator("#activeFilters").inner_text()
                assert page.locator(".library-search").evaluate("el => el.classList.contains('has-active-filters')")
                assert page.locator("#activeFilters").evaluate("el => el.closest('.library-search') !== null")
                page.keyboard.press("Escape")
                toggle.click()
                assert page.locator("#filterType").input_value() == "pdf"
                assert page.locator("#filterAuthor").input_value() == "Ada"
                assert page.locator("#filterFavorite").input_value() == "false"
                assert page.locator("#filterReading").input_value() == "unread"
                checks["combined_filter_and_reopen"] = "passed"
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=5)
    (ARTIFACTS / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()

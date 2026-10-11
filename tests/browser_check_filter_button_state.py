"""Check the Filters button cue with catalog filters, search, and sort.

Usage: PYTHONPATH=.:tests .venv/bin/python tests/browser_check_filter_button_state.py
Evidence: /tmp/tomeshed-bug-0040-browser/checks.json
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
ARTIFACTS = Path("/tmp/tomeshed-bug-0040-browser")
ARTIFACTS.mkdir(exist_ok=True)


def button_style(page):
    return page.locator("#filtersToggle").evaluate("""button => {
      const style = getComputedStyle(button);
      return {background: style.backgroundColor, color: style.color, border: style.borderColor};
    }""")


def assert_button_state(page, active):
    toggle = page.locator("#filtersToggle")
    expected = "Filters active" if active else "Filters"
    page.wait_for_function("expected => document.querySelector('#filtersToggle').getAttribute('aria-label') === expected", arg=expected)
    assert page.get_by_role("button", name=expected, exact=True).count() == 1
    assert toggle.get_attribute("aria-label") == expected
    assert toggle.evaluate("button => button.classList.contains('has-active-filters')") is active
    assert page.locator("#activeFilters").count() == 0
    assert page.get_by_text("No active filters", exact=True).count() == 0


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
                assert_button_state(page, False)
                default_style = button_style(page)
                page.locator("#librarySearch").fill("Book")
                page.wait_for_function("!catalogLoading && catalogSignature === catalogParams(0).toString()")
                assert_button_state(page, False)
                page.locator("#sortToggle").click()
                page.locator("#sortField").select_option("title")
                page.keyboard.press("Escape")
                assert_button_state(page, False)
                checks["default_search_sort"] = "passed"

                toggle = page.locator("#filtersToggle")
                toggle.click()
                cases = (
                    ("#filterScope", "documents"),
                    ("#filterType", "pdf"),
                    ("#filterAuthor", "Ada"),
                    ("#filterFavorite", "false"),
                    ("#filterReading", "unread"),
                    ("#filterTags input[value=History]", True),
                )
                for selector, value in cases:
                    control = page.locator(selector)
                    if value is True:
                        control.check()
                    elif selector == "#filterAuthor":
                        control.fill(value)
                    else:
                        control.select_option(value)
                    assert_button_state(page, True)
                    page.keyboard.press("Escape")
                    assert page.locator("#catalogFilters").is_hidden()
                    assert_button_state(page, True)
                    assert button_style(page)["background"] != default_style["background"]
                    toggle.click()
                    assert control.is_checked() if value is True else control.input_value() == value
                    page.locator("#clearFilters").click()
                    assert_button_state(page, False)
                    assert button_style(page) == default_style
                    toggle.click()
                checks["each_filter_and_clear"] = "passed"

                page.locator("#filterType").select_option("pdf")
                page.locator("#filterFavorite").select_option("false")
                page.locator("#filterTags input[value=History]").check()
                page.locator("#filterTagMode").select_option("ANY")
                assert_button_state(page, True)
                for theme in ("light", "dark"):
                    page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
                    page.keyboard.press("Escape")
                    assert_button_state(page, True)
                    active_style = button_style(page)
                    assert active_style["background"] != page.locator("#sortToggle").evaluate("button => getComputedStyle(button).backgroundColor")
                    toggle.hover()
                    assert button_style(page)["background"] == active_style["background"]
                    page.screenshot(path=str(ARTIFACTS / f"filters-active-{theme}.png"))
                    toggle.click()
                    assert page.locator("#filterType").input_value() == "pdf"
                    assert page.locator("#filterFavorite").input_value() == "false"
                    assert page.locator("#filterTags input[value=History]").is_checked()
                    assert page.locator("#filterTagMode").input_value() == "ANY"
                    assert page.get_by_role("button", name="Clear filters").is_enabled()
                page.locator("#clearFilters").click()
                assert_button_state(page, False)
                page.locator("#librarySearch").fill("")
                checks["multiple_themes_accessibility"] = "passed"

                toggle.click()
                page.locator("#filterTagMode").select_option("ANY")
                assert_button_state(page, False)
                assert page.locator("#clearFilters").is_enabled()
                page.locator("#clearFilters").click()
                assert page.locator("#filterTagMode").input_value() == "ALL"
                checks["tag_mode_without_tags"] = "passed"
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=5)
    (ARTIFACTS / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()

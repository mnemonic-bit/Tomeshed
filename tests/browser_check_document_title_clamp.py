"""Browser check for Bug 0039 document thumbnail title clamping.

Usage: .venv/bin/python tests/browser_check_document_title_clamp.py
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
LONG_TITLE = "A Complete Illustrated History of Libraries and Reading Across Many Places and Centuries " * 3
LONG_TITLE = LONG_TITLE.strip()


def title_geometry(heading):
    return heading.evaluate("""heading => {
      const style = getComputedStyle(heading);
      const lineHeight = parseFloat(style.lineHeight);
      const clone = heading.cloneNode(true);
      clone.style.display = 'block';
      clone.style.webkitLineClamp = 'unset';
      clone.style.overflow = 'visible';
      clone.style.position = 'absolute';
      clone.style.width = `${heading.getBoundingClientRect().width}px`;
      heading.parentElement.append(clone);
      const naturalLines = Math.round(clone.getBoundingClientRect().height / lineHeight);
      clone.remove();
      return {
        naturalLines,
        visibleLines: heading.getBoundingClientRect().height / lineHeight,
        fontSize: parseFloat(style.fontSize),
        lineHeight,
        clamp: style.webkitLineClamp,
        overflow: style.overflow,
        orient: style.webkitBoxOrient
      };
    }""")


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        database = seed_legacy_database(folder)
        with sqlite3.connect(database) as connection:
            for document_id, title in (("book00", "Short"), ("book01", "Measured Title"),
                                       ("book02", LONG_TITLE)):
                connection.execute("UPDATE documents SET title=?,search_key=? WHERE id=?",
                                   (title, title.casefold(), document_id))
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        environment = dict(os.environ, TOMESHED_DB=str(database),
                           TOMESHED_LIBRARY_DIR=str(folder / "storage"),
                           TOMESHED_CATALOG_PAGE_SIZE="50", HOST="127.0.0.1", PORT=str(port),
                           PYTHONDONTWRITEBYTECODE="1")
        server = subprocess.Popen([sys.executable, "tomeshed.py"], cwd=ROOT, env=environment,
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
                page = browser.new_page(viewport={"width": 1280, "height": 850})
                page.goto(base + "/login")
                page.locator("#password").fill("browser-password")
                page.locator("#password_confirmation").fill("browser-password")
                page.get_by_role("button", name="Set password and open library").click()
                page.wait_for_url(base + "/")
                page.wait_for_function("document.querySelectorAll('.document-card').length === 9")
                short = page.locator('[data-document-id="book00"] .document-copy h3')
                exact = page.locator('[data-document-id="book01"] .document-copy h3')
                long = page.locator('[data-document-id="book02"] .document-copy h3')
                for width in (1280, 390, 320):
                    page.set_viewport_size({"width": width, "height": 850})
                    page.evaluate("() => document.fonts.ready")
                    # Choose a title whose natural layout is exactly two lines at this card width.
                    for count in range(2, 20):
                        title = " ".join(["Measured", "Title"] * count)
                        exact.evaluate("(heading, title) => heading.textContent = title", title)
                        if title_geometry(exact)["naturalLines"] == 2:
                            break
                    else:
                        raise AssertionError(f"No exact two-line title at {width}px")
                    for heading, natural_lines, visible_lines in ((short, 1, 1), (exact, 2, 2)):
                        geometry = title_geometry(heading)
                        assert geometry["naturalLines"] == natural_lines, (width, geometry)
                        assert abs(geometry["visibleLines"] - visible_lines) < .05, (width, geometry)
                    geometry = title_geometry(long)
                    assert geometry["naturalLines"] > 2, (width, geometry)
                    assert abs(geometry["visibleLines"] - 2) < .05, (width, geometry)
                    assert geometry["clamp"] == "2" and geometry["overflow"] == "hidden", geometry
                    assert geometry["orient"] == "vertical", geometry
                    assert abs(geometry["fontSize"] - 15.52) < .02, geometry
                    assert abs(geometry["lineHeight"] / geometry["fontSize"] - 1.3) < .01, geometry
                    assert long.text_content() == LONG_TITLE
                    assert page.get_by_role("heading", name=LONG_TITLE, exact=True).count() == 1
                    assert page.get_by_role("button", name=f"Select {LONG_TITLE}").count() == 1
                    if width == 390:
                        long.screenshot(path="/tmp/tomeshed-bug-0039-title-390.png")
                page.set_viewport_size({"width": 1280, "height": 850})
                page.locator('[data-document-id="book02"] .document-open').dblclick()
                page.locator("#reader").wait_for(state="visible")
                assert page.locator("#readerTitle").text_content() == LONG_TITLE
                assert LONG_TITLE in page.locator("#readerDocumentPanel").inner_text()
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
    print("Bug 0039 browser check passed")

"""Check the Settings Back control across themes and viewport widths.

Usage: .venv/bin/python tests/browser_check_settings_back.py
Evidence: /tmp/tomeshed-bug-0008-browser
"""

import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check import free_port, start_server


ARTIFACTS = Path("/tmp/tomeshed-bug-0008-browser")
ARTIFACTS.mkdir(exist_ok=True)


def check_button(page, width, theme):
    page.set_viewport_size({"width": width, "height": 800})
    page.locator("#accountMenuButton").click()
    with page.expect_response(lambda response: response.url.endswith("/api/preferences") and response.request.method == "GET"):
        page.get_by_role("menuitem", name="Settings").click()
    page.wait_for_load_state("networkidle")
    page.locator("#prefTheme").select_option(theme)
    with page.expect_response(lambda response: response.url.endswith("/api/preferences") and response.request.method == "PATCH"):
        page.locator("#saveTheme").click()
    page.get_by_text("Theme saved.").wait_for()
    assert page.locator("html").get_attribute("data-theme") == theme
    button = page.get_by_role("button", name="Return to library")
    assert button.is_visible()
    assert button.evaluate("""el => el.getBoundingClientRect().top >=
      document.querySelector('.app-header').getBoundingClientRect().bottom""")
    assert button.locator("svg[aria-hidden=true] path").count() == 1
    assert button.inner_text() == ""

    normal = button.evaluate("""el => {
      const css = getComputedStyle(el);
      const svg = el.querySelector('svg');
      const icon = getComputedStyle(svg);
      const rect = el.getBoundingClientRect();
      return { width: rect.width, height: rect.height, radius: css.borderRadius,
        background: css.backgroundColor, border: css.borderColor,
        color: css.color, svgWidth: icon.width, svgHeight: icon.height,
        transform: icon.transform };
    }""")
    assert (normal["width"], normal["height"]) == (40, 40)
    assert normal["radius"] == "50%"
    assert normal["svgWidth"] == normal["svgHeight"] == "20px"
    assert normal["background"] == "rgba(0, 0, 0, 0)"
    assert normal["transform"] == "matrix(0, 1, -1, 0, 0, 0)"

    button.hover()
    hovered = button.evaluate("""el => {
      const css = getComputedStyle(el);
      return { background: css.backgroundColor, border: css.borderColor, color: css.color };
    }""")
    assert hovered["background"] != normal["background"]
    assert hovered["border"] != normal["border"]
    assert hovered["color"] != normal["color"]

    page.locator("#settingsSearchInput").focus()
    page.keyboard.press("Shift+Tab")
    assert button.evaluate("el => el === document.activeElement")
    focus = button.evaluate("""el => {
      const css = getComputedStyle(el);
      return { style: css.outlineStyle, width: css.outlineWidth, offset: css.outlineOffset };
    }""")
    assert focus == {"style": "solid", "width": "2px", "offset": "2px"}
    page.screenshot(path=str(ARTIFACTS / f"settings-{width}-{theme}-focus.png"))
    page.keyboard.press("Enter")
    assert page.locator("#libraryPage").is_visible()
    assert page.locator("#settingsPage").is_hidden()

    page.locator("#accountMenuButton").click()
    page.get_by_role("menuitem", name="Settings").click()
    page.get_by_role("button", name="Return to library").click()
    assert page.locator("#libraryPage").is_visible()
    assert page.locator("#settingsPage").is_hidden()


def main():
    checks = {}
    with tempfile.TemporaryDirectory() as temporary:
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        server = start_server(Path(temporary) / "tomeshed.db", port)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(base + "/")
                page.locator("#password").fill("browser-password")
                page.locator("#password_confirmation").fill("browser-password")
                page.get_by_role("button", name="Set password and open library").click()
                page.wait_for_url(base + "/")
                for width in (390, 1280):
                    for theme in ("light", "dark"):
                        check_button(page, width, theme)
                        checks[f"{width}-{theme}"] = "passed"
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=5)
    (ARTIFACTS / "checks.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()

"""Run the Feature 0001 browser acceptance checks with Playwright Chromium.

Usage: .venv/bin/python tests/browser_check.py
Screenshots and the JSON check report are written to /tmp/tomeshed-feature-0001-browser.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
ARTIFACTS = Path("/tmp/tomeshed-feature-0001-browser")
ARTIFACTS.mkdir(exist_ok=True)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(database, port):
    env = dict(os.environ, TOMESHED_DB=str(database), HOST="127.0.0.1", PORT=str(port))
    process = subprocess.Popen([sys.executable, "tomeshed.py"], cwd=ROOT, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(80):
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=.2) as response:
                if response.status == 200:
                    return process
        except Exception:
            time.sleep(.1)
    raise RuntimeError("Tomeshed did not start")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def bars_visible(page):
    return page.evaluate("""() => {
      const h = document.querySelector('.app-header').getBoundingClientRect();
      const f = document.querySelector('.version-footer').getBoundingClientRect();
      return h.top === 0 && f.bottom === innerHeight && h.bottom < f.top;
    }""")


def main():
    checks = []
    with tempfile.TemporaryDirectory() as temporary:
        database = Path(temporary) / "tomeshed.db"
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        server = start_server(database, port)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                page = context.new_page()
                check(page.goto(base + "/").url.endswith("/login"), "private page redirect")
                check(page.get_by_role("heading", name="Set administrator password").is_visible(), "setup heading")
                page.locator("#password").fill("browser-password")
                page.locator("#password_confirmation").fill("browser-password")
                page.get_by_role("button", name="Set password and open library").click()
                page.wait_for_url(base + "/")
                check(page.get_by_text("No books or PDFs yet").is_visible(), "empty library")
                check(page.get_by_text("Add a PDF, EPUB, or DoclingDocument JSON file").is_visible(), "empty explanation")
                check(page.locator("#uploadFile").count() == 1, "upload control")
                checks.append("AC-01 setup and AC-13 empty library")

                # Pointer, Enter, Space, Escape, and no-reload Settings navigation.
                menu = page.locator("#accountMenuButton")
                menu.click()
                check(page.get_by_role("menuitem", name="Settings").is_visible(), "pointer menu")
                page.keyboard.press("Escape")
                check(page.locator("#accountMenu").is_hidden(), "Escape closes menu")
                menu.focus(); page.keyboard.press("Enter")
                check(page.get_by_role("menuitem", name="Settings").is_visible(), "Enter opens menu")
                page.keyboard.press("Escape")
                menu.focus(); page.keyboard.press("Space")
                check(page.get_by_role("menuitem", name="Settings").is_visible(), "Space opens menu")
                navigation = []
                page.on("framenavigated", lambda frame: navigation.append(frame.url))
                page.get_by_role("menuitem", name="Settings").click()
                check(page.get_by_role("heading", name="Settings").is_visible(), "Settings view")
                page.get_by_role("button", name="Return to library").click()
                check(page.get_by_text("No books or PDFs yet").is_visible(), "returned to library")
                check(not navigation, "Settings navigation reloaded document")
                checks.append("AC-06 menu and Settings navigation")

                # Theme values, persistence, failed save, Settings search.
                menu.click(); page.get_by_role("menuitem", name="Settings").click()
                page.locator("#settingsSearchInput").fill("Theme")
                check(page.locator("#prefTheme").is_visible(), "search visible label")
                page.locator("#settingsSearchInput").fill("system-matched")
                check(page.locator("#settings-general").is_visible(), "search supporting text")
                page.locator("#settingsSearchInput").fill("unfindable setting")
                check(page.locator("#settingsNoResults").is_visible(), "search empty result")
                page.locator("#settingsSearchInput").fill("")
                page.locator("#prefTheme").select_option("dark")
                check(page.locator("html").get_attribute("data-theme") == "dark", "dark appearance")
                page.locator("#saveTheme").click()
                page.get_by_text("Theme saved.").wait_for()
                check(page.get_by_text("Theme saved.").is_visible(), "save response")
                page.locator("#prefTheme").select_option("light")
                check(page.locator("html").get_attribute("data-theme") == "light", "light appearance")
                page.locator("#prefTheme").select_option("system")
                check(page.locator("html").get_attribute("data-theme") in ("light", "dark"), "system appearance")
                def fail_preference(route):
                    if route.request.method == "PATCH":
                        route.fulfill(status=503, content_type="application/json", body='{"error":"Save unavailable"}')
                    else:
                        route.continue_()
                page.route("**/api/preferences", fail_preference)
                page.locator("#prefTheme").select_option("dark")
                page.locator("#saveTheme").click()
                page.get_by_text("Save unavailable").wait_for()
                check(page.locator("#prefTheme").input_value() == "dark", "failed save preserves value")
                check(page.get_by_text("Save unavailable").is_visible(), "failed save error")
                page.unroute("**/api/preferences", fail_preference)
                checks.append("AC-07 themes and failed save; AC-08 search")

                # Admin account controls by pointer and keyboard.
                page.locator('#settings-users').scroll_into_view_if_needed()
                form = page.locator('#addUserForm')
                form.locator('[name=username]').fill('reader')
                form.locator('[name=name]').fill('Reader')
                form.locator('[name=password]').fill('reader-password')
                form.get_by_role('button', name='Add account').click()
                page.get_by_text('Account added.').wait_for()
                check(page.get_by_text('Account added.').is_visible(), 'added account')
                card = page.locator('.user-card').filter(has_text='reader')
                card.get_by_role('button', name='Suspend').focus(); page.keyboard.press('Enter')
                page.locator('.user-card').filter(has_text='reader').get_by_role('button', name='Reactivate').wait_for()
                check(page.locator('.user-card').filter(has_text='reader').get_by_role('button', name='Reactivate').is_visible(), 'suspended with keyboard')
                card = page.locator('.user-card').filter(has_text='reader')
                card.get_by_role('button', name='Reactivate').click()
                page.locator('.user-card').filter(has_text='reader').get_by_role('button', name='Suspend').wait_for()
                card = page.locator('.user-card').filter(has_text='reader')
                card.get_by_label('New password').fill('new-reader-password')
                card.get_by_role('button', name='Save changes').focus(); page.keyboard.press('Enter')
                page.get_by_text('Account updated.').wait_for()
                check(page.get_by_text('Account updated.').is_visible(), 'password reset')
                reader_context = browser.new_context()
                reader = reader_context.new_page()
                reader.goto(base + '/login')
                reader.locator('#username').fill('reader')
                reader.locator('#password').fill('new-reader-password')
                reader.get_by_role('button', name='Sign in').click()
                check(not reader.locator('.auth-error').is_visible(), f"reader sign-in error: {reader.locator('.auth-error').all_text_contents()}")
                reader.wait_for_url(base + '/')
                reader.locator('#accountMenuButton').click()
                reader.get_by_role('menuitem', name='Settings').click()
                check(reader.locator('#settings-users').count() == 0, 'normal user lacks Users')
                check(reader.evaluate("fetch('/api/users').then(r => r.status)") == 403, 'normal user API denied')
                card = page.locator('.user-card').filter(has_text='reader')
                page.once('dialog', lambda dialog: dialog.accept())
                card.get_by_role('button', name='Remove').click()
                page.get_by_text('Account removed.').wait_for()
                check(page.get_by_text('Account removed.').is_visible(), 'removed account')
                check(reader.evaluate("fetch('/api/me').then(r => r.status)") == 401, 'removed session revoked')
                checks.append('AC-03 account pointer and keyboard')

                # Compare at both requested widths and themes; inspect bar and content bounds.
                for width in (390, 1280):
                    page.set_viewport_size({"width": width, "height": 800})
                    for theme in ('light', 'dark'):
                        page.locator('#prefTheme').select_option(theme)
                        page.locator('#saveTheme').click()
                        page.screenshot(path=str(ARTIFACTS / f'settings-{width}-{theme}.png'), full_page=True)
                        check(bars_visible(page), f'bars visible in Settings {width} {theme}')
                        page.locator('#addUserForm button').scroll_into_view_if_needed()
                        check(page.locator('#addUserForm button').is_visible(), 'last Settings control reachable')
                        check(page.evaluate("""() => {
                          const control = document.querySelector('#addUserForm button').getBoundingClientRect();
                          const footer = document.querySelector('.version-footer').getBoundingClientRect();
                          const header = document.querySelector('.app-header').getBoundingClientRect();
                          return control.top >= header.bottom && control.bottom <= footer.top;
                        }"""), 'last Settings control clear of fixed bars')
                        check(bars_visible(page), 'bars stay fixed after scroll')
                        page.locator('#settingsBack').click()
                        page.screenshot(path=str(ARTIFACTS / f'library-{width}-{theme}.png'), full_page=True)
                        check(bars_visible(page), f'bars visible in library {width} {theme}')
                        page.locator('#accountMenuButton').click(); page.get_by_role('menuitem', name='Settings').click()
                checks.append('AC-05 viewport bars and scrolling; AC-12 screenshots')

                # Controlled health responses and visibility changes.
                def health_version(route):
                    route.fulfill(status=200, content_type='application/json', body='{"ok":true,"version":"9.9.9","uptime_seconds":123}')
                page.route('**/api/health', health_version)
                page.evaluate('checkHealth()')
                page.wait_for_function("document.querySelector('#versionWarning').hidden === false")
                check(EXPECTED_VERSION in page.locator('#versionWarning').inner_text() and '9.9.9' in page.locator('#versionWarning').inner_text(), 'both mismatch versions')
                check(page.get_by_role('link', name='Refresh page').is_visible(), 'refresh action')
                page.unroute('**/api/health', health_version)
                page.evaluate('checkHealth()')
                page.wait_for_function("document.querySelector('#versionWarning').hidden === true")
                check(f'API v{EXPECTED_VERSION}' in page.locator('#apiVersion').inner_text(), 'matching version')
                # The normal visible-page timer must detect a later API change.
                page.route('**/api/health', health_version)
                started = time.monotonic()
                page.wait_for_function("document.querySelector('#versionWarning').hidden === false", timeout=30000)
                check(time.monotonic() - started <= 30, 'visible-page health interval')
                page.unroute('**/api/health', health_version)
                page.evaluate('checkHealth()')
                page.wait_for_function("document.querySelector('#versionWarning').hidden === true")
                # Headless Chromium keeps background tabs visible, so control
                # document.hidden and dispatch the browser visibility event.
                page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, get: () => true})")
                page.route('**/api/health', health_version)
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
                check(page.locator('#versionWarning').is_hidden(), 'hidden page did not poll')
                page.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, get: () => false}); document.dispatchEvent(new Event('visibilitychange'))")
                page.wait_for_function("document.querySelector('#versionWarning').hidden === false")
                page.unroute('**/api/health', health_version)
                def health_fail(route): route.fulfill(status=503, body='')
                page.route('**/api/health', health_fail)
                page.evaluate('checkHealth()')
                page.wait_for_function("document.querySelector('#connectionStatus').textContent === 'Connection error'")
                check('unavailable' in page.locator('#apiVersion').inner_text() and 'unavailable' in page.locator('#apiUptime').inner_text(), 'unavailable fields')
                check(page.locator('#versionWarning').is_hidden(), 'failed health is not mismatch')
                page.unroute('**/api/health', health_fail)
                checks.append('AC-09 controlled mismatch, match, 25-second timer, and visibility; AC-10 health failure')

                # Failed sign-out keeps the page and shows an error.
                def logout_fail(route): route.fulfill(status=503, body='')
                page.route('**/logout', logout_fail)
                page.locator('#accountMenuButton').click()
                page.get_by_role('menuitem', name='Log Out').click()
                page.get_by_text('Sign-out failed').wait_for()
                check(page.get_by_text('Sign-out failed').is_visible(), 'failed logout error')
                check(page.url == base + '/', 'failed logout did not navigate')
                page.unroute('**/logout', logout_fail)
                checks.append('AC-10 failed sign-out')

                # Touch activation in a new context with a persisted session cookie.
                touch = browser.new_context(has_touch=True, viewport={"width": 390, "height": 800})
                touch.add_cookies(context.cookies())
                touch_page = touch.new_page(); touch_page.goto(base + '/')
                touch_page.locator('#accountMenuButton').tap()
                check(touch_page.get_by_role('menuitem', name='Settings').is_visible(), 'touch menu')
                touch.close()
                checks.append('AC-06 touch activation')

                paused_id = page.evaluate("""async () => {
                  const response = await fetch('/api/users', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username:'paused', name:'Paused', password:'paused-password', role:'normal'})
                  });
                  if (!response.ok) throw new Error('Could not create suspended-session fixture');
                  return (await response.json()).id;
                }""")
                paused_context = browser.new_context()
                paused = paused_context.new_page(); paused.goto(base + '/login')
                paused.locator('#username').fill('paused')
                paused.locator('#password').fill('paused-password')
                paused.get_by_role('button', name='Sign in').click()
                paused.wait_for_url(base + '/')
                check(page.evaluate("""async id => {
                  const response = await fetch(`/api/users/${id}`, {
                    method: 'PATCH', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({suspended:true})
                  }); return response.status;
                }""", paused_id) == 200, 'suspend before restart')

                # A real process restart keeps a previously signed cookie valid.
                server.terminate(); server.wait(timeout=5)
                server = start_server(database, port)
                check(page.evaluate("fetch('/api/me').then(r => r.status)") == 200, 'session after process restart')
                check(reader.evaluate("fetch('/api/me').then(r => r.status)") == 401, 'removed session after process restart')
                check(paused.evaluate("fetch('/api/me').then(r => r.status)") == 401, 'suspended session after process restart')
                reader_context.close()
                paused_context.close()
                checks.append('AC-04 real restart with valid, suspended, and removed sessions')
                browser.close()
        finally:
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill()
    report = {"result": "passed", "checks": checks, "screenshots": str(ARTIFACTS)}
    (ARTIFACTS / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

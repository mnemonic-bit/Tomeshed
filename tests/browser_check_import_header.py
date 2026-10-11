"""Browser checks for conditional import actions and drawer focus."""

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


def job(state, name="Example.pdf", job_id="example"):
    return {"id": job_id, "state": state, "original_filename": name,
            "origin": "browser", "error": "Could not import file" if state == "failed" else None}


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ, TOMESHED_DB=str(folder / "library.db"),
                   TOMESHED_LIBRARY_DIR=str(folder / "documents"), HOST="127.0.0.1", PORT=str(port))
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
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(base + "/login")
                page.locator("#password").fill("browser-password")
                page.locator("#password_confirmation").fill("browser-password")
                page.get_by_role("button", name="Set password and open library").click()
                page.wait_for_url(base + "/")
                jobs = {"value": []}

                def respond(route):
                    route.fulfill(status=200, content_type="application/json",
                                  body=json.dumps({"jobs": jobs["value"]}))

                page.route("**/api/imports", respond)
                page.evaluate("() => loadImportJobs()")
                add = page.get_by_role("button", name="Add document")
                imports = page.locator("#importsButton")
                assert imports.is_hidden(), "Imports must be hidden without active jobs"
                assert add.is_visible()
                assert add.get_attribute("aria-label") == "Add document"
                assert add.evaluate("el => el.textContent.trim()") == "+"
                for width in (1280, 320):
                    page.set_viewport_size({"width": width, "height": 800})
                    dimensions = add.evaluate("""el => {
                      const box = el.getBoundingClientRect();
                      const css = getComputedStyle(el);
                      return {width: box.width, height: box.height, radius: css.borderRadius,
                        background: css.backgroundColor, right: box.right};
                    }""")
                    assert dimensions["width"] >= 44 and dimensions["height"] >= 44, dimensions
                    assert dimensions["width"] == dimensions["height"], dimensions
                    assert dimensions["radius"] == "50%", dimensions
                    assert dimensions["right"] <= width, dimensions
                    add.focus()
                    assert add.evaluate("el => el === document.activeElement")
                    add.press("Enter")
                    drawer = page.locator("#importsDrawer")
                    assert drawer.is_visible()
                    assert page.locator("#chooseLocalFile").is_visible()
                    assert page.locator("#importUrl").is_visible()
                    with page.expect_file_chooser():
                        page.locator("#chooseLocalFile").click()
                    page.locator("#closeImports").click()
                    assert drawer.is_hidden()
                    assert add.evaluate("el => el === document.activeElement")

                jobs["value"] = [job("pending")]
                page.evaluate("() => loadImportJobs()")
                assert imports.is_visible()
                assert page.locator("#activeImportCount").inner_text() == "1"
                jobs["value"].append(job("processing", "Second.pdf", "second"))
                page.evaluate("() => loadImportJobs()")
                assert page.locator("#activeImportCount").inner_text() == "2"
                imports.focus()
                jobs["value"] = [job("ready"), job("ready_with_warning", "Second.pdf", "second")]
                page.evaluate("() => loadImportJobs()")
                assert imports.is_hidden()
                assert add.evaluate("el => el === document.activeElement"), "Focus should move to Add document when Imports hides"
                jobs["value"] = [job("pending"), job("processing", "Second.pdf", "second")]
                page.evaluate("() => loadImportJobs()")
                imports.click()
                assert page.locator("#importsDrawer").is_visible()
                imports.focus()
                jobs["value"] = [job("failed"), job("ready_with_warning", "Second.pdf", "second")]
                page.evaluate("() => loadImportJobs()")
                assert imports.is_hidden()
                assert page.locator("#closeImports").evaluate("el => el === document.activeElement"), "Focus should move to drawer close when Imports hides"
                assert page.locator(".import-job").filter(has_text="Example.pdf").get_by_role("button", name="Retry").is_visible()
                page.locator("#closeImports").click()
                assert add.evaluate("el => el === document.activeElement")
                add.click()
                assert page.locator(".import-job").filter(has_text="Example.pdf").is_visible()
                page.locator("#closeImports").click()
                jobs["value"] = [job("ready"), job("ready_with_warning", "Second.pdf", "second")]
                page.evaluate("() => loadImportJobs()")
                assert imports.is_hidden()
                for terminal in ("ready", "ready_with_warning", "failed"):
                    jobs["value"] = [job("processing")]
                    page.evaluate("() => loadImportJobs()")
                    assert imports.is_visible(), terminal
                    jobs["value"] = [job(terminal)]
                    page.evaluate("() => loadImportJobs()")
                    assert imports.is_hidden(), terminal
                jobs["value"] = []
                page.reload()
                page.wait_for_function("document.querySelector('#importJobList').textContent.includes('No active or failed imports')")
                assert imports.is_hidden()

                # Resolve the newer response first; the older active snapshot must not restore the button.
                page.evaluate("""() => {
                  window.importFetch = window.fetch;
                  window.importResolvers = [];
                  window.fetch = (path, options) => path === '/api/imports'
                    ? new Promise(resolve => window.importResolvers.push(resolve))
                    : window.importFetch(path, options);
                  window.firstImports = loadImportJobs();
                  window.secondImports = loadImportJobs();
                }""")
                page.wait_for_function("window.importResolvers.length === 2")
                page.evaluate("""async () => {
                  const answer = jobs => new Response(JSON.stringify({jobs}), {
                    status: 200, headers: {'Content-Type': 'application/json'}});
                  window.importResolvers[1](answer([]));
                  await window.secondImports;
                  window.importResolvers[0](answer([{id:'stale',state:'pending',original_filename:'Stale.pdf',origin:'browser'}]));
                  await window.firstImports;
                  window.fetch = window.importFetch;
                }""")
                assert imports.is_hidden()
                assert "Stale.pdf" not in page.locator("#importJobList").inner_text()
                page.unroute("**/api/imports", respond)

                # Registration and cancellation publish real import-state events.
                pending = page.evaluate("""async () => (await (await fetch('/api/imports/register', {
                  method:'POST', headers:{'Content-Type':'application/json'},
                  body:JSON.stringify({filename:'Event.pdf',size:5})})).json()).id""")
                page.wait_for_function("!document.querySelector('#importsButton').hidden")
                assert page.locator("#activeImportCount").inner_text() == "1"
                page.evaluate("""async id => fetch(`/api/imports/${id}/cancel`, {method:'POST'})""", pending)
                page.wait_for_function("document.querySelector('#importsButton').hidden")
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()

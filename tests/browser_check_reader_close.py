"""Focused browser regression for the library position after closing the reader."""

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import port_number, seed, start_server
from test_documents import pdf_bytes


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        base = f'http://127.0.0.1:{port}'
        process = start_server(folder, port)
        try:
            warning_id = None
            for title in ('Reader PDF', 'Mixed PDF', 'Warning PDF', 'Missing PDF'):
                document_id, _ = seed(folder, pdf_bytes(1), 'pdf', title)
                if title == 'Warning PDF':
                    warning_id = document_id
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 390, 'height': 300})
                page.goto(base + '/login')
                page.locator('#password').fill('reader-password')
                page.locator('#password_confirmation').fill('reader-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 4")
                page.locator('#librarySearch').fill('PDF')
                card = page.locator('.document-card').filter(has_text='Warning PDF')
                button = card.locator('.document-open')
                for method in ('Close', 'Escape'):
                    button.scroll_into_view_if_needed()
                    page.evaluate('window.scrollTo(0, window.scrollY - 26)')
                    before = page.evaluate('window.scrollY')
                    assert before > 0, before
                    # Dispatch the card event without Playwright scrolling the covered card first.
                    button.dispatch_event('dblclick')
                    page.locator('#reader').wait_for(state='visible')
                    page.wait_for_function("document.querySelector('#readerPosition').textContent !== 'Opening…'")
                    assert page.evaluate('window.scrollY') == before
                    page.evaluate('window.scrollTo(0, 0)')
                    assert page.evaluate('window.scrollY') == 0
                    if method == 'Close':
                        page.locator('#readerClose').click()
                    else:
                        page.keyboard.press('Escape')
                    page.wait_for_function("document.querySelector('#reader').hidden")
                    after = page.evaluate('window.scrollY')
                    assert page.locator('#librarySearch').input_value() == 'PDF'
                    assert page.evaluate("document.activeElement.closest('.document-card')?.dataset.documentId") == warning_id
                    assert abs(after - before) <= 2, f'{method}: before={before}, after={after}'
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()

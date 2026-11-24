"""Browser acceptance checks for Bug 0050 health states and reader downloads."""

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import open_card, port_number, seed, start_server
from test_documents import pdf_bytes
from test_reader import epub_fixture


def check_health(page):
    status = page.locator('#connectionStatus')
    page.evaluate('checkHealth()')
    assert status.is_hidden(), 'Healthy connection status must occupy no footer space'
    assert 'Connected' not in page.locator('#versionFooter').inner_text()
    assert not page.locator('#versionFooter').inner_text().strip().startswith('·')

    def unavailable(route):
        route.abort('connectionrefused')

    page.route('**/api/health', unavailable)
    page.evaluate('checkHealth()')
    assert status.is_visible() and status.inner_text() == 'Connection error'
    assert page.locator('#versionWarning').is_hidden()
    page.unroute('**/api/health', unavailable)
    page.evaluate('checkHealth()')
    assert status.is_hidden()
    assert 'unavailable' not in page.locator('#apiVersion').inner_text()

    def mismatch(route):
        route.fulfill(json={'ok': True, 'version': '99.0.0', 'uptime_seconds': 100})

    page.route('**/api/health', mismatch)
    page.evaluate('checkHealth()')
    assert page.locator('#versionWarning').is_visible()
    assert '99.0.0' in page.locator('#versionWarning').inner_text()
    assert status.is_hidden()
    page.unroute('**/api/health', mismatch)
    page.evaluate('checkHealth()')
    assert page.locator('#versionWarning').is_hidden() and status.is_hidden()


def check_reader(page, title, original, content, folder):
    page.locator('#librarySearch').fill(title)
    open_card(page, title)
    toolbar = page.locator('.reader-toolbar')
    download = toolbar.get_by_role('link', name='Download original', exact=True)
    assert download.count() == 1
    assert page.locator('#readerDocumentPanel').get_by_role('link', name='Download original').count() == 0
    assert page.get_by_role('button', name='Edit Stored filename').count() == 0
    details = page.locator('#readerPanelContent')
    assert original in details.inner_text()
    assert 'Stored filename' not in details.inner_text()
    assert '.source' not in details.inner_text()
    assert details.get_by_role('button', name='Edit Title', exact=True).count() == 1
    assert details.get_by_role('button', name='Edit Author', exact=True).count() == 1
    page.locator('#readerPanelMinimize').click()
    assert download.is_visible()
    for width in (1000, 390, 320):
        page.set_viewport_size({'width': width, 'height': 800})
        bounds = toolbar.evaluate('''toolbar => [...toolbar.querySelectorAll('button, a, input')]
          .filter(el => el.getClientRects().length).map(el => {
            const r = el.getBoundingClientRect();
            return {name:el.getAttribute('aria-label') || el.textContent,
              left:r.left, right:r.right, top:r.top, bottom:r.bottom};
          })''')
        for box in bounds:
            assert box['left'] >= 0 and box['right'] <= width, (width, box)
        for index, box in enumerate(bounds):
            for other in bounds[index + 1:]:
                overlap_x = min(box['right'], other['right']) - max(box['left'], other['left'])
                overlap_y = min(box['bottom'], other['bottom']) - max(box['top'], other['top'])
                assert overlap_x <= 1 or overlap_y <= 1, (width, box, other)
        position = download.bounding_box()
        controls = toolbar.locator('.reader-controls').bounding_box()
        if width == 1000:
            assert position['x'] + position['width'] <= controls['x'], (position, controls)
    download.focus()
    with page.expect_download() as pending:
        page.keyboard.press('Enter')
    result = pending.value
    assert result.suggested_filename == original, result.suggested_filename
    saved = folder / ('download-' + original)
    result.save_as(saved)
    assert saved.read_bytes() == content
    page.locator('#readerClose').click()
    page.set_viewport_size({'width': 1000, 'height': 800})


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        base = f'http://127.0.0.1:{port}'
        process = start_server(folder, port)
        try:
            pdf = pdf_bytes(2)
            epub = epub_fixture()
            seed(folder, pdf, 'pdf', 'Original PDF ä')
            seed(folder, epub, 'epub', 'Original EPUB é')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1000, 'height': 800})
                page.goto(base + '/login')
                page.locator('#password').fill('bug0050-password')
                page.locator('#password_confirmation').fill('bug0050-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                check_health(page)
                check_reader(page, 'Original PDF ä', 'Original PDF ä.pdf', pdf, folder)
                page.locator('#librarySearch').fill('Original EPUB é')
                open_card(page, 'Original EPUB é')
                page.locator('#readerPanelRestore').click()
                page.locator('#readerClose').click()
                check_reader(page, 'Original EPUB é', 'Original EPUB é.epub', epub, folder)
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)
    print('Bug 0050 health states, reader layout, metadata, and downloads: passed')


if __name__ == '__main__':
    main()

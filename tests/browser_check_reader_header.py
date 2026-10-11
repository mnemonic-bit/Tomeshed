"""Focused browser check for Bug 0032 reader header and zoom."""

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import open_card, port_number, seed, start_server
from test_documents import pdf_bytes
from test_reader import docling_fixture, epub_fixture


def layout(page, width):
    page.set_viewport_size({'width': width, 'height': 750})
    boxes = page.evaluate('''() => {
      const ids = ['readerClose', 'readerTitle', 'readerPosition', 'readerPrevious',
        'readerNext', 'readerZoomOut', 'readerZoomPercent', 'readerZoomIn'];
      return Object.fromEntries(ids.map(id => {
        const r = document.getElementById(id).getBoundingClientRect();
        return [id, {left:r.left, right:r.right, top:r.top, bottom:r.bottom}];
      }));
    }''')
    for name, box in boxes.items():
        assert box['left'] >= 0 and box['right'] <= width, (width, name, boxes)
    assert boxes['readerTitle']['right'] - boxes['readerTitle']['left'] >= 20, (width, boxes)
    for left, right in [('readerClose', 'readerTitle'), ('readerTitle', 'readerPosition'),
                        ('readerPosition', 'readerPrevious'), ('readerNext', 'readerZoomOut')]:
        a, b = boxes[left], boxes[right]
        if a['top'] < b['bottom'] and b['top'] < a['bottom']:
            assert a['right'] <= b['left'] + 1, (width, left, right, boxes)
    assert boxes['readerPrevious']['top'] == boxes['readerNext']['top']
    assert boxes['readerZoomOut']['top'] == boxes['readerZoomIn']['top']
    if width >= 900:
        centers = [(box['top'] + box['bottom']) / 2 for box in boxes.values()]
        assert max(centers) - min(centers) < 5, boxes
        assert boxes['readerPosition']['left'] <= width / 2 <= boxes['readerPosition']['right'], boxes


def zoom_value(page):
    return page.locator('#readerContent').evaluate("el => Number(getComputedStyle(el).getPropertyValue('--reader-zoom'))")


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        base = f'http://127.0.0.1:{port}'
        process = start_server(folder, port)
        try:
            pdf_id, _ = seed(folder, pdf_bytes(8), 'pdf', 'A long reader header title for narrow layouts')
            seed(folder, epub_fixture(text='Paragraph ' * 400), 'epub', 'Header EPUB')
            seed(folder, docling_fixture(), 'docling', 'Header Docling')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1000, 'height': 750})
                page.goto(base + '/login')
                page.locator('#password').fill('reader-password')
                page.locator('#password_confirmation').fill('reader-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                page.wait_for_function("document.querySelectorAll('.document-card').length === 3")
                open_card(page, 'A long reader header title')
                assert page.locator('#readerPosition').inner_text() == 'Page 1 of 8'
                assert page.locator('#readerFinished, #readerStartOver').count() == 0
                assert page.locator('#readerPrevious svg, #readerNext svg').count() == 2
                assert page.locator('#readerPrevious').get_attribute('aria-label')
                assert page.locator('#readerNext').get_attribute('aria-label')
                assert page.locator('#readerZoomPercent').input_value() == '100'
                assert page.locator('#readerZoomPercent').evaluate('el => el.closest("button")') is None
                layout(page, 1000)
                page.locator('#readerNext').click()
                page.wait_for_function("document.querySelector('#readerPosition').textContent === 'Page 2 of 8'")
                page.locator('#readerPrevious').click()
                page.wait_for_function("document.querySelector('#readerPosition').textContent === 'Page 1 of 8'")
                page.locator('[data-page="4"]').scroll_into_view_if_needed()
                page.wait_for_function("document.querySelector('#readerPosition').textContent.includes('Page 4')")
                page.wait_for_timeout(700)
                before = page.request.get(base + f'/api/documents/{pdf_id}/progress').json()['position']
                page.locator('#readerZoomIn').click()
                assert page.locator('#readerZoomPercent').input_value() == '115'
                assert abs(zoom_value(page) - 1.15) < .001
                page.locator('#readerZoomOut').click()
                assert page.locator('#readerZoomPercent').input_value() == '100'
                field = page.locator('#readerZoomPercent')
                field.fill('175')
                field.press('Enter')
                assert abs(zoom_value(page) - 1.75) < .001
                assert field.input_value() == '175'
                field.fill('65')
                field.blur()
                assert abs(zoom_value(page) - .65) < .001
                field.fill('251')
                field.press('Enter')
                assert field.input_value() == '65' and abs(zoom_value(page) - .65) < .001
                field.fill('')
                field.blur()
                assert field.input_value() == '65'
                field.fill('not a number')
                field.press('Enter')
                assert field.input_value() == '65'
                page.locator('#readerZoomOut').click()
                assert field.input_value() == '65' and abs(zoom_value(page) - .65) < .001
                field.fill('175.5')
                field.press('Enter')
                assert field.input_value() == '175.5' and abs(zoom_value(page) - 1.755) < .001
                field.fill('250')
                field.press('Enter')
                assert abs(zoom_value(page) - 2.5) < .001
                page.locator('#readerZoomIn').click()
                assert field.input_value() == '250' and abs(zoom_value(page) - 2.5) < .001
                page.locator('#readerClose').focus()
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement.id') == 'readerPrevious'
                assert page.locator('#readerPrevious').evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
                page.wait_for_timeout(700)
                assert 'Page 4' in page.locator('#readerPosition').inner_text()
                assert page.request.get(base + f'/api/documents/{pdf_id}/progress').json()['position'] == before
                for width in (390, 320):
                    layout(page, width)
                page.locator('#readerClose').click()
                page.set_viewport_size({'width': 1000, 'height': 750})
                page.locator('#librarySearch').fill('Header EPUB')
                open_card(page, 'Header EPUB')
                assert page.locator('#readerPosition').inner_text().startswith('Location')
                page.locator('#readerClose').click()
                page.locator('#librarySearch').fill('Header Docling')
                open_card(page, 'Header Docling')
                assert page.locator('#readerPosition').inner_text().startswith('Page ')
                browser.close()
            print('Bug 0032 reader header: passed')
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
